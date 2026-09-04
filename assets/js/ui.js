/* =============================================================================
   INTERFACCIA
   -----------------------------------------------------------------------------
   La pagina mostra una cosa per volta: la risposta del giorno, oppure la scheda
   dello spot che hai scelto. Il resto sta dietro un tocco.
   ========================================================================== */

const APP = (() => {

  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const GG   = ['dom', 'lun', 'mar', 'mer', 'gio', 'ven', 'sab'];
  const MESI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
                'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'];
  const GIORNI = ['domenica', 'lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato'];

  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const n1 = (v) => v === null || v === undefined ? '–' : String(Math.round(v * 10) / 10).replace('.', ',');
  const n0 = (v) => v === null || v === undefined ? '–' : String(Math.round(v));
  const seg = (n) => TAVOLE.seg(n);
  /* le tre bande di colore: gli stessi tagli delle etichette del motore,
     così la parola scritta e il colore del punto non si contraddicono mai */
  const banda = (p) => p >= 62 ? 'buono' : p >= 30 ? 'medio' : 'scarso';

  let dati = null;
  let dataSel = iso(new Date());
  let filtri = { prov: 'tutte', tipo: 'tutti', categoria: 'tutte', specie: 'tutte',
                 testo: '', noKill: false, bimbi: false, disabili: false };
  let scelto = null;        // id dello spot aperto, oppure null = risposta del giorno
  let tuttiAperti = false;
  let lista = [];
  let svgMappa = null;
  let popId = null;         // spot con la scheda rapida aperta sulla mappa
  let popFissa = false;     // aperta con un tocco: resta finché non la chiudi

  /* ======================================================= avvio */
  async function init() {
    montaGiorni(); montaFiltri(); montaSpecie(); montaRegole(); collegaMenu();
    dallIndirizzo();
    window.addEventListener('hashchange', dallIndirizzo);
    window.addEventListener('resize', adattaMappa);
    window.addEventListener('keydown', e => { if (e.key === 'Escape') chiudiPop(); });
    document.addEventListener('click', e => { if (!e.target.closest('.pt,.pop')) chiudiPop(); });
    await carica();
  }

  /* Le pagine degli spot rimandano qui con #spot/<id>: cosi' un link porta
     dritto alla scheda giusta invece che alla risposta del giorno. */
  function dallIndirizzo() {
    const h = location.hash.replace('#', '');
    const s = h.startsWith('spot/') ? h.slice(5) : null;
    if (s && SPOT.some(x => x.id === s)) {
      scelto = s;
      vai('oggi', false, false);
    } else {
      if (scelto) scelto = null;
      vai(h || 'oggi', false, false);
    }
    if (dati) render();
  }

  async function carica(forza = false) {
    if (forza) API.svuotaCache();
    $('#risposta').innerHTML = `<div class="stato">
      <div class="gira">${seg('bussola')}</div>
      <p class="mini" id="stato-testo">Rilevo meteo, portata dei fiumi e stagionalità su ${SPOT.length} spot…</p></div>`;
    API.suStato(() => {
      const t = $('#stato-testo');
      if (t) t.innerHTML = 'Open-Meteo è al limite di richieste al minuto: aspetto qualche secondo '
        + 'e riprovo da solo.<br><span class="tenue">Succede solo alla prima apertura: poi i dati '
        + 'restano in cache 45 minuti.</span>';
    });
    $('#mappa').innerHTML = ''; $('#altri').innerHTML = '';
    try {
      dati = await API.tutto(SPOT);
      render();
    } catch (e) {
      const limite = !!(e && e.limite);
      $('#risposta').innerHTML = `<div class="stato">
        <div style="width:26px;margin:0 auto 14px;color:var(--allarme)">${seg('avviso')}</div>
        <h2>${limite ? 'Il servizio meteo ci ha messo in coda' : 'Dati meteo non raggiungibili'}</h2>
        <p class="mini" style="margin-top:8px;max-width:44ch;margin-inline:auto">${limite
          ? 'Open-Meteo è gratuito e limita le richieste al minuto: aspetta un minuto e riprova. '
            + 'La risposta resta poi in cache 45 minuti, quindi capita solo alla prima apertura.'
          : esc((e && e.message) || 'Controlla la connessione.')
            + ' Le specie e le regole restano consultabili.'}</p>
        <p style="margin-top:18px"><button class="btn vuoto" onclick="APP.ricarica()">Riprova</button></p></div>`;
    }
  }

  /* ======================================================= controlli */
  function montaGiorni() {
    const oggi = new Date(); oggi.setHours(12, 0, 0, 0);
    let h = '';
    for (let k = 0; k < 7; k++) {
      const d = new Date(oggi); d.setDate(d.getDate() + k);
      const v = iso(d);
      h += `<button type="button" class="gio" data-d="${v}" aria-pressed="${v === dataSel}">
        <span>${k === 0 ? 'oggi' : GG[d.getDay()]}</span><b>${d.getDate()}</b></button>`;
    }
    const box = $('#giorni'); box.innerHTML = h;
    $$('.gio', box).forEach(b => b.onclick = () => {
      dataSel = b.dataset.d;
      $$('.gio', box).forEach(x => x.setAttribute('aria-pressed', String(x === b)));
      scelto = null; render(); portaSu();
    });
  }

  function montaFiltri() {
    $('#f-prov').innerHTML = `<option value="tutte">tutte</option>` +
      Object.entries(PROVINCE).map(([k, v]) => `<option value="${k}">${v}</option>`).join('');
    $('#f-tipo').innerHTML = `<option value="tutti">tutti</option>` +
      [['fiume', 'fiumi'], ['torrente', 'torrenti'], ['lago', 'laghi'], ['bacino', 'bacini'],
       ['canale', 'canali'], ['cava', 'cave'], ['mare', 'mare e foci']]
      .map(([k, v]) => `<option value="${k}">${v}</option>`).join('');
    $('#f-cat').innerHTML = `<option value="tutte">tutte</option>` +
      Object.entries(CATEGORIE).map(([k, v]) => `<option value="${k}">${v.nome.toLowerCase()}</option>`).join('');
    const usate = new Set(); SPOT.forEach(s => (s.specie || []).forEach(i => usate.add(i)));
    $('#f-specie').innerHTML = `<option value="tutte">tutte</option>` +
      Array.from(usate).filter(i => SPECIE[i]).sort((a, b) => SPECIE[a].nome.localeCompare(SPECIE[b].nome, 'it'))
        .map(i => `<option value="${i}">${esc(SPECIE[i].nome.toLowerCase())}</option>`).join('');

    const c = (id, k) => $(id).onchange = e => { filtri[k] = e.target.value; scelto = null; render(); };
    c('#f-prov', 'prov'); c('#f-tipo', 'tipo'); c('#f-cat', 'categoria'); c('#f-specie', 'specie');

    let deb;
    $('#f-testo').oninput = e => {
      clearTimeout(deb); const v = e.target.value.trim();
      deb = setTimeout(() => { filtri.testo = v; scelto = null; render(); }, 200);
    };
    $$('.spunta[data-f]').forEach(b => b.onclick = () => {
      const k = b.dataset.f; filtri[k] = !filtri[k];
      b.setAttribute('aria-pressed', String(filtri[k])); scelto = null; render();
    });
    $('#azzera').onclick = () => {
      filtri = { prov: 'tutte', tipo: 'tutti', categoria: 'tutte', specie: 'tutte',
                 testo: '', noKill: false, bimbi: false, disabili: false };
      $('#f-prov').value = 'tutte'; $('#f-tipo').value = 'tutti';
      $('#f-cat').value = 'tutte'; $('#f-specie').value = 'tutte'; $('#f-testo').value = '';
      $$('.spunta[data-f]').forEach(b => b.setAttribute('aria-pressed', 'false'));
      scelto = null; render();
    };
    $('#aggiorna').onclick = () => carica(true);
  }

  function collegaMenu() {
    $$('nav.men button[data-v]').forEach(b => b.onclick = () => vai(b.dataset.v));
    $$('[data-vai]').forEach(a => a.onclick = e => { e.preventDefault(); vai(a.dataset.vai); });
  }

  function vai(v, su = true, scrivi = true) {
    if (!$(`section[data-v="${v}"]`)) v = 'oggi';
    if (scrivi && scelto) scelto = null;
    $$('section[data-v]').forEach(s => s.hidden = s.dataset.v !== v);
    $$('nav.men button[data-v]').forEach(b => {
      if (b.dataset.v === v) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
    });
    if (scrivi) {
      history.replaceState(null, '', '#' + v);
      if (dati) render();
    }
    if (su) window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  const portaSu = () => window.scrollTo({ top: 0, behavior: 'smooth' });

  /* ======================================================= disegno */
  function render() {
    if (!dati) return;
    lista = ENGINE.classifica(SPOT, dati, dataSel, filtri);

    const d = new Date(dataSel + 'T12:00:00');
    const luna = ENGINE.faseLunare(d);
    $('#data-oggi').textContent = `${GIORNI[d.getDay()]} ${d.getDate()} ${MESI[d.getMonth()]}`;
    $('#data-luna').textContent = `luna ${Math.round(luna.illum * 100)}%, ${luna.nome.toLowerCase()}`;

    /* quando i dati arrivano dal file preparato a monte, diciamo di quando sono */
    const fonte = $('#data-fonte');
    if (fonte) {
      const g = dati.generato ? new Date(dati.generato) : null;
      fonte.hidden = !g;
      if (g) fonte.textContent = `rilevati alle ${String(g.getHours()).padStart(2, '0')}:${String(g.getMinutes()).padStart(2, '0')}`;
    }

    if (!lista.length) {
      $('#risposta').innerHTML = `<div class="stato">
        <h2>Nessuno spot con questi criteri</h2>
        <p class="mini" style="margin-top:8px">Allarga la ricerca o azzera i filtri.</p></div>`;
      $('#mappa').innerHTML = ''; $('#altri').innerHTML = ''; $('#tutti').innerHTML = '';
      return;
    }

    const v = scelto ? lista.find(x => x.spot.id === scelto) : null;
    const box = $('#risposta');
    box.innerHTML = parzialeHTML() + (v ? schedaHTML(v) : rispostaHTML(lista[0]));
    box.classList.remove('entra'); void box.offsetWidth; box.classList.add('entra');
    collegaRisposta();

    chiudiPop(true);
    svgMappa = MAPPA.disegnaRegione($('#mappa'), lista, { onVista: riposizionaPop });
    collegaMappa(); evidenzia(scelto);
    /* con una scheda aperta la mappa si stringe su quel punto */
    if (v) MAPPA.centraSu(v.spot.lat, v.spot.lon, 4.5);

    disegnaAltri();
    if (tuttiAperti) disegnaTutti();
  }

  /* Se qualche lotto di dati non è arrivato lo diciamo, invece di far sparire
     in silenzio un pezzo di classifica. */
  function parzialeHTML() {
    const mancano = dati && dati.meteo ? SPOT.length - Object.keys(dati.meteo).length : 0;
    if (mancano <= 0) return '';
    return `<div class="avvisi" style="margin-bottom:clamp(18px,2.4vw,24px)">
      <div class="avviso">${seg('info')}<div>Il servizio meteo ha risposto solo in parte:
        oggi mancano ${mancano} spot su ${SPOT.length}.
        <button class="link" style="padding:0;font-size:inherit" onclick="APP.ricarica()">Riprova fra un minuto</button>
      </div></div></div>`;
  }

  /* ---------------------------------------------- la risposta del giorno */
  function rispostaHTML(v) {
    const s = v.spot, m = v.meteo, a = v.acqua;
    const pesce = v.specie.find(x => !x.soloRilascio) || v.specie[0];
    const ci = TAVOLE.ciel(m.wmo);

    const fatti = [];
    fatti.push(`<div class="fatto${banda(v.punteggio) === 'buono' ? ' acc' : ''}"><span class="occhio">indice</span>
      <span class="indice ${banda(v.punteggio)}"><b>${v.punteggio}</b><s>/100</s></span>
      <em>${esc(ENGINE.etichetta(v.punteggio).t.toLowerCase())}</em></div>`);
    if (pesce) fatti.push(`<div class="fatto"><span class="occhio">il pesce</span>
      <b style="font-size:clamp(1.15rem,2.2vw,1.5rem)">${esc(pesce.nome)}</b>
      <em>il più attivo oggi</em></div>`);
    fatti.push(`<div class="fatto"><span class="occhio">acqua</span>
      <b>${n1(a.temp)}<span class="u">°C</span></b><em>${esc(etAcqua(a.temp))}, stimata</em></div>`);
    if (a.flowRatio !== null)
      fatti.push(`<div class="fatto"><span class="occhio">portata</span>
        <b>${a.flowRatio >= 1 ? '+' : ''}${n0((a.flowRatio - 1) * 100)}<span class="u">%</span></b>
        <em>sulla mediana</em></div>`);
    else
      fatti.push(`<div class="fatto"><span class="occhio">cielo</span>
        <b style="font-size:clamp(1.15rem,2.2vw,1.5rem)">${esc(ci.testo)}</b>
        <em>nuvole ${n0(m.nuvole)}%</em></div>`);
    if (m.alba) fatti.push(`<div class="fatto"><span class="occhio">prima luce</span>
      <b>${esc(m.alba)}</b><em>la finestra migliore</em></div>`);

    return `
      <span class="occhio acc">Oggi vai qui</span>
      <h2 class="titolone">${esc(s.nome)}</h2>
      <div class="luogo">${esc(s.comune)}, ${esc(PROVINCE[s.prov])}</div>
      <div class="fatti">${fatti.join('')}</div>
      <p class="perche">${esc(v.spiegazione.slice(0, 2).join(' '))}</p>
      <div class="azioni">
        <button class="btn" data-apri="${esc(s.id)}">Come ci si arriva ${seg('freccia')}</button>
        <button class="link" data-giu>Vedi gli altri buoni di oggi</button>
      </div>`;
  }

  /* Quanto è largo il riquadro della carta locale, e cosa ci trovi dentro. Il
     lato non è sempre lo stesso: se l'acqua sta lontana, la carta si stringe
     attorno allo spot e al suo tratto d'acqua. */
  const misuraRiquadro = (s) =>
    `Riquadro di ${(MAPPA.latoLocale(s.id) / 1000).toFixed(1).replace('.', ',')} km, con ${s.acqua}.`;

  /* Il punto che aprono i tasti.

     Non è la coordinata della scheda. Quella dice di che pezzo di fiume
     parlano il meteo e la portata, e su un fiume largo cade in mezzo alla
     corrente: 82 spot su 222 mandavano chi premeva «Naviga» dentro l'acqua.
     tools/accessi.py calcola a parte il punto in cui una strada arriva alla
     sponda, e sta in ACCESSI. Dove non c'è, si torna alla coordinata della
     scheda, che è il meglio che sappiamo.

     «Naviga» apre l'applicazione di navigazione del telefono con l'indirizzo
     geo:, che su un computer non porta da nessuna parte: lì il tasto non
     compare (style.css). */
  const accessoDi = (s) =>
    (typeof ACCESSI !== 'undefined' && ACCESSI[s.id]) || null;

  const fuoriHTML = (s) => {
    const a = accessoDi(s);
    const la = (a ? a[0] : s.lat).toFixed(5), lo = (a ? a[1] : s.lon).toFixed(5);
    return `<div class="fuori">
      <a class="btn vuoto piccolo" target="_blank" rel="noopener noreferrer"
         href="https://www.openstreetmap.org/?mlat=${la}&mlon=${lo}#map=17/${la}/${lo}"
         >${seg('puntina')} OpenStreetMap</a>
      <a class="btn vuoto piccolo" target="_blank" rel="noopener noreferrer"
         href="https://www.google.com/maps/search/?api=1&query=${la},${lo}"
         >${seg('puntina')} Google Maps</a>
      <a class="btn vuoto piccolo solo-telefono" href="geo:${la},${lo}?q=${la},${lo}(${encodeURIComponent(s.nome)})"
         >${seg('navigatore')} Naviga</a>
      <span class="micro tenue num coord">${la}, ${lo}</span>
    </div>`;
  };

  /* Che cosa promettere di quel punto. Un punto calcolato sulla sponda
     disegnata e su una strada su cui ci si ferma è una cosa; un punto trovato
     allargando le soglie è un'altra, e va detto invece che lasciato credere. */
  const PERCHE = {
    mezzeria: ' La sponda qui non è disegnata: la misura è sulla mezzeria del corso d\'acqua.',
    ponte: ' Il punto è su un attraversamento: guarda da che parte si scende.',
    'strada grossa': ' È su una strada di grande traffico: cerca dove accostare.',
    allargato: ' Trovato allargando le soglie: è il tratto giusto, non il metro giusto.',
    mano: ' Controllato a mano.',
  };

  const dettoAccesso = (s) => {
    const a = accessoDi(s);
    if (!a) return ' Il segno è la coordinata della scheda: qui la sponda non è disegnata in mappa.';
    const testa = ` Il segno pieno è dove ci si ferma: ${a[3]}.`;
    return testa + (PERCHE[a[4]] || '');
  };

  /* ---------------------------------------------- la scheda dello spot */
  function schedaHTML(v) {
    const s = v.spot, m = v.meteo, a = v.acqua;
    const ci = TAVOLE.ciel(m.wmo);
    const utili = v.specie.filter(x => !x.soloRilascio);
    const inVista = (utili.length ? utili : v.specie).slice(0, 3);
    const resto = v.specie.filter(x => inVista.indexOf(x) < 0);
    const nAcc = MAPPA.contaAccessi(s.id);

    return `
      <div class="torna"><button class="link" data-chiudi>${seg('indietro')} Torna a oggi</button></div>

      <span class="occhio acc">indice ${v.punteggio}/100 · ${esc(ENGINE.etichetta(v.punteggio).t.toLowerCase())}</span>
      <h2 class="titolone">${esc(s.nome)}</h2>
      <div class="luogo">${esc(s.comune)}, ${esc(PROVINCE[s.prov])} · ${esc(s.acqua)}</div>

      ${avvisiHTML(v)}

      <div class="blocchi">
        <div class="duecol">
          <div class="bl">
            <span class="occhio">Dove fermarsi</span>
            <div class="porta-mappa" data-spot="${esc(s.id)}">${
              typeof GEO_LOCALE !== 'undefined' ? MAPPA.disegnaLocale(s) : MAPPA.attesaLocale()}</div>
            <p class="micro tenue" style="margin-top:9px"><span class="nota-lato">${
              esc(misuraRiquadro(s))}</span><span class="nota-acc">${
              esc(dettoAccesso(s))}${
              nAcc ? ` Gli altri segni numerati sono i tratti in cui una strada arriva alla riva.` : ''}</span></p>
            <p class="mini" style="margin-top:12px">${esc(s.comeArrivare)}</p>
            <p class="mini">${esc(s.accesso)}</p>
            ${fuoriHTML(s)}
          </div>

          <div style="display:grid;gap:clamp(26px,4vw,38px)">
            <div class="bl">
              <span class="occhio">Perché oggi qui</span>
              <ul class="motivi">${v.spiegazione.slice(0, 4).map(x => `<li>${esc(x)}</li>`).join('')}</ul>
            </div>

            <div class="bl">
              <span class="occhio">Come si presenta</span>
              <div class="rilev">
                <div class="ril"><u>acqua</u><b>${n1(a.temp)}<span class="u">°</span></b>
                  <em>${esc(etAcqua(a.temp))}</em></div>
                ${a.flowRatio !== null
                  ? `<div class="ril"><u>portata</u><b>${a.flowRatio >= 1 ? '+' : ''}${n0((a.flowRatio - 1) * 100)}<span class="u">%</span></b><em>sulla mediana</em></div>`
                  : ''}
                <div class="ril"><u>cielo</u><b style="font-size:1rem;line-height:1.35">${esc(ci.testo)}</b>
                  <em>nuvole ${n0(m.nuvole)}%</em></div>
                <div class="ril"><u>aria</u><b>${n0(m.tmax)}<span class="u">°</span></b>
                  <em>min ${n0(m.tmin)}°</em></div>
                <div class="ril"><u>luce</u><b style="font-size:1rem;line-height:1.35">${esc(m.alba || '–')}</b>
                  <em>tramonto ${esc(m.tramonto || '–')}</em></div>
              </div>
              <details class="pieghe" style="margin-top:18px">
                <summary>Tutti i rilevamenti</summary>
                <div class="dentro"><div class="rilev">
                  <div class="ril"><u>pioggia</u><b>${n1(m.pioggia)}<span class="u">mm</span></b>
                    <em>${n1(m.p72)} mm nelle 72 h</em></div>
                  <div class="ril"><u>pressione</u><b>${n0(m.press)}</b>
                    <em>${m.dPress === null ? 'hPa' : (m.dPress >= 0 ? '+' : '') + n1(m.dPress) + ' su ieri'}</em></div>
                  <div class="ril"><u>vento</u><b>${n0(m.vento)}<span class="u">km/h</span></b>
                    <em>da ${esc(rosa(m.ventoDir))}</em></div>
                  <div class="ril"><u>torbidità</u><b style="font-size:1rem;line-height:1.35">${esc(etTorb(a.torbidita))}</b>
                    <em>${n0(a.torbidita * 100)} su 100</em></div>
                  ${a.flow !== null && a.flowAssoluto
                    ? `<div class="ril"><u>deflusso</u><b>${n1(a.flow)}<span class="u">m³/s</span></b><em>modello GloFAS</em></div>` : ''}
                  <div class="ril"><u>quota</u><b>${m.quota === null ? '–' : n0(Math.max(0, m.quota))}<span class="u">m</span></b>
                    <em>sul livello del mare</em></div>
                </div></div>
              </details>
            </div>

            ${v.finestre.length ? `<div class="bl">
              <span class="occhio">Le finestre buone</span>
              <ul class="motivi">${v.finestre.slice(0, 3).map(f =>
                `<li><b>${esc(f.q)}</b>, ${esc(f.o)}. ${esc(f.why)}</li>`).join('')}</ul>
            </div>` : ''}
          </div>
        </div>

        <div class="bl">
          <span class="occhio">Cosa insidiare</span>
          <div>${inVista.map(pesceHTML).join('')}</div>
          ${resto.length ? `<details class="pieghe" style="margin-top:6px">
            <summary>Le altre ${resto.length} specie di questo spot</summary>
            <div class="dentro">${resto.map(pesceHTML).join('')}</div></details>` : ''}
        </div>

        <div>
          <details class="pieghe">
            <summary>Com'è fatto il posto</summary>
            <div class="dentro">
              <p class="mini">${esc(s.fondale)}</p>
              <p class="mini" style="margin-top:10px"><b>Tecniche:</b> ${esc((s.tecniche || []).join(' · '))}</p>
              <p class="mini"><b>Esche:</b> ${esc((s.esche || []).join(' · '))}</p>
              <p class="mini"><b>Stagioni migliori:</b> ${esc((s.stagioniTop || []).join(', ') || '–')} ·
                 <b>Difficoltà:</b> ${esc(s.livello)} ·
                 <b>Acque:</b> ${esc(CATEGORIE[s.categoria].nome.toLowerCase())}</p>
            </div>
          </details>
          <details class="pieghe">
            <summary>Regole e cose da sapere</summary>
            <div class="dentro"><p class="mini">${esc(s.note)}</p>
              <p class="micro tenue" style="margin-top:10px">${esc(CATEGORIE[s.categoria].desc)}</p></div>
          </details>
        </div>
      </div>`;
  }

  function pesceHTML(f) {
    const q = Math.round(Math.min(100, f.score * 100));
    return `<div class="pesce${f.soloRilascio ? ' spenta' : ''}">
      <div class="fig">${TAVOLE.pesce(f.id)}</div>
      <div>
        <h4>${esc(f.nome)}
          ${f.vietata ? `<span class="tag rosso">in divieto</span>`
            : f.protetta ? `<span class="tag rosso">protetta</span>` : ''}
          ${f.rara ? `<span class="tag">raro qui</span>` : ''}
          <span class="q">${q}</span></h4>
        <div class="sotto">${esc(f.prof)}</div>
        <div class="sotto"><b>Esche:</b> ${esc((f.esche || []).slice(0, 4).join(', ') || '–')}</div>
        <details class="pieghe" style="border:0;margin-top:2px">
          <summary style="padding:6px 0;font-size:.84rem">Dettagli e regole</summary>
          <div class="dentro" style="padding-bottom:6px"><dl>
            <dt>tecniche</dt><dd>${esc((f.tecniche || []).join(', ') || '–')}</dd>
            <dt>acqua</dt><dd>${f.tOpt[0]}–${f.tOpt[1]} °C · ${esc(ore(f.luce))}</dd>
            <dt>regole</dt><dd>${regole(f)}</dd>
            ${f.taglia ? `<dt>taglia</dt><dd>${esc(f.taglia)}</dd>` : ''}
          </dl>${f.dritte ? `<p class="cons">${esc(f.dritte)}</p>` : ''}</div>
        </details>
      </div>
    </div>`;
  }

  function regole(f) {
    const p = [];
    p.push(f.misuraMin ? `misura minima ${f.misuraMin} cm` : 'nessuna misura minima regionale');
    if (f.limiteGiorno === 0) p.push('pesca vietata');
    else if (f.limiteGiorno) p.push(`max ${f.limiteGiorno} ${f.limiteGiorno === 1 ? 'capo' : 'capi'} al giorno`);
    if (f.registrazione) p.push('obbligo di registrazione');
    p.push(`divieto: ${f.divietoTesto}`);
    return esc(p.join(' · '));
  }

  function avvisiHTML(v) {
    const out = [], a = v.acqua, m = v.meteo, s = v.spot;
    if (a.flowRatio !== null && a.flowRatio > 2.6)
      out.push(['rosso', `Portata a +${Math.round((a.flowRatio - 1) * 100)}% sulla mediana: piena in atto. Non entrare in alveo, non guadare.`]);
    else if (a.flowRatio !== null && a.flowRatio > 1.8)
      out.push(['', `Portata in rialzo marcato (+${Math.round((a.flowRatio - 1) * 100)}%): acqua veloce e velata, attenzione ai guadi.`]);
    if ([95, 96, 99].indexOf(m.wmo) >= 0)
      out.push(['rosso', 'Temporali previsti. Le canne in carbonio conducono: allontanati dall\'acqua al primo tuono.']);
    if (/Limentra/.test(s.acqua || ''))
      out.push(['', 'Rilasci quotidiani dalla diga di Suviana: il livello sale in pochi minuti.']);
    if (/Savio/.test(s.acqua || ''))
      out.push(['', 'La portata dipende dai rilasci della diga di Quarto: serali nei giorni lavorativi.']);
    if (/Taro/.test(s.acqua || ''))
      out.push(['rosso', 'Sul Taro vige il divieto di pesca fino al 31/12/2026 dalla derivazione di Ramiola alla foce: verifica l\'estensione esatta.']);
    const vietate = v.specie.filter(x => x.vietata && !x.protetta);
    if (vietate.length)
      out.push(['', `Oggi in divieto: ${vietate.map(x => x.nome.toLowerCase()).join(', ')}. Rilascio immediato in acqua.`]);
    if (s.noKill) out.push(['acc', 'Tratti no kill: amo singolo senza ardiglione, slamatura in acqua, nessun prelievo.']);
    return out.length
      ? `<div class="avvisi" style="margin-top:clamp(24px,3vw,32px)">${out.map(([c, t]) =>
          `<div class="avviso ${c}">${seg(c === 'acc' ? 'scudo' : 'avviso')}<div>${esc(t)}</div></div>`).join('')}</div>`
      : '';
  }

  /* ---------------------------------------------- altri spot */
  function disegnaAltri() {
    const altri = lista.slice(1, 7);
    if (!altri.length) { $('#altri').innerHTML = ''; return; }
    $('#altri').innerHTML = `
      <div class="altri-testa">
        <h2>Altri buoni oggi</h2>
        <span class="micro tenue">${lista.length} spot con i filtri attuali</span>
      </div>
      <div class="righe">${altri.map(rigaHTML).join('')}</div>
      <div class="piu"><button class="link" id="btn-tutti">${
        tuttiAperti ? 'Nascondi l\'elenco completo' : 'Vedi tutti i ' + lista.length} ${seg('freccia')}</button></div>`;
    $('#btn-tutti').onclick = () => {
      tuttiAperti = !tuttiAperti;
      if (tuttiAperti) {
        disegnaTutti();
        requestAnimationFrame(() => $('#tutti').scrollIntoView({ behavior: 'smooth', block: 'start' }));
      } else $('#tutti').innerHTML = '';
      disegnaAltri();
    };
    collegaRighe($('#altri'));
  }

  function disegnaTutti() {
    $('#tutti').innerHTML = `
      <div class="altri-testa"><h2>Tutti gli spot</h2>
        <span class="micro tenue">in ordine di indice</span></div>
      <div class="righe">${lista.map(rigaHTML).join('')}</div>`;
    collegaRighe($('#tutti'));
  }

  function rigaHTML(v) {
    const s = v.spot;
    const b = v.specie.filter(x => !x.soloRilascio).slice(0, 2).map(x => x.nome.toLowerCase());
    return `<button type="button" class="riga ${banda(v.punteggio)}" data-apri="${esc(s.id)}">
      <span class="n">${v.punteggio}</span>
      <span>
        <span class="tit">${esc(s.nome)}</span>
        <span class="sub">${esc(s.comune)}, ${esc(PROVINCE[s.prov])}${b.length ? ' · ' + esc(b.join(', ')) : ''}</span>
      </span>
      <span class="dx">acqua <b>${n1(v.acqua.temp)}°</b>${
        v.acqua.flowRatio !== null ? ' · portata <b>' + (v.acqua.flowRatio >= 1 ? '+' : '') + n0((v.acqua.flowRatio - 1) * 100) + '%</b>' : ''}</span>
    </button>`;
  }

  const collegaRighe = (r) => $$('.riga[data-apri]', r).forEach(b => {
    const id = b.dataset.apri;
    b.onclick     = () => apri(id);
    b.onmouseenter = () => accendi(id, true);
    b.onmouseleave = () => accendi(id, false);
    b.onfocus     = () => accendi(id, true);
    b.onblur      = () => accendi(id, false);
  });

  function collegaRisposta() {
    const r = $('#risposta');
    $$('[data-apri]', r).forEach(b => b.onclick = () => apri(b.dataset.apri));
    const ch = $('[data-chiudi]', r);
    if (ch) ch.onclick = () => {
      scelto = null;
      history.replaceState(null, '', '#oggi');
      render(); portaSu();
    };
    const g = $('[data-giu]', r);
    if (g) g.onclick = () => $('#altri').scrollIntoView({ behavior: 'smooth', block: 'start' });
    caricaMappaLocale();
  }

  /* l'indirizzo segue la scheda aperta: si puo' condividere e si puo' tornare
     indietro, e combacia con la pagina statica /spot/<nome>/ */
  function apri(id) {
    scelto = id;
    history.replaceState(null, '', '#spot/' + id);
    render(); portaSu();
  }

  /* la mappa locale arriva a parte, alla prima scheda aperta */
  function caricaMappaLocale() {
    const porta = $('.porta-mappa');
    if (!porta || typeof GEO_LOCALE !== 'undefined') return;
    const id = porta.dataset.spot;
    MAPPA.caricaLocale().then(ok => {
      const p = $(`.porta-mappa[data-spot="${id}"]`);
      const v = lista.find(x => x.spot.id === id);
      if (!p || !v) return;
      p.innerHTML = ok ? MAPPA.disegnaLocale(v.spot)
        : `<div class="locale"><div class="locale-vuota"><p class="mini">Mappa non caricata.</p></div></div>`;
      const lato = $('.nota-lato');
      if (lato) lato.textContent = misuraRiquadro(v.spot);
      const nota = $('.nota-acc');
      const n = MAPPA.contaAccessi(id);
      if (nota) nota.textContent = dettoAccesso(v.spot)
        + (n ? ' Gli altri segni numerati sono i tratti in cui una strada arriva alla riva.' : '');
    });
  }

  /* ---------------------------------------------- mappa regionale
     Con il mouse il punto si racconta al passaggio e il clic porta dritto alla
     scheda dello spot. Al tocco, dove il passaggio non esiste, il primo tocco
     apre la scheda rapida e il secondo apre la scheda intera. */
  function collegaMappa() {
    if (!svgMappa) return;
    const conMouse = window.matchMedia('(hover:hover) and (pointer:fine)').matches;

    $$('.pt', svgMappa).forEach(g => {
      const id = g.dataset.id;
      if (!lista.some(x => x.spot.id === id)) return;

      if (conMouse) {
        g.addEventListener('mouseenter', () => { accendi(id, true); if (!popFissa) mostraPop(id, false); });
        g.addEventListener('mouseleave', () => { accendi(id, false); if (!popFissa) chiudiPop(); });
        g.addEventListener('click', e => { e.stopPropagation(); chiudiPop(true); apri(id); });
        /* con la tastiera il fuoco fa le veci del passaggio. Al tocco no: il
           fuoco arriva insieme al tocco e la scheda comparirebbe due volte */
        g.addEventListener('focus', () => { accendi(id, true); mostraPop(id, false); });
        g.addEventListener('blur',  () => { accendi(id, false); if (!popFissa) chiudiPop(); });
      } else {
        g.addEventListener('click', e => {
          e.stopPropagation();
          if (popId === id && popFissa) { chiudiPop(true); apri(id); }
          else mostraPop(id, true);
        });
      }
      g.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chiudiPop(true); apri(id); }
      });
    });
  }

  /* Il punto sulla mappa e la riga nell'elenco sono lo stesso spot visto da due
     parti: accendendo l'uno si accende anche l'altra. */
  function accendi(id, on) {
    if (svgMappa) {
      const g = $(`.pt[data-id="${CSS.escape(id)}"]`, svgMappa);
      if (g) g.classList.toggle('punta', on);
    }
    $$(`.riga[data-apri="${CSS.escape(id)}"]`).forEach(b => b.classList.toggle('punta', on));
  }

  /* posizione del punto dentro il riquadro della mappa */
  function ancora(g, corpo) {
    const r = g.getBoundingClientRect(), c = corpo.getBoundingClientRect();
    return { x: r.left + r.width / 2 - c.left, y: r.top - c.top, giu: r.bottom - c.top,
             w: c.width, h: c.height };
  }

  /* La stessa scheda rapida in due modi: al passaggio si legge soltanto, al
     tocco resta ferma e porta i suoi comandi. */
  function mostraPop(id, fissa) {
    const v = lista.find(x => x.spot.id === id);
    const corpo = $('.mappa-corpo', $('#mappa'));
    if (!v || !corpo) return;
    const pop = $('.pop', corpo), s = v.spot, a = v.acqua;
    const pesce = v.specie.find(x => !x.soloRilascio) || v.specie[0];

    const dati = [`acqua ${n1(a.temp)}°`];
    if (a.flowRatio !== null)
      dati.push(`portata ${a.flowRatio >= 1 ? '+' : ''}${n0((a.flowRatio - 1) * 100)}%`);
    if (pesce) dati.push(pesce.nome.toLowerCase());
    if (s.noKill) dati.push('no kill');

    popId = id; popFissa = !!fissa;
    pop.classList.toggle('ferma', popFissa);
    pop.innerHTML = `
      ${popFissa ? '<button class="pop-x" type="button" aria-label="Chiudi la scheda rapida">×</button>' : ''}
      <div class="p-testa">
        <span class="p-pun ${banda(v.punteggio)}">${v.punteggio}</span>
        <span class="micro tenue">${esc(ENGINE.etichetta(v.punteggio).t.toLowerCase())}</span>
      </div>
      <b class="p-nome">${esc(s.nome)}</b>
      <span class="p-sub">${esc(s.comune)}, ${esc(PROVINCE[s.prov])} · ${esc(s.acqua)}</span>
      <div class="p-dati">${dati.map(d => `<span>${esc(d)}</span>`).join('')}</div>
      ${popFissa ? '<div class="p-az"><button class="btn piccolo" type="button">Apri la scheda</button></div>' : ''}`;
    pop.hidden = false;
    if (popFissa) {
      $('.pop-x', pop).onclick = () => chiudiPop();
      $('.p-az .btn', pop).onclick = () => { chiudiPop(true); apri(id); };
    }
    evidenzia(id);
    riposizionaPop();
    requestAnimationFrame(() => pop.classList.add('vista'));
  }

  function riposizionaPop() {
    if (!popId || !svgMappa) return;
    const corpo = $('.mappa-corpo', $('#mappa'));
    const g = corpo && $(`.pt[data-id="${CSS.escape(popId)}"]`, svgMappa);
    if (!g) return;
    const pop = $('.pop', corpo), p = ancora(g, corpo);

    /* se il punto esce dal riquadro trascinando, la scheda sparisce con lui */
    if (p.x < 0 || p.x > p.w || p.giu < 0 || p.y > p.h) { pop.style.visibility = 'hidden'; return; }
    pop.style.visibility = '';

    const larg = pop.offsetWidth, alt = pop.offsetHeight;
    /* sopra al punto se ci sta, altrimenti sotto. Se il riquadro è troppo basso
       per tutte e due, e sul telefono la regione è una striscia larga e bassa,
       la scheda si appoggia dentro il riquadro e rinuncia alla punta: meglio
       senza punta che tagliata a metà, con il pulsante fuori dal bordo. */
    const staSopra = p.y - alt - 16 >= 0;
    const staSotto = p.giu + alt + 16 <= p.h;
    const libera = !staSopra && !staSotto;
    pop.classList.toggle('sotto', !staSopra && staSotto);
    pop.classList.toggle('libera', libera);

    const lim = Math.max(larg / 2 + 10, Math.min(p.x, p.w - larg / 2 - 10));
    pop.style.left = lim + 'px';
    pop.style.top = libera
      ? Math.max(8, Math.min(p.y + 12, p.h - alt - 8)) + 'px'
      : (staSopra ? p.y : p.giu) + 'px';
    pop.style.setProperty('--dx', (p.x - lim).toFixed(1) + 'px');
  }

  function chiudiPop(subito) {
    if (!popId && !subito) return;
    const corpo = $('.mappa-corpo', $('#mappa'));
    popId = null; popFissa = false;
    if (!corpo) return;
    const pop = $('.pop', corpo);
    if (!pop) return;
    pop.classList.remove('vista');
    if (subito) pop.hidden = true;
    else setTimeout(() => { if (!popId) pop.hidden = true; }, 220);
    evidenzia(scelto);
  }

  function adattaMappa() {
    const host = $('#mappa');
    if (dati && host && MAPPA.daRidisegnare(host)) { render(); return; }
    MAPPA.adatta(); riposizionaPop();
  }

  function evidenzia(id) {
    if (!svgMappa) return;
    $$('.pt', svgMappa).forEach(g => g.classList.toggle('scelto', !!id && g.dataset.id === id));
  }

  /* ======================================================= etichette */
  const ore = (l) => ({ alba: 'prime luci', crepuscolo: 'alba e tramonto', notte: 'dopo il buio',
    giorno: 'ore centrali', qualsiasi: 'tutto il giorno' }[l] || 'tutto il giorno');
  function etAcqua(t) {
    if (t === null) return 'stima non disponibile';
    if (t < 6) return 'molto fredda'; if (t < 11) return 'fredda'; if (t < 16) return 'fresca';
    if (t < 21) return 'temperata'; if (t < 25) return 'calda'; return 'molto calda';
  }
  function etTorb(v) {
    if (v < 0.18) return 'limpida'; if (v < 0.38) return 'appena velata';
    if (v < 0.6) return 'velata'; if (v < 0.78) return 'torbida'; return 'molto torbida';
  }
  const rosa = (d) => (d === null || d === undefined) ? '–'
    : ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSO','SO','OSO','O','ONO','NO','NNO'][Math.round(d / 22.5) % 16];
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const mesiPunta = (m) => {
    const max = Math.max.apply(null, m);
    return m.map((v, i) => [v, i]).filter(x => x[0] >= max * .85).map(x => MESI[x[1]]).join(', ') || '–';
  };

  /* ======================================================= specie */
  function montaSpecie() {
    const voci = Object.entries(SPECIE).sort((a, b) => {
      const g = GRUPPI_SPECIE.indexOf(a[1].gruppo) - GRUPPI_SPECIE.indexOf(b[1].gruppo);
      return g !== 0 ? g : a[1].nome.localeCompare(b[1].nome, 'it');
    });
    $('#specie-corpo').innerHTML = GRUPPI_SPECIE.map(gr => {
      const it = voci.filter(x => x[1].gruppo === gr);
      if (!it.length) return '';
      return `<h2 style="margin:clamp(32px,4vw,48px) 0 0">${esc(cap(gr))}</h2>
      <div class="griglia">${it.map(x => {
        const id = x[0], s = x[1];
        const q = SPOT.filter(y => (y.specie || []).indexOf(id) >= 0).length;
        return `<div class="card">
          <div class="fig">${TAVOLE.pesce(id)}</div>
          <h3>${esc(s.nome)}</h3>
          <div class="sci">${esc(s.sci)}</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">
            ${s.autoctona ? '<span class="tag acc">autoctona</span>' : '<span class="tag">alloctona</span>'}
            ${s.protetta ? '<span class="tag rosso">protetta</span>' : ''}
            ${q ? `<span class="tag">${q} spot</span>` : ''}
          </div>
          <dl>
            <dt>misura</dt><dd>${s.misuraMin ? s.misuraMin + ' cm' : '–'}</dd>
            <dt>al giorno</dt><dd>${s.limiteGiorno === 0 ? 'pesca vietata'
              : (s.limiteGiorno ? s.limiteGiorno + (s.limiteGiorno === 1 ? ' capo' : ' capi') : '–')}</dd>
            <dt>divieto</dt><dd>${esc(s.divietoTesto)}</dd>
            <dt>acqua</dt><dd>${s.tOpt[0]}–${s.tOpt[1]} °C</dd>
            <dt>ore</dt><dd>${esc(ore(s.luce))}</dd>
            <dt>punta</dt><dd>${esc(mesiPunta(s.mesi))}</dd>
            ${s.esche.length ? `<dt>esche</dt><dd>${esc(s.esche.join(', '))}</dd>` : ''}
          </dl>
          ${s.dritte ? `<p class="cons">${esc(s.dritte)}</p>` : ''}
        </div>`;
      }).join('')}</div>`;
    }).join('');
  }

  /* ======================================================= regole */
  function montaRegole() {
    const R = REGOLE;
    const grup = (t, v) => `<h2 style="margin:clamp(34px,4vw,48px) 0 0">${esc(t)}</h2>
      <div class="voci">${v.map(r => `<div class="voce"><h3>${esc(r.t)}</h3>
        <div><p>${esc(r.d)}</p>${r.warn ? `<p class="att">${esc(r.warn)}</p>` : ''}</div></div>`).join('')}</div>`;

    const tab = Object.entries(SPECIE).sort((a, b) => a[1].nome.localeCompare(b[1].nome, 'it'))
      .map(x => { const s = x[1]; return `<tr>
        <td><b>${esc(s.nome)}</b><span class="sci">${esc(s.sci)}</span></td>
        <td class="num" data-eti="Misura">${s.misuraMin ? s.misuraMin + ' cm' : '–'}</td>
        <td class="num" data-eti="Al giorno">${s.limiteGiorno === 0 ? 'vietata' : (s.limiteGiorno || '–')}</td>
        <td data-eti="Divieto">${esc(s.divietoTesto)}</td></tr>`; }).join('');

    $('#regole-corpo').innerHTML = `
      <div class="avviso" style="margin-top:22px">${seg('info')}<div>${esc(R.aggiornato)}
        Questa è una sintesi: <b>fa fede solo il testo ufficiale</b> del Regolamento regionale e del
        calendario ittico della tua provincia.</div></div>
      ${grup('Avvisi in vigore', R.avvisi)}
      ${grup('Licenze e permessi', R.licenza)}
      ${grup('Attrezzi ammessi', R.attrezzi)}
      ${grup('Limiti di prelievo', R.limiti)}
      <h2 style="margin:clamp(34px,4vw,48px) 0 0">Misure minime e divieti</h2>
      <p class="mini tenue" style="max-width:60ch;margin-top:8px">Allegato 2 al Regolamento regionale
        1/2018, come modificato dal 1/2020. Le specie alloctone non hanno misure minime né divieti regionali.</p>
      <div class="scorre" style="margin-top:16px"><table class="dati">
        <thead><tr><th>Specie</th><th>Misura minima</th><th>Capi al giorno</th><th>Divieto</th></tr></thead>
        <tbody>${tab}</tbody></table></div>
      <h2 style="margin:clamp(34px,4vw,48px) 0 0">Zone delle acque</h2>
      <div class="voci">
        ${Object.entries(CATEGORIE).map(x => `<div class="voce"><h3>${esc(x[1].nome)}</h3>
          <div><p>${esc(x[1].desc)}</p></div></div>`).join('')}
        ${R.zone.map(z => `<div class="voce"><h3>${esc(z.t)} (${esc(z.sigla)})</h3>
          <div><p>${esc(z.d)}</p></div></div>`).join('')}
      </div>
      ${grup('Sicurezza', R.sicurezza)}
      <h2 style="margin:clamp(34px,4vw,48px) 0 0">Fonti</h2>
      <div class="voci">${R.fonti.map(f => `<div class="voce">
        <h3><a href="${esc(f.u)}" target="_blank" rel="noopener noreferrer">${esc(f.t)}</a></h3><div></div>
      </div>`).join('')}</div>`;
  }

  return { init, vai, ricarica: () => carica(true), apri };
})();

document.addEventListener('DOMContentLoaded', APP.init);
