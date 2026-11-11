/* =============================================================================
   REGOLE: pesca sportiva e ricreativa in Emilia-Romagna
   Riferimenti: L.R. 11/2012 · Reg. reg. 1/2018 (Allegato 1 e Allegato 2)
   modificato dal Reg. reg. 1/2020 · Programma ittico regionale annuale ·
   calendari ittici provinciali.
   ========================================================================== */

const REGOLE = {

  aggiornato: 'Verificato a novembre 2026 sulle fonti regionali e sui calendari ittici 2026/2027 delle nove province. I calendari cambiano ogni anno: controlla sempre prima di uscire.',

  /* Quello che i calendari ittici provinciali aggiungono all'Allegato 2, letto
     l'11 novembre 2026 sui nove calendari 2026/2027 e su quello regionale. Il
     motore lo applica spot per spot, dalla provincia della scheda: una specie
     che in quella provincia non si può trattenere pesa come una in divieto e
     non diventa «il pesce del giorno». Qui stanno solo le regole che valgono in
     tutti i corpi idrici della provincia; quelle di un tratto solo (zone no
     kill, trofei, aree regolamentate) restano nelle note delle schede.
     Va riletto a ogni nuovo calendario: di solito esce a fine marzo. */
  province: {
    stagione: '2026/2027',
    /* detenzione vietata tutto l'anno */
    nonTrattenibili: {
      tinca:   ['PC', 'RE', 'MO', 'BO', 'FE', 'RA'],
      luccio:  ['PC', 'RE', 'MO', 'BO', 'FE', 'RA'],
      lasca:   ['PR', 'RE', 'MO', 'FC', 'RN'],
      vairone: ['FC', 'RN']
    },
    /* periodi di divieto più lunghi di quelli regionali. A Parma l'anticipo
       della carpa vale solo sull'Enza in comune con Reggio, e resta fuori. */
    periodi: [
      { specie: ['carpa'], prov: ['RE', 'MO', 'FE', 'RA', 'FC'], divieto: [4, 15, 6, 30],
        testo: 'il divieto va dal 15 aprile al 30 giugno' },
      { specie: ['cavedano', 'barbo', 'rovella', 'alborella', 'triotto', 'carpa', 'tinca', 'scardola'],
        prov: ['RN'], divieto: [4, 15, 6, 30],
        testo: 'i ciprinidi autoctoni non si trattengono dal 15 aprile al 30 giugno' }
    ],
    /* misure minime più alte: la trota a Modena e a Rimini nelle acque D, che
       è dove sta */
    misure: {
      cavedano:   { PC: 20, FC: 20, PR: 22, RE: 22 },
      trotaFario: { PC: 25, MO: 25, RN: 25 }
    },
    limiti: { trotaFario: { RN: 3 } }
  },

  /* Acque D che aprono la prima domenica di maggio invece dell'ultima di marzo
     (calendario ittico di Parma 2026/2027): Lago Santo e Laghi Gemini, cioè i
     Lagoni, e i laghi Ballano e Verde, dove si pesca «dalla prima domenica di
     maggio alla prima domenica di ottobre». */
  apertureDiMaggio: ['pr-lago-santo-parmense', 'pr-lagoni', 'pr-lago-ballano'],

  /* Schede segnate D su cui la chiusura invernale NON viene applicata, perché
     la categoria è in dubbio. L'invaso del Molato (Lago di Trebecco) sta nel
     calendario ittico di Piacenza 2026/2027 fra le zone per il carp fishing
     notturno, vietato solo dal 15 maggio al 30 giugno: in un'acqua D non
     potrebbe esserci. Va controllato sulla carta interattiva regionale, e
     corretta la categoria nella scheda. */
  categoriaDaVerificare: ['pc-lago-trebecco'],

  /* Le due frasi che rispondono a «serve la licenza?» nelle pagine degli spot
     e dei comuni. Stanno qui, accanto alle voci complete, perché il prezzo
     cambi in un posto solo. */
  /* Chi cerca «nuovo regolamento pesca emilia-romagna 2026» vuole sapere se
     le regole sono cambiate. Verificato a ottobre 2026 sulle pagine regionali:
     nel 2026 non è uscito un regolamento nuovo. */
  vigente: 'No. Il testo di riferimento resta il Regolamento regionale 1/2018, con l\'Allegato 2 delle misure minime e dei divieti modificato nel 2020. Per la stagione 2026/2027 vale il Programma ittico regionale (BUR n. 79 del 02/04/2026); i divieti temporanei sono negli avvisi in vigore.',

  licenzaBreve:'serve la licenza di tipo B (22,72 euro, un anno, per chi risiede in Emilia-Romagna) o di tipo C (6,82 euro, 30 giorni)',
  esentiBreve: 'Non serve a chi ha superato i 65 anni, ai minori di 12 anni accompagnati da un adulto con licenza e negli impianti di pesca a pagamento.',

  licenza: [
    { t: 'Licenza obbligatoria', d: 'Per la pesca sportiva e ricreativa nelle acque interne serve la licenza di tipo B o C, secondo la L.R. 11/2012 e il Reg. reg. 1/2018. La licenza è la ricevuta del versamento della tassa di concessione regionale: va tenuta con un documento d\'identità e vale su tutto il territorio nazionale.' },
    { t: 'Licenza di tipo B: 22,72 euro, un anno', d: 'Per chi risiede in Emilia-Romagna. Vale 365 giorni dal versamento e costa 22,72 euro sul c/c postale 116400 intestato a Regione Emilia-Romagna, Tasse concessioni regionali, con dati anagrafici, codice fiscale e causale. Si paga in posta con il bollettino o online sul sito della Regione.' },
    { t: 'Licenza di tipo C: 6,82 euro, 30 giorni', d: 'Per cittadini italiani e stranieri. Vale 30 giorni dal versamento e costa 6,82 euro, sullo stesso conto e con gli stessi dati. Per pagare online serve il codice fiscale, anche a chi viene dall\'estero.' },
    { t: 'Chi non ha bisogno della licenza', d: 'Chi ha superato i 65 anni; i minori di 12 anni accompagnati da un maggiorenne con licenza o esente; i minori di 18 anni con l\'attestato di un corso di avvicinamento alla pesca delle associazioni piscatorie; le persone dell\'art. 3 della legge 104/1992; gli stranieri in gara; chi pesca in un impianto a pagamento o in spazi privati.', warn: 'Le esenzioni valgono in Emilia-Romagna: nelle altre regioni vanno verificate sul posto.' },
    { t: 'Licenze di altre regioni', d: 'La licenza rilasciata in un\'altra regione o dalle Province autonome di Trento e Bolzano vale anche in Emilia-Romagna.' },
    { t: 'Tesserino segnacatture salmonidi', d: 'Nelle zone D serve il tesserino per la pesca controllata dei salmonidi, su cui registrare le trote che si intende trattenere. È gratuito e viene distribuito dai Comuni montani e collinari e dalle associazioni piscatorie. Valido su tutto il territorio regionale.' },
    { t: 'Porti marittimi', d: 'Per pescare nei porti di Rimini, Riccione, Cattolica e Bellaria serve un\'apposita licenza annuale della Capitaneria di Porto.' },
    { t: 'Bacini e zone a regime speciale', d: 'Suviana, Brasimone e S. Maria richiedono il tesserino dell\'Ente Parchi BO (online o presso esercenti convenzionati; tariffa ridotta del 50% per under 18 e persone con disabilità). Le zone turistiche (Santa Maria del Taro, Piane di Carniglia, Ponte Lugagnano) e le aree gestite da società (Dolo, Treponti Altobidente) richiedono permessi giornalieri a pagamento.' }
  ],

  attrezzi: [
    { t: 'Canne', d: 'Da una a tre canne, con o senza mulinello, ciascuna con non più di tre ami, collocate entro uno spazio di 10 metri.' },
    { t: 'Lenza a mano', d: 'Una lenza a mano con non più di 3 ami, utilizzabile solo da fermo o da natante.' },
    { t: 'Bilancella', d: 'Lato massimo della rete 1,5 metri, montata su palo di manovra, con lato delle maglie non inferiore a 10 mm.' },
    { t: 'Spinning', d: 'Pesca al lancio con esca artificiale munita di non più di due ami singoli senza ardiglione o con ardiglione schiacciato.' },
    { t: 'Pastura', d: 'Massimo 10 litri di pastura, oppure 4 kg di pastura solida o di boiles, comprese le esche, per giornata di pesca.' }
  ],

  limiti: [
    { t: 'Limite complessivo', d: 'Oltre ai limiti per specie, ogni pescatore non può prelevare più di 5 kg di pesce al giorno, con deroga quando il peso venga superato da un unico esemplare.', warn: 'I calendari provinciali e di bacino possono essere più restrittivi: in alcuni contesti locali si trovano limiti di 4 kg nelle zone B e 3 kg nelle zone C e D.' },
    { t: 'Salmonidi', d: 'Trota fario: massimo 5 capi al giorno, misura minima 22 cm, con obbligo di registrazione delle catture. Il temolo ha misura minima 35 cm e limite di 2 capi. Verifica il calendario provinciale: a Parma il limite nelle zone a salmonidi è di 3 esemplari non inferiori a 25 cm, sia trota sia salmerino alpino; nel piacentino è vietata la detenzione di trote sotto i 25 cm.' },
    { t: 'Stagione dei salmonidi', d: 'Le acque da salmonidi (categoria D) aprono l\'ultima domenica di marzo e chiudono la prima domenica di ottobre. Nelle acque di categoria D è vietata la pesca a ogni specie tra le ore 19 della prima domenica di ottobre e le ore 5 dell\'ultima domenica di marzo.' },
    { t: 'Misurazione', d: 'La lunghezza dei pesci si misura dall\'apice del muso a bocca chiusa fino all\'estremità della coda.' },
    { t: 'Rilascio obbligatorio', d: 'Gli esemplari delle specie autoctone e parautoctone catturati durante il periodo di divieto, o di misura inferiore alla minima consentita, devono essere immediatamente rilasciati e reimmessi in acqua.' },
    { t: 'Specie alloctone', d: 'Sono alloctone tutte le specie non inserite nell\'Allegato 1 (siluro, persico trota, lucioperca, carassio, pesce gatto, amur, aspio, iridea, breme…): non hanno misure minime né periodi di divieto regionali. Ne è vietata l\'immissione e la reimmissione.' }
  ],

  zone: [
    { sigla: 'ZPI', t: 'Zona di protezione integrale', d: 'Pesca vietata.' },
    { sigla: 'ZRF', t: 'Zona di ripopolamento e frega', d: 'Area destinata alla riproduzione: divieti totali o temporanei.' },
    { sigla: 'ZPSI', t: 'Zona di protezione delle specie ittiche', d: 'Divieti mirati su specie o periodi.' },
    { sigla: 'ZRSP', t: 'Zona a regime speciale di pesca', d: 'Regole proprie: no-kill, carp fishing notturno, zone turistiche, campi gara. Presenti in tutti i territori con la sola esclusione del forlivese per il carp-fishing.' }
  ],

  /* Un avviso con `spot` chiude quegli spot: l'indice del giorno va a zero e
     la scheda, nell'applicazione e nelle pagine statiche, dice perché. `dal` e
     `al` (AAAA-MM-GG) sono gli estremi del divieto; senza `al` dura finché
     qualcuno non lo toglie da qui. Passato `al`, l'avviso sparisce da solo.
     Gli spot vanno scritti uno per uno: «il Taro» non è chiuso tutto, solo
     dalla derivazione di Ramiola in giù. */
  avvisi: [
    { t: 'Anguilla: pesca sportiva vietata per tutto il 2026', d: 'Il decreto ministeriale n. 107712 del 4 marzo 2026 (art. 5) vieta la pesca sportiva dell\'anguilla europea su tutto il territorio nazionale per l\'intero anno. Il calendario ittico regionale 2026/2027 la mette fra le specie di cui la detenzione è sempre vietata: se abbocca, va rilasciata subito.', livello: 'alto' },
    { t: 'Luccio, tinca, lasca e vairone: dove non si trattengono', d: 'I calendari ittici provinciali 2026/2027 vietano la detenzione di tinca e luccio in tutte le acque di Piacenza, Reggio Emilia, Modena, Bologna, Ferrara e Ravenna; della lasca a Parma, Reggio Emilia, Modena, Forlì-Cesena e Rimini; del vairone a Forlì-Cesena e Rimini. La carpa è in divieto dal 15 aprile (non dal 15 maggio) a Reggio Emilia, Modena, Ferrara, Ravenna e Forlì-Cesena. A Rimini tutti i ciprinidi autoctoni si rilasciano dal 15 aprile al 30 giugno.', livello: 'medio' },
    { t: 'Misure minime più alte in provincia', d: 'Cavedano: 20 cm a Piacenza e Forlì-Cesena, 22 cm a Parma e Reggio Emilia. Trota: 25 cm in tutte le acque di Piacenza e nelle acque D di Modena e di Rimini, dove il limite è di 3 capi al giorno.', livello: 'medio' },
    { t: 'Lago del Brasimone: divieto di pesca', d: 'Dal 20/10/2026 la pesca è vietata in tutto il bacino del Brasimone (Camugnano, BO), a ogni specie, finché l\'invaso non torna al livello normale. È una zona di protezione temporanea istituita dalla Regione con la Determinazione n. 20213 per il forte abbassamento dell\'acqua.', livello: 'alto', spot: ['bo-brasimone'], dal: '2026-10-20' },
    { t: 'Fiume Taro: divieto di pesca fino al 31/12/2026', d: 'Per la scarsità idrica è istituita una zona di protezione temporanea della fauna ittica nel tratto tra il punto di derivazione in località Ramiola (Medesano, PR) e la foce, compresi i canali di bonifica alimentati con risorsa prelevata in deroga.', livello: 'alto', spot: ['pr-taro-san-secondo'], al: '2026-12-31' },
    { t: 'Bacini di Suviana, Brasimone e S. Maria', d: 'Nuovo regolamento per il triennio 2026-29 (BUR n. 167 del 01/07/2026). Vietata la pesca e la detenzione di esemplari vivi o morti di vairone, pigo e savetta.', livello: 'medio' },
    { t: 'Provincia di Parma', d: 'Divieto di detenzione della lasca e dei cavedani sotto i 22 cm in tutte le acque provinciali. Nel Lago Santo e nei Laghi Gemini la pesca apre la prima domenica di maggio; nei laghi Ballano e Verde si pesca dalla prima domenica di maggio alla prima domenica di ottobre.', livello: 'medio' },
    { t: 'Casse di espansione del Secchia', d: 'Misure minime locali per lucci e persici e divieto di utilizzo di esche artificiali dal 15 dicembre al 15 maggio.', livello: 'medio' },
    { t: 'Canale Boicelli e zone ferraresi', d: 'Zone di protezione delle specie ittiche con divieto di pesca alla savetta, al cavedano e al barbo.', livello: 'medio' }
  ],

  sicurezza: [
    { t: 'Rilasci dalle dighe', d: 'Limentra (diga di Suviana) e Savio (diga di Quarto) subiscono rilasci quotidiani che alzano il livello in pochi minuti. Non entrare in alveo senza aver verificato gli orari. Suviana e Brasimone possono variare di livello anche nell\'arco di poche ore.' },
    { t: 'Canale Emiliano Romagnolo', d: 'Sponde cementate ripide e particolarmente scivolose: pesca vicino alle scalette di risalita e sempre in compagnia.' },
    { t: 'Cave e sponde fangose', d: 'Nelle cave di Santarcangelo attenzione ai tratti fangosi e alle zone semipaludose: rischio concreto di affondamento.' },
    { t: 'Linee elettriche', d: 'Nel Cavo Lama e in molti canali di bonifica: massima attenzione all\'attraversamento di linee elettriche con le canne lunghe.' },
    { t: 'Portata in aumento', d: 'Se la portata prevista è in forte crescita rispetto alla media, evita l\'alveo e i guadi: le piene appenniniche arrivano in fretta e modificano l\'alveo.' }
  ],

  fonti: [
    { t: 'Pesca sportiva, Regione Emilia-Romagna', u: 'https://agricoltura.regione.emilia-romagna.it/pesca/pesca-sportiva-professionale-acque-interne' },
    { t: 'Come ottenere o rinnovare la licenza di pesca B o C', u: 'https://agricoltura.regione.emilia-romagna.it/pesca/pesca-sportiva-professionale-acque-interne/come-ottenere-o-rinnovare-la-licenza-di-pesca-b-o-c' },
    { t: 'Pagamento online della licenza di pesca (Regione Emilia-Romagna)', u: 'https://agri.regione.emilia-romagna.it/TesseriniCaccia/licenze-pesca.jsp' },
    { t: 'Divieto di pesca temporaneo nel Lago del Brasimone (Det. n. 20213 del 20/10/2026)', u: 'https://agricoltura.regione.emilia-romagna.it/pesca/notizie/2026/divieto-di-pesca-temporaneo-nel-lago-del-brasimone' },
    { t: 'Carta interattiva delle zone ittiche e dei regolamenti', u: 'https://agricoltura.regione.emilia-romagna.it/pesca/pesca-sportiva-professionale-acque-interne/calendari-ittici/carta-interattiva' },
    { t: 'Aree di pesca regolamentata in Emilia-Romagna', u: 'https://agricoltura.regione.emilia-romagna.it/pesca/pesca-sportiva-professionale-acque-interne/aree-di-pesca-regolamentata-in-emilia-romagna' },
    { t: 'Regolamento regionale n. 1/2018 (testo vigente su Demetra)', u: 'https://demetra.regione.emilia-romagna.it/al/articolo?urn=er%3Aassemblealegislativa%3Aregolamento%3A2018%3B1' },
    { t: 'Allegato 2 modificato, BUR n. 377 del 29/10/2020', u: 'https://bur.regione.emilia-romagna.it/area-bollettini/bollettini-in-lavorazione/n-377-del-29-10-2020-parte-prima.2020-10-30.1839750467/modifica-dellallegato-2-del-regolamento-regionale-2-febbraio-2018-n-1-di-attuazione-delle-disposizioni-in-materia-di-tutela-della-fauna-ittica-e-dellecosistema-acquatico-e-di-disciplina-della-pesca-dellacquacoltura-e-delle-attivita-connesse-nelle-acque/allegato-regolamento-regionale.2020-10-30.1604064195' },
    { t: 'Calendari ittici 2026/2027, regionale e delle nove province', u: 'https://agricoltura.regione.emilia-romagna.it/pesca/pesca-sportiva-professionale-acque-interne/calendari-ittici' },
    { t: 'Anguilla: D.M. n. 107712 del 4 marzo 2026 (Masaf)', u: 'https://www.masaf.gov.it/flex/cm/pages/ServeBLOB.php/L/IT/IDPagina/24397' },
    { t: 'Programma ittico regionale 2026/2027', u: 'https://bur.regione.emilia-romagna.it/area-bollettini/n-79-del-02-04-2026-parte-seconda/l-r-n-11-2012-art-5-adozione-del-programma-ittico-regionale-2026-2027/allegato1' },
    { t: 'Itinerari di pesca sportiva in Emilia-Romagna (PDF)', u: 'https://agricoltura.regione.emilia-romagna.it/pesca/pubblicazioni/pesca-sportiva/itinerari-di-pesca-sportiva-in-emilia-romagna' },
    { t: 'Tesserino pesca Suviana, Brasimone e S. Maria (Ente Parchi BO)', u: 'https://enteparchi.bo.it/pagina.php?id=42' },
    { t: 'Previsioni meteo e portata dei fiumi: Open-Meteo (licenza CC BY 4.0)', u: 'https://open-meteo.com/' }
  ]
};
