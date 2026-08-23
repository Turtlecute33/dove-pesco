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

**Una domanda, una risposta.** La pagina apre con un solo spot: nome, luogo, indice, il
pesce del giorno, acqua, portata, prima luce e una frase sul perché. Sotto, la mappa con
tutti gli spot. Sotto ancora, sei righe con le alternative e un «vedi tutti i 222».
Nient'altro: filtri, rilevamenti completi, specie secondarie e regole stanno dietro un
tocco.

## Le pagine: un indirizzo per ogni spot

L'applicazione vive a un solo indirizzo e calcola tutto nel browser. Comodo da usare,
invisibile a un motore di ricerca: 222 spot e 40 specie senza un indirizzo proprio non si
possono indicizzare, e chi cerca «dove pescare sul Panaro» non arriva.

Per questo `tools/genera-pagine.py` scrive **277 pagine statiche** a ogni pubblicazione:

```
/spot/<nome>/          222 schede: come arrivare, accessi, fondale, specie, esche, note
/specie/<nome>/         40 schede: misura minima, divieto, temperatura, esche, dove si trova
/provincia/<nome>/       9 elenchi per corso d'acqua, con le specie più diffuse
/spot/  /specie/         i due indici completi
/regole/ /metodo/ /privacy/
sitemap.xml  robots.txt  404.html
```

Dentro ci vanno **solo i fatti che non cambiano**. L'indice del giorno no: cambia ogni
due ore, e su una pagina statica sarebbe vecchio. C'è invece un link che apre lo spot
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

**Regionale** — confini, 68 corsi d'acqua reali, 95 specchi d'acqua, nove città per
orientarsi. Gli spot sono punti: il colore dice come si presenta la giornata, il nome
compare al passaggio. Nessun numero stampato sulla mappa, altrimenti diventa un
tabellone. Si trascina, si ingrandisce con il pizzico del trackpad, con due dita o con i
tasti in alto a destra; punti e nomi si contro-scalano e restano della stessa misura a
ogni ingrandimento. Toccando un punto si apre la **scheda rapida** — indice, acqua,
portata, pesce del giorno — e da lì si apre la scheda intera.

**Locale** — per ogni spot un riquadro di 3,6 km con il tratto d'acqua, le strade, le
sterrate, i sentieri, i parcheggi e i **punti di accesso**: i tratti in cui una strada o
un sentiero arriva a meno di 70 m dall'acqua, calcolati sulla geometria, non disegnati a
mano. È lì che conviene fermarsi. Pesa 2,2 MB e per questo viene caricata solo alla prima
scheda aperta, non all'avvio.

## Precisione delle coordinate

Le coordinate scritte a mano cadevano spesso lontano dall'acqua. Sono state
ricalibrate agganciandole alla geometria del corso d'acqua che ogni scheda dichiara:

| | prima | dopo |
|---|---|---|
| Spot entro 260 m dall'acqua | 72 su 151 | **192 su 200** |
| Peggior scarto residuo | 2,0 km | 810 m |

Gli 8 rimanenti sono tutti entro 810 m, quindi l'acqua resta comunque dentro il
riquadro della mappa locale (i 22 spot di mare non entrano nel conto). Il controllo si
rilancia con `tools/verifica-coordinate.py`; per i 51 spot aggiunti nel 2026 le
coordinate sono state agganciate al corso d'acqua dichiarato e il comune di ogni punto è
stato verificato a ritroso, perché sui fiumi di confine la sponda cambia provincia.

## Struttura

```
index.html                     4 viste: Oggi · Specie · Regole · Metodo
.github/workflows/dati.yml     riscarica le previsioni ogni 2 ore e pubblica su Pages
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
  geo-regione.js               geometria della mappa regionale (84 KB)
  geo-locale.js                222 mappe locali (2,2 MB, caricata a richiesta)
  api.js                       legge il file delle previsioni, con Open-Meteo di riserva
  engine.js                    modello dell'indice
  mappa.js                     disegno delle due mappe
  ui.js                        interfaccia
tools/
  aggiorna-dati.py             scarica meteo e portata e scrive previsioni.json
  genera-pagine.py            prepara _sito/: applicazione + 277 pagine + sitemap
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
ogni 2 ore   tools/aggiorna-dati.py  →  assets/dati/previsioni.json  (280 KB, 39 KB compressi)
             il workflow ripubblica il sito con dentro il file fresco
```

Il browser legge quel file e **non chiama nessun servizio esterno**: prima schermata
immediata, nessun limite da superare, nessun indirizzo IP di chi pesca mostrato a terzi.
Sotto la data compare l'ora del rilevamento.

Se il file manca o ha più di 5 ore — sito aperto con un doppio clic, pubblicazione senza
workflow, aggiornamento fermo — `api.js` torna da solo a chiamare Open-Meteo dal browser,
come faceva prima: a tre richieste per volta, con ritenta automatica sui 429 e con quello
che arriva mostrato comunque.

### Metterlo in piedi su GitHub Pages

1. carica la cartella in un repo e vai su **Settings → Pages → Source: GitHub Actions**;
2. il workflow parte al primo push, poi ogni due ore e quando lo lanci a mano da Actions;
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
python3 tools/bake-geo.py            # mappa regionale da OpenStreetMap
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
