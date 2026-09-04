/* =============================================================================
   MAPPE
   -----------------------------------------------------------------------------
   Due mappe in SVG, disegnate da geometria OpenStreetMap incorporata nel sito:
   nessun server di tile, nessuna libreria, nessuna chiamata di rete.

   1. Regionale: dove sono tutti gli spot. Solo punti: il colore dice come si
      presenta la giornata, la scheda rapida compare al passaggio e il clic apre
      lo spot. Nessun numero addosso alla mappa, altrimenti diventa un
      tabellone. Si trascina, si ingrandisce con le dita o con i tasti: punti e
      nomi si contro-scalano e restano leggibili a ogni ingrandimento.
   2. Locale: il tratto d'acqua, le strade, i parcheggi e i punti in cui una
      strada arriva a toccare l'acqua. Serve a decidere dove fermarsi.
   ========================================================================== */

const MAPPA = (() => {

  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  function proietta(lat, lon) {
    return {
      x: (lon - GEO_PROJ.lon0) * GEO_PROJ.k * GEO_PROJ.scale,
      y: -(lat - GEO_PROJ.lat0) * GEO_PROJ.scale
    };
  }

  /* ========================================================================
     MAPPA REGIONALE
     ==================================================================== */
  const MARGINE = 34;

  const ICONE = {
    piu:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5.5v13M5.5 12h13"/></svg>`,
    meno:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5.5 12h13"/></svg>`,
    tutta: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4.2H4.2V9M15 4.2h4.8V9M9 19.8H4.2V15M15 19.8h4.8V15"/></svg>`
  };

  let vista = null;      /* lo stato della mappa regionale che sta in pagina */
  let stretta = false;   /* proporzione con cui è stata disegnata l'ultima volta */

  /* La regione è larga il doppio di quanto è alta. Su un telefono diventerebbe
     una striscia alta due dita: i punti si accavallano e non se ne centra uno.
     Sotto i 620 px allarghiamo il riquadro soltanto in verticale: la mappa non
     si deforma, cresce l'acqua intorno, e i punti tornano toccabili. */
  const PROPORZIONE_STRETTA = 1.2;

  /* La soglia è la stessa che in style.css fa scendere la leggenda sotto la
     mappa, ed è la stessa su cui style.css riserva l'altezza del riquadro prima
     che la mappa esista: se qui e là non coincidono, la pagina si sposta. */
  const STRETTO = '(max-width:620px)';

  function disegnaRegione(host, classifica, opz) {
    const [x0, y0, x1, y1] = GEO_BBOX;
    const larg = (x1 - x0) + MARGINE * 2;
    const nat = (y1 - y0) + MARGINE * 2;
    stretta = matchMedia(STRETTO).matches;
    const alt = stretta ? Math.max(nat, larg / PROPORZIONE_STRETTA) : nat;
    const base = [x0 - MARGINE, y0 - MARGINE - (alt - nat) / 2, larg, alt];

    const banda = (p) => p >= 62 ? 'buono' : p >= 30 ? 'medio' : 'scarso';

    /* Il mare sta sotto la terra: dove i due poligoni si sovrappongono deve
       vincere la costa vera, non il taglio del rettangolo. */
    const acqua  = (typeof GEO_MARE === 'undefined' ? [] : GEO_MARE)
      .map(d => `<path class="m-mare" d="${d}"/>`).join('');
    const terre  = GEO_CONFINE.map(d => `<path class="m-terra" d="${d}"/>`).join('');
    const laghi  = GEO_LAGHI.map(l => `<path class="m-lago" d="${l.d}"/>`).join('');
    const fiumi2 = GEO_FIUMI.filter(f => f.r === 2).map(f => `<path class="m-fiume r2" d="${f.d}"/>`).join('');
    const fiumi1 = GEO_FIUMI.filter(f => f.r === 1).map(f => `<path class="m-fiume r1" d="${f.d}"/>`).join('');

    /* poche città, solo per orientarsi */
    const citta = GEO_CITTA.slice(0, 9).map(c =>
      `<g class="cit" style="--x:${c.x}px;--y:${c.y}px">` +
      `<circle class="m-citta" cx="0" cy="0" r="3.4"/>` +
      `<text class="m-nome" x="8" y="6.5">${esc(c.n)}</text></g>`).join('');

    /* i punti stanno all'origine e si spostano con la trasformazione: così a ogni
       ingrandimento basta cambiare una variabile per tenerli della stessa misura */
    const punti = classifica.map((v, i) => {
      const p = proietta(v.spot.lat, v.spot.lon);
      return `<g class="pt ${banda(v.punteggio)}${i === 0 ? ' primo' : ''}" data-id="${esc(v.spot.id)}"
        style="--x:${p.x.toFixed(1)}px;--y:${p.y.toFixed(1)}px"
        tabindex="0" role="button" aria-label="${esc(v.spot.nome)}, indice ${v.punteggio}">
        <circle class="anello" cx="0" cy="0" r="15"/>
        <circle class="tocco" cx="0" cy="0" r="16"/>
        <circle class="dot" cx="0" cy="0" r="7"/>
      </g>`;
    }).join('');

    host.innerHTML = `
      <div class="mappa-guscio">
        <div class="mappa-corpo">
          <svg class="mappa" viewBox="${base.map(n => n.toFixed(0)).join(' ')}"
               role="img" aria-label="Mappa degli spot di pesca in Emilia-Romagna">
            <g>${acqua}${terre}</g>
            <g>${fiumi2}${fiumi1}${laghi}</g>
            <g>${citta}</g>
            <g>${punti}</g>
          </svg>
          <div class="mappa-strumenti">
            <button type="button" data-z="piu"   title="Ingrandisci"   aria-label="Ingrandisci">${ICONE.piu}</button>
            <button type="button" data-z="meno"  title="Rimpicciolisci" aria-label="Rimpicciolisci">${ICONE.meno}</button>
            <button type="button" data-z="tutta" title="Tutta la regione" aria-label="Tutta la regione">${ICONE.tutta}</button>
          </div>
          <div class="mappa-legenda">
            <span class="lg-tit">Indice di oggi</span>
            <span class="lg"><i class="buono"></i>62 – 100 <em>ottime</em></span>
            <span class="lg"><i class="medio"></i>30 – 61 <em>discrete</em></span>
            <span class="lg"><i class="scarso"></i>0 – 29 <em>scarse</em></span>
          </div>
          <div class="pop" hidden></div>
        </div>
        <div class="mappa-piede">
          <span class="chiave">${classifica.length} spot in mappa</span>
        </div>
      </div>`;

    vista = creaVista(host.querySelector('.mappa-corpo'), (opz && opz.onVista) || null);
    return host.querySelector('svg.mappa');
  }

  /* ------------------------------------------------------------------------
     Trascinamento e ingrandimento: cambiamo solo il viewBox, così le linee
     restano vettoriali. La variabile --is rimpicciolisce punti e nomi nella
     stessa misura in cui la mappa cresce.
     --------------------------------------------------------------------- */
  function creaVista(corpo, onVista) {
    const svg = corpo.querySelector('svg.mappa');
    const b = svg.getAttribute('viewBox').split(' ').map(Number);
    const st = { x: b[0], y: b[1], w: b[2], h: b[3] };
    const MIN = b[2] / 14;
    const puntatori = new Map();
    const preso = new Set();          /* puntatori catturati dal riquadro */
    let spostato = false, ultima = null;

    /* su schermo stretto la mappa rimpicciolisce: punti e nomi vanno ingranditi */
    const fattore = () => corpo.clientWidth < 560 ? 1.9 : corpo.clientWidth < 860 ? 1.35 : 1;

    function limita() {
      st.w = Math.min(b[2], Math.max(MIN, st.w));
      st.h = st.w * b[3] / b[2];
      st.x = Math.min(b[0] + b[2] - st.w, Math.max(b[0], st.x));
      st.y = Math.min(b[1] + b[3] - st.h, Math.max(b[1], st.y));
    }

    function applica() {
      limita();
      const k = b[2] / st.w;
      svg.setAttribute('viewBox', `${st.x.toFixed(1)} ${st.y.toFixed(1)} ${st.w.toFixed(1)} ${st.h.toFixed(1)}`);
      /* i punti non crescono con la mappa, ma un filo sì: a forte ingrandimento
         un pallino identico a quello di partenza sembrerebbe sperduto */
      corpo.style.setProperty('--is', (fattore() / Math.pow(k, .86)).toFixed(3));
      corpo.querySelector('[data-z="piu"]').disabled  = st.w <= MIN * 1.001;
      corpo.querySelector('[data-z="meno"]').disabled = st.w >= b[2] * .999;
      corpo.querySelector('[data-z="tutta"]').disabled = st.w >= b[2] * .999;
      if (onVista) onVista();
    }

    /* px sullo schermo → unità della mappa */
    function inMappa(cx, cy) {
      const r = svg.getBoundingClientRect();
      return { x: st.x + (cx - r.left) / r.width * st.w, y: st.y + (cy - r.top) / r.height * st.h };
    }

    function zoom(f, cx, cy) {
      const r = svg.getBoundingClientRect();
      if (cx === undefined) { cx = r.left + r.width / 2; cy = r.top + r.height / 2; }
      const p = inMappa(cx, cy);
      const fx = (cx - r.left) / r.width, fy = (cy - r.top) / r.height;
      st.w = Math.min(b[2], Math.max(MIN, st.w / f));
      st.h = st.w * b[3] / b[2];
      st.x = p.x - fx * st.w;
      st.y = p.y - fy * st.h;
      applica();
    }

    function tutta() { st.x = b[0]; st.y = b[1]; st.w = b[2]; st.h = b[3]; applica(); }

    function centraSu(lat, lon, ingrandimento) {
      const p = proietta(lat, lon);
      st.w = Math.min(b[2], Math.max(MIN, b[2] / (ingrandimento || 4)));
      st.h = st.w * b[3] / b[2];
      st.x = p.x - st.w / 2; st.y = p.y - st.h / 2;
      applica();
    }

    /* --- gesti --- */
    corpo.querySelectorAll('.mappa-strumenti button').forEach(t => {
      t.onclick = () => t.dataset.z === 'tutta' ? tutta() : zoom(t.dataset.z === 'piu' ? 1.7 : 1 / 1.7);
    });

    /* Il puntatore si prende solo quando il trascinamento comincia davvero:
       prenderlo subito sposterebbe il clic finale dal punto al riquadro, e i
       punti della mappa non si aprirebbero piu'. */
    const prendi = (e) => {
      if (preso.has(e.pointerId)) return;
      preso.add(e.pointerId);
      try { corpo.setPointerCapture(e.pointerId); } catch (_) { /* puntatore gia' finito */ }
    };

    corpo.addEventListener('pointerdown', e => {
      if (e.target.closest('.mappa-strumenti, .pop')) return;
      puntatori.set(e.pointerId, { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY });
      if (puntatori.size === 2) { corpo.style.touchAction = 'none'; ultima = distanza(); prendi(e); }
      if (puntatori.size === 1) { spostato = false; corpo.classList.add('trascina'); }
    });

    corpo.addEventListener('pointermove', e => {
      const p = puntatori.get(e.pointerId);
      if (!p) return;
      const dx = e.clientX - p.x, dy = e.clientY - p.y;
      p.x = e.clientX; p.y = e.clientY;

      if (puntatori.size >= 2) {                       /* pizzico: ingrandisce */
        const d = distanza(), c = centro();
        if (ultima && d) zoom(d / ultima, c.x, c.y);
        ultima = d; spostato = true; prendi(e);
        return;
      }
      /* Trascinamento o tocco? Si guarda quanto ci si è allontanati dal punto di
         partenza, non quanto si è mosso l'ultimo passo: altrimenti uno
         spostamento lento resterebbe un tocco. Il dito è meno preciso del
         mouse e ha diritto a un margine più largo. */
      if (Math.hypot(e.clientX - p.x0, e.clientY - p.y0) > (e.pointerType === 'mouse' ? 3 : 9)) {
        spostato = true; prendi(e);
      }
      const r = svg.getBoundingClientRect();
      st.x -= dx * st.w / r.width;
      st.y -= dy * st.h / r.height;
      applica();
    });

    const fine = (e) => {
      puntatori.delete(e.pointerId); preso.delete(e.pointerId);
      if (puntatori.size < 2) { ultima = null; corpo.style.touchAction = ''; }
      if (!puntatori.size) corpo.classList.remove('trascina');
    };
    corpo.addEventListener('pointerup', fine);
    corpo.addEventListener('pointercancel', fine);
    /* senza cattura i movimenti finiscono appena si esce: il gesto si abbandona
       qui, altrimenti resterebbe un puntatore fantasma nel conto */
    corpo.addEventListener('pointerleave', e => { if (!preso.has(e.pointerId)) fine(e); });

    /* il clic che chiude un trascinamento non deve aprire nulla */
    corpo.addEventListener('click', e => {
      if (!spostato) return;
      spostato = false; e.stopPropagation(); e.preventDefault();
    }, true);

    /* solo il pizzico del trackpad ingrandisce: la rotellina resta alla pagina */
    corpo.addEventListener('wheel', e => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      zoom(Math.exp(-e.deltaY * .012), e.clientX, e.clientY);
    }, { passive: false });

    corpo.addEventListener('dblclick', e => {
      if (e.target.closest('.mappa-strumenti, .pop')) return;
      zoom(1.9, e.clientX, e.clientY);
    });

    function distanza() {
      const v = Array.from(puntatori.values());
      return v.length < 2 ? 0 : Math.hypot(v[0].x - v[1].x, v[0].y - v[1].y);
    }
    function centro() {
      const v = Array.from(puntatori.values());
      return { x: (v[0].x + v[1].x) / 2, y: (v[0].y + v[1].y) / 2 };
    }

    applica();
    return { applica, zoom, tutta, centraSu, ingrandita: () => st.w < b[2] * .999 };
  }

  const adatta = () => { if (vista) vista.applica(); };
  /* dopo una rotazione la proporzione può non essere più quella giusta: qui non
     basta adattare, la mappa va ridisegnata */
  const daRidisegnare = (host) => !!vista && host.clientWidth > 0 &&
    matchMedia(STRETTO).matches !== stretta;
  const centraSu = (lat, lon, k) => { if (vista) vista.centraSu(lat, lon, k); };
  const tuttaLaRegione = () => { if (vista) vista.tutta(); };

  /* ========================================================================
     MAPPA LOCALE
     ==================================================================== */

  /* Pesa 2,1 MB: si carica alla prima scheda aperta, non all'avvio. */
  let promessa = null;
  function caricaLocale() {
    if (typeof GEO_LOCALE !== 'undefined') return Promise.resolve(true);
    if (promessa) return promessa;
    promessa = new Promise((ok) => {
      const s = document.createElement('script');
      s.src = 'assets/js/geo-locale.js';
      s.onload = () => ok(true);
      s.onerror = () => ok(false);
      document.head.appendChild(s);
    });
    return promessa;
  }

  const attesaLocale = () => `<div class="locale"><div class="locale-vuota">
      <div class="gira">${TAVOLE.seg('bussola')}</div>
      <p class="mini">Carico la mappa dei dintorni…</p></div></div>`;

  /* I percorsi che generiamo hanno una forma sola: M x y, poi l dx dy. Qui
     tornano a essere punti, per misurare quanto dista l'acqua dal punto. */
  function puntiDa(d) {
    const linee = [];
    let cur = null, x = 0, y = 0;
    (String(d || '').match(/[MlZ][^MlZ]*/g) || []).forEach((t) => {
      const n = (t.slice(1).match(/-?\d+(?:\.\d+)?/g) || []).map(Number);
      if (t[0] === 'M') {
        if (cur && cur.length > 1) linee.push(cur);
        if (n.length >= 2) { x = n[0]; y = n[1]; cur = [[x, y]]; }
      } else if (t[0] === 'l' && cur) {
        for (let i = 0; i + 1 < n.length; i += 2) { x += n[i]; y += n[i + 1]; cur.push([x, y]); }
      }
    });
    if (cur && cur.length > 1) linee.push(cur);
    return linee;
  }

  /* il punto d'acqua più vicino allo spot, e quanto dista */
  function acquaVicina(d) {
    let best = null, bd = Infinity;
    puntiDa(d).forEach((linea) => {
      for (let i = 0; i < linea.length - 1; i++) {
        const [ax, ay] = linea[i], [bx, by] = linea[i + 1];
        const dx = bx - ax, dy = by - ay, n2 = dx * dx + dy * dy;
        const t = n2 === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / n2));
        const px = ax + t * dx, py = ay + t * dy, q = Math.hypot(px, py);
        if (q < bd) { bd = q; best = [px, py]; }
      }
    });
    return { pt: best, d: bd };
  }

  /* Quanto lontano può stare l'acqua prima che valga la pena spostare il
     riquadro. Sotto questa distanza il punto e il fiume si vedono già insieme. */
  const SCARTO = 380;

  /* Il riquadro non è sempre lo stesso quadrato. Se l'acqua su cui si pesca
     cade lontano dal punto (una coordinata approssimata, un fiume largo, una
     foce), il riquadro scivola verso l'acqua quel tanto che basta a tenere
     dentro tutti e due, e si stringe per non uscire dai dati incisi. Così la
     carta mostra sempre lo spot *e* la sua acqua, non uno dei due. */
  /* GEO_RAGGIO arriva con geo-locale.js, che si carica alla prima scheda
     aperta: prima di allora non esiste, e leggerlo direttamente fermava tutta
     la scheda a metà. Finché non c'è, vale la misura con cui è stato inciso. */
  const raggioLocale = () => (typeof GEO_RAGGIO !== 'undefined') ? GEO_RAGGIO : 1800;

  function inquadra(g) {
    const R = raggioLocale();
    /* Il riquadro intero contiene già tutta la geometria incisa: si sposta solo
       quando *nessuna* acqua è vicina al punto, e allora va verso la più
       vicina, qualunque sia. Inseguire l'acqua della scheda anche quando ce
       n'è dell'altra sotto i piedi sposterebbe la carta per niente. */
    const vicina = acquaVicina([g.wm, g.ma, g.ws, g.wg, g.wp, g.wa].filter(Boolean).join(' '));
    if (!vicina.pt || vicina.d <= SCARTO) return { cx: 0, cy: 0, mezzo: R };
    const cx = Math.round(vicina.pt[0] / 2), cy = Math.round(vicina.pt[1] / 2);
    return { cx, cy, mezzo: Math.round(R - Math.max(Math.abs(cx), Math.abs(cy))) };
  }

  /* il lato del riquadro in metri: alla scheda serve per dire quanto è largo */
  const latoLocale = (id) => {
    const g = (typeof GEO_LOCALE !== 'undefined') ? GEO_LOCALE[id] : null;
    return g ? inquadra(g).mezzo * 2 : raggioLocale() * 2;
  };

  function disegnaLocale(spot) {
    const g = (typeof GEO_LOCALE !== 'undefined') ? GEO_LOCALE[spot.id] : null;
    if (!g) {
      return `<div class="locale"><div class="locale-vuota">
        <p class="mini">Mappa dei dintorni non disponibile.</p>
        <p class="micro tenue num">${spot.lat.toFixed(4)}, ${spot.lon.toFixed(4)}</p></div></div>`;
    }
    const { cx, cy, mezzo } = inquadra(g);
    /* la legenda nomina l'acqua della scheda solo se la carta l'ha davvero
       riconosciuta: in riva al mare è la battigia, altrove il tratto inciso */
    const mia = !!(g.wm || g.ma || g.mb || (g.ws && spot.tipo === 'mare'));
    const lato = mezzo * 2;
    const u = (px) => Math.round(px * lato / 420);      // px a schermo → unità della mappa

    /* Il punto che aprono i tasti, disegnato qui: la carta e il tasto devono
       indicare lo stesso posto, o si torna al difetto che stiamo togliendo.
       Sta in gradi, la carta in metri: si converte con la stessa proiezione
       che ha inciso la carta, centrata sulle coordinate della scheda. */
    const a = (typeof ACCESSI !== 'undefined') ? ACCESSI[spot.id] : null;
    const qui = a ? [
      (a[1] - spot.lon) * 111320 * Math.cos(spot.lat * Math.PI / 180),
      -(a[0] - spot.lat) * 110540,
    ] : null;

    /* gli altri posti in cui una strada arriva alla riva: utili, ma non sono
       quello che si apre. Chi è già disegnato come punto di accesso non si
       ripete a due passi da sé. */
    const acc = (g.ac || [])
      .filter(([x, y]) => !qui || Math.hypot(x - qui[0], y - qui[1]) > u(22))
      .map(([x, y], i) => `
      <g class="l-acc"><circle cx="${x}" cy="${y}" r="${u(7.5)}"/>
      <text x="${x}" y="${y + u(4.4)}" text-anchor="middle" font-size="${u(8)}">${i + 1}</text></g>`).join('');

    const puntoAcc = qui ? `
      <g class="l-acc-qui"><circle cx="${qui[0]}" cy="${qui[1]}" r="${u(10)}"/></g>` : '';

    const pk = (g.pk || []).map(([x, y]) => `
      <g class="l-pk"><rect x="${x - u(7)}" y="${y - u(7)}" width="${u(14)}" height="${u(14)}"/>
      <text x="${x}" y="${y + u(5)}" text-anchor="middle" font-size="${u(10)}">P</text></g>`).join('');

    const lb = (g.lb || []).slice(0, 5).map(([x, y, n, r]) =>
      `<text class="l-eti" x="${x}" y="${y}" text-anchor="middle"
        font-size="${u(r > 1 ? 8 : 9.4)}">${esc(n)}</text>`).join('');

    const sm = lato > 2200 ? 500 : 250;
    const sx = cx - mezzo + u(22), sy = cy + mezzo - u(22);

    return `<div class="locale">
      <svg viewBox="${cx - mezzo} ${cy - mezzo} ${lato} ${lato}" role="img"
           aria-label="Dintorni di ${esc(spot.nome)}${spot.acqua ? ', con ' + esc(spot.acqua) : ''}, riquadro di ${(lato / 1000).toFixed(1)} km">
        ${g.ws ? `<path class="l-mare" d="${g.ws}"/>` : ''}
        ${g.wa ? `<path class="l-area" d="${g.wa}"/>` : ''}
        ${g.ma ? `<path class="l-mia-area" d="${g.ma}"/>` : ''}
        ${g.wb ? `<path class="l-sponda" d="${g.wb}"/>` : ''}
        ${g.mb ? `<path class="l-mia-sponda" d="${g.mb}"/>` : ''}
        ${g.r3 ? `<path class="l-r3" d="${g.r3}"/>` : ''}
        ${g.r2 ? `<path class="l-r2" d="${g.r2}"/>` : ''}
        ${g.r1 ? `<path class="l-r1" d="${g.r1}"/>` : ''}
        ${g.wp ? `<path class="l-acqua-p" d="${g.wp}"/>` : ''}
        ${g.wg ? `<path class="l-acqua-g" d="${g.wg}"/>` : ''}
        ${g.wm ? `<path class="l-mia" d="${g.wm}"/>` : ''}
        ${lb}${pk}${acc}
        <g class="l-qui${qui ? ' vuoto' : ''}"><circle cx="0" cy="0" r="${u(qui ? 5.5 : 8)}"/></g>
        ${puntoAcc}
        <g>
          <path d="M${sx} ${sy}h${sm}M${sx} ${sy - u(3.5)}v${u(7)}M${sx + sm} ${sy - u(3.5)}v${u(7)}"
            stroke="var(--ink-4)" stroke-width="${u(1.1)}" fill="none"/>
          <text x="${sx + sm / 2}" y="${sy - u(6)}" text-anchor="middle" font-size="${u(7.5)}"
            font-family="Archivo,sans-serif" font-weight="600" fill="var(--ink-3)">${sm} m</text>
        </g>
      </svg>
      <div class="locale-piede">
        ${qui ? `<span class="chiave"><i style="background:var(--acc)"></i> dove fermarsi</span>` : ''}
        <span class="chiave"><i style="background:var(--ink)"></i> ${qui ? 'la coordinata della scheda' : 'lo spot'}</span>
        ${mia && spot.acqua ? `<span class="chiave"><i style="background:var(--acc-2)"></i> ${esc(spot.acqua)}</span>` : ''}
        ${acc ? `<span class="chiave"><i style="background:transparent;box-shadow:inset 0 0 0 2px var(--acc)"></i> altri accessi</span>` : ''}
        ${(g.pk || []).length ? `<span class="chiave"><i style="background:var(--ink-3);border-radius:0"></i> parcheggio</span>` : ''}
      </div>
    </div>`;
  }

  /* Quanti segni numerati la carta disegna davvero. Non g.ac.length: da quello
     disegnaLocale toglie i punti che cadono addosso al punto di accesso, e la
     didascalia annunciava segni che non c'erano: su quattro spot, tutti. */
  const contaAccessi = (id) => {
    const g = (typeof GEO_LOCALE !== 'undefined') ? GEO_LOCALE[id] : null;
    if (!g || !g.ac) return 0;
    const s = (typeof SPOT !== 'undefined') ? SPOT.find(x => x.id === id) : null;
    const a = (typeof ACCESSI !== 'undefined') ? ACCESSI[id] : null;
    if (!s || !a) return g.ac.length;
    const qx = (a[1] - s.lon) * 111320 * Math.cos(s.lat * Math.PI / 180);
    const qy = -(a[0] - s.lat) * 110540;
    const soglia = inquadra(g).mezzo * 2 * 22 / 420;
    return g.ac.filter(([x, y]) => Math.hypot(x - qx, y - qy) > soglia).length;
  };

  return { disegnaRegione, disegnaLocale, caricaLocale, attesaLocale, proietta, contaAccessi,
           latoLocale, adatta, daRidisegnare, centraSu, tuttaLaRegione };
})();
