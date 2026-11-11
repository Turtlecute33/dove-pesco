/* =============================================================================
   INDICE: unisce i quattro elenchi di spot e raccoglie le tabelle di supporto.
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

/* -----------------------------------------------------------------------------
   CELLE DI PORTATA
   GloFAS lavora su celle di 5 km e Open-Meteo restituisce quella più vicina
   alla coordinata, che spesso non è quella in cui il modello fa scorrere il
   fiume: a Pontelagoscuro rispondeva 0,06 m³/s, con il Po a mille nella cella
   accanto. Per gli spot elencati qui la portata si chiede al centro di una
   cella vicina, scelta da tools/celle-portata.py; per tutti gli altri alla
   coordinata dello spot. Meteo e quota restano sempre sulla coordinata dello
   spot.
   -------------------------------------------------------------------------- */
/* CELLE_PORTATA:inizio (generato da tools/celle-portata.py, non modificare a mano) */
const CELLE_PORTATA = {
  'bo-limentra-castrola': [44.225, 11.025],
  'bo-limentra-verzuno': [44.275, 11.075],
  'bo-reno-biagioni': [44.125, 10.925],
  'bo-reno-casalecchio': [44.525, 11.275],
  'bo-reno-galliera': [44.825, 11.375],
  'bo-reno-pontecchio': [44.475, 11.225],
  'bo-samoggia-monteveglio': [44.525, 11.075],
  'bo-santerno-castel-del-rio': [44.225, 11.475],
  'bo-setta-gardelletta': [44.325, 11.175],
  'bo-setta-lagaro': [44.275, 11.175],
  'bo-setta-rioveggio': [44.325, 11.175],
  'bo-sillaro-castel-san-pietro': [44.325, 11.625],
  'fc-bidente-santa-sofia': [43.975, 11.875],
  'fc-bidente-strabatenza': [43.925, 11.825],
  'fc-montone-rocca': [44.025, 11.875],
  'fc-rabbi-giumella': [43.925, 11.825],
  'fc-rabbi-predappio': [44.175, 12.025],
  'fc-rabbi-premilcuore': [43.925, 11.825],
  'fc-savio-bagno-romagna': [43.875, 12.025],
  'fc-savio-quarto': [43.975, 12.175],
  'fc-torrente-alferello': [43.875, 12.025],
  'fc-torrente-para': [43.825, 12.175],
  'fe-panaro-bondeno': [44.875, 11.375],
  'fe-po-francolino': [44.925, 11.675],
  'fe-po-goro-mesola': [44.975, 12.275],
  'fe-po-goro-serravalle': [45.025, 12.125],
  'fe-po-pontelagoscuro': [44.925, 11.675],
  'fe-po-ro': [44.975, 11.775],
  'fe-po-volano-migliarino': [44.825, 11.975],
  'fe-reno-argenta': [44.575, 11.875],
  'fe-reno-panfilia': [44.825, 11.375],
  'mo-dardagna': [44.075, 10.775],
  'mo-dolo-romanoro': [44.375, 10.575],
  'mo-dragone-palagano': [44.425, 10.625],
  'mo-dragone-riccovolto': [44.225, 10.625],
  'mo-leo-dardagna': [44.275, 10.825],
  'mo-panaro-camposanto': [44.825, 11.175],
  'mo-panaro-docciola': [44.375, 10.875],
  'mo-panaro-ponte-chiozzo': [44.325, 10.875],
  'mo-panaro-ponte-samone': [44.425, 10.875],
  'mo-panaro-savignano': [44.525, 10.975],
  'mo-panaro-spilamberto': [44.575, 10.975],
  'mo-panaro-vignola': [44.525, 10.975],
  'mo-rio-perticara': [44.225, 10.625],
  'mo-rio-tagliole': [44.225, 10.625],
  'mo-scoltenna-fiumalbo': [44.225, 10.625],
  'mo-scoltenna-fola': [44.275, 10.725],
  'mo-secchia-concordia': [44.975, 10.925],
  'mo-secchia-pescale': [44.525, 10.725],
  'mo-secchia-ponte-veggia': [44.625, 10.725],
  'pc-arda-castellarquato': [44.925, 9.875],
  'pc-arda-lugagnano': [44.875, 9.825],
  'pc-nure-bettola': [44.875, 9.625],
  'pc-nure-bosconure': [44.775, 9.575],
  'pc-trebbia-marsaglia': [44.775, 9.375],
  'pr-bratica-corniglio': [44.525, 10.125],
  'pr-taro-fornovo': [44.725, 10.125],
  'pr-taro-san-secondo': [44.925, 10.225],
  'pr-taro-santa-maria': [44.475, 9.625],
  'ra-reno-foce-monte': [44.525, 12.225],
  'ra-senio-casola': [44.275, 11.575],
  'ra-tramazzo-isola': [44.075, 11.775],
  're-dragone-cargedolo': [44.375, 10.575],
  're-enza-selvanizza': [44.475, 10.275],
  're-enza-vetto': [44.525, 10.325],
  're-po-gualtieri': [44.975, 10.625],
  're-po-guastalla': [44.975, 10.625],
  're-po-luzzara': [45.025, 10.725],
  'rn-marecchia-novafeltria': [43.925, 12.275],
  'rn-marecchia-petrella': [43.875, 12.225],
  'rn-marecchia-santarcangelo': [44.075, 12.475],
  'rn-marecchia-verrucchio': [44.025, 12.375]
};
/* CELLE_PORTATA:fine */
