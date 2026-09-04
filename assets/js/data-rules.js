/* =============================================================================
   REGOLE: pesca sportiva e ricreativa in Emilia-Romagna
   Riferimenti: L.R. 11/2012 · Reg. reg. 1/2018 (Allegato 1 e Allegato 2)
   modificato dal Reg. reg. 1/2020 · Programma ittico regionale annuale ·
   calendari ittici provinciali.
   ========================================================================== */

const REGOLE = {

  aggiornato: 'Verificato ad agosto 2026 sulle fonti regionali. I calendari provinciali cambiano ogni anno: controlla sempre prima di uscire.',

  licenza: [
    { t: 'Licenza obbligatoria', d: 'Per la pesca sportiva e ricreativa nelle acque interne serve la licenza di tipo B o C, secondo la L.R. 11/2012 e il Reg. reg. 1/2018.' },
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

  avvisi: [
    { t: 'Fiume Taro: divieto di pesca fino al 31/12/2026', d: 'Per la scarsità idrica è istituita una zona di protezione temporanea della fauna ittica nel tratto tra il punto di derivazione in località Ramiola (Medesano, PR) e la foce, compresi i canali di bonifica alimentati con risorsa prelevata in deroga.', livello: 'alto' },
    { t: 'Bacini di Suviana, Brasimone e S. Maria', d: 'Nuovo regolamento per il triennio 2026-29 (BUR n. 167 del 01/07/2026). Vietata la pesca e la detenzione di esemplari vivi o morti di vairone, pigo e savetta.', livello: 'medio' },
    { t: 'Provincia di Parma', d: 'Divieto permanente di pesca al barbo canino e alla lasca. Divieto di pesca a cavedano e vairone dal 15 marzo al 30 giugno. Divieto di detenzione di cavedani sotto i 22 cm. Detenzione della cheppia vietata in tutte le acque provinciali.', livello: 'medio' },
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
    { t: 'Carta interattiva delle zone ittiche e dei regolamenti', u: 'https://agricoltura.regione.emilia-romagna.it/pesca/pesca-sportiva-professionale-acque-interne/calendari-ittici/carta-interattiva' },
    { t: 'Aree di pesca regolamentata in Emilia-Romagna', u: 'https://agricoltura.regione.emilia-romagna.it/pesca/pesca-sportiva-professionale-acque-interne/aree-di-pesca-regolamentata-in-emilia-romagna' },
    { t: 'Regolamento regionale n. 1/2018 (testo vigente su Demetra)', u: 'https://demetra.regione.emilia-romagna.it/al/articolo?urn=er%3Aassemblealegislativa%3Aregolamento%3A2018%3B1' },
    { t: 'Allegato 2 modificato, BUR n. 377 del 29/10/2020', u: 'https://bur.regione.emilia-romagna.it/area-bollettini/bollettini-in-lavorazione/n-377-del-29-10-2020-parte-prima.2020-10-30.1839750467/modifica-dellallegato-2-del-regolamento-regionale-2-febbraio-2018-n-1-di-attuazione-delle-disposizioni-in-materia-di-tutela-della-fauna-ittica-e-dellecosistema-acquatico-e-di-disciplina-della-pesca-dellacquacoltura-e-delle-attivita-connesse-nelle-acque/allegato-regolamento-regionale.2020-10-30.1604064195' },
    { t: 'Programma ittico regionale 2026/2027', u: 'https://bur.regione.emilia-romagna.it/area-bollettini/n-79-del-02-04-2026-parte-seconda/l-r-n-11-2012-art-5-adozione-del-programma-ittico-regionale-2026-2027/allegato1' },
    { t: 'Itinerari di pesca sportiva in Emilia-Romagna (PDF)', u: 'https://agricoltura.regione.emilia-romagna.it/pesca/pubblicazioni/pesca-sportiva/itinerari-di-pesca-sportiva-in-emilia-romagna' },
    { t: 'Tesserino pesca Suviana, Brasimone e S. Maria (Ente Parchi BO)', u: 'https://enteparchi.bo.it/pagina.php?id=42' },
    { t: 'Previsioni meteo e portata dei fiumi: Open-Meteo (licenza CC BY 4.0)', u: 'https://open-meteo.com/' }
  ]
};
