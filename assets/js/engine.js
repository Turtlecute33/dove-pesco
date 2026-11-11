/* =============================================================================
   MOTORE DI VALUTAZIONE
   -----------------------------------------------------------------------------
   Incrocia, per ogni spot e per un giorno scelto:
     · stagione e finestra di attività di ogni specie
     · temperatura dell'acqua stimata (inerzia termica per tipo di acqua)
     · temperatura di superficie e moto ondoso del mare, dove lo spot è sul mare
     · portata del fiume rispetto alla mediana delle ultime settimane
     · pioggia caduta nelle 72 ore precedenti e pioggia prevista
     · tendenza barometrica
     · copertura nuvolosa, vento, fase lunare
     · periodi di divieto e misure minime (Allegato 2), le regole in più dei
       calendari ittici provinciali e la chiusura invernale delle acque D
   Restituisce un punteggio 0-100, il perché e i consigli operativi.
   ========================================================================== */

const ENGINE = (() => {

  /* ------------------------------------------------------------------ utils */
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const iso = (d) => d.toISOString().slice(0, 10);
  const media = (a) => a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;
  const mediana = (a) => {
    if (!a.length) return 0;
    const s = [...a].sort((x, y) => x - y);
    const m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  };
  const num = (v) => (typeof v === 'number' && isFinite(v)) ? v : null;

  /* m³/s sommati a portata e mediana prima di farne il rapporto: mezzo metro
     cubo su un fiume e cento litri su un torrente non fanno una piena */
  const PORTATA_MINIMA = { fiume: 0.5, torrente: 0.1 };
  const ONDA_MOSSA = [0.5, 1.5];   // metri di onda massima: mare mosso, buono da riva
  const ONDA_GROSSA = 2;           // da qui in su dai moli e dalla spiaggia non si pesca

  /* Campana asimmetrica. Dentro l'optimum non è piatta: vale 1 al centro e
     scende a 0,88 ai bordi, così spot con acqua "giusta" ma non ideale non
     finiscono a pari merito. Fuori decade, fino a ~0 oltre i limiti vitali. */
  function campana(x, [oMin, oMax], [vMin, vMax]) {
    if (x === null) return 0.6;                       // dato assente: neutro
    if (x >= oMin && x <= oMax) {
      const c = (oMin + oMax) / 2;
      const hw = (oMax - oMin) / 2 || 1;
      const d = Math.abs(x - c) / hw;                  // 0 al centro, 1 al bordo
      return 1 - 0.12 * d * d;
    }
    if (x < oMin) {
      if (x <= vMin) return 0.03;
      return 0.03 + 0.97 * Math.pow((x - vMin) / (oMin - vMin), 1.5);
    }
    if (x >= vMax) return 0.03;
    return 0.03 + 0.97 * Math.pow((vMax - x) / (vMax - oMax), 1.5);
  }

  /* ------------------------------------------------- temperatura dell'acqua */
  /* Modello a inerzia: l'acqua segue la media dell'aria degli ultimi N giorni,
     smorzata verso la temperatura media annua (≈ temperatura di falda) a
     quella quota. Non è una misura: è una stima, dichiarata come tale.

     I numeri non sono più scelti a occhio. A novembre 2026 il modello è stato
     messo davanti alle misure di ARPAE: 575 campioni del 2024-2025 su 50
     stazioni di fiume e torrente da 1 a 1043 m, 128 su dieci canali, 126 in
     superficie su cinque invasi (Molato, Mignano, Suviana, Brasimone,
     Ridracoli). L'aria è quella di Open-Meteo nello stesso punto.

                     errore medio (°C)      di cui in estate
                     prima     ora          prima          ora
       torrenti       3,4      1,9      4,6 in meno    0,3 in meno
       fiumi          2,3      1,8      2,1 in meno    0,3 in meno
       canali         2,6      1,7      1,9 in meno    pari
       invasi         3,9      2,7      4,3 in meno    0,5 in meno

     L'errore stava quasi tutto d'estate e in basso: un torrente di pianura
     prendeva i numeri di un torrente di sorgente (smorzo 0,55, un tetto a 20 °C)
     e a luglio usciva a 19 °C con l'acqua vera a 26. Ma «torrente» è un nome,
     non una quota: l'Idice a Castenaso e il Dolo a Civago si chiamano uguale.
     Ora per le acque correnti decide la quota: in pianura l'acqua segue l'aria
     quasi per intero, in montagna resta fredda come prima, e in mezzo si sfuma. */
  const INERZIA = {
    torrente: { giorni: 3,  corrente: true, tetto: 31 },
    fiume:    { giorni: 5,  corrente: true, tetto: 31 },
    canale:   { giorni: 3,  smorzo: 0.95, offset: +2.25, tetto: 33 },
    lago:     { giorni: 14, smorzo: 0.85, offset: +1.25, tetto: 30 },
    bacino:   { giorni: 14, smorzo: 0.85, offset: +1.25, tetto: 30 },
    cava:     { giorni: 9,  smorzo: 0.90, offset: +1.75, tetto: 31 },
    /* di riserva: sul mare si usa la temperatura di superficie di Open-Meteo.
       Tarato su due anni di quella misura in tre punti della costa: prima
       sbagliava di 3,8 °C (6 in meno ad agosto, 3 in più a gennaio), ora di 1,1. */
    mare:     { giorni: 14, smorzo: 1.00, offset: +2.25, tetto: 31 }
  };
  /* Acque correnti: da 100 m in giù valgono i numeri di pianura, da 900 m in
     su quelli di sorgente. */
  const PIANURA = { quota: 100, smorzo: 0.85, offset: +0.75 };
  const MONTAGNA = { quota: 900, smorzo: 0.55, offset: -1.2 };

  function tempAcqua(spot, serieAriaMedia, quota) {
    const p = INERZIA[spot.tipo] || INERZIA.fiume;
    const finestra = serieAriaMedia.slice(-p.giorni).filter(v => v !== null);
    if (!finestra.length) return null;
    const aria = media(finestra);
    /* Media annua dell'aria in Emilia-Romagna, corretta per la quota */
    const annua = 14.6 - 0.0058 * (quota || 0);
    let smorzo = p.smorzo, offset = p.offset;
    if (p.corrente) {
      const f = clamp(((quota || 0) - PIANURA.quota) / (MONTAGNA.quota - PIANURA.quota), 0, 1);
      smorzo = PIANURA.smorzo + (MONTAGNA.smorzo - PIANURA.smorzo) * f;
      offset = PIANURA.offset + (MONTAGNA.offset - PIANURA.offset) * f;
    }
    return clamp(annua + smorzo * (aria - annua) + offset, 1, p.tetto);
  }

  /* ---------------------------------------------------------- fase lunare  */
  function faseLunare(date) {
    /* Giorni dal novilunio del 6 gennaio 2000 (JD 2451550.1), ciclo sinodico */
    const syn = 29.530588853;
    const ms = date.getTime() - Date.UTC(2000, 0, 6, 18, 14);
    const eta = ((ms / 86400000) % syn + syn) % syn;
    const frazione = eta / syn;
    const illum = (1 - Math.cos(2 * Math.PI * frazione)) / 2;
    let nome;
    if (frazione < 0.03 || frazione > 0.97) nome = 'Luna nuova';
    else if (frazione < 0.22) nome = 'Luna crescente';
    else if (frazione < 0.28) nome = 'Primo quarto';
    else if (frazione < 0.47) nome = 'Gibbosa crescente';
    else if (frazione < 0.53) nome = 'Luna piena';
    else if (frazione < 0.72) nome = 'Gibbosa calante';
    else if (frazione < 0.78) nome = 'Ultimo quarto';
    else nome = 'Luna calante';
    return { frazione, illum, nome, eta: Math.round(eta) };
  }

  /* ------------------------------------------- la stagione delle acque D   */
  /* La trota e le acque di categoria D non chiudono in una data ma in una
     domenica: dalle 19 della prima di ottobre alle 5 dell'ultima di marzo
     (Reg. reg. 1/2018, art. 23). Con le date fisse 5 ottobre - 25 marzo, nel
     2026 la trota risultava aperta dal 26 al 28 marzo, tre giorni prima
     dell'apertura vera di domenica 29. Le due domeniche si pescano: quella di
     ottobre fino a sera, quella di marzo dall'alba. Torna null se è aperto,
     altrimenti la domenica in cui si riapre. Con `aMaggio` l'apertura è la
     prima domenica di maggio: vale per i laghi di crinale che il calendario
     di Parma tiene chiusi più a lungo (REGOLE.apertureDiMaggio). */
  const ultimaDomenicaMarzo = (anno) => { const d = new Date(anno, 2, 31); d.setDate(31 - d.getDay()); return d; };
  const primaDomenica = (anno, mese) => { const d = new Date(anno, mese, 1); d.setDate(1 + (7 - d.getDay()) % 7); return d; };
  function stagioneChiusa(date, aMaggio) {
    const anno = date.getFullYear();
    const apertura = (a) => aMaggio ? primaDomenica(a, 4) : ultimaDomenicaMarzo(a);
    if (date < apertura(anno)) return apertura(anno);
    const chiude = primaDomenica(anno, 9);
    chiude.setDate(chiude.getDate() + 1);              // il lunedì dopo
    return date >= chiude ? apertura(anno + 1) : null;
  }

  const tra = (date, [m1, g1, m2, g2]) => {
    const v = (date.getMonth() + 1) * 100 + date.getDate();
    const a = m1 * 100 + g1, b = m2 * 100 + g2;
    return a <= b ? (v >= a && v <= b) : (v >= a || v <= b);
  };

  /* --------------------------------------------------------- divieti (Alleg. 2) */
  function inDivieto(sp, date) {
    if (sp.chiusuraSalmonidi) return !!stagioneChiusa(date);
    if (!sp.divieto || !sp.divieto.length) return false;
    return sp.divieto.some(p => tra(date, p));
  }

  /* ------------------------------------------------ le regole delle province */
  /* L'Allegato 2 vale in tutta la regione, ma ogni calendario ittico
     provinciale aggiunge del suo: a Bologna il luccio non si trattiene mai, a
     Rimini i ciprinidi autoctoni si rilasciano dal 15 aprile. Senza queste
     regole il luccio di Varignana era il «pesce del giorno» da portare a casa.
     La tabella sta in data-rules.js (REGOLE.province). */
  function regolaLocale(spot, id, date) {
    const P = (typeof REGOLE !== 'undefined' && REGOLE.province) || null;
    const out = { nonTrattenibile: false, vietata: false, misuraMin: null, limite: null, testo: null };
    if (!P) return out;
    const dove = 'in provincia di ' + ((typeof PROVINCE !== 'undefined' && PROVINCE[spot.prov]) || spot.prov);
    if (((P.nonTrattenibili || {})[id] || []).includes(spot.prov)) {
      out.nonTrattenibile = true;
      out.testo = `${dove} non si può trattenere, tutto l'anno (calendario ittico ${P.stagione})`;
      return out;
    }
    const per = (P.periodi || []).find(p => p.specie.includes(id) && p.prov.includes(spot.prov));
    if (per) {
      out.vietata = tra(date, per.divieto);
      out.testo = `${dove} ${per.testo} (calendario ittico ${P.stagione})`;
    }
    const mis = ((P.misure || {})[id] || {})[spot.prov];
    if (mis) out.misuraMin = mis;
    const lim = ((P.limiti || {})[id] || {})[spot.prov];
    if (lim) out.limite = lim;
    return out;
  }

  /* ------------------------------------------- divieti temporanei sullo spot */
  /* Il divieto che chiude uno spot intero (secca, lavori, ordinanze) sta negli
     avvisi di data-rules.js, con gli spot che tocca. Senza questo controllo il
     Brasimone, chiuso dal 20 ottobre 2026, continuava a prendere il suo
     punteggio e a finire fra i posti consigliati del giorno.               */
  function chiusura(spot, dataISO) {
    const avvisi = (typeof REGOLE !== 'undefined' && REGOLE.avvisi) || [];
    const avviso = avvisi.find(a => (a.spot || []).includes(spot.id)
      && (!a.dal || dataISO >= a.dal) && (!a.al || dataISO <= a.al));
    if (avviso) return avviso;

    /* Le acque di categoria D d'inverno sono chiuse a ogni specie, non solo
       alla trota. Prima il motore fermava la trota e lasciava il resto: 68 spot
       davano un indice e un «pesce del giorno» (vairone, cavedano) da ottobre a
       marzo, in acque dove non si può pescare niente. I laghetti a pagamento
       sono acque private e restano fuori dalla chiusura, e così le schede la
       cui categoria D è in dubbio (REGOLE.categoriaDaVerificare). */
    const R = (typeof REGOLE !== 'undefined' && REGOLE) || {};
    if (spot.categoria === 'D' && !spot.pagamento && !(R.categoriaDaVerificare || []).includes(spot.id)) {
      const aMaggio = (R.apertureDiMaggio || []).includes(spot.id);
      const riapre = stagioneChiusa(new Date(dataISO + 'T12:00:00'), aMaggio);
      if (riapre) {
        const quando = `domenica ${riapre.getDate()} ${aMaggio ? 'maggio' : 'marzo'} ${riapre.getFullYear()}`;
        return {
          t: 'Acque di categoria D: pesca chiusa fino a ' + quando,
          d: aMaggio
            ? 'Qui il calendario ittico di Parma vieta la pesca dalle 19 della prima domenica di ottobre alle 5 della prima domenica di maggio.'
            : 'Nelle acque da salmonidi la pesca a ogni specie è vietata dalle 19 della prima domenica di ottobre alle 5 dell\'ultima domenica di marzo (Reg. reg. 1/2018, art. 23).',
          livello: 'alto', stagionale: true, riapre: quando
        };
      }
    }
    return null;
  }

  /* --------------------------------------------------- stagione, senza scalini */
  /* `mesi` dà un valore per mese. Letto così com'è, l'indice saltava il primo
     del mese a meteo identico: il luccio passava da 0,9 a 0,3 fra il 30
     novembre e il 1° dicembre. Qui il valore del mese vale a metà mese e si
     sfuma verso il mese vicino. Uno zero non si sfuma: vuol dire divieto o
     pesce assente, e deve restare un gradino. */
  function stagionale(mesi, date) {
    const m = date.getMonth();
    const v = mesi[m];
    if (!v) return 0;
    const giorni = new Date(date.getFullYear(), m + 1, 0).getDate();
    const x = (date.getDate() - 0.5) / giorni - 0.5;   // -0,5 a inizio mese, +0,5 alla fine
    const vicino = mesi[(m + (x < 0 ? 11 : 1)) % 12];
    return vicino ? v + (vicino - v) * Math.abs(x) : v;
  }

  const STAGIONE = (m) => (m <= 1 || m === 11) ? 'inverno'
    : (m <= 4) ? 'primavera' : (m <= 7) ? 'estate'
    : (m <= 9) ? 'autunno' : 'autunno';

  /* ==================================================== valutazione singola */
  function valuta(spot, meteoSpot, portataSpot, dataISO) {
    const date = new Date(dataISO + 'T12:00:00');
    const d = meteoSpot && meteoSpot.daily;
    if (!d) return null;

    const i = d.time.indexOf(dataISO);
    if (i < 0) return null;

    const quota = num(meteoSpot.elevation) || 0;

    /* ---- serie storiche fino al giorno scelto ---- */
    const mediaAria = d.temperature_2m_mean
      ? d.temperature_2m_mean.slice(0, i + 1).map(num)
      : d.temperature_2m_max.slice(0, i + 1).map((v, k) =>
          (num(v) !== null && num(d.temperature_2m_min[k]) !== null)
            ? (v + d.temperature_2m_min[k]) / 2 : null);

    /* Sul mare la temperatura non si stima dall'aria: Open-Meteo dà quella di
       superficie, la stessa che usano i bollettini. La stima resta di riserva,
       per quando quel dato non arriva. */
    const giorno = (serie) => (serie ? num(serie[i]) : null);
    const tMare = spot.tipo === 'mare' ? giorno(d.sea_surface_temperature) : null;
    const onda = spot.tipo === 'mare' ? giorno(d.wave_height_max) : null;
    const tAcqua = tMare !== null ? tMare : tempAcqua(spot, mediaAria, quota);

    /* ---- meteo del giorno ---- */
    const tmax = num(d.temperature_2m_max[i]);
    const tmin = num(d.temperature_2m_min[i]);
    const wmo = d.weather_code[i];
    const pioggia = num(d.precipitation_sum[i]) || 0;
    const nuvole = num(d.cloud_cover_mean[i]);
    const vento = num(d.wind_speed_10m_max[i]) || 0;
    const ventoDir = num(d.wind_direction_10m_dominant[i]);
    const press = num(d.pressure_msl_mean[i]);
    const pressPrec = num(d.pressure_msl_mean[i - 1]);
    const dPress = (press !== null && pressPrec !== null) ? press - pressPrec : null;

    const p72 = [1, 2, 3].reduce((s, k) => s + (num(d.precipitation_sum[i - k]) || 0), 0);
    const alba = d.sunrise[i] ? d.sunrise[i].slice(11, 16) : null;
    const tramonto = d.sunset[i] ? d.sunset[i].slice(11, 16) : null;

    /* ---- portata (GloFAS) ----
       Il modello lavora su celle: su un corso minore o vicino a una confluenza
       il valore assoluto può riferirsi a un ramo diverso da quello che pescherai.
       Lo scarto sulla mediana resta comunque un buon indice del deflusso locale,
       quindi lo usiamo sempre, mentre il valore in m³/s lo mostriamo solo quando
       è coerente con la taglia del corso d'acqua. */
    let flow = null, flowRatio = null, flowTrend = null, flowAssoluto = false;
    if (portataSpot && portataSpot.daily && portataSpot.daily.river_discharge) {
      const t = portataSpot.daily.time, q = portataSpot.daily.river_discharge;
      const j = t.indexOf(dataISO);
      if (j >= 0 && num(q[j]) !== null) {
        flow = q[j];
        const prima = q.slice(0, Math.max(1, j)).map(num).filter(v => v !== null);
        const base = mediana(prima);
        /* Il rapporto fra due numeri piccoli è rumore: da 0,03 a 0,09 m³/s
           faceva +200% e «piena». GloFAS sottostima molto le magre dei fiumi
           appenninici (il Reno a Marzabotto d'estate gli risulta a 30 litri
           al secondo), e ogni temporale diventava una piena di una settimana.
           Una portata fissa sommata sopra e sotto non sposta un fiume vero e
           calma i numeri piccoli. In 47 giorni d'autunno i giorni «in piena»
           sui fiumi scendono dal 16% al 7%: ancora troppi per essere tutte
           piene vere, e il rimedio serio sono i livelli misurati da ARPAE. */
        const fondo = PORTATA_MINIMA[spot.tipo] || PORTATA_MINIMA.fiume;
        if (prima.length) flowRatio = (flow + fondo) / (base + fondo);
        if (j > 0 && num(q[j - 1]) !== null) flowTrend = flow - q[j - 1];
        flowAssoluto = spot.tipo === 'torrente' ? flow >= 0.08 : flow >= 0.8;
        if (flow < 0.02) { flow = null; flowRatio = null; flowTrend = null; }
      }
    }

    /* Torbidità stimata: pioggia recente + portata sopra la norma */
    let torbidita = 0;                                  // 0 limpida → 1 fangosa
    torbidita += clamp(p72 / 35, 0, 0.55);
    torbidita += clamp(pioggia / 25, 0, 0.25);
    if (flowRatio !== null) torbidita += clamp((flowRatio - 1.15) / 2.2, 0, 0.45);
    if (spot.tipo === 'canale' || spot.tipo === 'lago' || spot.tipo === 'cava') torbidita *= 0.6;
    torbidita = clamp(torbidita, 0, 1);

    /* ------------------------------------------------- punteggio per specie */
    const mese = date.getMonth();
    const stag = STAGIONE(mese);
    const luna = faseLunare(date);

    const specie = (spot.specie || []).map(id => {
      const sp = SPECIE[id];
      if (!sp) return null;

      const locale = regolaLocale(spot, id, date);
      const vietata = inDivieto(sp, date) || locale.vietata;
      const soloRilascio = vietata || sp.protetta || sp.limiteGiorno === 0 || locale.nonTrattenibile;

      const fStag = stagionale(sp.mesi, date);
      const fTemp = campana(tAcqua, sp.tOpt, sp.tLive);

      /* portata: preferenza della specie */
      let fFlow = 1;
      if (flowRatio !== null) {
        const scarto = flowRatio - 1;                    // >0 sopra la norma
        fFlow = 1 + (sp.portata || 0) * clamp(scarto, -0.8, 1.2) * 0.35;
        if (flowRatio > 2.6) fFlow *= 0.45;              // piena: pesca compromessa
        else if (flowRatio > 1.8) fFlow *= 0.75;
        else if (flowRatio < 0.45) fFlow *= 0.82;        // magra severa
        fFlow = clamp(fFlow, 0.2, 1.3);
      }

      /* torbidità: chi la ama e chi la odia */
      const fTorb = clamp(1 + (sp.torbida || 0) * (torbidita - 0.32) * 1.25, 0.35, 1.25);

      /* pressione in calo = pesce che si alimenta */
      let fPress = 1;
      if (dPress !== null) {
        const calo = clamp(-dPress / 6, -1, 1);          // +1 = crollo di 6 hPa
        fPress = 1 + (sp.press || 0) * calo * 0.28;
        if (dPress < -8) fPress *= 0.88;                 // fronte violento: si spegne
        fPress = clamp(fPress, 0.7, 1.25);
      }

      /* luce: cielo coperto favorisce i crepuscolari, penalizza i visivi */
      let fLuce = 1;
      if (nuvole !== null) {
        const cop = nuvole / 100;
        if (sp.luce === 'crepuscolo' || sp.luce === 'notte' || sp.luce === 'alba') fLuce = 0.86 + 0.28 * cop;
        else if (sp.luce === 'giorno') fLuce = 1.1 - 0.25 * cop;
      }

      /* luna: rilevante per i predatori notturni */
      let fLuna = 1;
      if (sp.luce === 'notte') fLuna = 0.9 + 0.22 * luna.illum;

      /* freddo/caldo estremo dell'aria: comfort del pescatore a parte,
         l'escursione termica forte smuove i pesci di acqua ferma */
      let fEscursione = 1;
      if (tmax !== null && tmin !== null && spot.tipo !== 'mare') {
        const esc = tmax - tmin;
        if (esc > 16 && ['lago', 'bacino', 'cava', 'canale'].includes(spot.tipo)) fEscursione = 0.93;
      }

      /* presenza sporadica secondo la guida: presente, ma non è il motivo per andarci */
      const rara = !!(typeof RARITA !== 'undefined' && RARITA[spot.id] && RARITA[spot.id].includes(id));

      let s = fStag * fTemp * fFlow * fTorb * fPress * fLuce * fLuna * fEscursione;
      if (rara) s *= 0.42;
      if (soloRilascio) s *= 0.34;                       // pescabile ma non trattenibile

      return {
        id, nome: sp.nome, icona: sp.icona, gruppo: sp.gruppo,
        score: clamp(s, 0, 1.4), rara,
        vietata, soloRilascio, protetta: !!sp.protetta,
        /* dove la provincia vieta di trattenerla, misura e capi non hanno senso */
        nonTrattenibile: locale.nonTrattenibile,
        misuraMin: locale.nonTrattenibile ? null : (locale.misuraMin || sp.misuraMin),
        limiteGiorno: locale.nonTrattenibile ? null : (locale.limite || sp.limiteGiorno),
        divietoTesto: locale.testo || sp.divietoTesto, registrazione: !!sp.registrazione,
        norme: !!sp.norme,
        prof: sp.prof[stag], taglia: sp.taglia,
        esche: sp.esche, tecniche: sp.tecniche, dritte: sp.dritte,
        tOpt: sp.tOpt, luce: sp.luce,
        fattori: { fStag, fTemp, fFlow, fTorb, fPress, fLuce }
      };
    }).filter(Boolean).sort((a, b) => b.score - a.score);

    /* ------------------------------------------------ punteggio dello spot */
    const utili = specie.filter(s => !s.soloRilascio);
    const top = specie[0] ? specie[0].score : 0;
    const tre = media(specie.slice(0, 3).map(s => s.score));
    let base = top * 0.62 + tre * 0.38;

    /* modificatori dello spot */
    const mod = [];

    if (flowRatio !== null && flowRatio > 2.6) {
      base *= 0.55; mod.push({ t: 'Portata in piena', v: -1 });
    } else if (flowRatio !== null && flowRatio < 0.4 && spot.tipo !== 'canale') {
      base *= 0.8; mod.push({ t: 'Magra severa', v: -1 });
    }

    if (pioggia > 18) { base *= 0.82; mod.push({ t: 'Pioggia forte prevista', v: -1 }); }
    if ([95, 96, 99].includes(wmo)) { base *= 0.7; mod.push({ t: 'Temporali', v: -1 }); }

    /* Il mare vive di mareggiate, e adesso l'onda si legge invece di dedurla
       dal vento. Il vento a terra diceva «mare mosso» anche con la brezza del
       pomeriggio e il mare piatto: in tre mesi, nei giorni in cui una delle due
       misure dava mare mosso, l'altra era d'accordo quattro volte su dieci. Mosso (da mezzo metro a un metro e mezzo) è
       l'acqua che lavora il fondo sotto riva; da due metri in su dai moli non
       si pesca. Senza il dato dell'onda si torna al vento. */
    const mareGrosso = onda !== null && onda >= ONDA_GROSSA;
    if (vento > 38 || mareGrosso) {
      const p = (spot.tipo === 'lago' || spot.tipo === 'bacino' || spot.tipo === 'cava' || spot.tipo === 'mare') ? 0.72 : 0.9;
      base *= p; mod.push({ t: mareGrosso ? 'Mare molto mosso' : 'Vento forte', v: -1 });
    } else if (spot.tipo === 'mare'
        && (onda !== null ? (onda >= ONDA_MOSSA[0] && onda < ONDA_MOSSA[1]) : (vento >= 18 && vento <= 36))) {
      base *= 1.12; mod.push({ t: 'Mare mosso: spigole attive', v: 1 });
    }

    /* Torrenti: nelle ondate di calore l'acqua fresca è oro */
    if (spot.categoria === 'D' && tAcqua !== null && tAcqua <= 16 && tmax !== null && tmax >= 30) {
      base *= 1.14; mod.push({ t: 'Acqua fresca in giornata torrida', v: 1 });
    }

    /* Stagione consigliata dalla guida regionale */
    if (spot.stagioniTop && spot.stagioniTop.includes(stag)) {
      base *= 1.08; mod.push({ t: 'Stagione consigliata per questo spot', v: 1 });
    }

    if (!utili.length) { base *= 0.6; mod.push({ t: 'Nessuna specie trattenibile oggi', v: -1 }); }

    const chiuso = chiusura(spot, dataISO);
    if (chiuso) { base = 0; mod.unshift({ t: chiuso.t, v: -1 }); }

    /* Scala finale: compressione esponenziale. Nessun giorno è perfetto, quindi
       100 non è raggiungibile; in cambio la fascia alta resta discriminante. */
    const punteggio = Math.round(100 * clamp(1 - Math.exp(-1.55 * Math.max(0, base)), 0, 0.97));

    /* ---------------------------------------------------- finestre migliori */
    const finestre = [];
    if (alba) finestre.push({ q: 'Alba', o: `${sposta(alba, -30)} – ${sposta(alba, 120)}`, why: 'La prima luce è la finestra più produttiva su torrenti e laghi.' });
    if (tramonto) finestre.push({ q: 'Tramonto', o: `${sposta(tramonto, -120)} – ${sposta(tramonto, 40)}`, why: 'Ultima ora di luce: i predatori si spostano in caccia.' });
    if (specie.some(s => s.luce === 'notte' && !s.soloRilascio)) {
      finestre.push({ q: 'Notte', o: `${sposta(tramonto, 60)} – 24:00`, why: 'Siluro, lucioperca e carpa danno il meglio dopo il buio. Verifica gli orari consentiti.' });
    }
    if (nuvole !== null && nuvole > 65) {
      finestre.push({ q: 'Tutto il giorno', o: 'cielo coperto', why: 'Con il cielo coperto la luce resta bassa: la finestra utile si allarga.' });
    }

    return {
      spot, punteggio, specie, mod, chiuso,
      meteo: {
        wmo, tmax, tmin, pioggia, p72, nuvole, vento, ventoDir,
        press, dPress, alba, tramonto, quota
      },
      acqua: { temp: tAcqua, misurata: tMare !== null, onda, torbidita, flow, flowRatio, flowTrend, flowAssoluto },
      luna, stagione: stag, finestre: chiuso ? [] : finestre,
      spiegazione: chiuso
        ? [chiuso.stagionale
            ? `Acque di categoria D: fino a ${chiuso.riapre} la pesca è chiusa a ogni specie. L'indice torna alla riapertura.`
            : 'Lo spot è chiuso da un divieto temporaneo: finché resta in vigore non c\'è un pesce del giorno.']
        : spiega(spot, specie, tAcqua, torbidita, flowRatio, dPress, nuvole, stag, punteggio, mod, tMare !== null)
    };
  }

  function sposta(hhmm, minuti) {
    if (!hhmm) return '–';
    const [h, m] = hhmm.split(':').map(Number);
    let t = h * 60 + m + minuti;
    t = ((t % 1440) + 1440) % 1440;
    return String(Math.floor(t / 60)).padStart(2, '0') + ':' + String(t % 60).padStart(2, '0');
  }

  /* -------------------------------------------------------- testo del perché */
  function spiega(spot, specie, tAcqua, torb, flowRatio, dPress, nuvole, stag, punteggio, mod, misurata) {
    const f = [];
    const target = specie.filter(s => !s.soloRilascio).slice(0, 2);

    if (tAcqua !== null) {
      const t = tAcqua.toFixed(1).replace('.', ',');
      const A = misurata ? 'Mare in superficie' : 'Acqua stimata';
      if (target.length) {
        const sp = target[0];
        const dentro = tAcqua >= sp.tOpt[0] && tAcqua <= sp.tOpt[1];
        f.push(dentro
          ? `${A} a ${t} °C: in pieno optimum per ${sp.nome.toLowerCase()} (${sp.tOpt[0]}–${sp.tOpt[1]} °C).`
          : tAcqua < sp.tOpt[0]
            ? `${A} a ${t} °C: sotto l'optimum di ${sp.nome.toLowerCase()} (${sp.tOpt[0]}–${sp.tOpt[1]} °C), aspettati mangiate lente e recuperi rallentati.`
            : `${A} a ${t} °C: sopra l'optimum di ${sp.nome.toLowerCase()} (${sp.tOpt[0]}–${sp.tOpt[1]} °C), concentrati sulle prime e ultime ore.`);
      } else {
        f.push(`${A} a ${t} °C.`);
      }
    }

    if (flowRatio !== null) {
      const pc = Math.round((flowRatio - 1) * 100);
      if (flowRatio > 2.6) f.push(`Portata a +${pc}% sulla mediana recente: piena in atto, non entrare in alveo.`);
      else if (flowRatio > 1.5) f.push(`Portata a +${pc}%: acqua abbondante e velata, buona per barbi e siluri, difficile per la mosca.`);
      else if (flowRatio > 1.12) f.push(`Portata a +${pc}%: leggero rialzo, la condizione che di solito accende il pesce.`);
      else if (flowRatio < 0.55) f.push(`Portata a ${pc}%: magra marcata, il pesce è concentrato nelle buche più profonde.`);
      else f.push('Portata vicina alla media del periodo: condizioni regolari.');
    }

    if (torb > 0.55) f.push('Acqua torbida: esche vistose e profumate, dimentica i terminali invisibili.');
    else if (torb < 0.2 && spot.categoria === 'D') f.push('Acqua limpidissima: terminali 0,10–0,12 e avvicinamento silenzioso da valle.');

    if (dPress !== null) {
      if (dPress <= -3) f.push(`Pressione in calo (${dPress.toFixed(1).replace('.', ',')} hPa): fase di alimentazione attiva.`);
      else if (dPress >= 4) f.push(`Pressione in aumento (+${dPress.toFixed(1).replace('.', ',')} hPa): il pesce tende a chiudersi, insisti nelle ore di luce bassa.`);
    }

    if (nuvole !== null && nuvole > 70) f.push('Cielo coperto: la finestra utile si allarga a tutta la giornata.');
    else if (nuvole !== null && nuvole < 20) f.push('Cielo sereno: alba e tramonto sono le uniche vere finestre.');

    const bonus = mod.filter(m => m.v > 0).map(m => m.t);
    if (bonus.length) f.push(bonus.join('. ') + '.');

    return f;
  }

  /* ================================================== classifica su tutti  */
  function classifica(spots, dati, dataISO, filtri = {}) {
    const out = [];
    spots.forEach(s => {
      if (!passa(s, filtri)) return;
      const v = valuta(s, dati.meteo[s.id], dati.portata[s.id], dataISO);
      if (v) out.push(v);
    });
    out.sort((a, b) => b.punteggio - a.punteggio);
    return out;
  }

  function passa(s, f) {
    if (f.prov && f.prov !== 'tutte' && s.prov !== f.prov) return false;
    if (f.tipo && f.tipo !== 'tutti' && s.tipo !== f.tipo) return false;
    if (f.categoria && f.categoria !== 'tutte' && s.categoria !== f.categoria) return false;
    if (f.specie && f.specie !== 'tutte' && !(s.specie || []).includes(f.specie)) return false;
    if (f.noKill && !s.noKill) return false;
    if (f.bimbi && !s.bimbi) return false;
    if (f.disabili && !s.disabili) return false;
    if (f.testo) {
      const q = f.testo.toLowerCase();
      const blob = [s.nome, s.comune, s.acqua, PROVINCE[s.prov], ...(s.specie || []).map(i => SPECIE[i] && SPECIE[i].nome)]
        .filter(Boolean).join(' ').toLowerCase();
      if (!blob.includes(q)) return false;
    }
    return true;
  }

  function etichetta(p, chiuso) {
    if (chiuso) return { t: 'Pesca vietata', c: 'low' };
    if (p >= 78) return { t: 'Eccellente', c: 'ok' };
    if (p >= 62) return { t: 'Ottimo', c: 'ok' };
    if (p >= 46) return { t: 'Buono', c: 'mid' };
    if (p >= 30) return { t: 'Discreto', c: 'mid' };
    if (p >= 16) return { t: 'Scarso', c: 'low' };
    return { t: 'Da evitare', c: 'low' };
  }

  /* Le tre fasce di colore. Stava in ui.js come costante locale, ma adesso il
     punteggio lo disegnano in due: l'applicazione e le pagine statiche scritte
     da tools/genera-pagine.py. Due soglie uguali scritte in due posti diversi
     restano uguali finche' qualcuno non ne cambia una sola. */
  const banda = (p) => p >= 62 ? 'buono' : p >= 30 ? 'medio' : 'scarso';

  return { valuta, classifica, etichetta, banda, faseLunare, inDivieto, tempAcqua,
           STAGIONE, passa, chiusura, stagioneChiusa, stagionale, regolaLocale };
})();
