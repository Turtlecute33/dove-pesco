# Dove Pesco — Emilia-Romagna

**[dovepescare.com](https://dovepescare.com/)**

Sito statico che risponde a una domanda sola: **stamattina, dove vado a pescare?**

222 spot su fiumi, torrenti, laghi, canali e mare. Ogni mattina ognuno riceve un
*indice del giorno*, calcolato incrociando la portata reale del corso d'acqua, la
temperatura stimata dell'acqua, la pioggia delle 72 ore precedenti, la pressione, la
luce, la luna e la finestra stagionale di ogni specie — con i divieti dell'Allegato 2
già applicati.

## Uso

Apri `index.html` con un doppio clic. Nessun build, nessuna dipendenza, nessun server:
anche i caratteri sono incorporati come data URI perché il browser non li blocchi
sotto `file://`.

Aperto così, il sito chiama Open-Meteo dal browser: il file delle previsioni si legge
solo quando la pagina è servita da un server (`python3 -m http.server` basta).

Per pubblicarlo, carica la cartella su qualsiasi hosting statico. Su GitHub Pages c'è in
più il workflow che tiene fresche le previsioni: vedi «Le previsioni: un file, non una
chiamata a testa».

## Come è organizzata

**Una domanda, una risposta.** In cima, una riga sola dice cosa fa il sito — un voto da 0
a 100 su 222 spot, ogni mattina, e cosa lo decide — perché il titolo da solo non bastava:
chi arriva la prima volta vedeva un nome di fiume e un numero, senza sapere di che numero
si trattasse. È scritta nell'HTML, non generata: si legge prima che parta uno script.

Poi la pagina apre con un solo spot: nome, luogo, indice, il
pesce del giorno, acqua, portata, prima luce e una frase sul perché. Sotto, la mappa con
tutti gli spot. Sotto ancora, sei righe con le alternative e un «vedi tutti i 222».
Nient'altro: filtri, rilevamenti completi, specie secondarie e regole stanno dietro un
tocco.

## Le pagine: un indirizzo per ogni spot

L'applicazione vive a un solo indirizzo e calcola tutto nel browser. Comodo da usare,
invisibile a un motore di ricerca: 222 spot e 40 specie senza un indirizzo proprio non si
possono indicizzare, e chi cerca «dove pescare sul Panaro» non arriva.

Per questo `tools/genera-pagine.py` scrive **278 pagine statiche** a ogni pubblicazione:

```
/spot/<nome>/          222 schede: come arrivare, accessi, fondale, specie, esche, note
/specie/<nome>/         40 schede: misura minima, divieto, temperatura, esche, dove si trova
/provincia/<nome>/       9 elenchi per corso d'acqua, con le specie più diffuse
/spot/ /provincia/ /specie/   i tre indici completi
/regole/ /metodo/ /privacy/
sitemap.xml  robots.txt  404.html
```

L'elenco di tutti i 278 indirizzi sta anche in fondo all'applicazione, in un `<details>`
chiuso. Prima stava dentro un `<noscript>`, ed era come non esserci: Googlebot esegue
JavaScript, e quando lo esegue butta via il contenuto di `<noscript>`. Risultato, la home
— la pagina con più autorità del sito — passava **dieci** collegamenti, tutti verso
l'esterno, e nessuno verso le 277 pagine che deve far trovare. Ora ne passa 291.

Dentro ci vanno **solo i fatti che non cambiano**. L'indice del giorno no: cambia ogni
quattro ore, e su una pagina statica sarebbe vecchio. C'è invece un link che apre lo spot
nell'applicazione — `/#spot/<id>`, che l'applicazione riconosce all'avvio — così un
indirizzo condiviso porta dritto alla scheda giusta.

Le pagine riusano `assets/css/style.css`: stessa impaginazione, stesse schede, stessi
colori. `assets/css/pagina.css` aggiunge solo le briciole di pane, gli elenchi di
collegamenti e il richiamo all'applicazione.

Il titolo di primo livello della pagina è fisso («Dove pescare oggi in Emilia-Romagna»):
il nome dello spot, che cambia ogni mattina, è il titolo di secondo livello dentro la
scheda. Prima erano quattro `h1` sulla stessa pagina, e quello visibile cambiava ogni
giorno.

```bash
python3 tools/genera-pagine.py                          # scrive _sito/, pronto da servire
python3 tools/genera-pagine.py --base https://tuo.it    # per un altro dominio
cd _sito && python3 -m http.server                      # per guardarlo
```

Il generatore legge gli elenchi in `assets/js` con node, quindi i dati stanno in un posto
solo: si aggiunge uno spot a `data-spots-*.js` e la sua pagina compare al deploy
successivo. Se il sito non sta alla radice del dominio (per esempio
`<utente>.github.io/<repo>/`), i link interni prendono da soli il prefisso giusto.

## Le due mappe

Nessuna libreria di mappe e nessun server di tile. La geometria è stata scaricata una
volta sola da OpenStreetMap, semplificata e incorporata nel sito come percorsi SVG.

**Regionale** — confini, il mare, 107 corsi d'acqua reali, 95 specchi d'acqua, nove città
per orientarsi. Gli spot sono punti: il colore dice come si presenta la giornata. Nessun
numero stampato sulla mappa, altrimenti diventa un tabellone. Si trascina, si ingrandisce
con il pizzico del trackpad, con due dita o con i tasti in alto a destra; punti e nomi si
contro-scalano e restano della stessa misura a ogni ingrandimento.

Su questa carta ogni spot deve avere **la sua** acqua sotto il punto, e per molti non
c'era: l'elenco dei corsi da scaricare era scritto a mano in `bake-geo.py` e nessuno lo
confrontava con i dati. Sessanta spot su 222 stavano su terra vergine — i quattro della
Limentra di Treppio, il Dardagna, l'Aveto, il Canal Bianco a Ferrara, il Navile, il
Naviglio, il Burana, i laghetti di crinale — e i 19 di mare stavano peggio, perché il mare
non era disegnato affatto. Ora l'elenco lo decidono le schede: si scarica la rete
principale per nome intero, si guarda quali punti sono rimasti senz'acqua addosso, e solo
per quelli si cerca per parole (la scheda dice «Torrente Limentra di Treppio», la mappa
dice «Limentra»), tenendo i corsi che passano davvero vicino a chi li nomina. Alla fine lo
script **dice quali schede sono rimaste scoperte**, invece di lasciarlo scoprire a chi
guarda la mappa.

| | prima | dopo |
|---|---|---|
| Corsi d'acqua sulla carta | 68 | **107** |
| Il mare | non disegnato | **disegnato** |
| Spot senza acqua disegnata entro 500 m | 60 su 222 | **2 su 222** |
| oltre 1,5 km da qualsiasi acqua | 43 | **0** |

La mappa è un comando, non un'illustrazione. Con il mouse il passaggio apre la **scheda
rapida** — indice, acqua, portata, pesce del giorno — e il clic porta dritto alla scheda
dello spot. Al tocco, dove il passaggio non esiste, il primo tocco ferma la scheda rapida
e il secondo apre lo spot; da tastiera il punto si raggiunge con il tabulatore e si apre
con Invio. Il punto sulla mappa e la riga nell'elenco sono lo stesso spot visto da due
parti: accendendo l'uno si accende anche l'altra.

**Locale** — per ogni spot un riquadro fino a 3,6 km con il tratto d'acqua, le strade, le
sterrate, i sentieri, i parcheggi e i **punti di accesso**: i tratti in cui una strada o
un sentiero arriva a meno di 70 m dall'acqua, calcolati sulla geometria, non disegnati a
mano. È lì che conviene fermarsi. Pesa 2,1 MB e per questo viene caricata solo alla prima
scheda aperta, non all'avvio.

Su questa carta si vede **l'acqua su cui si pesca**, non un intrico di righe azzurre
tutte uguali. In una finestra di 3,6 km di rii e fossi ce ne sono a decine: il generatore
confronta il nome che ogni scheda dichiara nel campo `acqua` con i nomi di OpenStreetMap —
per parole, non per stringa intera, perché la scheda dice «Torrente Limentra di Treppio» e
la mappa dice «Limentra» — e incide quel tratto a parte. È l'unico disegnato in grande, in
tinta piena, col nome scritto in legenda.

Il **mare** OpenStreetMap non lo disegna: disegna la linea di riva, con la terra a sinistra
e l'acqua a destra di come è percorsa. Sui 22 spot di mare la carta restava tutta color
terra, con il punto in mezzo al niente. Ora la riva viene tagliata sul quadrato della
finestra e richiusa lungo il bordo dal lato dell'acqua: ne esce un poligono, che è il mare.
Lo stesso trucco vale ora anche sulla carta regionale, dove il quadrato è il rettangolo
della carta e il lato buono lo indica una sonda nell'angolo di nord-est, che lì è mare
aperto: i portocanali di Cervia, Cesenatico, Riccione e Rimini stavano addosso al nome del
paese, senza un filo d'acqua intorno.

Il riquadro infine **segue l'acqua**. Se il tratto d'acqua cade lontano dal punto — una
foce, un fiume largo, una coordinata a mano — la finestra scivola verso l'acqua quel tanto
che basta a tenere dentro tutti e due, e si stringe per non uscire dalla geometria incisa.
Non c'è più una scheda che mostri lo spot senza il suo fiume.

## Precisione delle coordinate

Le coordinate scritte a mano cadevano spesso lontano dall'acqua. `tools/ricalibra.py`
cerca in OpenStreetMap il corso d'acqua che ogni scheda dichiara e sposta la stazione sul
punto più vicino di **quell'**acqua, non della prima che passa.

Nel secondo giro sono state mosse **42 stazioni**: i 22 spot di mare, che nessuno aveva
mai agganciato alla riva, e una manciata di punti finiti nel posto sbagliato — il Po a
Torricella stava in provincia di Cremona, il Po a Luzzara sette chilometri dentro la
campagna, il Collettore Acque Alte in mezzo a Crevalcore, il porto di Cattolica in centro
paese. Otto sono state agganciate a mano, verificando a ritroso il comune del punto,
perché sui fiumi di confine la sponda cambia provincia.

| | prima | dopo |
|---|---|---|
| Spot con la propria acqua nella carta | 0 su 222 | **219 su 222** |
| di cui entro 100 m | — | **217** |
| Distanza mediana dall'acqua dichiarata | — | **3 m** |
| Peggior scarto da qualsiasi acqua | 940 m | **423 m** |

Al terzo giro `bake-geo.py` ha trovato **dieci coordinate ancora sbagliate**, che i
controlli di prima non vedevano: misuravano la distanza dal fosso più vicino, e un fosso
c'è quasi sempre. Misurando invece la distanza dall'acqua *dichiarata* sono venuti fuori
il Lago Santo Parmense sei chilometri a valle del suo lago, il Lago Calamone altri sei
chilometri fuori, il Cavo Napoleonico due volte a sei chilometri dal canale, il Po di Goro
otto chilometri dentro la campagna, il Bacino di Santa Maria cinque chilometri dal suo
invaso, e il Collettore Acque Alte, la Valle Fattibello, il Lago di Ponte e il Lago di
Pometo più vicini ma comunque fuori. Ognuna è stata riagganciata all'acqua giusta,
partendo dal paese che il nome della scheda dichiara — Salvatonica, Mirabello, Serravalle —
e non dalla coordinata sbagliata, che avrebbe tirato l'aggancio sul tratto vicino a sé.

Restano tre schede la cui acqua **non esiste in OpenStreetMap con quel nome**: lo Scolo
Riolo a Malalbergo (il punto è su un canale, a 14 m, ma il canale in mappa non ha quel
nome), il Lago di Pometo (un invaso di un chilometro quadro, senza nome) e i Laghi di
Varignana, dove nessuno specchio d'acqua si chiama Pozzo Rosso: quel punto sta a 800 m dal
laghetto più vicino e va verificato sul posto. Il Lago della Fiera di Rimini è nel parco
del quartiere fieristico e in mappa non c'è. Il controllo si rilancia con
`tools/verifica-coordinate.py` sulle mini-carte già scaricate, o con `tools/bake-geo.py`,
che lo rifà contro OpenStreetMap in diretta e stampa l'elenco.

## Struttura

```
index.html                     4 viste: Oggi · Specie · Regole · Metodo, piu' l'indice
.github/workflows/dati.yml     riscarica le previsioni ogni 4 ore e pubblica su Pages
assets/dati/previsioni.json    le previsioni pronte (generate, non versionate)
assets/og.png                  l'anteprima per chi condivide un link
assets/css/
  style.css                    panna, angoli tondi, ombre morbide, un solo accento
  pagina.css                   il poco in più che serve alle pagine statiche
  caratteri.css                Fraunces e Archivo, incorporati come data URI
assets/fonts/                  i woff2 originali (per rigenerare caratteri.css)
assets/js/
  tavole.js                    16 disegni di pesci a linea + simboli, costruiti in codice
  data-species.js              40 specie: biologia, profondità, esche, regole
  data-spots-*.js              222 spot in quattro elenchi
  data-index.js                unione, province, categorie, mappa delle rarità
  data-rules.js                licenze, attrezzi, limiti, zone, avvisi, fonti
  geo-regione.js               geometria della mappa regionale (101 KB, mare compreso)
  geo-locale.js                222 mappe locali (2,1 MB, caricata a richiesta)
  api.js                       legge il file delle previsioni, con Open-Meteo di riserva
  engine.js                    modello dell'indice
  mappa.js                     disegno delle due mappe
  ui.js                        interfaccia
tools/
  aggiorna-dati.py             scarica meteo e portata e scrive previsioni.json
  genera-pagine.py             prepara _sito/: applicazione + 278 pagine + sitemap
  bake-geo.py                  la carta regionale, e l'elenco degli spot senz'acqua
  bake-locale.py               le 222 mini-carte, il mare e l'acqua di ogni scheda
  nomi_acqua.py                confronta «Torrente Limentra di Treppio» e «Limentra»
  ricalibra.py                 aggancia le coordinate all'acqua che la scheda dichiara
  og-immagine.py               ridisegna assets/og.png (solo se cambia il marchio)
```

## Copertura

| Provincia | Spot | | Ambiente | Spot |
|---|---|---|---|---|
| Bologna | 46 | | Fiumi | 81 |
| Modena | 36 | | Torrenti | 68 |
| Ferrara | 30 | | Canali e cavi | 26 |
| Forlì-Cesena | 25 | | Mare, moli e foci | 22 |
| Parma | 21 | | Laghi | 12 |
| Reggio Emilia | 20 | | Bacini e dighe | 10 |
| Piacenza | 18 | | Cave | 3 |
| Ravenna | 14 | | | |
| Rimini | 12 | | **di cui no kill** | **33** |

Comprende i piccoli spot di paese — Viazzano, Bocconi, Giumella, Salsominore, Bedogno,
Salvatonica, Isola di Tredozio, Governara, Ponte Organasco, Macerato, Riccovolto,
Bosconure, Ponte di Bagnana — non solo i tratti famosi.

Nel 2026 sono stati aggiunti 51 spot su Bologna (19), Modena (17) e Ferrara (15), dove la
rete d'acqua è più fitta: l'asta del Reno con Idice, Sillaro, Savena, Samoggia, Setta e
Santerno; il Panaro e il Secchia dalla collina alla bassa; i canali di bonifica (Emiliano
Romagnolo, Navile, Naviglio, Diversivo, Burana, Canal Bianco); il Po ferrarese da Stellata
a Berra e i rami del delta fino al mare.

## Come nasce l'indice

Sei fattori moltiplicati fra loro, specie per specie:

1. **Stagione** — curva di attività mensile per ogni specie.
2. **Temperatura dell'acqua** — stimata con un modello a inerzia termica: l'acqua segue
   la media dell'aria degli ultimi N giorni, smorzata verso la temperatura media annua
   alla quota dello spot. N e smorzamento cambiano per ambiente (3 giorni per un
   torrente sorgivo, 14 per un bacino profondo), con un tetto per tipo. È una stima
   dichiarata, non una misura.
3. **Portata** — dato reale dal modello idrologico GloFAS, confrontato con la mediana
   delle settimane precedenti nello stesso punto. Non usata su laghi, cave, mare e
   canali di bonifica.
4. **Pioggia e torbidità** — 72 ore precedenti + previsione + scarto di portata,
   confrontate con la preferenza di ogni specie.
5. **Pressione, luce, luna** — variazione barometrica sul giorno prima, copertura
   nuvolosa, fase lunare calcolata in locale.
6. **Divieti e presenza reale** — una specie in divieto o protetta pesa il 34%; dove la
   guida regionale scrive «rari», pesa il 42%.

Indice = 62% della specie migliore + 38% della media delle prime tre, poi modificatori
d'ambiente (piena, magra, temporali, vento, mare mosso, acqua fresca in giornata
torrida, stagione consigliata) e compressione esponenziale su 100. **Il 100 non è
raggiungibile**: nessun giorno è perfetto.

## Le previsioni: un file, non una chiamata a testa

Open-Meteo è gratuito, senza chiave e con i limiti contati **per indirizzo IP**: 600
chiamate al minuto, 10.000 al giorno. Un caricamento completo del sito ne pesa circa 350
(222 punti × 11 variabili × 17 giorni, più la portata su 149 corsi d'acqua). Se ogni
visitatore chiamasse dal proprio browser funzionerebbe — mille utenti sono mille quote
diverse — ma chi ricarica spesso, o sta dietro a un IP condiviso (ufficio, scuola, rete
mobile), si prenderebbe un 429.

Perciò le previsioni le scarica una volta sola GitHub Actions:

```
ogni 4 ore   tools/aggiorna-dati.py  →  assets/dati/previsioni.json  (280 KB, 39 KB compressi)
             il workflow ripubblica il sito con dentro il file fresco
```

Due richieste in tutto, una per servizio: Open-Meteo accetta tutte le coordinate insieme,
e un giro dura cinque secondi. Prima erano dieci richieste a lotti di 40 spot, e ogni
lotto dopo il primo si incagliava al primo tentativo per poi riuscire al secondo: con un
tetto di attesa di 180 secondi un giro arrivava a venti minuti, tenendo occupata la coda
di pubblicazione. Non era un rifiuto di Open-Meteo — non arriva mai un 429 — ma una
connessione che si apre e non risponde: gli indirizzi di uscita di GitHub Actions sono
condivisi fra molti, e connessioni ravvicinate dallo stesso indirizzo cadono nel vuoto.
Ora il tetto è di 25 secondi, il primo ritentativo è immediato e il passo si interrompe da
solo dopo 7 minuti.

Il browser legge quel file e **non chiama nessun servizio esterno**: prima schermata
immediata, nessun limite da superare, nessun indirizzo IP di chi pesca mostrato a terzi.
Sotto la data compare l'ora del rilevamento.

Se il file manca o ha più di 9 ore — due giri di fila non arrivati, sito aperto con un
doppio clic, pubblicazione senza il workflow — `api.js` torna da solo a chiamare Open-Meteo
dal browser,
come faceva prima: a tre richieste per volta, con ritenta automatica sui 429 e con quello
che arriva mostrato comunque.

### Metterlo in piedi su GitHub Pages

1. carica la cartella in un repo e vai su **Settings → Pages → Source: GitHub Actions**;
2. il workflow parte al primo push, poi ogni quattro ore e quando lo lanci a mano da Actions;
3. se un giro fallisce, il sito resta pubblicato con le previsioni precedenti.

Per un dominio tuo: punta il DNS a GitHub (record `A` verso 185.199.108–111.153 per il
dominio nudo, più un `CNAME` da `www` verso `<utente>.github.io.` perché anche chi scrive
`www.` arrivi), scrivilo in **Settings → Pages → Custom domain**, spunta **Enforce HTTPS**
e aggiungi la variabile `DOMINIO` in **Settings → Secrets and variables → Actions →
Variables**. `genera-pagine.py` scrive il file `CNAME` in ogni pubblicazione, così il
dominio non si perde a ogni deploy, e usa lo stesso valore per gli indirizzi canonici,
per la sitemap e per il `robots.txt`.

Alla prima pubblicazione con un dominio nuovo, dichiara il sito in
[Google Search Console](https://search.google.com/search-console) e manda la sitemap:
`https://<dominio>/sitemap.xml`.

Due avvertenze: i workflow programmati vengono sospesi da GitHub dopo 60 giorni senza
commit nel repo (basta un commit per riattivarli), e il cron è a discrezione della coda,
quindi può partire con qualche minuto di ritardo. Il file si può anche generare a mano con
`python3 tools/aggiorna-dati.py`.

I dati Open-Meteo sono CC BY 4.0: ripubblicarli in un file è consentito, l'attribuzione è
nel file stesso e nel piede del sito.

## Privacy

Nessun account, cookie, tracciamento, font o script di terze parti. Pubblicato con il
workflow, il browser non fa **nessuna chiamata fuori dal sito**: legge il file delle
previsioni servito insieme alla pagina.

Quando invece tocca alla riserva (file assente o vecchio), le chiamate vanno solo a
Open-Meteo, raggruppate in una decina di richieste e tenute in cache 45 minuti in
`localStorage` — solo previsioni, nessun dato personale. La posizione dell'utente non
viene mai richiesta.

## Rigenerare i dati

Gli script in `tools/` servono solo se vuoi aggiornare la geometria o aggiungere spot.
Il sito funziona senza di essi.

```bash
python3 tools/bake-geo.py            # mappa regionale; elenca gli spot senz'acqua
python3 tools/bake-locale.py         # 222 mappe locali (ripresa da cache)
python3 tools/verifica-coordinate.py # controlla che ogni spot sia sull'acqua
python3 tools/ricalibra.py --correggi # aggancia gli spot al corso d'acqua dichiarato
python3 tools/inline-font.py         # rigenera caratteri.css dai woff2
python3 tools/aggiorna-dati.py       # previsioni pronte in assets/dati/previsioni.json
python3 tools/genera-pagine.py       # la cartella da pubblicare, in _sito/
python3 tools/og-immagine.py         # ridisegna assets/og.png (serve cairosvg)
```

`tools/.cache-locale.json` conserva le mappe locali già scaricate: cancellalo solo se
vuoi rifare tutto da capo. Overpass limita le richieste: gli script provano più mirror
a rotazione e riprendono da dove si erano fermati.

## Fonti

- **Schede degli spot**: [«Itinerari di pesca sportiva in Emilia-Romagna»](https://agricoltura.regione.emilia-romagna.it/pesca/pubblicazioni/pesca-sportiva/itinerari-di-pesca-sportiva-in-emilia-romagna), Regione Emilia-Romagna — 40 itinerari ufficiali, espansi per località.
- **Misure minime, divieti, limiti**: Allegato 2 del [Reg. reg. 1/2018](https://demetra.regione.emilia-romagna.it/al/articolo?urn=er%3Aassemblealegislativa%3Aregolamento%3A2018%3B1), come modificato dal Reg. reg. 1/2020.
- **Zone e regolamenti**: [carta interattiva regionale](https://agricoltura.regione.emilia-romagna.it/pesca/pesca-sportiva-professionale-acque-interne/calendari-ittici/carta-interattiva), Programma ittico regionale 2026/2027, calendari ittici provinciali.
- **Meteo e portata**: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0), portata dal modello GloFAS.
- **Cartografia**: [OpenStreetMap](https://www.openstreetmap.org/copyright), licenza ODbL.
- **Caratteri**: interfaccia con il carattere di sistema (San Francisco su Apple), Archivo
  come ripiego altrove; Fraunces per titoli e numeri. Licenza SIL Open Font 1.1.

## Limiti dichiarati

Il modello non conosce la pressione di pesca, gli orari esatti dei rilasci delle dighe,
la torbidità reale, le schiuse di insetti, le chiusure temporanee decise ieri, né lo
stato delle strade di crinale in inverno. È uno strumento di orientamento, non
un'autorizzazione: fa fede solo il Regolamento regionale vigente e il calendario ittico
della provincia.

## Da fare, eventualmente

- Livelli idrometrici reali dai dati aperti ARPAE, più precisi di GloFAS sui corsi minori.
- Foto reali degli spot: il codice è pronto a sostituire le illustrazioni.
- Registro personale delle catture in `localStorage`, per pesare gli spot sull'esperienza.
