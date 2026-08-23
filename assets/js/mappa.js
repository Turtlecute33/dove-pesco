/* =============================================================================
   MAPPE
   -----------------------------------------------------------------------------
   Due mappe in SVG, disegnate da geometria OpenStreetMap incorporata nel sito:
   nessun server di tile, nessuna libreria, nessuna chiamata di rete.

   1. Regionale — dove sono tutti gli spot. Solo punti: il colore dice come si
      presenta la giornata, il nome compare al passaggio. Nessun numero addosso
      alla mappa, altrimenti diventa un tabellone. Si trascina, si ingrandisce
      con le dita o con i tasti: punti e nomi si contro-scalano e restano
      leggibili a ogni ingrandimento.
   2. Locale — il tratto d'acqua, le strade, i parcheggi e i punti in cui una
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

  let vista = null;   /* lo stato della mappa regionale che sta in pagina */

  function disegnaRegione(host, classifica, opz) {
    const [x0, y0, x1, y1] = GEO_BBOX;
    const base = [x0 - MARGINE, y0 - MARGINE, (x1 - x0) + MARGINE * 2, (y1 - y0) + MARGINE * 2];

    const banda = (p) => p >= 62 ? 'buono' : p >= 30 ? 'medio' : 'scarso';

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
            <g>${terre}</g>
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
          <div class="etichetta" hidden></div>
          <div class="pop" hidden></div>
        </div>
        <div class="mappa-piede">
          <span class="chiave">${classifica.length} spot in mappa</span>
          <span class="chiave" style="margin-left:auto">Trascina per spostarti · pizzica o usa + e − per ingrandire</span>
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

    corpo.addEventListener('pointerdown', e => {
      if (e.target.closest('.mappa-strumenti, .pop')) return;
      puntatori.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (puntatori.size === 2) { corpo.style.touchAction = 'none'; ultima = distanza(); }
      if (puntatori.size === 1) { spostato = false; corpo.classList.add('trascina'); }
      corpo.setPointerCapture(e.pointerId);
    });

    corpo.addEventListener('pointermove', e => {
      const p = puntatori.get(e.pointerId);
      if (!p) return;
      const dx = e.clientX - p.x, dy = e.clientY - p.y;
      p.x = e.clientX; p.y = e.clientY;

      if (puntatori.size >= 2) {                       /* pizzico: ingrandisce */
        const d = distanza(), c = centro();
        if (ultima && d) zoom(d / ultima, c.x, c.y);
        ultima = d; spostato = true;
        return;
      }
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) spostato = true;
      const r = svg.getBoundingClientRect();
      st.x -= dx * st.w / r.width;
      st.y -= dy * st.h / r.height;
      applica();
    });

    const fine = (e) => {
      puntatori.delete(e.pointerId);
      if (puntatori.size < 2) { ultima = null; corpo.style.touchAction = ''; }
      if (!puntatori.size) corpo.classList.remove('trascina');
    };
    corpo.addEventListener('pointerup', fine);
    corpo.addEventListener('pointercancel', fine);

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
  const centraSu = (lat, lon, k) => { if (vista) vista.centraSu(lat, lon, k); };
  const tuttaLaRegione = () => { if (vista) vista.tutta(); };

  /* ========================================================================
     MAPPA LOCALE
     ==================================================================== */

  /* Pesa 1,6 MB: si carica alla prima scheda aperta, non all'avvio. */
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

  function disegnaLocale(spot) {
    const g = (typeof GEO_LOCALE !== 'undefined') ? GEO_LOCALE[spot.id] : null;
    if (!g) {
      return `<div class="locale"><div class="locale-vuota">
        <p class="mini">Mappa dei dintorni non disponibile.</p>
        <p class="micro tenue num">${spot.lat.toFixed(4)}, ${spot.lon.toFixed(4)}</p></div></div>`;
    }
    const R = GEO_RAGGIO;
    const u = (px) => Math.round(px * (R * 2) / 420);   // px a schermo → unità della mappa

    const acc = (g.ac || []).map(([x, y], i) => `
      <g class="l-acc"><circle cx="${x}" cy="${y}" r="${u(9)}"/>
      <text x="${x}" y="${y + u(5.2)}" text-anchor="middle" font-size="${u(9.5)}">${i + 1}</text></g>`).join('');

    const pk = (g.pk || []).map(([x, y]) => `
      <g class="l-pk"><rect x="${x - u(7)}" y="${y - u(7)}" width="${u(14)}" height="${u(14)}"/>
      <text x="${x}" y="${y + u(5)}" text-anchor="middle" font-size="${u(10)}">P</text></g>`).join('');

    const lb = (g.lb || []).slice(0, 5).map(([x, y, n, r]) =>
      `<text class="l-eti" x="${x}" y="${y}" text-anchor="middle"
        font-size="${u(r > 1 ? 8 : 9.4)}">${esc(n)}</text>`).join('');

    const sm = 500, sx = -R + u(22), sy = R - u(22);

    return `<div class="locale">
      <svg viewBox="${-R} ${-R} ${R * 2} ${R * 2}" role="img"
           aria-label="Dintorni di ${esc(spot.nome)}, riquadro di ${(R * 2 / 1000).toFixed(1)} km">
        ${g.wa ? `<path class="l-area" d="${g.wa}"/>` : ''}
        ${g.r3 ? `<path class="l-r3" d="${g.r3}"/>` : ''}
        ${g.r2 ? `<path class="l-r2" d="${g.r2}"/>` : ''}
        ${g.r1 ? `<path class="l-r1" d="${g.r1}"/>` : ''}
        ${g.wp ? `<path class="l-acqua-p" d="${g.wp}"/>` : ''}
        ${g.wg ? `<path class="l-acqua-g" d="${g.wg}"/>` : ''}
        ${lb}${pk}${acc}
        <g class="l-qui"><circle cx="0" cy="0" r="${u(8)}"/></g>
        <g>
          <path d="M${sx} ${sy}h${sm}M${sx} ${sy - u(3.5)}v${u(7)}M${sx + sm} ${sy - u(3.5)}v${u(7)}"
            stroke="var(--ink-4)" stroke-width="${u(1.1)}" fill="none"/>
          <text x="${sx + sm / 2}" y="${sy - u(6)}" text-anchor="middle" font-size="${u(7.5)}"
            font-family="Archivo,sans-serif" font-weight="600" fill="var(--ink-3)">${sm} m</text>
        </g>
      </svg>
      <div class="locale-piede">
        <span class="chiave"><i style="background:var(--ink)"></i> lo spot</span>
        ${(g.ac || []).length ? `<span class="chiave"><i style="background:var(--acc)"></i> la strada tocca l'acqua</span>` : ''}
        ${(g.pk || []).length ? `<span class="chiave"><i style="background:var(--ink-3);border-radius:0"></i> parcheggio</span>` : ''}
      </div>
    </div>`;
  }

  const contaAccessi = (id) => {
    const g = (typeof GEO_LOCALE !== 'undefined') ? GEO_LOCALE[id] : null;
    return g && g.ac ? g.ac.length : 0;
  };

  return { disegnaRegione, disegnaLocale, caricaLocale, attesaLocale, proietta, contaAccessi,
           adatta, centraSu, tuttaLaRegione };
})();
