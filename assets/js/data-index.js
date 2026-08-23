/* =============================================================================
   INDICE — unisce i quattro elenchi di spot e raccoglie le tabelle di supporto.
   Va caricato DOPO data-spots-emilia.js, data-spots-romagna.js,
   data-spots-extra.js e data-spots-centro.js.
   ========================================================================== */

/* Unione dei quattro elenchi */
const SPOT = [].concat(
  typeof SPOT_EMILIA  !== 'undefined' ? SPOT_EMILIA  : [],
  typeof SPOT_ROMAGNA !== 'undefined' ? SPOT_ROMAGNA : [],
  typeof SPOT_EXTRA   !== 'undefined' ? SPOT_EXTRA   : [],
  typeof SPOT_CENTRO  !== 'undefined' ? SPOT_CENTRO  : []
);

const PROVINCE = {
  PC: 'Piacenza', PR: 'Parma', RE: 'Reggio Emilia', MO: 'Modena',
  BO: 'Bologna', FE: 'Ferrara', RA: 'Ravenna', FC: 'Forlì-Cesena', RN: 'Rimini'
};

/* -----------------------------------------------------------------------------
   RARITÀ LOCALE
   Dove la guida regionale scrive "rari", "qualche raro", "sporadiche" o
   "scarsa presenza", la specie non deve trainare il punteggio dello spot.
   Il motore ne riduce il peso: presente sì, ma non è il motivo per andarci.
   -------------------------------------------------------------------------- */
const RARITA = {
  'pc-po-isola-serafini':   ['storione'],
  'pc-tidone-pianello':     ['trotaFario'],
  'pc-arda-lugagnano':      ['carpa'],
  'pc-nure-bettola':        ['trotaFario'],
  'pr-po-polesine':         ['tinca', 'anguilla'],
  'pr-ceno-varano':         ['anguilla'],
  'pr-ceno-viazzano':       ['lasca'],
  'pr-lago-santo-parmense': ['carpa', 'scardola', 'tinca', 'cavedano'],
  'pr-lago-ballano':        ['carpa', 'scardola', 'tinca'],
  'pr-lagoni':              ['tinca'],
  're-secchia-cerredolo':   ['trotaFario'],
  're-secchia-gatta':       ['trotaFario'],
  're-lago-calamone':       ['carassio', 'scardola'],
  're-laghi-cerretani':     ['carpa'],
  're-dragone-cargedolo':   ['lasca'],
  'mo-panaro-ponte-samone': ['temolo', 'trotaIridea', 'carpa'],
  'mo-panaro-ponte-chiozzo':['temolo', 'trotaFario'],
  'mo-leo-fanano':          ['cavedano', 'barbo'],
  'bo-reno-riola':          ['trotaFario'],
  'bo-setta-gardelletta':   ['trotaFario'],
  'bo-setta-rioveggio':     ['trotaFario'],
  'bo-limentra-verzuno':    ['trotaIridea'],
  'bo-limentra-castrola':   ['trotaIridea'],
  'bo-suviana':             ['carpaErbivora'],
  'bo-brasimone':           ['carpaErbivora'],
  'bo-castel-dell-alpi':    ['carpaErbivora'],
  'bo-santerno-castel-del-rio': ['lasca', 'rovella'],
  'ra-senio-casola':        ['trotaFario', 'carpa', 'vairone', 'lasca', 'barbo'],
  'ra-lamone-brisighella':  ['trotaFario'],
  'ra-lamone-san-martino':  ['trotaFario'],
  'ra-lago-di-ponte':       ['trotaFario', 'persicoReale'],
  'ra-destra-reno':         ['siluro', 'pesceGatto'],
  'fc-montone-rocca':       ['anguilla', 'trotaFario'],
  'fc-montone-portico':     ['cavedano'],
  'fc-rabbi-predappio':     ['trotaFario', 'carpa'],
  'fc-bidente-corniolo':    ['barbo'],
  'fc-bidente-pietrapazza': ['vairone'],
  'fc-lago-ridracoli':      ['carpa', 'vairone'],
  'fc-savio-mercato-saraceno': ['pesceGatto', 'anguilla', 'scardola'],
  'fc-savio-bagno-romagna': ['cavedano', 'barbo'],
  'rn-marecchia-verrucchio':['carpa'],
  'rn-marecchia-petrella':  ['cavedano', 'barbo'],
  'fe-navigabile-migliarino': ['siluro', 'spigola'],
  /* terza tranche */
  'pc-nure-bosconure':       ['trotaFario'],
  'pc-tidone-nibbiano':      ['trotaFario'],
  'pc-arda-castellarquato':  ['lasca'],
  'pc-po-monticelli':        ['anguilla', 'cefalo'],
  'pr-po-zibello':           ['anguilla'],
  'pr-po-stagno-roccabianca':['scardola', 'anguilla'],
  'pr-taro-fornovo':         ['trotaFario'],
  'pr-ceno-ponte-lamberti':  ['lasca'],
  're-po-brescello':         ['anguilla'],
  're-secchiello-governara': ['barboCanino'],
  're-cavo-fiuma-reggiolo':  ['anguilla', 'pesceGatto'],
  'mo-panaro-docciola':      ['temolo', 'trotaFario', 'carpa'],
  'mo-leo-dardagna':         ['cavedano', 'barbo'],
  'mo-scoltenna-riolunato':  ['cavedano', 'barbo'],
  'bo-reno-marzabotto':      ['lasca'],
  'bo-limentra-molino-casio':['trotaIridea'],
  'bo-limentra-bagnana':     ['trotaIridea'],
  'bo-laghetti-castrola':    ['cavedano'],
  'bo-santa-maria':          ['luccio', 'trotaFario'],
  'bo-santerno-macerato':    ['lasca', 'trotaFario'],
  'fe-po-goro-gorino':       ['siluro', 'carpa'],
  'fc-bidente-strabatenza':  ['vairone'],
  'fc-rabbi-tontola':        ['trotaFario', 'carpa'],
  'fc-savio-quarto':         ['scardola'],
  'rn-marecchia-santarcangelo': ['carpa'],
  'rn-marecchia-novafeltria':['trotaFario']
};

const CATEGORIE = {
  A: { nome: 'Zona A', desc: 'Acque salmastre e fiume Po: specie delle acque interne e specie marine.' },
  B: { nome: 'Zona B', desc: 'Ciprinidi ed esocidi: in particolare tinca, carpa, luccio.' },
  C: { nome: 'Zona C', desc: 'Ciprinidi reofili: in particolare cavedano, barbo, lasca.' },
  D: { nome: 'Zona D', desc: 'Salmonidi e timallidi: trota (diverse varietà) e temolo.' },
  mare: { nome: 'Acque marittime', desc: 'Mare, moli, pontili e foci: si applicano le norme sulla pesca marittima.' }
};
