/* =============================================================================
   TAVOLE E SEGNI
   -----------------------------------------------------------------------------
   Disegni a linea in stile incisione: profilo, opercolo, linea laterale, pinne
   con i raggi. Nessuna immagine esterna e nessuna richiesta di rete: sono
   percorsi SVG costruiti qui, pochi byte l'uno.
   Tutti i pesci guardano a sinistra, su griglia 200 × 88.
   ========================================================================== */

const TAVOLE = (() => {

  const f1 = (v) => (Math.round(v * 10) / 10).toString();

  /* ---------------------------------------------------------- costruttori */

  /* Pinna: base da A a B (davanti → dietro), apice spostato di h lungo la
     normale e inclinato all'indietro di "falce": le pinne dei pesci sono
     sempre rastremate verso la coda, mai bolle simmetriche.
     Il bordo e' una quadratica; i raggi cadono esattamente sul bordo. */
  function pinna(ax, ay, bx, by, h, n = 5, falce = .42, sottile = false) {
    const dx = bx - ax, dy = by - ay, L = Math.hypot(dx, dy) || 1;
    const ux = dx / L, uy = dy / L;
    const nx = -dy / L, ny = dx / L;
    const mx = (ax + bx) / 2, my = (ay + by) / 2;
    /* punto di controllo: alzato di 2h perche' la quadratica passa a meta' */
    const cx = mx + nx * h * 2 + ux * L * falce, cy = my + ny * h * 2 + uy * L * falce;
    let d = `<path d="M${f1(ax)} ${f1(ay)}Q${f1(cx)} ${f1(cy)} ${f1(bx)} ${f1(by)}"/>`;
    for (let i = 1; i < n; i++) {
      const t = i / n, u = 1 - t;
      const ex = u * u * ax + 2 * u * t * cx + t * t * bx;
      const ey = u * u * ay + 2 * u * t * cy + t * t * by;
      const px = ax + dx * t, py = ay + dy * t;
      d += `<path d="M${f1(px)} ${f1(py)}L${f1(ex)} ${f1(ey)}" stroke-width="${sottile ? .5 : .65}" opacity=".5"/>`;
    }
    return d;
  }

  /* Coda a forcella. Parte esattamente dal peduncolo, cioe' dagli stessi due
     punti in cui finiscono il dorso e il ventre: cosi' non resta lo stacco. */
  function coda(x, y, l = 30, ap = 19, inc = 9, pd = 4) {
    return `<path d="M${f1(x)} ${f1(y - pd)}L${f1(x + l)} ${f1(y - ap)}Q${f1(x + l - inc)} ${f1(y)} ${f1(x + l)} ${f1(y + ap)}L${f1(x)} ${f1(y + pd)}"/>` +
      `<path d="M${f1(x + 2)} ${f1(y - pd + .5)}L${f1(x + l - 4)} ${f1(y - ap + 4)}M${f1(x + 2)} ${f1(y + pd - .5)}L${f1(x + l - 4)} ${f1(y + ap - 4)}" stroke-width=".55" opacity=".4"/>`;
  }

  /* Bocca: breve tratto che rientra dalla punta del muso */
  const bocca = (x, y, l = 9, giu = 1.6) =>
    `<path d="M${f1(x)} ${f1(y)}q${f1(l * .55)} ${f1(giu)} ${f1(l)} ${f1(giu * .7)}" stroke-width="1"/>`;

  const occhio = (x, y, r = 3.4) =>
    `<circle cx="${x}" cy="${y}" r="${r}"/><circle cx="${x}" cy="${y}" r="${(r * .4).toFixed(1)}" fill="currentColor" stroke="none"/>`;

  const opercolo = (x, y, h) =>
    `<path d="M${x} ${y}q-5 ${h / 2} 0 ${h}" stroke-width="1"/>`;

  const laterale = (d, tratteggio = true) =>
    `<path d="${d}" stroke-width=".7" ${tratteggio ? 'stroke-dasharray="1.6 4"' : ''} opacity=".65"/>`;

  const macchie = (l, r = 1.5) =>
    l.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="currentColor" stroke="none" opacity=".45"/>`).join('');

  /* Accenno di scagliatura: brevi archi nel terzo superiore del fianco.
     Se corrono per tutta l'altezza sembrano costole, non scaglie. */
  const scaglie = (x0, x1, yTop, yBot, passo = 15) => {
    const h = (yBot - yTop) * .34;
    let s = '';
    for (let x = x0; x <= x1; x += passo) {
      const k = (x - x0) / (x1 - x0);
      const giu = yTop + (yBot - yTop) * (.22 + .1 * Math.sin(k * Math.PI));
      s += `<path d="M${f1(x)} ${f1(giu)}q2.6 ${f1(h / 2)} 0 ${f1(h)}" stroke-width=".4" opacity=".2"/>`;
    }
    return s;
  };

  const p = (b) =>
    `<svg viewBox="0 0 200 88" fill="none" stroke="currentColor" stroke-width="1.45"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${b}</svg>`;

  const F = {};

  /* ------------------------------------------------------------ SALMONIDI */
  F.trota = p(`
    <path d="M16 45C32 28.5 64 19.5 98 21.5C122 23 142 30.5 156 41"/>
    <path d="M16 45C30 58.5 62 68.5 98 66.5C122 65 142 57.5 156 49"/>
    ${coda(156, 45, 31, 19, 9, 4)}
    ${bocca(16, 45, 10, 2)}
    ${opercolo(40, 30, 31)}
    ${pinna(82, 22.6, 108, 22.4, -12, 6, .3)}
    <path d="M128 27.8q6-5.4 10-1.4" stroke-width="1"/>
    ${pinna(68, 57, 88, 62.6, 11, 4, .5)}
    ${pinna(96, 65, 116, 63.4, 10, 4, .5)}
    ${pinna(124, 61.6, 144, 55.4, 10, 4, .5)}
    ${laterale('M27 44.6c16 3.4 46 5 82 3.2 19-1 33-2.5 45-4.4')}
    ${occhio(28.5, 41)}
    ${macchie([[56, 33], [72, 28], [90, 31], [106, 27], [68, 43], [86, 45], [104, 41], [120, 36], [122, 47], [54, 48], [112, 51]])}
  `);

  F.temolo = p(`
    <path d="M16 46C32 32 62 24 96 25C120 26 139 32.5 155 42"/>
    <path d="M16 46C30 58 60 66.5 96 65.5C119 64.7 138 59 155 50"/>
    ${coda(155, 46, 30, 18, 9, 4)}
    ${bocca(16, 46, 9, 1.8)}
    ${opercolo(38, 33, 28)}
    ${pinna(62, 25.4, 112, 23, -16, 9, .2)}
    <path d="M127 31q6-5.2 10-1.2" stroke-width="1"/>
    ${pinna(66, 58.4, 86, 63.4, 11, 4, .5)}
    ${pinna(96, 65.2, 116, 62.8, 10, 4, .5)}
    ${pinna(124, 60.4, 143, 55, 9, 4, .5)}
    ${laterale('M27 46c15 3.2 45 4.8 80 3 18-.9 31-2.3 43-4.1')}
    ${occhio(28.5, 42.6)}
  `);

  /* ------------------------------------------------------------ CIPRINIDI */
  F.cavedano = p(`
    <path d="M14 46C30 26.5 62 17.5 98 19.5C124 21 145 28.5 158 40.5"/>
    <path d="M14 46C28 61.5 60 71.5 98 69.5C124 68 145 61.5 158 49.5"/>
    ${coda(158, 45, 31, 20, 10, 4.5)}
    ${bocca(14, 46, 11, 2.4)}
    ${opercolo(40, 30, 33)}
    ${pinna(84, 20.4, 110, 21.4, -12, 6, .28)}
    ${pinna(66, 59, 88, 65.6, 12, 4, .5)}
    ${pinna(98, 68, 118, 65.6, 11, 4, .5)}
    ${pinna(124, 63.4, 146, 55.6, 11, 4, .5)}
    ${laterale('M27 45.4c16 4 48 6 86 4 19-1 33-2.5 44-4.4')}
    ${occhio(28.5, 41, 3.8)}
    ${scaglie(48, 134, 30, 60, 14)}
  `);

  F.barbo = p(`
    <path d="M12 52C28 34.5 60 23.5 96 24.5C122 25.3 142 32 155 43.5"/>
    <path d="M12 52C26 64.5 58 72.5 94 71.5C120 70.7 142 63.5 155 52.5"/>
    ${coda(155, 48, 30, 19, 9, 4.5)}
    <path d="M12 52c6-2.2 12-3 17-2.2M12 52c5 3 11 5 16 5.2" stroke-width=".9"/>
    <path d="M18.5 50.6q-4.6 5.6-11 7.6M20.5 55q-3 6.4-10.4 10" stroke-width=".8" opacity=".76"/>
    ${opercolo(38, 37, 31)}
    ${pinna(76, 25.6, 100, 27.4, -11, 6, .3)}
    ${pinna(62, 62, 84, 68.6, 12, 4, .5)}
    ${pinna(94, 70.4, 114, 68.4, 11, 4, .5)}
    ${pinna(122, 66, 143, 58.4, 10, 4, .5)}
    ${laterale('M25 51.4c16 4 48 6 86 4 18-.9 31-2.3 42-4.2')}
    ${occhio(30, 44, 3.2)}
    ${scaglie(50, 132, 35, 65, 15)}
  `);

  F.alborella = p(`
    <path d="M18 45C34 32.5 64 25.5 98 26.5C120 27.3 138 33 152 42"/>
    <path d="M18 45C31 56 62 63.5 98 62.5C120 61.7 138 56 152 48"/>
    ${coda(152, 45, 28, 15, 8, 3)}
    ${bocca(18, 45, 8, 1.4)}
    ${opercolo(40, 34, 23)}
    ${pinna(88, 26.6, 106, 27.8, -10, 5, .3)}
    ${pinna(72, 55, 90, 59.4, 9, 3, .5, true)}
    ${pinna(100, 60.8, 118, 58, 8, 3, .5, true)}
    ${laterale('M27 44.6c15 3 46 4.6 82 2.8 16-.8 27-1.9 37-3.2', false)}
    ${occhio(29, 41, 3)}
  `);

  F.carpa = p(`
    <path d="M14 52C26 28.5 58 12.5 96 13.5C126 14.3 147 26 157 45"/>
    <path d="M14 52C24 70.5 56 82.5 96 81.5C125 80.7 147 68.5 157 55"/>
    ${coda(157, 50, 32, 22, 10, 5)}
    <path d="M14 52c6-3 12-4 17-3.2M14 52c5 4 11 6 16 6.4" stroke-width=".9"/>
    <path d="M20 50q-5 5.6-13 7.6M22 55q-3.4 6.6-12 10.4" stroke-width=".8" opacity=".76"/>
    ${opercolo(40, 33, 38)}
    ${pinna(66, 16.4, 126, 23.4, -12, 9, .14)}
    ${pinna(66, 70, 90, 78, 13, 4, .5)}
    ${pinna(100, 79.6, 122, 75.6, 12, 4, .5)}
    ${pinna(128, 72, 150, 61.6, 12, 4, .5)}
    ${occhio(30, 44, 3.8)}
    ${scaglie(48, 142, 28, 72, 14)}
  `);

  F.cheppia = p(`
    <path d="M16 44C30 24.5 62 14.5 98 16.5C124 18 146 27.5 158 41"/>
    <path d="M16 44C28 61.5 60 72.5 98 70.5C124 69 146 60 158 49"/>
    ${coda(158, 45, 29, 19, 9, 4)}
    ${bocca(16, 44, 9, 2)}
    ${opercolo(40, 28, 33)}
    ${pinna(80, 17.6, 104, 19.4, -11, 5, .3)}
    ${pinna(64, 61, 84, 66.6, 11, 4, .5)}
    ${pinna(96, 69.6, 116, 66.8, 11, 4, .5)}
    ${pinna(122, 64.6, 142, 57, 10, 4, .5)}
    ${occhio(28, 39, 4)}
    ${macchie([[48, 30], [61, 27]], 1.9)}
  `);

  /* ------------------------------------------------------------ PREDATORI */
  F.luccio = p(`
    <path d="M6 48C22 39.5 46 32 78 30C110 28 138 33 157 43.5"/>
    <path d="M6 48C20 58 46 66.5 78 67.5C110 68.5 138 60 157 52.5"/>
    ${coda(157, 48, 29, 18, 9, 4.5)}
    <path d="M6 48c8-4 17-6 26-7M6 48c7 5 16 8 25 9" stroke-width=".9"/>
    ${opercolo(40, 39, 21)}
    ${pinna(110, 32.8, 140, 37, -13, 6, .24)}
    ${pinna(110, 55.6, 140, 51.8, 12, 6, .24)}
    ${pinna(58, 54, 78, 60, 11, 4, .5)}
    ${pinna(84, 57.6, 102, 61, 10, 3, .5)}
    ${laterale('M21 47.4c22 3.6 60 4.6 100 1.8 14-1 24-2.2 33-3.4')}
    ${occhio(32, 43, 3.2)}
    ${macchie([[56, 38], [72, 35], [88, 37], [104, 34], [70, 50], [86, 52], [102, 48], [118, 44], [54, 52], [120, 55], [132, 42], [134, 50]], 1.7)}
  `);

  F.persico = p(`
    <path d="M18 50C30 28.5 58 16.5 92 17.5C120 18.4 141 31 150 45.5"/>
    <path d="M18 50C29 67.5 58 78.5 94 77.5C120 76.6 142 66.5 150 54.5"/>
    ${coda(150, 50, 31, 20, 9, 4.5)}
    ${bocca(18, 50, 10, 2.4)}
    ${opercolo(42, 32, 36)}
    ${pinna(58, 19.4, 92, 21.2, -13, 8, .18)}
    ${pinna(100, 22.4, 130, 30.4, -8, 5, .3)}
    ${pinna(66, 67, 90, 74.6, 12, 4, .5)}
    ${pinna(98, 76, 120, 71, 12, 4, .5)}
    ${pinna(124, 68, 144, 58.4, 11, 4, .5)}
    ${occhio(31, 41, 4)}
    <path d="M54 29q3.4 13 .8 38M70 25q3.6 15 .8 43M88 24q3.6 16 .8 45M105 28q3.2 14 .6 41M120 35q2.6 11 .6 31"
      stroke-width="1.7" opacity=".13"/>
  `);

  F.siluro = p(`
    <path d="M10 44C24 31 48 25 78 26C112 27 144 33 166 43"/>
    <path d="M10 44C20 58 44 66 80 68C114 70 146 62 166 53"/>
    ${coda(166, 48, 20, 14, 6, 5)}
    <path d="M14.5 40Q26 18 44 9M16.5 42Q26 24 40 13.6" stroke-width=".9" opacity=".85"/>
    <path d="M12 48q7 10 18 15.6M14 51q6 11 16 18" stroke-width=".8" opacity=".7"/>
    ${bocca(10, 44, 13, 2.6)}
    ${opercolo(44, 34, 26)}
    ${pinna(74, 28.2, 92, 29.6, -7, 4, .3, true)}
    ${pinna(98, 66, 156, 59.6, 10, 8, .12)}
    ${pinna(52, 53, 74, 60, 11, 4, .5)}
    ${occhio(30, 38, 2.4)}
    ${laterale('M25 42.4c26 3.6 66 5.6 106 2.8 16-1.1 28-2.6 39-4.3')}
  `);

  F.anguilla = p(`
    <path d="M4 65C14 62 30 58 48 50C66 42 84 42 102 34C120 26 134 14 154 12C168 10.8 180 15 186 22"/>
    <path d="M4 65C14 68 32 66 50 58C68 50 86 50 104 42C122 34 136 22 156 20C168 19 178 22 183 30"/>
    <path d="M186 22q6.4 5 -3 8"/>
    <path d="M180 27q-5 1.6-9 .6" stroke-width=".9"/>
    <path d="M30 58.6q-3.4-4.6-1-9M52 50.4q-3.4-4.6-1-9M76 44.2q-3.4-4.6-1-9M100 36q-3.4-4.6-1-9M124 26.6q-3-4.6-.6-9M148 15.6q-2.6-4.6 0-8.6"
      stroke-width=".6" opacity=".42"/>
    <path d="M32 66.6q4 4.6 1.6 9.6M56 58q4 4.6 1.6 9.6M80 50q4 4.6 1.6 9.6M104 42q4 4.6 1.6 9.6M128 32q3.6 4.6 1.2 9.6"
      stroke-width=".6" opacity=".42"/>
    ${occhio(176, 24, 2.4)}
    ${opercolo(166, 20, 13)}
  `);

  /* ----------------------------------------------------------------- MARE */
  F.spigola = p(`
    <path d="M14 46C30 28.5 60 19.5 96 20.5C122 21.3 143 29 155 42"/>
    <path d="M14 46C27 61.5 58 70.5 96 69.5C122 68.7 143 60.5 155 50"/>
    ${coda(155, 46, 31, 19, 9, 4)}
    ${bocca(14, 46, 11, 2.6)}
    ${opercolo(38, 31, 33)}
    ${pinna(56, 21, 88, 23, -12, 7, .18)}
    ${pinna(96, 24.2, 126, 32, -8, 5, .3)}
    ${pinna(64, 61, 86, 67.6, 12, 4, .5)}
    ${pinna(98, 69, 118, 66.4, 11, 4, .5)}
    ${pinna(124, 62.8, 144, 55, 10, 4, .5)}
    ${occhio(29, 40, 3.6)}
    ${laterale('M27 44.4c16 4 48 6 86 4 18-.9 31-2.3 42-4.2')}
  `);

  F.orata = p(`
    <path d="M18 50C26 24.5 54 9 92 10C124 11 148 26 155 45"/>
    <path d="M18 50C26 68 56 79 94 78C124 77 148 65 155 55"/>
    ${coda(155, 50, 31, 21, 10, 5)}
    ${bocca(18, 50, 10, 2.6)}
    ${opercolo(44, 29, 38)}
    ${pinna(62, 13.4, 128, 23.6, -11, 9, .14)}
    ${pinna(66, 68, 92, 75.4, 10, 4, .5)}
    ${pinna(98, 76.6, 122, 72, 10, 4, .5)}
    ${pinna(126, 69, 146, 60.4, 9, 4, .5)}
    ${occhio(32, 39, 4.2)}
    <path d="M31.6 28.6q3.6 2.6 7 5" stroke-width="2.4" opacity=".6"/>
    ${scaglie(50, 140, 22, 74, 15)}
  `);

  F.cefalo = p(`
    <path d="M16 46C32 33.5 62 25.5 98 26.5C122 27.3 141 33 154 42.5"/>
    <path d="M16 46C30 58 46 66 82 67C110 67.8 141 57 154 49.5"/>
    ${coda(154, 46, 29, 16, 8, 3.5)}
    <path d="M18 40q7-3.4 18-4" stroke-width="1.1"/>
    ${opercolo(42, 34, 26)}
    ${pinna(66, 26.4, 88, 28, -9, 5, .3)}
    ${pinna(104, 29, 126, 34.4, -6, 4, .3, true)}
    ${pinna(72, 58, 92, 62.8, 10, 3, .5)}
    ${pinna(102, 63.4, 120, 60, 9, 3, .5)}
    ${occhio(31, 40, 3.4)}
    ${laterale('M29 45.4c16 3 48 4.8 84 3 16-.8 27-1.9 37-3.2')}
  `);

  F.pelagico = p(`
    <path d="M16 44C32 29.5 62 21.5 96 22.5C120 23.3 139 30 153 41.5"/>
    <path d="M16 44C29 57.5 60 66.5 96 65.5C120 64.7 140 57 153 48.5"/>
    ${coda(153, 45, 32, 18, 12, 3.5)}
    <path d="M140 34.4l8 1.6M144 40l8 .8M140 53.6l8-1.6M144 48l8-.8" stroke-width=".85" opacity=".65"/>
    ${bocca(16, 44, 9, 1.6)}
    ${opercolo(40, 30, 29)}
    ${pinna(60, 23.2, 86, 24.8, -10, 5, .28)}
    ${pinna(96, 25.8, 118, 31, -6, 4, .3, true)}
    ${pinna(70, 57, 90, 61.6, 10, 3, .5)}
    ${pinna(100, 62, 118, 58.4, 9, 3, .5)}
    ${occhio(29, 39, 3.4)}
    <path d="M46 30q9 3.4 0 9.4M58 27q10 3.6 0 10.4M72 25q10 3.8 0 11"
      stroke-width=".55" opacity=".3"/>
  `);

  F.ghiozzo = p(`
    <path d="M20 50C34 39.5 62 33 94 34C118 34.8 136 39 147 45.5"/>
    <path d="M20 50C32 61.5 62 68 94 67C117 66.2 136 59 147 52.5"/>
    ${coda(147, 49, 28, 14, 4, 3.5)}
    ${bocca(20, 50, 11, 2.6)}
    ${opercolo(44, 40, 19)}
    ${pinna(54, 34.4, 78, 36.2, -8, 5, .28, true)}
    ${pinna(90, 37.2, 114, 41.4, -5.5, 4, .3, true)}
    ${pinna(60, 60, 82, 65.6, 11, 4, .5)}
    ${pinna(98, 65.6, 120, 61.2, 10, 4, .5)}
    ${occhio(32, 44, 3.4)}
    ${macchie([[62, 44], [80, 41], [98, 44], [116, 42], [72, 54], [92, 55], [110, 51]], 1.7)}
  `);

  /* ------------------------------------------------- da specie a tavola   */
  const RUBRICA = {
    trotaFario: 'trota', trotaIridea: 'trota', trotaLacustre: 'trota', salmerino: 'trota',
    temolo: 'temolo',
    cavedano: 'cavedano', rovella: 'cavedano', triotto: 'cavedano', scardola: 'cavedano',
    bosega: 'cavedano', savetta: 'cavedano', pigo: 'cavedano', breme: 'cheppia',
    barbo: 'barbo', barboCanino: 'barbo', lasca: 'barbo', gobione: 'ghiozzo',
    vairone: 'alborella', alborella: 'alborella', sanguinerola: 'alborella',
    carpa: 'carpa', carpaErbivora: 'carpa', carassio: 'carpa', tinca: 'carpa',
    luccio: 'luccio', aspio: 'luccio',
    persicoReale: 'persico', persicoTrota: 'persico', lucioperca: 'persico',
    siluro: 'siluro', pesceGatto: 'siluro',
    anguilla: 'anguilla',
    cheppia: 'cheppia', cefalo: 'cefalo', storione: 'siluro',
    spigola: 'spigola', orata: 'orata', mormora: 'orata',
    pescePelagico: 'pelagico', paganello: 'ghiozzo'
  };

  const pesce = (idSpecie) => F[RUBRICA[idSpecie] || 'cavedano'] || F.cavedano;

  /* ==========================================================  SEGNI  === */
  const S = {};
  const g = (b, sw = 1.4) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${b}</svg>`;

  /* rosa dei venti a 32 punte */
  S.rosa = `<svg viewBox="-6 -6 112 112" fill="none" stroke="currentColor" aria-hidden="true">
    <circle cx="50" cy="50" r="46" stroke-width="1"/>
    <circle cx="50" cy="50" r="35" stroke-width=".55" opacity=".55"/>
    <circle cx="50" cy="50" r="9" stroke-width=".8"/>
    ${Array.from({ length: 32 }, (_, i) => {
      const a = i * Math.PI / 16, lungo = i % 8 === 0, medio = i % 4 === 0;
      const r0 = lungo ? 35 : medio ? 39 : 42;
      return `<path d="M${f1(50 + r0 * Math.sin(a))} ${f1(50 - r0 * Math.cos(a))}L${f1(50 + 46 * Math.sin(a))} ${f1(50 - 46 * Math.cos(a))}" stroke-width="${lungo ? .9 : .5}" opacity="${lungo ? 1 : .65}"/>`;
    }).join('')}
    <path d="M50 7 57.5 50 50 44.5 42.5 50Z" fill="currentColor" stroke="none"/>
    <path d="M50 93 42.5 50 50 55.5 57.5 50Z" fill="none" stroke-width=".85"/>
    <text x="50" y="-0.5" text-anchor="middle" font-family="Fraunces, serif" font-size="12"
      font-style="italic" fill="currentColor" stroke="none">N</text>
  </svg>`;

  S.bussola = g(`<circle cx="12" cy="12" r="9"/><path d="m15.4 8.6-2 5.4-5.4 2 2-5.4Z"/>`);
  S.avviso = g(`<path d="M12 3.6 21.4 20H2.6Z"/><path d="M12 9.6v4.6"/><circle cx="12" cy="16.9" r=".95" fill="currentColor" stroke="none"/>`);
  S.scudo = g(`<path d="M12 2.8 4.6 5.8v5.6c0 4.6 3 8.6 7.4 10.2 4.4-1.6 7.4-5.6 7.4-10.2V5.8Z"/><path d="m8.8 11.8 2.3 2.3 4.4-4.6"/>`);
  S.ricarica = g(`<path d="M20.4 12a8.4 8.4 0 1 1-2.7-6.2"/><path d="M20.8 4.4v4.4h-4.4"/>`);
  S.info = g(`<circle cx="12" cy="12" r="9"/><path d="M12 11.2v5.4"/><circle cx="12" cy="7.9" r=".95" fill="currentColor" stroke="none"/>`);
  S.filtro = g(`<path d="M3.6 6.4h16.8M6.8 12h10.4M10 17.6h4"/>`);
  S.luna = g(`<path d="M20.4 14.6A8.6 8.6 0 0 1 9.4 3.6a8.8 8.8 0 1 0 11 11Z"/>`);
  S.freccia = g(`<path d="M4.5 12h14M12.8 6.2 18.6 12l-5.8 5.8"/>`);
  S.puntina = g(`<path d="M12 21.4c4.2-4.6 6.4-8 6.4-10.6a6.4 6.4 0 1 0-12.8 0c0 2.6 2.2 6 6.4 10.6Z"/><circle cx="12" cy="10.6" r="2.4"/>`);
  S.navigatore = g(`<path d="M20.8 3.2 3.6 10.4l7.2 2.8 2.8 7.2Z"/>`);
  S.indietro = g(`<path d="M19.5 12h-14M11.2 6.2 5.4 12l5.8 5.8"/>`);

  /* --- cielo, in stile inciso --- */
  const C = {};
  C.sereno = g(`<circle cx="12" cy="12" r="4.4"/>${Array.from({length:8},(_,i)=>{const a=i*Math.PI/4,s=Math.sin(a),c=Math.cos(a);return `<path d="M${f1(12+6.6*s)} ${f1(12-6.6*c)}L${f1(12+9.4*s)} ${f1(12-9.4*c)}"/>`}).join('')}`);
  C.velato = g(`<circle cx="9.4" cy="9.4" r="3.6"/><path d="M9.4 3v-1.6M3 9.4H1.4M4.9 4.9 3.7 3.7M14 4.9l1.2-1.2"/><path d="M8.4 19.4h9.4a3.6 3.6 0 0 0 .4-7.2 5 5 0 0 0-9.5 1.3 3 3 0 0 0-.3 5.9Z"/>`);
  C.coperto = g(`<path d="M6.8 18.6h10a4 4 0 0 0 .5-8 5.6 5.6 0 0 0-10.6 1.5 3.3 3.3 0 0 0 .1 6.5Z"/>`);
  C.pioggia = g(`<path d="M7 15.4h9.4a3.7 3.7 0 0 0 .4-7.4A5.2 5.2 0 0 0 7.1 9.4 3 3 0 0 0 7 15.4Z"/><path d="m8.6 18.4-.8 2.4M12 18.4l-.8 2.4M15.4 18.4l-.8 2.4"/>`);
  C.rovesci = g(`<path d="M7 14.4h9.4a3.7 3.7 0 0 0 .4-7.4A5.2 5.2 0 0 0 7.1 8.4 3 3 0 0 0 7 14.4Z"/><path d="m8 17.4-1 3.4M11.6 17.4l-1 3.4M15.2 17.4l-1 3.4" stroke-width="1.7"/>`);
  C.temporale = g(`<path d="M7 14.2h9.4a3.7 3.7 0 0 0 .4-7.4A5.2 5.2 0 0 0 7.1 8.2 3 3 0 0 0 7 14.2Z"/><path d="m12.9 16.2-3 4.2h2.9l-1.2 3.2"/>`);
  C.neve = g(`<path d="M7 14.2h9.4a3.7 3.7 0 0 0 .4-7.4A5.2 5.2 0 0 0 7.1 8.2 3 3 0 0 0 7 14.2Z"/><path d="M9 17.8h.01M12 19.2h.01M15 17.8h.01M10.6 21.2h.01M13.6 21.2h.01"/>`);
  C.nebbia = g(`<path d="M7.4 12.4h9.2a3.6 3.6 0 0 0 .4-7.2 5 5 0 0 0-9.6 1.2 2.9 2.9 0 0 0 0 6Z"/><path d="M4.4 16h15.2M6.4 19.4h11.2"/>`);

  const CIELO = {
    0:['sereno','Sereno'], 1:['sereno','Poco nuvoloso'], 2:['velato','Nuvolosità variabile'],
    3:['coperto','Coperto'], 45:['nebbia','Nebbia'], 48:['nebbia','Nebbia con brina'],
    51:['pioggia','Pioviggine'], 53:['pioggia','Pioviggine'], 55:['pioggia','Pioviggine fitta'],
    56:['pioggia','Pioviggine gelata'], 57:['pioggia','Pioviggine gelata'],
    61:['pioggia','Pioggia leggera'], 63:['pioggia','Pioggia'], 65:['pioggia','Pioggia forte'],
    66:['pioggia','Pioggia gelata'], 67:['pioggia','Pioggia gelata forte'],
    71:['neve','Neve leggera'], 73:['neve','Neve'], 75:['neve','Neve abbondante'], 77:['neve','Nevischio'],
    80:['rovesci','Rovesci leggeri'], 81:['rovesci','Rovesci'], 82:['rovesci','Rovesci violenti'],
    85:['neve','Rovesci di neve'], 86:['neve','Rovesci di neve forti'],
    95:['temporale','Temporale'], 96:['temporale','Temporale con grandine'], 99:['temporale','Grandinata']
  };

  return {
    pesce, pesci: F, segni: S, cielo: C, CIELO,
    seg: (n) => S[n] || S.info,
    ciel: (w) => { const c = CIELO[w] || ['coperto', '—']; return { svg: C[c[0]], testo: c[1] }; }
  };
})();
