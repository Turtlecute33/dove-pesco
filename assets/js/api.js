/* =============================================================================
   DATI DEL GIORNO: file statico, con Open-Meteo come rete di sicurezza
   -----------------------------------------------------------------------------
   Prima strada: assets/dati/previsioni.json, un file da una quarantina di KB
   compressi che GitHub Actions rigenera ogni quattro ore. Se c'è ed è fresco, il
   browser non chiama nessun servizio esterno: nessun 429, nessuna attesa,
   niente indirizzo IP dell'utente mostrato a terzi.

   Seconda strada, se il file manca o è vecchio (sito aperto con un doppio clic,
   pubblicazione senza il workflow, aggiornamento fermo): si chiama Open-Meteo
   dal browser come prima.

   Nessuna chiave, nessun tracciamento, nessun cookie. Le chiamate dal vivo
   vengono raggruppate: 222 spot in una decina di richieste.

   Open-Meteo è gratuito ma pone un limite al minuto, e una pagina intera ci va
   vicino. Perciò qui dentro ci sono tre accorgimenti:

     1. le richieste partono a tre per volta, non tutte insieme;
     2. se arriva un 429 si aspetta e si riprova, invece di arrendersi;
     3. la risposta resta in cache 45 minuti in localStorage, così ricaricare la
        pagina o aprirne un'altra scheda non ripete la rete.

   Se un lotto proprio non arriva, si mostra comunque il resto: mancheranno
   quaranta spot su duecento, non tutta la pagina.
   ========================================================================== */

const API = (() => {

  const FILE_STATICO = 'assets/dati/previsioni.json';
  /* Il flusso rigenera il file ogni 4 ore. Nove ore vogliono dire che due giri
     di fila non sono arrivati: allora è meglio la rete. Un margine più stretto
     manderebbe in rete tutti i visitatori per un semplice ritardo della coda di
     GitHub, che è quello che vogliamo evitare. I dati sono giornalieri, quindi
     un file di nove ore contiene comunque i valori di oggi. */
  const ETA_MAX = 9 * 60 * 60 * 1000;
  const METEO_URL = 'https://api.open-meteo.com/v1/forecast';
  const FLOOD_URL = 'https://flood-api.open-meteo.com/v1/flood';
  const CHUNK = 40;              // spot per richiesta
  const PARALLELE = 3;           // richieste contemporanee
  const TTL = 45 * 60 * 1000;    // 45 minuti
  const PAST = 10;               // giorni passati (per la temperatura dell'acqua)
  const FWD = 7;                 // giorni di previsione
  const RIPROVE = [1500, 6000, 14000];   // pause fra un tentativo e l'altro
  const PAUSA_LIMITE = 12000;            // quanto fermarsi tutti dopo un 429
  const TETTO = 38000;                   // oltre questo si smette e si mostra ciò che c'è

  const DAILY = [
    'weather_code', 'temperature_2m_max', 'temperature_2m_min', 'temperature_2m_mean',
    'precipitation_sum', 'wind_speed_10m_max', 'wind_direction_10m_dominant',
    'pressure_msl_mean', 'cloud_cover_mean', 'sunrise', 'sunset'
  ].join(',');

  let limitato = false;          // vero se l'ultimo giro ha incontrato un 429
  let nonPrimaDi = 0;            // tregua condivisa dopo un 429
  let scadenza = 0;              // ora oltre la quale non si insiste più
  let avvisa = null;             // l'interfaccia può ascoltare lo stato

  /* ---------- cache ----------
     localStorage così sopravvive alla ricarica e alle altre schede; se il
     browser lo nega (navigazione privata, quota piena) si ripiega sulla
     sessione e, in ultima istanza, si procede senza cache. */
  function magazzino() {
    for (const nome of ['localStorage', 'sessionStorage']) {
      try {
        const m = window[nome];
        const k = '__prova__';
        m.setItem(k, '1'); m.removeItem(k);
        return m;
      } catch (e) { /* si prova il prossimo */ }
    }
    return null;
  }
  const MAG = magazzino();

  function cacheGet(key) {
    if (!MAG) return null;
    try {
      const raw = MAG.getItem(key);
      if (!raw) return null;
      const o = JSON.parse(raw);
      if (Date.now() - o.t > TTL) { MAG.removeItem(key); return null; }
      return o.v;
    } catch (e) { return null; }
  }
  function cacheSet(key, v) {
    if (!MAG) return;
    try { MAG.setItem(key, JSON.stringify({ t: Date.now(), v })); }
    catch (e) {
      /* quota piena: si buttano le voci vecchie e si riprova una volta sola */
      try {
        scadute(true);
        MAG.setItem(key, JSON.stringify({ t: Date.now(), v }));
      } catch (e2) { /* si procede senza cache */ }
    }
  }
  function scadute(tutte) {
    if (!MAG) return;
    Object.keys(MAG).filter(k => k.startsWith('mto:') || k.startsWith('flw:')).forEach(k => {
      if (tutte) return MAG.removeItem(k);
      try {
        const o = JSON.parse(MAG.getItem(k));
        if (Date.now() - o.t > TTL) MAG.removeItem(k);
      } catch (e) { MAG.removeItem(k); }
    });
  }

  function chunks(arr, n) {
    const out = [];
    for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n));
    return out;
  }

  const attesa = (ms) => new Promise(r => setTimeout(r, ms));

  /* Esegue i lavori a pochi per volta: un colpo solo di dieci richieste
     supererebbe il limite al minuto di Open-Meteo. */
  async function aPochiPerVolta(lavori, quanti) {
    const esiti = new Array(lavori.length);
    let i = 0;
    await Promise.all(Array.from({ length: Math.min(quanti, lavori.length) }, async () => {
      while (i < lavori.length) {
        const k = i++;
        esiti[k] = await lavori[k]();
      }
    }));
    return esiti;
  }

  /* Open-Meteo restituisce un oggetto per una sola posizione,
     un array per più posizioni. Normalizziamo sempre ad array. */
  const asArray = (j) => (Array.isArray(j) ? j : [j]);

  /* Se un lotto incassa un 429, tutti gli altri si fermano con lui: insistere
     in parallelo non farebbe che tenere chiusa la porta più a lungo. */
  async function turno() {
    const d = Math.min(nonPrimaDi, scadenza) - Date.now();
    if (d > 0) await attesa(d);
  }

  async function fetchJSON(url) {
    let ultimo = null;
    for (let giro = 0; giro <= RIPROVE.length; giro++) {
      if (giro) {
        /* non si tiene la gente davanti alla rotellina più di mezzo minuto:
           scaduto il tetto si mostra quello che è arrivato */
        if (Date.now() > scadenza) break;
        await attesa(Math.min(RIPROVE[giro - 1], scadenza - Date.now()));
        await turno();
      }
      try {
        const r = await fetch(url, { cache: 'no-store' });
        if (r.status === 429) {              // limite di richieste: si riprova
          if (!limitato && avvisa) avvisa('limite');
          limitato = true;
          nonPrimaDi = Date.now() + PAUSA_LIMITE;
          ultimo = new Error('limite');
          continue;
        }
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return await r.json();
      } catch (e) { ultimo = e; }
    }
    throw ultimo || new Error('rete');
  }

  /* ========================================================================
     LA PRIMA STRADA: il file preparato da GitHub Actions
     ==================================================================== */
  let statico;   // undefined = non ancora provato · null = non c'è o è vecchio

  /* Il file è compatto: nomi corti, orari senza data, una sola riga di giorni
     per tutti. Qui torna nella forma che il motore si aspetta. */
  function espandi(j) {
    const meteo = {}, portata = {};
    const g = j.giorni || [], gp = j.giorniPortata || [];
    Object.keys(j.spot || {}).forEach(id => {
      const s = j.spot[id];
      if (!s.tmax) return;
      meteo[id] = { elevation: s.q, daily: {
        time: g,
        weather_code: s.wmo, temperature_2m_max: s.tmax, temperature_2m_min: s.tmin,
        temperature_2m_mean: s.tmed, precipitation_sum: s.pio,
        wind_speed_10m_max: s.ven, wind_direction_10m_dominant: s.dir,
        pressure_msl_mean: s.pre, cloud_cover_mean: s.nuv,
        sunrise: (s.alba || []).map((h, i) => h ? g[i] + 'T' + h : null),
        sunset:  (s.tram || []).map((h, i) => h ? g[i] + 'T' + h : null)
      } };
      if (s.por) portata[id] = { daily: { time: gp, river_discharge: s.por } };
    });
    return { meteo, portata };
  }

  async function daFileStatico() {
    if (statico !== undefined) return statico;
    statico = null;
    try {
      /* no-cache: si chiede al server se c'è una versione più nuova, senza
         riscaricare il file quando non è cambiato */
      const r = await fetch(FILE_STATICO, { cache: 'no-cache' });
      if (!r.ok) return null;
      const j = await r.json();
      const eta = Date.now() - Date.parse(j.generato);
      if (!(eta >= 0) || eta > ETA_MAX) return null;        // vecchio: meglio la rete
      const d = espandi(j);
      if (!Object.keys(d.meteo).length) return null;
      d.generato = j.generato;
      d.statico = true;
      d.persi = 0;
      statico = d;
    } catch (e) { /* file:// oppure file assente: si passa alla rete */ }
    return statico;
  }

  /* ---------- meteo ---------- */
  async function meteo(spots) {
    const out = {};
    const groups = chunks(spots, CHUNK);
    const esiti = await aPochiPerVolta(groups.map(g => async () => {
      const key = 'mto:' + g.map(s => s.id).join('|');
      let data = cacheGet(key);
      if (!data) {
        const u = `${METEO_URL}?latitude=${g.map(s => s.lat).join(',')}`
          + `&longitude=${g.map(s => s.lon).join(',')}`
          + `&daily=${DAILY}&past_days=${PAST}&forecast_days=${FWD}`
          + `&timezone=Europe%2FRome`;
        try { data = asArray(await fetchJSON(u)); }
        catch (e) { return false; }          // lotto perso: gli altri restano
        cacheSet(key, data);
      }
      g.forEach((s, i) => { if (data[i]) out[s.id] = data[i]; });
      return true;
    }), PARALLELE);
    return { dati: out, persi: esiti.filter(x => !x).length, lotti: groups.length };
  }

  /* ---------- portata dei fiumi (GloFAS) ---------- */
  async function portata(spots) {
    /* Solo corsi d'acqua naturali: laghi, cave e mare non hanno portata, e i
       canali artificiali non sono modellati da GloFAS (il loro livello dipende
       dalle chiuse e dai prelievi irrigui, non dal deflusso naturale). */
    const target = spots.filter(s => ['fiume', 'torrente'].includes(s.tipo));
    const out = {};
    const groups = chunks(target, CHUNK);
    await aPochiPerVolta(groups.map(g => async () => {
      const key = 'flw:' + g.map(s => s.id).join('|');
      let data = cacheGet(key);
      if (!data) {
        const u = `${FLOOD_URL}?latitude=${g.map(s => s.lat).join(',')}`
          + `&longitude=${g.map(s => s.lon).join(',')}`
          + `&daily=river_discharge&past_days=45&forecast_days=7`;
        try { data = asArray(await fetchJSON(u)); }
        catch (e) { data = []; }             // senza portata l'indice si calcola lo stesso
        if (data.length) cacheSet(key, data);
      }
      g.forEach((s, i) => { if (data[i]) out[s.id] = data[i]; });
      return true;
    }), PARALLELE);
    return out;
  }

  async function tutto(spots) {
    limitato = false; nonPrimaDi = 0; scadenza = Date.now() + TETTO;

    const pronto = await daFileStatico();
    if (pronto) return pronto;          // niente rete: i dati erano già lì

    scadute(false);
    /* prima il meteo (senza non si calcola nulla), poi la portata: due ondate
       separate pesano meno sul limite al minuto */
    const m = await meteo(spots);
    if (!Object.keys(m.dati).length) {
      const e = new Error(limitato
        ? 'Open-Meteo ha temporaneamente bloccato le richieste da questa rete (limite gratuito al minuto).'
        : 'Nessuna risposta da Open-Meteo.');
      e.limite = limitato;
      throw e;
    }
    const p = await portata(spots);
    return { meteo: m.dati, portata: p, persi: m.persi, lotti: m.lotti, limitato };
  }

  function svuotaCache() {
    statico = undefined;      // si riprova anche il file statico
    scadute(true);
  }

  /* l'interfaccia registra qui la funzione con cui raccontare l'attesa */
  const suStato = (fn) => { avvisa = fn; };

  return { tutto, meteo, portata, svuotaCache, suStato };
})();
