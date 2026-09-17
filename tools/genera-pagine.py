#!/usr/bin/env python3
"""Prepara la cartella da pubblicare: pagine statiche, sitemap e robots.txt.

Il sito resta l'applicazione a pagina singola. Queste pagine servono a dare un
indirizzo proprio a ogni spot, a ogni specie, a ogni corso d'acqua, a ogni
comune e a ogni provincia: un motore di ricerca non puo' indicizzare uno stato
interno del programma, quindi con il solo index.html gli spot restano
invisibili.

Ogni pagina porta i fatti che non cambiano (acqua, fondale, accessi, specie,
esche, regole) e, in coda, l'indice del giorno gia' calcolato. L'indice lo
calcola qui lo stesso motore che gira nel browser, sullo stesso
previsioni.json: e' l'unica cosa che questo sito sappia e nessun altro dica,
e finche' viveva solo nel browser nessun motore di ricerca la vedeva. Se il
file delle previsioni manca o e' vecchio il blocco si omette e basta.

  python3 tools/genera-pagine.py                    # scrive in _sito/
  python3 tools/genera-pagine.py --out /tmp/prova
  python3 tools/genera-pagine.py --base https://esempio.it
  python3 tools/genera-pagine.py --senza-indice     # salta l'indice del giorno
"""

import argparse
import collections
import datetime
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.parse
import zoneinfo

# Le previsioni sono chieste a Open-Meteo con timezone=Europe/Rome (vedi
# tools/aggiorna-dati.py), quindi le giornate del file sono giornate italiane.
# La pubblicazione pero' gira in UTC: `on: push` puo' scattare a qualsiasi ora,
# e fra le 22 e mezzanotte UTC (cioe' dopo mezzanotte a Roma) prendere la data
# in UTC voleva dire scrivere su ogni pagina il punteggio di ieri.
FUSO = zoneinfo.ZoneInfo('Europe/Rome')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATI = ['data-species.js', 'data-spots-emilia.js', 'data-spots-romagna.js',
        'data-spots-extra.js', 'data-spots-centro.js', 'data-index.js',
        'data-rules.js']

TIPI = {
    'fiume': 'Fiume', 'torrente': 'Torrente', 'lago': 'Lago',
    'bacino': 'Bacino', 'canale': 'Canale', 'cava': 'Cava', 'mare': 'Mare',
}
# Il plurale italiano non si fa aggiungendo una lettera: «lago» fa «laghi» e
# «fiume» fa «fiumi». La regola scritta a mano dava «13 fiumei, 9 canalei, 2
# lago», e stava nella prima riga delle nove pagine di provincia.
# Il mare e' uno solo: contarne otto vuol dire otto tratti di costa.
TIPI_CONTA = {
    'fiume': ('fiume', 'fiumi'), 'torrente': ('torrente', 'torrenti'),
    'lago': ('lago', 'laghi'), 'bacino': ('bacino', 'bacini'),
    'canale': ('canale', 'canali'), 'cava': ('cava', 'cave'),
    'mare': ('tratto di mare', 'tratti di mare'),
}
MESI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio',
        'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']
ORE = {'alba': 'prime luci', 'crepuscolo': 'alba e tramonto', 'notte': 'notte',
       'giorno': 'ore centrali', 'qualsiasi': 'tutto il giorno'}


# ---------------------------------------------------------------- dati

def leggi_dati():
    """Legge gli elenchi JS con node e li restituisce come dizionari."""
    js = r"""
      const fs = require('fs'), vm = require('vm'), p = require('path');
      const cartella = p.join(process.env.RADICE, 'assets/js');
      const src = %s.map(f => fs.readFileSync(p.join(cartella, f), 'utf8')).join('\n');
      const ctx = vm.createContext({});
      const out = vm.runInContext(src + '\n;JSON.stringify({SPOT, SPECIE, PROVINCE,'
        + ' CATEGORIE, RARITA, REGOLE, GRUPPI_SPECIE});', ctx);
      process.stdout.write(out);
    """ % json.dumps(DATI)
    try:
        raw = subprocess.run(['node', '-e', js], check=True, capture_output=True,
                             text=True, env={**os.environ, 'RADICE': BASE}).stdout
    except FileNotFoundError:
        sys.exit('serve node per leggere gli elenchi in assets/js')
    except subprocess.CalledProcessError as e:
        sys.exit('node non ha letto gli elenchi:\n' + e.stderr)
    return json.loads(raw)


# Quanto puo' essere vecchio previsioni.json perche' l'indice finisca nelle
# pagine. Lo stesso tetto di assets/js/api.js: oltre, nel browser il file viene
# scartato e si va in rete, quindi scriverlo qui vorrebbe dire pubblicare un
# numero che l'applicazione non mostrerebbe piu'.
ETA_MAX_ORE = 9


def leggi_indice(quando=None):
    """L'indice del giorno di ogni spot, calcolato con il motore del browser.

    Non c'e' una seconda formula: si caricano assets/js/engine.js e api.js in
    node, si legge lo stesso assets/dati/previsioni.json che legge la pagina e
    si chiama ENGINE.valuta(), spot per spot. Una copia in Python del punteggio
    sarebbe divergere al primo ritocco del motore.

    Torna {} quando il file non c'e', e' piu' vecchio di ETA_MAX_ORE o node non
    risponde: in quel caso le pagine escono senza il blocco del giorno, che e'
    esattamente come uscivano prima.
    """
    # Un solo runInContext, come in leggi_dati(): gli elenchi, api.js e engine.js
    # si dichiarano con const, e un const in cima a uno script non finisce fra le
    # proprieta' del contesto. Visto da fuori, ctx.SPOT non esiste; valutato
    # nello stesso script, SPOT c'e'. Percio' anche l'espressione finale sta li'
    # dentro, e quello che torna e' gia' la stringa JSON.
    js = r"""
      const fs = require('fs'), vm = require('vm'), p = require('path');
      const cartella = p.join(process.env.RADICE, 'assets/js');
      const leggi = f => fs.readFileSync(p.join(cartella, f), 'utf8');

      const f = p.join(process.env.RADICE, 'assets/dati/previsioni.json');
      if (!fs.existsSync(f)) { process.stdout.write('{}'); return; }
      const prev = JSON.parse(fs.readFileSync(f, 'utf8'));
      const eta = Date.now() - Date.parse(prev.generato);
      if (!(eta >= 0) || eta > %d * 3600 * 1000) { process.stdout.write('{}'); return; }

      // en-CA da AAAA-MM-GG, ed e' l'unico modo breve per avere la data di Roma
      // e non quella di UTC: i giorni del file sono giorni italiani.
      const giorno = process.env.GIORNO
        || new Date().toLocaleDateString('en-CA', { timeZone: 'Europe/Rome' });
      const ctx = vm.createContext({ PREV: prev, GIORNO: giorno, module: { exports: {} } });
      const src = [...%s, 'api.js', 'engine.js'].map(leggi).join('\n');

      const coda = `
        const dati = API.espandi(PREV);
        const fuori = {};
        const persi = [];
        SPOT.forEach(s => {
          let v;
          // Uno spot che fa saltare il motore non deve portarsi dietro gli
          // altri duecento: senza questo, una sola eccezione faceva uscire node
          // con errore, e tutte le pagine restavano senza indice del giorno con
          // il flusso verde e una riga sola su stderr a dirlo.
          try {
            v = ENGINE.valuta(s, dati.meteo[s.id], dati.portata[s.id], GIORNO);
          } catch (err) {
            persi.push(s.id + ': ' + err.message);
            return;
          }
          if (!v) return;
          fuori[s.id] = {
            punteggio: v.punteggio,
            etichetta: ENGINE.etichetta(v.punteggio).t,
            banda: ENGINE.banda(v.punteggio),
            specie: v.specie.filter(x => !x.soloRilascio).slice(0, 3)
                     .map(x => ({ nome: x.nome, id: x.id })),
            tAcqua: v.acqua.temp, flowRatio: v.acqua.flowRatio,
            alba: v.meteo.alba, tramonto: v.meteo.tramonto,
            finestre: v.finestre.slice(0, 2).map(x => ({ q: x.q, o: x.o })),
            spiegazione: v.spiegazione.slice(0, 3),
            mod: v.mod.map(x => ({ t: x.t, v: x.v }))
          };
        });
        JSON.stringify({ generato: PREV.generato, giorno: GIORNO, spot: fuori, persi });
      `;
      process.stdout.write(vm.runInContext(src + '\n' + coda, ctx));
    """ % (ETA_MAX_ORE, json.dumps(DATI))
    amb = {**os.environ, 'RADICE': BASE}
    if quando:
        amb['GIORNO'] = quando
    try:
        raw = subprocess.run(['node', '-e', '(() => {%s})()' % js], check=True,
                             capture_output=True, text=True, env=amb, timeout=180).stdout
    except FileNotFoundError:
        sys.exit('serve node per leggere gli elenchi in assets/js')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        sys.stderr.write('indice del giorno non calcolato: %s\n'
                         % (getattr(err, 'stderr', '') or err))
        return {}
    return json.loads(raw or '{}')


# ---------------------------------------------------------------- date

# Le fonti da cui ogni sezione del sito dipende davvero. Servono al <lastmod>
# della sitemap: e' l'unico dei tre campi facoltativi che Google legge, mentre
# <changefreq> e <priority> li dichiara ignorati da anni.
FONTI = {
    'spot': ['assets/js/data-spots-emilia.js', 'assets/js/data-spots-romagna.js',
             'assets/js/data-spots-extra.js', 'assets/js/data-spots-centro.js',
             'assets/js/data-index.js', 'assets/js/geo-accessi.js'],
    'specie': ['assets/js/data-species.js'],
    'regole': ['assets/js/data-rules.js'],
    'fisse': ['tools/genera-pagine.py'],
    'app': ['index.html', 'assets/js/engine.js', 'assets/js/ui.js'],
}

# genera-pagine.py stava dentro ogni sezione, non solo dentro 'fisse': bastava
# spostare una virgola nel generatore perche' tutti i 281 <lastmod> passassero
# alla stessa data, e infatti erano tutti uguali. Una data che si muove quando
# il contenuto non si muove e' esattamente il campo che il crawler impara a non
# leggere piu'. Ora ogni sezione guarda solo i dati da cui dipende; a dire
# quando cambia davvero una scheda ci pensa l'indice del giorno, che ha una
# data sua.


def data_commit(rel):
    """Data dell'ultimo commit che ha toccato il file, come AAAA-MM-GG."""
    try:
        r = subprocess.run(['git', 'log', '-1', '--format=%cs', '--', rel],
                           cwd=BASE, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    d = r.stdout.strip()
    return d if re.fullmatch(r'\d{4}-\d{2}-\d{2}', d) else None


def date_sezioni():
    """Per ogni sezione, la data dell'ultima modifica vera del suo contenuto.

    Senza cronologia (clone shallow, cartella non in git) si torna None e il
    <lastmod> si omette. E' voluto: una data inventata (la data di build, che
    cambierebbe a ogni giro di cron senza che nulla sia cambiato) insegna al
    crawler che il campo mente, e da quel momento lo ignora.
    """
    date = {}
    for sez, file in FONTI.items():
        v = [d for d in (data_commit(f) for f in file) if d]
        date[sez] = max(v) if v else None
    v = [d for d in date.values() if d]
    date['home'] = max(v) if v else None
    return date


def lastmod(u, date, freschi=None):
    """La data da mettere in sitemap per questo indirizzo.

    Dove la pagina porta davvero l'indice del giorno, la data e' quella
    dell'indice: e' il pezzo che cambia, e cambia una volta al giorno. Le altre
    tengono la data dell'ultimo commit che ne ha toccato i dati.

    `freschi` sono gli indirizzi che il blocco lo hanno per davvero, non quelli
    che potrebbero averlo: tre spot mancano dal file delle previsioni, escono
    senza indice, e marcarli comunque come cambiati ogni giorno sarebbe la
    stessa data che si muove a vuoto che questa funzione vuole togliere.
    """
    if u in (freschi or {}):
        return freschi[u]
    if u == '/':
        return date['home']
    if u.startswith('/specie'):
        return date['specie']
    if u.startswith(('/spot', '/provincia', '/acqua', '/comune')):
        return date['spot']
    if u.startswith('/regole'):
        return date['regole']
    return date['fisse']


# ---------------------------------------------------------------- utilita'

def e(t):
    return html.escape(str(t if t is not None else ''), quote=True)


def slug(t):
    t = unicodedata.normalize('NFKD', str(t))
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-zA-Z0-9]+", '-', t.lower())
    return t.strip('-')


MARCHIO = ' | Dove Pesco'


def taglia(t, n):
    """Accorcia a n caratteri senza spezzare una parola."""
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) <= n:
        return t
    return t[:n].rsplit(' ', 1)[0].rstrip(' ,.;:–-') + '…'


def titolo(testa, n=62):
    """Il titolo con il marchio in coda, se ci sta.

    taglia() su una stringa che finisce con «| Dove Pesco» taglia dentro il
    marchio, e nel risultato di ricerca «... | Dove…» sembra una pagina rotta.
    Il richiamo o c'e' tutto o non c'e': prima si prova con, poi senza, e solo
    all'ultimo si accorcia quello che resta.
    """
    testa = re.sub(r'\s+', ' ', testa).strip()
    if len(testa) + len(MARCHIO) <= n:
        return testa + MARCHIO
    return testa if len(testa) <= n else taglia(testa, n)


def cresci(testa, code, tetto=158):
    """La descrizione parte dai fatti e si allunga finche' ci sta.

    Tagliare a 158 lasciava la frase a meta' con i puntini: chi legge il
    risultato di ricerca vede una frase mozzata, non un testo denso. Meglio
    perdere l'ultima aggiunta per intero che mostrarne mezza.
    """
    fuori = testa
    for coda in code:
        if coda and len(fuori) + len(coda) + 1 <= tetto:
            fuori += ' ' + coda
    return fuori


def elenco(v, cong='e'):
    """['a','b','c'] -> 'a, b e c'

    Quando una voce contiene gia' una virgola si separa con il punto e virgola:
    tre nomi di specie come «Sgombro, palamita, aguglia» uniti dalle virgole
    diventano sei pesci invece di tre, e chi legge non ha modo di accorgersene.
    """
    v = [x for x in v if x]
    if not v:
        return ''
    if len(v) == 1:
        return v[0]
    sep = '; ' if any(',' in x for x in v) else ', '
    return sep.join(v[:-1]) + ' ' + cong + ' ' + v[-1]


def conta_tipo(n, tipo):
    """13 -> '13 fiumi', 1 -> '1 fiume'."""
    uno = TIPI.get(tipo, tipo).lower()
    return '%d %s' % (n, TIPI_CONTA.get(tipo, (uno, uno))[0 if n == 1 else 1])


def distanza(a, b):
    """Chilometri fra due spot, formula dell'emisenoverso."""
    r, f1, f2 = 6371.0, math.radians(a['lat']), math.radians(b['lat'])
    dl = math.radians(b['lon'] - a['lon'])
    h = (math.sin((f2 - f1) / 2) ** 2
         + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def mesi_punta(m):
    top = max(m)
    return [MESI[i] for i, v in enumerate(m) if v >= top * 0.85]


# ---------------------------------------------------------------- indirizzi

def indirizzi(d):
    """Assegna a ogni spot e a ogni specie il suo indirizzo, senza collisioni."""
    presi = set()

    def unico(s, ripiego):
        if s and s not in presi:
            presi.add(s)
            return s
        s = ripiego
        n = 2
        while s in presi:
            s = ripiego + '-' + str(n)
            n += 1
        presi.add(s)
        return s

    for s in d['SPOT']:
        s['slug'] = unico(slug(s['nome']),
                          slug(s['nome'] + '-' + s['comune']) or s['id'])
    presi = set()
    for k, sp in d['SPECIE'].items():
        sp['id'] = k
        sp['slug'] = unico(slug(sp['nome']), k.lower())


# ---------------------------------------------------------------- impaginato

CSS = ('<link rel="stylesheet" href="/assets/css/style.css">\n'
       '<link rel="stylesheet" href="/assets/css/pagina.css">\n'
       '<link rel="stylesheet" href="/assets/css/caratteri.css" media="print"'
       ' onload="this.media=\'all\';this.onload=null">\n'
       '<noscript><link rel="stylesheet" href="/assets/css/caratteri.css"></noscript>')

# async e non defer: uno script defer che non risponde tiene fermo DOMContentLoaded
# fino al timeout della connessione.
TAVOLE = ('<script async src="https://s.dovepescare.com/assets/js/tavole-meteo.js"'
          ' data-website-id="c49315c5-3c62-47ed-bd39-5a5c6eec2a45"></script>')

ICONA = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
         "%3Crect width='32' height='32' fill='%23FAF7F1'/%3E%3Cg fill='none' stroke='%231B5E63'"
         " stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 16c3.4-4.6"
         " 7.4-6.9 12-6.9 3.6 0 6.4 1.6 8.6 4.9-2.2 4.7-5 6.4-8.6 6.4-4.6 0-8.6-2.3-12-4.4Z'/%3E"
         "%3Cpath d='m5 16 3.1-2.5M5 16l3.1 2.5'/%3E%3Ccircle cx='20.4' cy='14.4' r='1'"
         " fill='%231B5E63' stroke='none'/%3E%3C/g%3E%3C/svg%3E")

LOGO = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"'
        ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M2.6 12c3.2-4.4 7-6.6 11.4-6.6 3.4 0 6.1 1.6 8.2 4.7-2.1 4.5-4.8 6.1-8.2'
        ' 6.1-4.4 0-8.2-2.2-11.4-4.2Z"/><path d="m2.6 12 2.9-2.4M2.6 12l2.9 2.4"/>'
        '<circle cx="17.2" cy="10.6" r=".9" fill="currentColor" stroke="none"/></svg>')

# gli stessi due segni di assets/js/tavole.js, qui a mano: le pagine statiche
# non caricano JavaScript
SEGNO = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"'
         ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">%s</svg>')
PUNTINA = SEGNO % ('<path d="M12 21.4c4.2-4.6 6.4-8 6.4-10.6a6.4 6.4 0 1 0-12.8 0c0 2.6 2.2 6'
                   ' 6.4 10.6Z"/><circle cx="12" cy="10.6" r="2.4"/>')
NAVIGATORE = SEGNO % '<path d="M20.8 3.2 3.6 10.4l7.2 2.8 2.8 7.2Z"/>'

MENU = [('/', 'Oggi'), ('/spot/', 'Spot'), ('/specie/', 'Specie'),
        ('/regole/', 'Regole'), ('/metodo/', 'Metodo')]

# Quanti spot ci sono davvero. Era scritto a mano, 222, in undici punti fra
# pagine, piede, sitemap e og: gli spot nel frattempo sono diventati 225, e
# /spot/ e /provincia/ arrivavano a dire due numeri diversi nella stessa
# navigata. Lo conta main() una volta sola e lo leggono tutti.
CONTA = {'spot': 0, 'specie': 0}

# Gli indirizzi che hanno scritto davvero l'indice del giorno, con la sua data.
# Lo riempie pagina() mentre impagina, e lo legge la sitemap: cosi' il <lastmod>
# dice quello che e' successo e non quello che si sperava succedesse.
FRESCHI = {}


def leggi_accessi():
    """I punti di accesso calcolati da tools/accessi.py. Il file e' generato e
       sta in git: se manca, i tasti tornano alla coordinata della scheda."""
    p = os.path.join(BASE, 'assets', 'js', 'geo-accessi.js')
    if not os.path.exists(p):
        return {}
    fuori = {}
    for riga in open(p):
        riga = riga.strip()
        if riga.startswith('"'):
            fuori[riga.split('"')[1]] = json.loads(riga[riga.index('['):riga.rindex(']') + 1])
    return fuori


# Perche' quel punto non e' al massimo della confidenza. Sono quattro cause
# diverse, e prima la scheda ne raccontava sempre una sola: per una buona meta'
# degli spot a confidenza 2 diceva una cosa falsa.
PERCHE = {
    'mezzeria': ' La sponda qui non è disegnata: la misura è sulla mezzeria del corso d\'acqua.',
    'ponte': ' Il punto è su un attraversamento: guarda da che parte si scende.',
    'strada grossa': ' È su una strada di grande traffico: cerca dove accostare.',
    'allargato': ' Trovato allargando le soglie: è il tratto giusto, non il metro giusto.',
    'mano': ' Controllato a mano.',
}


def detto_accesso(s, accessi):
    """Che cosa promettere di quel punto, senza promettere di piu'."""
    a = (accessi or {}).get(s['id'])
    if not a:
        return ('Il punto qui sotto è la coordinata della scheda: su questo spot '
                'la sponda non è disegnata in mappa e non sappiamo indicare '
                'l\'accesso esatto.')
    return ('Il punto qui sotto è dove ci si ferma: %s.' % a[3]) + PERCHE.get(a[4], '')


def fuori_html(s, accessi=None):
    """I tasti che aprono il punto esatto in una mappa di terzi o nel navigatore.

    Aprono il punto di accesso calcolato da tools/accessi.py, non la coordinata
    della scheda: quella sceglie la cella del meteo e della portata, e su un
    fiume largo cade in mezzo alla corrente. Dove il punto non c'e', si torna
    alla coordinata della scheda."""
    a = (accessi or {}).get(s['id'])
    la, lo = ('%.5f' % (a[0] if a else s['lat']), '%.5f' % (a[1] if a else s['lon']))
    return f"""<div class="fuori">
  <a class="btn vuoto piccolo" target="_blank" rel="noopener noreferrer"
     href="https://www.openstreetmap.org/?mlat={la}&amp;mlon={lo}#map=17/{la}/{lo}"
     >{PUNTINA} OpenStreetMap</a>
  <a class="btn vuoto piccolo" target="_blank" rel="noopener noreferrer"
     href="https://www.google.com/maps/search/?api=1&amp;query={la},{lo}"
     >{PUNTINA} Google Maps</a>
  <a class="btn vuoto piccolo solo-telefono"
     href="geo:{la},{lo}?q={la},{lo}({urllib.parse.quote(s['nome'])})"
     >{NAVIGATORE} Naviga</a>
  <span class="micro tenue num coord">{la}, {lo}</span>
</div>"""


def pagina(base, url, tit, desc, corpo, ld=None, briciole=None, indicizza=True,
           modificato=None):
    """Impagina una pagina statica. url comincia e finisce con /.

    `modificato` e' la data del contenuto che cambia davvero, cioe' quella
    dell'indice del giorno. Va nel <time> visibile e in dateModified: senza,
    una pagina che si riscrive ogni quattro ore non ha modo di dire quando.
    """
    testa_ind = ('<link rel="canonical" href="%s">' % e(base + url) if indicizza
                 else '<meta name="robots" content="noindex, follow">')
    nav = ''.join('<a href="%s"%s>%s</a>' % (u, ' aria-current="page"' if u == url else '', t)
                  for u, t in MENU)
    br = ''
    if briciole:
        voci = []
        for i, (u, t) in enumerate(briciole):
            ultimo = i == len(briciole) - 1
            voci.append('<span aria-current="page">%s</span>' % e(t) if ultimo
                        else '<a href="%s">%s</a>' % (e(u), e(t)))
        br = ('<nav class="briciole" aria-label="Percorso">%s</nav>'
              % '<i aria-hidden="true">/</i>'.join(voci))
    ldjson = ''
    if ld:
        blocchi = [b for b in (ld if isinstance(ld, list) else [ld]) if b]
        if modificato:
            # dateModified esiste su CreativeWork, non su Place e non su
            # ItemList: appenderlo li' e' una proprieta' che il vocabolario non
            # prevede, quindi un campo che nessuno legge. La data va su un nodo
            # WebPage, che descrive la pagina e non la cosa di cui parla.
            blocchi.insert(0, {
                '@context': 'https://schema.org', '@type': 'WebPage',
                '@id': base + url + '#pagina',
                'url': base + url, 'name': tit, 'inLanguage': 'it',
                'dateModified': modificato,
                'isPartOf': {'@type': 'WebSite', '@id': base + '/#sito'},
            })
        ldjson = ''.join(
            '<script type="application/ld+json">%s</script>\n'
            % json.dumps(b, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
            for b in blocchi)
    firma = ''
    if modificato:
        FRESCHI[url] = modificato
        firma = ('<p class="firma mini tenue">Aggiornato il <time datetime="%s">%s</time></p>'
                 % (e(modificato), e(data_lunga(modificato))))

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(tit)}</title>
<meta name="description" content="{e(desc)}">
{testa_ind}
<meta name="color-scheme" content="light">
<meta name="referrer" content="no-referrer">
<meta name="theme-color" content="#EFE9DD">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Dove Pesco">
<meta property="og:locale" content="it_IT">
<meta property="og:title" content="{e(tit)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(base + url)}">
<meta property="og:image" content="{e(base)}/assets/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Dove Pesco: l'indice del giorno per gli spot di pesca dell'Emilia-Romagna">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{ICONA}">
{CSS}
{ldjson}</head>
<body>

<header class="top">
 <div class="col largo">
  <div class="top-in">
    <a class="logo" href="/">{LOGO} Dove Pesco</a>
    <nav class="men men-link" aria-label="Sezioni">{nav}</nav>
  </div>
 </div>
</header>

<main class="sez">
 <div class="col">
{br}
{corpo}
{firma}
 </div>
</main>

<footer class="piede">
  <div class="col largo">
   <div class="piede-in">
    <div class="piede-g">
      <div>
        <span class="occhio">Dove Pesco</span>
        <p class="mini tenue" style="margin-top:9px">{CONTA['spot']} spot in Emilia-Romagna,
          ordinati ogni mattina sui dati del giorno. Dati aperti, licenze in chiaro.</p>
        <ul>
          <li><a href="/">Indice del giorno</a></li>
          <li><a href="/spot/">Tutti gli spot</a></li>
          <li><a href="/acqua/">Fiume per fiume</a></li>
          <li><a href="/comune/">Comune per comune</a></li>
          <li><a href="/provincia/">Provincia per provincia</a></li>
          <li><a href="/specie/">Tutte le specie</a></li>
        </ul>
      </div>
      <div>
        <span class="occhio">Il sito</span>
        <ul>
          <li><a href="/regole/">Regole e divieti</a></li>
          <li><a href="/metodo/">Come nasce l'indice</a></li>
          <li><a href="/privacy/">Privacy e dati</a></li>
        </ul>
      </div>
      <div>
        <span class="occhio">Fonti</span>
        <ul>
          <li><a href="https://agricoltura.regione.emilia-romagna.it/pesca/pesca-sportiva-professionale-acque-interne" target="_blank" rel="noopener noreferrer">Pesca sportiva (Regione E-R)</a></li>
          <li><a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo</a>: meteo e portata</li>
          <li><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>: mappe</li>
        </ul>
      </div>
    </div>
    <p class="fine">Strumento di orientamento, non un'autorizzazione. Fa fede solo il Regolamento
      regionale vigente e il calendario ittico della provincia. Rispetta misure minime, periodi di
      divieto e cartellonistica in loco. Cartografia © OpenStreetMap contributors, ODbL.</p>
   </div>
  </div>
</footer>

{TAVOLE}
</body>
</html>
"""


def briciola_ld(base, briciole):
    return {
        '@context': 'https://schema.org', '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': t,
             **({'item': base + u} if u else {})}
            for i, (u, t) in enumerate(briciole)],
    }


def cta(url, testo):
    return ('<p class="cta-app"><a class="btn-link" href="%s">%s</a></p>'
            % (e(url), e(testo)))


def righe(voci):
    """Elenco di link con sottotitolo, per gli indici e i collegamenti fra pagine."""
    return ('<ul class="elenco-link">%s</ul>' % ''.join(
        '<li><a href="%s"><b>%s</b><span>%s</span></a></li>' % (e(u), e(t), e(s))
        for u, t, s in voci))


def voci_html(coppie):
    """Il blocco <div class="voci"> di definizioni, usato da tutte le pagine.

    Ogni voce e' (titolo, valore) oppure (titolo, valore, True) quando il valore
    e' gia' HTML e non va riscappato. Le voci vuote spariscono.
    """
    fuori = []
    for c in coppie:
        t, v, grezzo = c[0], c[1], (len(c) > 2 and c[2])
        if v:
            fuori.append('<div class="voce"><h3>%s</h3><div><p>%s</p></div></div>'
                         % (e(t), v if grezzo else e(v)))
    return ''.join(fuori)


def faq_ld(voci):
    """Le domande e risposte di una pagina, in forma leggibile da una macchina.

    Sono le stesse che la pagina scrive per esteso: schema.org vuole che la
    risposta compaia anche nel testo visibile, e marcare qualcosa che il
    visitatore non vede e' proprio il caso che le linee guida vietano.
    """
    return {
        '@context': 'https://schema.org', '@type': 'FAQPage',
        'mainEntity': [{'@type': 'Question', 'name': dom,
                        'acceptedAnswer': {'@type': 'Answer', 'text': ris}}
                       for dom, ris in voci if ris],
    }


def faq_html(voci):
    return ('<h2>Domande frequenti</h2><div class="voci">%s</div>'
            % ''.join('<div class="voce"><h3>%s</h3><div><p>%s</p></div></div>'
                      % (e(dom), e(ris)) for dom, ris in voci if ris))


# ---------------------------------------------------------------- indice del giorno

def num(v, dec=1):
    """Un numero come lo scrive un italiano: virgola, non punto."""
    return ('%.*f' % (dec, v)).replace('.', ',')


def data_lunga(iso):
    """'2026-08-23' -> '23 agosto 2026'."""
    a, m, g = iso.split('-')
    return '%d %s %s' % (int(g), MESI[int(m) - 1], a)


def ora_di(generato):
    """L'ora del rilevamento nel fuso di chi pesca, non in UTC.

    aggiorna-dati.py scrive `generato` in UTC, e l'applicazione lo mostra con
    getHours(), cioe' nel fuso del browser. Affettare la stringa e basta faceva
    dire alla pagina «rilevamento delle 09:15» e al piede dell'applicazione
    «rilevati alle 11:15» per lo stesso identico file.
    """
    try:
        t = datetime.datetime.fromisoformat(generato)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return t.astimezone(FUSO).strftime('%H:%M')


def blocco_oggi(s, oggi, d):
    """Come si presenta questo spot oggi: il pezzo che prima viveva solo nel browser.

    E' l'unica cosa che il sito sappia e che nessun altro dica, e finche' si
    calcolava solo nel browser nessun motore di ricerca la vedeva: le 225 schede
    pubblicavano gli stessi fatti fermi che stanno in qualunque guida. Qui il
    numero e' gia' scritto nella pagina, con la data e l'ora del rilevamento
    accanto, perche' un indice senza la sua data non vuol dire niente.
    """
    v = (oggi.get('spot') or {}).get(s['id'])
    if not v:
        return '', None
    ora = ora_di(oggi.get('generato'))
    voci = [('Acqua stimata', '%s °C' % num(v['tAcqua']) if v.get('tAcqua') is not None else '')]
    if v.get('flowRatio') is not None:
        pc = round((v['flowRatio'] - 1) * 100)
        voci.append(('Portata', '%+d%% sulla mediana recente' % pc))
    if v.get('finestre'):
        f = v['finestre'][0]
        voci.append(('Finestra migliore', '%s, %s' % (f['q'].lower(), f['o'])))
    if v.get('specie'):
        voci.append(('Specie del giorno', ' · '.join(
            '<a href="/specie/%s/">%s</a>' % (d['SPECIE'][x['id']]['slug'], e(x['nome']))
            for x in v['specie'] if x['id'] in d['SPECIE']), True))

    avvisi = ''.join('<p class="att">%s</p>' % e(m['t'])
                     for m in v.get('mod', []) if m.get('v', 0) < 0)
    perche = ''.join('<li>%s</li>' % e(x) for x in v.get('spiegazione', []))

    return f"""<h2>Come si presenta oggi</h2>
<p class="mini tenue" style="margin-top:8px;max-width:66ch">Indice del
  {e(data_lunga(oggi['giorno']))}{', rilevamento delle ' + e(ora) if ora else ''}. Si ricalcola a
  ogni pubblicazione, sei volte al giorno. Come nasce il numero è spiegato nel
  <a href="/metodo/">metodo</a>.</p>
<div class="oggi">
  <span class="indice {e(v.get('banda') or 'medio')}"><b>{v['punteggio']}</b><s>/100</s></span>
  <em>{e((v.get('etichetta') or '').lower())}</em>
</div>
{avvisi}
<div class="voci">{voci_html(voci)}</div>
{('<ul class="lista-limiti">' + perche + '</ul>') if perche else ''}
{cta('/#spot/' + s['id'], 'Apri lo spot con la mappa e i sette giorni')}""", v


def migliore_oggi(spots, oggi):
    """Lo spot con l'indice piu' alto fra quelli passati, per le pagine d'insieme."""
    v = [(oggi['spot'][s['id']], s) for s in spots if s['id'] in (oggi.get('spot') or {})]
    return max(v, key=lambda x: x[0]['punteggio']) if v else (None, None)


def riga_oggi(spots, oggi, dove):
    """Una riga sola: qual e' il posto migliore oggi in questo insieme."""
    v, s = migliore_oggi(spots, oggi)
    if not v:
        return ''
    ora = ora_di(oggi.get('generato'))
    return f"""<h2>Come si presenta oggi</h2>
<p class="mini tenue" style="margin-top:8px;max-width:66ch">Indice del
  {e(data_lunga(oggi['giorno']))}{', rilevamento delle ' + e(ora) if ora else ''}, ricalcolato a
  ogni pubblicazione.</p>
<div class="oggi">
  <span class="indice {e(v.get('banda') or 'medio')}"><b>{v['punteggio']}</b><s>/100</s></span>
  <em>{e((v.get('etichetta') or '').lower())} a
    <a href="/spot/{e(s['slug'])}/">{e(s['nome'])}</a></em>
</div>
<p class="mini" style="margin-top:12px;max-width:66ch">È il valore più alto {dove} oggi.
  {e(v['spiegazione'][0]) if v.get('spiegazione') else ''}</p>"""


# ---------------------------------------------------------------- pagine spot

def pagina_spot(d, s, base, accessi=None, oggi=None, hub=None):
    prov = d['PROVINCE'][s['prov']]
    cat = d['CATEGORIE'][s['categoria']]
    tipo = TIPI.get(s['tipo'], s['tipo'].capitalize())
    rari = set(d['RARITA'].get(s['id'], []))
    sp_ids = [x for x in s.get('specie', []) if x in d['SPECIE']]
    oggi = oggi or {}
    hub = hub or {'acqua': {}, 'comune': {}}

    # Il taglio dell'ultimo ripiego finiva con i puntini in mezzo al nome dello
    # spot: un titolo che si interrompe («Bidente a Santa Sofia (area
    # regolamentata Treponti): pesca…») nel risultato di ricerca sembra rotto.
    # Meglio perdere il richiamo che il nome, quindi si scala fino al nome nudo.
    for testa in ('%s: dove pescare a %s' % (s['nome'], s['comune']),
                  '%s: pesca a %s (%s)' % (s['nome'], s['comune'], s['prov']),
                  '%s: pesca a %s' % (s['nome'], s['comune']),
                  '%s: dove pescare (%s)' % (s['nome'], s['prov']),
                  s['nome']):
        if len(testa) <= 62:
            break
    tit = titolo(testa)

    # la descrizione si allunga dalla coda: prima i fatti, poi i richiami
    nomi = [d['SPECIE'][x]['nome'] for x in sp_ids]
    desc = cresci('Pescare a %s, %s (%s): accessi, fondale, esche e regole.'
                  % (s['nome'], s['comune'], prov),
                  ['Le %d specie dichiarate: %s.' % (len(nomi), elenco(nomi[:3]).lower())
                   if nomi else '',
                   'Indice del giorno su portata e meteo.'])

    # Il comune entra nelle briciole solo dove ha una pagina propria, cioe' dove
    # ha piu' di uno spot: altrimenti la briciola porterebbe a se stessa.
    briciole = [('/', 'Oggi'), ('/spot/', 'Spot'),
                ('/provincia/%s/' % slug(prov), prov)]
    if s['comune'] in hub['comune']:
        briciole.append(('/comune/%s/' % hub['comune'][s['comune']], s['comune']))
    briciole.append((None, s['nome']))

    # apertura: solo fatti dichiarati negli elenchi, nessuna aggiunta
    categoria = (cat['nome'].replace('Zona ', 'categoria ')
                 if cat['nome'].startswith('Zona ') else cat['nome'].lower())
    apre = ['<strong>%s</strong> si pesca sul %s, nel comune di %s (%s). %s, %s.'
            % (e(s['nome']), e(s['acqua']), e(s['comune']), e(prov),
               e(tipo), e(categoria if s['categoria'] == 'mare'
                          else 'acque di ' + categoria))]
    if nomi:
        apre.append('Le specie dichiarate sono %d: %s.'
                    % (len(nomi), e(elenco(nomi))))

    segni = []
    for k, t in (('noKill', 'no kill'), ('bimbi', 'adatto ai bambini'),
                 ('disabili', 'postazioni accessibili'),
                 ('notturna', 'pesca notturna ammessa'), ('gare', 'campo gara')):
        if s.get(k):
            segni.append('<span class="tag acc">%s</span>' % t)
    segni.append('<span class="tag">livello %s</span>' % e(s.get('livello', '–')))
    if s.get('stagioniTop'):
        segni.append('<span class="tag">meglio in %s</span>'
                     % e(elenco(s['stagioniTop'])))

    # specie: ogni riga rimanda alla pagina della specie
    sp_html = ''
    if sp_ids:
        voci = []
        for x in sp_ids:
            sp = d['SPECIE'][x]
            tag = ''
            if sp.get('protetta'):
                tag = '<span class="tag rosso">protetta</span>'
            elif x in rari:
                tag = '<span class="tag">raro qui</span>'
            voci.append(
                '<tr><td><a href="/specie/%s/"><b>%s</b></a><span class="sci">%s</span></td>'
                '<td class="num" data-eti="Misura">%s</td>'
                '<td class="num" data-eti="Al giorno">%s</td>'
                '<td data-eti="Divieto">%s %s</td></tr>'
                % (sp['slug'], e(sp['nome']), e(sp['sci']),
                   (str(sp['misuraMin']) + ' cm') if sp.get('misuraMin') else '–',
                   'vietata' if sp.get('limiteGiorno') == 0 else (sp.get('limiteGiorno') or '–'),
                   e(sp['divietoTesto']), tag))
        sp_html = (
            '<h2>Cosa si pesca</h2>'
            '<p class="mini tenue" style="max-width:62ch;margin-top:8px">Misure minime e periodi '
            'di divieto dall\'Allegato 2 del Regolamento regionale 1/2018. Il calendario ittico '
            'della provincia può essere più restrittivo.</p>'
            '<div class="scorre" style="margin-top:16px"><table class="dati">'
            '<thead><tr><th>Specie</th><th>Misura minima</th><th>Capi al giorno</th>'
            '<th>Divieto</th></tr></thead><tbody>%s</tbody></table></div>' % ''.join(voci))

    posto = [('Come arrivare', s.get('comeArrivare')),
             ('Accessi', s.get('accesso')),
             ('Fondale e struttura', s.get('fondale')),
             ('Note e regole locali', s.get('note'))]
    posto_html = ''.join(
        '<div class="voce"><h3>%s</h3><div><p>%s</p></div></div>' % (e(t), e(v))
        for t, v in posto if v)

    attr = []
    if s.get('tecniche'):
        attr.append(('Tecniche', elenco(s['tecniche'])))
    if s.get('esche'):
        attr.append(('Esche', elenco(s['esche'])))
    attr.append(('Acque', '%s. %s' % (cat['nome'], cat['desc'])))
    attr_html = ''.join(
        '<div class="voce"><h3>%s</h3><div><p>%s</p></div></div>' % (e(t), e(v))
        for t, v in attr)

    # collegamenti: stesso corso d'acqua, poi i piu' vicini della provincia
    altri, visti = [], {s['id']}
    for o in d['SPOT']:
        if o['id'] not in visti and o['acqua'] == s['acqua']:
            altri.append((o, 'stesso corso d\'acqua'))
            visti.add(o['id'])
    vicini = sorted((o for o in d['SPOT'] if o['id'] not in visti and o['prov'] == s['prov']),
                    key=lambda o: distanza(s, o))
    for o in vicini:
        altri.append((o, '%.0f km' % distanza(s, o)))
    vic_html = righe([('/spot/%s/' % o['slug'], o['nome'],
                       '%s, %s · %s' % (o['comune'], d['PROVINCE'][o['prov']], perche))
                      for o, perche in altri[:8]])

    # Il luogo era testo morto. Adesso porta al corso d'acqua e al comune, che
    # sono le due domande che la gente scrive per intero («torrente leo», «dove
    # pescare a Cesenatico») e a cui prima rispondevano due schede in
    # concorrenza fra loro invece di una pagina d'insieme.
    luogo = []
    if s['comune'] in hub['comune']:
        luogo.append('<a href="/comune/%s/">%s</a>' % (hub['comune'][s['comune']], e(s['comune'])))
    else:
        luogo.append(e(s['comune']))
    luogo.append('<a href="/provincia/%s/">%s</a>' % (slug(prov), e(prov)))
    acqua_link = ('<a href="/acqua/%s/">%s</a>' % (hub['acqua'][s['acqua']], e(s['acqua']))
                  if s['acqua'] in hub['acqua'] else e(s['acqua']))

    oggi_html, v_oggi = blocco_oggi(s, oggi, d)

    faq = [
        ('Dove si trova %s?' % s['nome'],
         '%s si trova sul %s, nel comune di %s, in provincia di %s. %s'
         % (s['nome'], s['acqua'], s['comune'], prov,
            detto_accesso(s, accessi))),
        ('Che pesci ci sono a %s?' % s['nome'],
         ('Le specie dichiarate sono %d: %s. Misure minime e periodi di divieto seguono '
          'l\'Allegato 2 del Regolamento regionale 1/2018.' % (len(nomi), elenco(nomi)))
         if nomi else ''),
        ('Con che esche si pesca a %s?' % s['nome'],
         ('Le esche indicate per questo spot sono: %s. Le tecniche: %s.'
          % (elenco(s['esche']), elenco(s.get('tecniche') or ['nessuna indicata'])))
         if s.get('esche') else ''),
        ('Serve la licenza per pescare a %s?' % s['nome'],
         'Sì. In Emilia-Romagna serve la licenza di tipo B e il versamento annuale. %s è in %s: %s'
         % (s['nome'], cat['nome'].lower(), cat['desc'])),
    ]
    if v_oggi:
        faq.insert(0, (
            'Si pesca bene a %s oggi?' % s['nome'],
            'L\'indice del %s è %d su 100 (%s). %s'
            % (data_lunga(oggi['giorno']), v_oggi['punteggio'],
               (v_oggi.get('etichetta') or '').lower(),
               ' '.join(v_oggi.get('spiegazione', [])))))

    corpo = f"""<span class="occhio acc">{e(tipo)} · {e(prov)}</span>
<h1>{e(s['nome'])} <span class="h1-luogo">dove pescare a {e(s['comune'])}</span></h1>
<div class="luogo">{', '.join(luogo)} · {acqua_link}</div>
<div class="segni">{''.join(segni)}</div>
<div class="intro">{' '.join(apre)}</div>
{oggi_html or cta('/#spot/' + s['id'], "Vedi l'indice di oggi per questo spot")}
<h2>Il posto</h2>
<div class="voci">{posto_html}</div>
{sp_html}
<h2>Tecniche, esche e acque</h2>
<div class="voci">{attr_html}</div>
<h2>Dove fermarsi</h2>
<p class="mini">{e(detto_accesso(s, accessi))}
  La carta dei dintorni, con strade, sentieri e parcheggi, è nella
  <a href="/#spot/{e(s['id'])}">scheda dell'applicazione</a>.</p>
{fuori_html(s, accessi)}
<h2>Altri spot vicini</h2>
{vic_html}
{faq_html(faq)}
<p class="mini tenue" style="margin-top:26px;max-width:72ch">Scheda ricavata da
  «Itinerari di pesca sportiva in Emilia-Romagna» della Regione Emilia-Romagna, espansa per
  località. Prima di uscire controlla il
  <a href="/regole/">quadro delle regole</a>, il calendario ittico della provincia di
  {e(prov)} e la cartellonistica sul posto.</p>"""

    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'Place',
        '@id': base + '/spot/%s/#place' % s['slug'],
        'name': s['nome'], 'url': base + '/spot/%s/' % s['slug'],
        'description': taglia(s.get('fondale') or desc, 300),
        'image': base + '/assets/og.png',
        'geo': {'@type': 'GeoCoordinates', 'latitude': round(s['lat'], 5),
                'longitude': round(s['lon'], 5)},
        'address': {'@type': 'PostalAddress', 'addressLocality': s['comune'],
                    'addressRegion': prov, 'addressCountry': 'IT'},
        'isAccessibleForFree': True,
        'publicAccess': True,
        **({'amenityFeature': [{'@type': 'LocationFeatureSpecification',
                                'name': 'Postazioni accessibili', 'value': True}]}
           if s.get('disabili') else {}),
    }, faq_ld(faq)]
    u = '/spot/%s/' % s['slug']
    return u, pagina(base, u, tit, desc, corpo, ld, briciole,
                     modificato=oggi.get('giorno') if v_oggi else None)


# ---------------------------------------------------------------- pagine specie

def pagina_specie(d, sp, base, hub=None):
    dove = [s for s in d['SPOT'] if sp['id'] in (s.get('specie') or [])]
    hub = hub or {'acqua': {}, 'comune': {}}

    # Il titolo si accorciava tagliando dentro «| Dove Pesco», e quattro pagine
    # uscivano con il marchio spezzato a meta'. Il richiamo si perde tutto o non
    # si perde: mezzo marchio nel risultato di ricerca sembra un errore.
    tit = titolo('%s: pesca in Emilia-Romagna' % sp['nome'])

    # La coda diceva «0 spot in Emilia-Romagna dove si trova», e su cinque specie
    # veniva pure troncata a meta' frase. Una specie che nessuno spot dichiara
    # non e' una specie senza pagina: e' una specie che sta nella regione ma non
    # nelle schede, e la descrizione ora lo dice invece di contare zero.
    coda = ('%d spot in Emilia-Romagna dove si trova.' % len(dove) if dove
            else 'Presente nelle acque della regione, non dichiarata negli spot descritti.')
    desc = cresci('%s (%s): misura minima, periodo di divieto, temperatura, esche e tecniche.'
                  % (sp['nome'], sp['sci']), [coda])
    briciole = [('/', 'Oggi'), ('/specie/', 'Specie'), (None, sp['nome'])]

    segni = ['<span class="tag acc">autoctona</span>' if sp.get('autoctona')
             else '<span class="tag">alloctona</span>']
    if sp.get('protetta'):
        segni.append('<span class="tag rosso">protetta</span>')
    if sp.get('reteNatura'):
        segni.append('<span class="tag">Rete Natura 2000</span>')
    segni.append('<span class="tag">%s</span>' % e(sp['gruppo']))
    if dove:
        segni.append('<span class="tag">%d spot</span>' % len(dove))

    dati = [
        ('Misura minima', (str(sp['misuraMin']) + ' cm') if sp.get('misuraMin')
         else 'nessuna misura regionale'),
        ('Capi al giorno', 'pesca vietata' if sp.get('limiteGiorno') == 0
         else (str(sp['limiteGiorno']) if sp.get('limiteGiorno') else 'nessun limite per specie')),
        ('Periodo di divieto', sp['divietoTesto']),
        ('Acqua di massima attività', '%d–%d °C (si alimenta fra %d e %d °C)'
         % (sp['tOpt'][0], sp['tOpt'][1], sp['tLive'][0], sp['tLive'][1])),
        ('Ore migliori', ORE.get(sp['luce'], sp['luce'])),
        ('Mesi di punta', elenco(mesi_punta(sp['mesi']))),
        ('Taglia', sp.get('taglia') or '–'),
    ]
    dati_html = ''.join('<div class="voce"><h3>%s</h3><div><p>%s</p></div></div>'
                        % (e(t), e(v)) for t, v in dati)

    prof_html = ''
    if sp.get('prof'):
        prof_html = ('<h2>A che profondità sta</h2><div class="voci">%s</div>'
                     % ''.join('<div class="voce"><h3>%s</h3><div><p>%s</p></div></div>'
                               % (e(k.capitalize()), e(v)) for k, v in sp['prof'].items()))

    modo = []
    if sp.get('esche'):
        modo.append(('Esche', elenco(sp['esche'])))
    if sp.get('tecniche'):
        modo.append(('Tecniche', elenco(sp['tecniche'])))
    modo_html = ('<h2>Come si insidia</h2><div class="voci">%s</div>'
                 % ''.join('<div class="voce"><h3>%s</h3><div><p>%s</p></div></div>'
                           % (e(t), e(v)) for t, v in modo)) if modo else ''

    dritte_html = ('<h2>Dritte</h2><p class="nota" style="margin-top:14px">%s</p>'
                   % e(sp['dritte'])) if sp.get('dritte') else ''

    dove_html = ''
    if dove:
        per_prov = {}
        for s in dove:
            per_prov.setdefault(s['prov'], []).append(s)
        blocchi = []
        for pv in [k for k in d['PROVINCE'] if k in per_prov]:
            v = sorted(per_prov[pv], key=lambda s: s['nome'])
            blocchi.append(
                '<h3 class="sotto-tit"><a href="/provincia/%s/">%s</a> '
                '<span class="tenue">%d spot</span></h3>%s'
                % (slug(d['PROVINCE'][pv]), e(d['PROVINCE'][pv]), len(v),
                   righe([('/spot/%s/' % s['slug'], s['nome'],
                           '%s · %s' % (s['comune'], s['acqua'])) for s in v])))
        dove_html = ('<h2>Dove si pesca in Emilia-Romagna</h2>'
                     '<p class="mini tenue" style="margin-top:8px">%d spot dichiarano la presenza '
                     'di questa specie.</p>%s' % (len(dove), ''.join(blocchi)))

    # In quali acque sta, non solo in quali schede. «Dove si trova il luccio in
    # Emilia-Romagna» e' una domanda sui fiumi, e l'elenco di spot da solo non
    # la stava rispondendo: qui i corsi d'acqua stanno per nome, e portano alla
    # pagina del corso d'acqua invece che a un tratto solo.
    acque_html = ''
    if dove:
        per_acqua = {}
        for s in dove:
            per_acqua.setdefault(s['acqua'], []).append(s)
        ordinate = sorted(per_acqua.items(), key=lambda x: (-len(x[1]), x[0]))
        per_tipo = {}
        for s in dove:
            per_tipo.setdefault(s['tipo'], set()).add(s['acqua'])
        conte = elenco([conta_tipo(len(v), k)
                        for k, v in sorted(per_tipo.items(), key=lambda x: -len(x[1]))])
        acque_html = (
            '<h2>In quali acque si trova</h2>'
            '<p class="mini tenue" style="margin-top:8px;max-width:66ch">%s dichiarano questa '
            'specie: %s.</p><p class="mini" style="margin-top:12px;max-width:72ch">%s</p>'
            % ('%d corsi d\'acqua' % len(ordinate) if len(ordinate) > 1 else 'Un corso d\'acqua',
               conte,
               ' · '.join(
                   ('<a href="/acqua/%s/">%s</a> <span class="tenue">(%d)</span>'
                    % (hub['acqua'][a], e(a), len(v))) if a in hub['acqua']
                   else '%s <span class="tenue">(%d)</span>' % (e(a), len(v))
                   for a, v in ordinate)))

    # La curva mensile era gia' nei dati e non usciva da nessuna parte: si vedeva
    # solo il picco, in «Mesi di punta». E' l'unica cosa che qui si sappia sulla
    # stagione e vale piu' di tre nomi di mese.
    # Dodici mesi in una tabella diventano dodici schede impilate sul telefono,
    # e da li' passa l'ottanta per cento di chi legge: mezzo schermo a testa per
    # dire un numero, e il resto della pagina spinto sotto. Una striscia di
    # dodici colonne dice la stessa cosa in un colpo d'occhio e sta in una riga.
    picco = max(sp['mesi']) or 1
    quote = [(m, round(100 * v / picco)) for m, v in zip(MESI, sp['mesi'])]
    punta = set(mesi_punta(sp['mesi']))
    mesi_html = ('<h2>Mese per mese</h2>'
                 '<p class="mini tenue" style="margin-top:8px;max-width:66ch">Quanto è attiva nel '
                 'corso dell\'anno, sul suo massimo: %s il periodo migliore. La curva entra '
                 'nell\'indice del giorno insieme a temperatura, portata e meteo.</p>'
                 '<ol class="calendario">%s</ol>'
                 % (elenco(mesi_punta(sp['mesi'])),
                    ''.join('<li%s aria-label="%s: %d%% dell\'attività massima">'
                            '<span class="asta"><i style="height:%d%%"></i></span>'
                            '<b>%s</b><s>%d%%</s></li>'
                            % (' class="punta"' if m in punta else '', m, q, max(q, 2), m[:3], q)
                            for m, q in quote)))

    # Le domande cominciano dal nome, invece di infilarlo dentro la frase: negli
    # elenchi non c'e' il genere, e «la misura minima del cheppia» o «della
    # muggine» sarebbero due errori scritti da un programma che tira a indovinare
    # sull'ultima lettera. Cosi' la domanda e' giusta per tutte e quaranta.
    nome = sp['nome']
    faq = [
        ('%s: qual è la misura minima in Emilia-Romagna?' % nome,
         ('%d cm, dall\'Allegato 2 del Regolamento regionale 1/2018.' % sp['misuraMin'])
         if sp.get('misuraMin')
         else 'Il regolamento regionale non fissa una misura minima per questa specie. I '
              'calendari ittici provinciali possono aggiungerne una.'),
        ('%s: quando è vietata la pesca?' % nome,
         'Periodo di divieto: %s. Fuori da quel periodo il limite è %s.'
         % (sp['divietoTesto'],
            'la pesca resta vietata' if sp.get('limiteGiorno') == 0
            else ('%d capi al giorno' % sp['limiteGiorno'] if sp.get('limiteGiorno')
                  else 'quello generale, senza un tetto per specie'))),
        ('%s: dove si trova in Emilia-Romagna?' % nome,
         ('%d spot descritti dichiarano questa specie, su %s.'
          % (len(dove), elenco(sorted({s['acqua'] for s in dove})[:6]))) if dove else ''),
        ('%s: con che esche si pesca?' % nome,
         ('Le esche indicate sono: %s. Le tecniche: %s.'
          % (elenco(sp['esche']), elenco(sp.get('tecniche') or ['nessuna indicata'])))
         if sp.get('esche') else ''),
        ('%s: a che temperatura dell\'acqua si alimenta?' % nome,
         'Fra %d e %d °C, con la massima attività fra %d e %d °C. Le ore migliori sono %s, i mesi '
         'di punta %s.' % (sp['tLive'][0], sp['tLive'][1], sp['tOpt'][0], sp['tOpt'][1],
                           ORE.get(sp['luce'], sp['luce']), elenco(mesi_punta(sp['mesi'])))),
    ]

    # Collegamenti fra specie: prima quelle dello stesso gruppo, poi si completa
    # scorrendo l'elenco alfabetico in cerchio. Serve a garantire un minimo di
    # collegamenti in entrata anche alle specie che quasi nessuno spot dichiara:
    # bosega, pigo, sanguinerola, savetta e triotto ne avevano due in tutto, ed
    # erano le ultime della coda del crawler.
    tutte = sorted(d['SPECIE'].values(), key=lambda o: o['nome'])
    simili = [o for o in tutte if o['id'] != sp['id'] and o['gruppo'] == sp['gruppo']][:8]
    if len(simili) < 6:
        i = next(k for k, o in enumerate(tutte) if o['id'] == sp['id'])
        visti = {sp['id']} | {o['id'] for o in simili}
        for k in range(1, len(tutte)):
            o = tutte[(i + k) % len(tutte)]
            if o['id'] not in visti:
                simili.append(o)
                visti.add(o['id'])
            if len(simili) >= 6:
                break
    sim_html = ('<h2>Altre specie</h2>'
                '<p class="mini" style="margin-top:10px;max-width:72ch">%s</p>'
                % ' · '.join('<a href="/specie/%s/">%s</a>' % (o['slug'], e(o['nome']))
                             for o in simili)) if simili else ''

    corpo = f"""<span class="occhio acc">{e(sp['gruppo'])}</span>
<h1>{e(sp['nome'])} <span class="h1-luogo">pesca in Emilia-Romagna</span></h1>
<div class="luogo sci-tit">{e(sp['sci'])}</div>
<div class="segni">{''.join(segni)}</div>
{cta('/#specie', 'Apri la scheda con il disegno e i confronti')}
<h2>Regole e biologia</h2>
<div class="voci">{dati_html}</div>
{mesi_html}
{prof_html}
{modo_html}
{dritte_html}
{acque_html}
{dove_html}
{faq_html(faq)}
{sim_html}
<p class="mini tenue" style="margin-top:26px;max-width:72ch">Misure minime, limiti e periodi di
  divieto dall'Allegato 2 del <a href="/regole/">Regolamento regionale 1/2018</a>, come modificato
  dal 1/2020. I calendari ittici provinciali possono essere più restrittivi.</p>"""

    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'Article',
        'headline': '%s (%s): regole, biologia e spot in Emilia-Romagna' % (sp['nome'], sp['sci']),
        'description': desc,
        'url': base + '/specie/%s/' % sp['slug'],
        'image': base + '/assets/og.png',
        'inLanguage': 'it',
        'isPartOf': {'@type': 'WebSite', '@id': base + '/#sito'},
        'about': {'@type': 'Thing', 'name': sp['nome'],
                  'alternateName': sp['sci']},
    }, faq_ld(faq)]
    u = '/specie/%s/' % sp['slug']
    return u, pagina(base, u, tit, desc, corpo, ld, briciole)


# ---------------------------------------------------------------- corsi d'acqua e comuni

# Quante schede servono perche' un corso d'acqua o un comune meriti una pagina
# propria. Con una sola la pagina sarebbe il doppione della scheda: stesso
# titolo, stesso elenco, un solo link dentro. Da due in su c'e' qualcosa da
# mettere insieme che nella singola scheda non c'e'.
SOGLIA_HUB = 2

# Quasi tutti i nomi d'acqua sono maschili (il fiume, il torrente, il cavo, il
# canale, il lago, il mare, il collettore, il Po). Le eccezioni sono poche e
# note, e restano qui invece che in un indovinello sulla desinenza.
ACQUE_FEMMINILI = ('sacca', 'valle', 'foce', 'cava', 'darsena', 'fossa', 'roggia',
                   'chiusa', 'diga', 'lanca')


def nel(nome):
    """«nel Fiume Po», «nella Sacca di Goro»."""
    return 'nella' if nome.split()[0].lower() in ACQUE_FEMMINILI else 'nel'


def raggruppa(spot, chiave):
    """Gli spot per corso d'acqua o per comune, solo dove sono almeno SOGLIA_HUB."""
    g = {}
    for s in spot:
        g.setdefault(s[chiave], []).append(s)
    return {k: sorted(v, key=lambda s: s['nome'])
            for k, v in g.items() if len(v) >= SOGLIA_HUB}


def specie_diffuse(d, spot, quante=10):
    """Le specie piu' dichiarate da un gruppo di spot, con quante volte."""
    freq = {}
    for s in spot:
        for x in s.get('specie', []):
            if x in d['SPECIE']:
                freq[x] = freq.get(x, 0) + 1
    return sorted(freq.items(), key=lambda x: (-x[1], d['SPECIE'][x[0]]['nome']))[:quante]


def pagina_acqua(d, nome, spot, base, oggi=None, hub=None):
    """Un corso d'acqua intero, con tutti i suoi spot.

    Le ricerche che il sito prendeva di piu' erano i nomi delle acque
    («torrente leo», «cavo napoleonico», «fiume ceno»), e non c'era una pagina
    per nessuna: rispondevano due o tre schede di tratti diversi, che si
    toglievano posizione a vicenda. Questa e' la pagina che mancava.
    """
    oggi = oggi or {}
    hub = hub or {'acqua': {}, 'comune': {}}
    sg = slug(nome)
    u = '/acqua/%s/' % sg
    # Il tipo e' quello della maggioranza dei tratti, non quello del primo in
    # ordine alfabetico: il Po di Volano ha due tratti di fiume e uno di canale,
    # e chiamarlo «Canale» dipendeva da come si ordinavano i nomi.
    conte_tipo = collections.Counter(s['tipo'] for s in spot)
    comune_tipo = min(conte_tipo, key=lambda t: (-conte_tipo[t], t))
    tipo = TIPI.get(comune_tipo, comune_tipo.capitalize())
    prov = sorted({d['PROVINCE'][s['prov']] for s in spot})
    comuni = sorted({s['comune'] for s in spot})

    tit = titolo('%s: dove pescare, %d spot' % (nome, len(spot)))
    desc = cresci('I %d spot di pesca sul %s.' % (len(spot), nome),
                  ['A %s.' % elenco(comuni[:4]) if len(comuni) > 1
                   else 'A %s.' % comuni[0],
                   'Accessi, fondale, specie dichiarate, esche e regole.',
                   'Con l\'indice del giorno.'])
    briciole = [('/', 'Oggi'), ('/acqua/', 'Corsi d\'acqua'), (None, nome)]

    # «da Fanano a Fanano» quando il corso d'acqua sta in un comune solo, e
    # «da Bardi a Varsi» quando ce ne sono due: la seconda sembra dire monte e
    # valle, ma l'ordine e' alfabetico e non sa da che parte scorre l'acqua.
    dove_comuni = ('nel comune di %s' % e(comuni[0]) if len(comuni) == 1
                   else 'in %d comuni: %s' % (len(comuni), e(elenco(comuni))))

    top = specie_diffuse(d, spot)
    cat = sorted({d['CATEGORIE'][s['categoria']]['nome'] for s in spot})
    nk = [s for s in spot if s.get('noKill')]

    dati = [
        ('Spot', '%d, in %s' % (len(spot), elenco(['provincia di ' + p for p in prov]))),
        ('Comuni attraversati', elenco(comuni)),
        ('Categorie delle acque', elenco(cat)),
        ('Tratti no kill', elenco([s['nome'] for s in nk]) if nk else ''),
    ]

    per_prov = {}
    for s in spot:
        per_prov.setdefault(s['prov'], []).append(s)
    blocchi = []
    for pv in [k for k in d['PROVINCE'] if k in per_prov]:
        v = per_prov[pv]
        blocchi.append(
            '<h3 class="sotto-tit"><a href="/provincia/%s/">%s</a> '
            '<span class="tenue">%d spot</span></h3>%s'
            % (slug(d['PROVINCE'][pv]), e(d['PROVINCE'][pv]), len(v),
               righe([('/spot/%s/' % s['slug'], s['nome'],
                       '%s · %s' % (s['comune'], TIPI.get(s['tipo'], s['tipo']).lower()))
                      for s in v])))

    faq = [
        ('Dove si pesca %s %s?' % (nel(nome), nome),
         'Su questo corso d\'acqua ci sono %d spot descritti, in %s: %s.'
         % (len(spot), elenco(comuni), elenco([s['nome'] for s in spot]))),
        ('Che pesci ci sono %s %s?' % (nel(nome), nome),
         ('Le specie piu\' dichiarate sono: %s.'
          % elenco(['%s (%d spot)' % (d['SPECIE'][x]['nome'].lower(), n) for x, n in top[:6]]))
         if top else ''),
        ('Ci sono tratti no kill %s %s?' % (nel(nome), nome),
         ('Sì: %s.' % elenco([s['nome'] for s in nk])) if nk
         else 'Fra gli spot descritti su questo corso d\'acqua non ce ne sono di no kill. '
              'I calendari ittici provinciali cambiano ogni anno: verifica prima di uscire.'),
    ]

    corpo = f"""<span class="occhio acc">{e(tipo)} · Emilia-Romagna</span>
<h1>{e(nome)} <span class="h1-luogo">dove pescare, spot per spot</span></h1>
<div class="luogo">{e(elenco(prov))}</div>
<div class="intro">{len(spot)} spot descritti {nel(nome)} {e(nome)}, {dove_comuni}. Per ognuno:
  come arrivare, i punti di accesso, il fondale, le specie dichiarate, le esche e le regole
  locali.</div>
{riga_oggi(spot, oggi, 'su questo corso d\'acqua')}
<h2>Il corso d'acqua</h2>
<div class="voci">{voci_html(dati)}</div>
<h2>Le specie più diffuse</h2>
{righe([('/specie/%s/' % d['SPECIE'][x]['slug'], d['SPECIE'][x]['nome'],
         '%d spot su %d · %s' % (n, len(spot), d['SPECIE'][x]['sci'])) for x, n in top])}
<h2>Tutti gli spot, provincia per provincia</h2>
{''.join(blocchi)}
{faq_html(faq)}
<p class="mini tenue" style="margin-top:26px;max-width:72ch">Le categorie delle acque e i periodi
  di divieto le fissa la Regione, ma il calendario ittico della provincia può essere più
  restrittivo: prima di partire, il <a href="/regole/">quadro delle regole</a>.</p>"""

    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'ItemList',
        'name': 'Spot di pesca %s %s' % (nel(nome), nome),
        'description': desc, 'url': base + u,
        'numberOfItems': len(spot),
        'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': s['nome'],
                             'url': base + '/spot/%s/' % s['slug']}
                            for i, s in enumerate(spot)],
    }, faq_ld(faq)]
    return u, pagina(base, u, tit, desc, corpo, ld, briciole,
                     modificato=oggi.get('giorno') if migliore_oggi(spot, oggi)[0] else None)


def pagina_comune(d, nome, spot, base, oggi=None, hub=None):
    """Un comune con piu' di uno spot.

    «dove pescare a <comune>» e' la domanda per cui il sito esiste, ed era
    l'unica a cui non rispondeva nessuna pagina: c'erano le nove province, che
    sono troppo larghe, e le singole schede, che sono troppo strette.
    """
    oggi = oggi or {}
    hub = hub or {'acqua': {}, 'comune': {}}
    sg = slug(nome)
    u = '/comune/%s/' % sg
    prov = d['PROVINCE'][spot[0]['prov']]
    acque = sorted({s['acqua'] for s in spot})

    # Nove comuni su dieci portano il nome del capoluogo di provincia, e per
    # quelli «nel comune di Rimini, in provincia di Rimini» e una briciola
    # «Rimini / Rimini» dicono due volte la stessa parola.
    omonimo = nome == prov
    tit = titolo('Dove pescare a %s: %d spot' % (nome, len(spot)))
    desc = cresci('I %d spot di pesca nel comune di %s%s.'
                  % (len(spot), nome, '' if omonimo else ' (%s)' % prov),
                  ['Su %s.' % elenco(acque[:3]),
                   'Accessi, specie dichiarate, esche e regole.',
                   'Con l\'indice del giorno.'])
    briciole = [('/', 'Oggi'), ('/comune/', 'Comuni')]
    if not omonimo:
        briciole.append(('/provincia/%s/' % slug(prov), prov))
    briciole.append((None, nome))

    top = specie_diffuse(d, spot)
    scorci = []
    for t, k in (('No kill', 'noKill'), ('Con i bambini', 'bimbi'),
                 ('Postazioni accessibili', 'disabili'), ('Pesca notturna ammessa', 'notturna')):
        v = [s for s in spot if s.get(k)]
        if v:
            scorci.append((t, ' · '.join('<a href="/spot/%s/">%s</a>'
                                         % (s['slug'], e(s['nome'])) for s in v), True))

    acque_html = ' · '.join(
        ('<a href="/acqua/%s/">%s</a>' % (hub['acqua'][a], e(a))) if a in hub['acqua'] else e(a)
        for a in acque)

    faq = [
        ('Dove si pesca a %s?' % nome,
         'Nel comune di %s ci sono %d spot descritti: %s. Le acque sono %s.'
         % (nome, len(spot), elenco([s['nome'] for s in spot]), elenco(acque))),
        ('Che pesci si prendono a %s?' % nome,
         ('Le specie piu\' dichiarate sono: %s.'
          % elenco(['%s (%d spot)' % (d['SPECIE'][x]['nome'].lower(), n) for x, n in top[:6]]))
         if top else ''),
        ('Serve la licenza per pescare a %s?' % nome,
         'Sì. In Emilia-Romagna serve la licenza di tipo B con il versamento annuale, valida in '
         'tutta la regione. Il calendario ittico della provincia di %s può aggiungere divieti '
         'locali.' % prov),
    ]

    corpo = f"""<span class="occhio acc">{e(prov)} · Emilia-Romagna</span>
<h1>Dove pescare a {e(nome)}</h1>
<div class="luogo">{acque_html}</div>
<div class="intro">{len(spot)} spot nel comune di {e(nome)}, in
  <a href="/provincia/{slug(prov)}/">provincia di {e(prov)}</a>. Per ognuno: come arrivare, i punti
  di accesso, il fondale, le specie dichiarate, le esche e le regole locali.</div>
{riga_oggi(spot, oggi, 'nel comune')}
{('<h2>Scorciatoie</h2><div class="voci">' + voci_html(scorci) + '</div>') if scorci else ''}
<h2>Gli spot</h2>
{righe([('/spot/%s/' % s['slug'], s['nome'],
         '%s · %s' % (s['acqua'], TIPI.get(s['tipo'], s['tipo']).lower())) for s in spot])}
<h2>Le specie più diffuse</h2>
{righe([('/specie/%s/' % d['SPECIE'][x]['slug'], d['SPECIE'][x]['nome'],
         '%d spot su %d · %s' % (n, len(spot), d['SPECIE'][x]['sci'])) for x, n in top])}
{faq_html(faq)}
<p class="mini tenue" style="margin-top:26px;max-width:72ch">Zone, divieti e categorie delle acque
  cambiano ogni anno: controlla il calendario ittico della provincia di {e(prov)} e il
  <a href="/regole/">quadro delle regole</a>.</p>"""

    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'ItemList',
        'name': 'Spot di pesca a %s' % nome, 'description': desc, 'url': base + u,
        'numberOfItems': len(spot),
        'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': s['nome'],
                             'url': base + '/spot/%s/' % s['slug']}
                            for i, s in enumerate(spot)],
    }, faq_ld(faq)]
    return u, pagina(base, u, tit, desc, corpo, ld, briciole,
                     modificato=oggi.get('giorno') if migliore_oggi(spot, oggi)[0] else None)


# ---------------------------------------------------------------- province

def pagina_provincia(d, sigla, base, oggi=None, hub=None):
    oggi = oggi or {}
    hub = hub or {'acqua': {}, 'comune': {}}
    nome = d['PROVINCE'][sigla]
    sp = sorted((s for s in d['SPOT'] if s['prov'] == sigla), key=lambda s: s['nome'])
    u = '/provincia/%s/' % slug(nome)
    tit = titolo('Dove pescare in provincia di %s: %d spot' % (nome, len(sp)))
    desc = taglia('I %d spot di pesca della provincia di %s: fiumi, torrenti, laghi e canali, '
                  'con accessi, specie e regole. Indice del giorno su portata e meteo.'
                  % (len(sp), nome), 158)
    briciole = [('/', 'Oggi'), ('/spot/', 'Spot'), ('/provincia/', 'Province'), (None, nome)]

    per_tipo = {}
    for s in sp:
        per_tipo.setdefault(s['tipo'], []).append(s)
    conte = elenco([conta_tipo(len(v), k)
                    for k, v in sorted(per_tipo.items(), key=lambda x: -len(x[1]))])

    freq = {}
    for s in sp:
        for x in s.get('specie', []):
            if x in d['SPECIE']:
                freq[x] = freq.get(x, 0) + 1
    top = sorted(freq.items(), key=lambda x: (-x[1], d['SPECIE'][x[0]]['nome']))[:10]
    top_html = righe([('/specie/%s/' % d['SPECIE'][x]['slug'], d['SPECIE'][x]['nome'],
                       '%d spot · %s' % (n, d['SPECIE'][x]['sci'])) for x, n in top])

    acque = {}
    for s in sp:
        acque.setdefault(s['acqua'], []).append(s)
    # Il nome del corso d'acqua era testo morto: adesso, dove esiste, porta alla
    # pagina che raccoglie tutti i suoi tratti, anche quelli fuori provincia.
    blocchi = []
    for a in sorted(acque, key=lambda a: (-len(acque[a]), a)):
        v = acque[a]
        eti = ('<a href="/acqua/%s/">%s</a>' % (hub['acqua'][a], e(a))
               if a in hub['acqua'] else e(a))
        blocchi.append('<h3 class="sotto-tit">%s <span class="tenue">%d</span></h3>%s'
                       % (eti, len(v), righe([
                           ('/spot/%s/' % s['slug'], s['nome'],
                            '%s · %s%s' % (s['comune'], TIPI.get(s['tipo'], s['tipo']).lower(),
                                           ', no kill' if s.get('noKill') else ''))
                           for s in sorted(v, key=lambda s: s['nome'])])))

    com = sorted({s['comune'] for s in sp if s['comune'] in hub['comune']})
    com_html = (('<h2>Comune per comune</h2>'
                 '<p class="mini tenue" style="margin-top:8px;max-width:66ch">I comuni della '
                 'provincia con più di uno spot descritto.</p>'
                 '<p class="mini" style="margin-top:12px;max-width:72ch">%s</p>')
                % ' · '.join('<a href="/comune/%s/">%s</a>' % (hub['comune'][c], e(c))
                             for c in com)) if com else ''

    nk = [s for s in sp if s.get('noKill')]
    bimbi = [s for s in sp if s.get('bimbi')]
    acc = [s for s in sp if s.get('disabili')]
    scorci = []
    for t, v in (('No kill', nk), ('Con i bambini', bimbi), ('Postazioni accessibili', acc)):
        if v:
            scorci.append('<div class="voce"><h3>%s</h3><div><p>%s</p></div></div>'
                          % (e(t), ' · '.join('<a href="/spot/%s/">%s</a>'
                                              % (s['slug'], e(s['nome'])) for s in v)))

    faq = [
        ('Dove si pesca in provincia di %s?' % nome,
         '%d spot descritti, su %s. I corsi d\'acqua con più tratti sono %s.'
         % (len(sp), conte, elenco(sorted(acque, key=lambda a: (-len(acque[a]), a))[:5]))),
        ('Che pesci ci sono in provincia di %s?' % nome,
         ('Le specie più dichiarate sono: %s.'
          % elenco(['%s (%d spot)' % (d['SPECIE'][x]['nome'].lower(), n) for x, n in top[:6]]))
         if top else ''),
        ('Ci sono tratti no kill in provincia di %s?' % nome,
         ('Sì: %s.' % elenco([s['nome'] for s in nk])) if nk
         else 'Fra gli spot descritti in questa provincia non ce ne sono di no kill. I calendari '
              'ittici provinciali cambiano ogni anno: verifica prima di uscire.'),
    ]

    corpo = f"""<span class="occhio acc">Emilia-Romagna</span>
<h1>Dove pescare in provincia di {e(nome)}</h1>
<div class="intro">{len(sp)} spot in provincia di {e(nome)}: {e(conte)}.
  Per ognuno: come arrivare, i punti di accesso, il fondale, le specie dichiarate, le esche e le
  regole locali.</div>
{riga_oggi(sp, oggi, 'in provincia') or cta('/', "Vedi l'indice di oggi, spot per spot")}
{('<h2>Scorciatoie</h2><div class="voci">' + ''.join(scorci) + '</div>') if scorci else ''}
<h2>Le specie più diffuse</h2>
{top_html}
{com_html}
<h2>Tutti gli spot, per corso d'acqua</h2>
{''.join(blocchi)}
{faq_html(faq)}
<p class="mini tenue" style="margin-top:26px;max-width:72ch">Zone, divieti e categorie delle acque
  cambiano ogni anno: controlla il calendario ittico della provincia di {e(nome)} e il
  <a href="/regole/">quadro delle regole</a>.</p>"""

    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'ItemList',
        'name': 'Spot di pesca in provincia di %s' % nome,
        'description': desc, 'url': base + u,
        'numberOfItems': len(sp),
        'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': s['nome'],
             'url': base + '/spot/%s/' % s['slug']} for i, s in enumerate(sp)],
    }, faq_ld(faq)]
    return u, pagina(base, u, tit, desc, corpo, ld, briciole,
                     modificato=oggi.get('giorno') if migliore_oggi(sp, oggi)[0] else None)


# ---------------------------------------------------------------- indici

def pagina_indice_provincia(d, base):
    """/provincia/ esisteva come cartella e non come pagina: chi tagliava
       l'indirizzo a mano, e chi lo indovinava, trovava un 404. Le nove
       province, invece, sono una domanda che la gente fa."""
    u = '/provincia/'
    tit = titolo('Dove pescare provincia per provincia')
    desc = ('Le nove province dell\'Emilia-Romagna: %d spot di pesca su fiumi, torrenti, laghi, '
            'canali e mare, con accessi, specie dichiarate e regole locali.' % len(d['SPOT']))
    briciole = [('/', 'Oggi'), ('/spot/', 'Spot'), (None, 'Province')]
    voci = []
    for sig, nome in d['PROVINCE'].items():
        sp = [s for s in d['SPOT'] if s['prov'] == sig]
        if not sp:
            continue
        acque = {}
        for s in sp:
            acque.setdefault(s['acqua'], 0)
            acque[s['acqua']] += 1
        prime = [a for a, _ in sorted(acque.items(), key=lambda x: (-x[1], x[0]))[:3]]
        voci.append(('/provincia/%s/' % slug(nome), nome,
                     '%d spot · %s' % (len(sp), elenco(prime))))
    voci.sort(key=lambda v: -int(v[2].split()[0]))
    corpo = f"""<span class="occhio acc">Emilia-Romagna</span>
<h1>Dove pescare, provincia per provincia</h1>
<div class="intro">{len(d['SPOT'])} spot in nove province, dal Trebbia al Marecchia e dal Po al
  mare. Ogni elenco è ordinato per corso d'acqua, con le specie più diffuse della provincia e le
  scorciatoie no kill, con i bambini e accessibili.</div>
{cta('/', "Vedi l'indice di oggi, spot per spot")}
{righe(voci)}
<p class="mini tenue" style="margin-top:26px;max-width:72ch">Le categorie delle acque, le zone e i
  periodi di divieto li fissa la Regione, ma il calendario ittico della provincia può essere più
  restrittivo: prima di partire, il <a href="/regole/">quadro delle regole</a>.</p>"""
    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'ItemList',
        'name': 'Province dell\'Emilia-Romagna', 'numberOfItems': len(voci),
        'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': t,
                             'url': base + uu}
                            for i, (uu, t, _) in enumerate(voci)]}]
    return u, pagina(base, u, tit, desc, corpo, ld, briciole)


def pagina_indice_acqua(d, base, gruppi, hub):
    """/acqua/: l'elenco dei corsi d'acqua che hanno una pagina propria."""
    u = '/acqua/'
    n = len(gruppi)
    tit = titolo('Dove pescare, fiume per fiume: %d corsi d\'acqua' % n)
    desc = taglia('I %d corsi d\'acqua dell\'Emilia-Romagna con più di uno spot descritto: Po, '
                  'Reno, Trebbia, Secchia, Panaro, Marecchia e gli altri, con gli spot di ogni '
                  'tratto.' % n, 158)
    briciole = [('/', 'Oggi'), (None, 'Corsi d\'acqua')]
    voci = []
    for nome in sorted(gruppi, key=lambda a: (-len(gruppi[a]), a)):
        v = gruppi[nome]
        prov = sorted({d['PROVINCE'][s['prov']] for s in v})
        voci.append(('/acqua/%s/' % hub['acqua'][nome], nome,
                     '%d spot · %s' % (len(v), elenco(prov))))
    corpo = f"""<span class="occhio acc">Emilia-Romagna</span>
<h1>Dove pescare, fiume per fiume</h1>
<div class="intro">I {n} corsi d'acqua con più di uno spot descritto, dal Po al Marecchia. Ogni
  pagina raccoglie tutti i tratti di quel fiume, torrente o canale, con le specie più diffuse e
  l'indice del giorno. Gli altri corsi d'acqua hanno un solo spot: si trovano
  <a href="/spot/">nell'elenco completo</a>.</div>
{righe(voci)}"""
    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'ItemList',
        'name': 'Corsi d\'acqua dell\'Emilia-Romagna', 'numberOfItems': len(voci),
        'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': t,
                             'url': base + uu} for i, (uu, t, _) in enumerate(voci)]}]
    return u, pagina(base, u, tit, desc, corpo, ld, briciole)


def pagina_indice_comune(d, base, gruppi, hub):
    """/comune/: l'elenco dei comuni che hanno una pagina propria."""
    u = '/comune/'
    n = len(gruppi)
    tit = titolo('Dove pescare, comune per comune: %d comuni' % n)
    desc = taglia('I %d comuni dell\'Emilia-Romagna con più di uno spot di pesca descritto, da '
                  'Ravenna a Comacchio: accessi, specie e regole di ognuno.' % n, 158)
    briciole = [('/', 'Oggi'), (None, 'Comuni')]
    voci = []
    for nome in sorted(gruppi, key=lambda c: (-len(gruppi[c]), c)):
        v = gruppi[nome]
        voci.append(('/comune/%s/' % hub['comune'][nome], nome,
                     '%d spot · %s' % (len(v), d['PROVINCE'][v[0]['prov']])))
    corpo = f"""<span class="occhio acc">Emilia-Romagna</span>
<h1>Dove pescare, comune per comune</h1>
<div class="intro">I {n} comuni con più di uno spot descritto. Ogni pagina raccoglie gli spot di
  quel comune, le acque che lo attraversano, le specie più diffuse e l'indice del giorno. I comuni
  con un solo spot si trovano <a href="/spot/">nell'elenco completo</a> e
  <a href="/provincia/">provincia per provincia</a>.</div>
{righe(voci)}"""
    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'ItemList',
        'name': 'Comuni dell\'Emilia-Romagna con spot di pesca', 'numberOfItems': len(voci),
        'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': t,
                             'url': base + uu} for i, (uu, t, _) in enumerate(voci)]}]
    return u, pagina(base, u, tit, desc, corpo, ld, briciole)


def pagina_indice_spot(d, base):
    u = '/spot/'
    n = len(d['SPOT'])
    tit = titolo('Tutti i %d spot di pesca in Emilia-Romagna' % n)
    desc = taglia('L\'elenco completo: %d spot di pesca in Emilia-Romagna su fiumi, torrenti, '
                  'laghi, canali e mare, provincia per provincia, con accessi, specie e regole.'
                  % n, 158)
    briciole = [('/', 'Oggi'), (None, 'Spot')]
    blocchi = []
    for sig, nome in d['PROVINCE'].items():
        v = sorted((s for s in d['SPOT'] if s['prov'] == sig), key=lambda s: s['nome'])
        if not v:
            continue
        blocchi.append(
            '<h2 class="sotto-tit"><a href="/provincia/%s/">%s</a> '
            '<span class="tenue">%d spot</span></h2>%s'
            % (slug(nome), e(nome), len(v), righe([
                ('/spot/%s/' % s['slug'], s['nome'],
                 '%s · %s' % (s['comune'], s['acqua'])) for s in v])))
    corpo = f"""<h1>Tutti gli spot</h1>
<div class="intro">{len(d['SPOT'])} spot in Emilia-Romagna, divisi per <a
  href="/provincia/">provincia</a>. Ogni scheda dice come arrivare, dove ci si ferma, cosa nuota
  e cosa dice la legge. L'ordine del giorno, calcolato su portata e meteo, è
  nell'<a href="/">indice di oggi</a>.</div>
{''.join(blocchi)}"""
    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'ItemList',
        'name': 'Spot di pesca in Emilia-Romagna', 'numberOfItems': len(d['SPOT']),
        'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': s['nome'],
                             'url': base + '/spot/%s/' % s['slug']}
                            for i, s in enumerate(d['SPOT'])]}]
    return u, pagina(base, u, tit, desc, corpo, ld, briciole)


def pagina_indice_specie(d, base):
    u = '/specie/'
    tit = titolo('Le %d specie ittiche dell\'Emilia-Romagna' % len(d['SPECIE']))
    desc = ('Le specie di pesce delle acque dell\'Emilia-Romagna: misura minima, periodo di '
            'divieto, capi al giorno, esche e tecniche, con gli spot dove si trovano.')
    briciole = [('/', 'Oggi'), (None, 'Specie')]
    blocchi = []
    for gr in d['GRUPPI_SPECIE']:
        v = sorted((s for s in d['SPECIE'].values() if s['gruppo'] == gr),
                   key=lambda s: s['nome'])
        if not v:
            continue
        blocchi.append('<h2 class="sotto-tit">%s</h2>%s' % (e(gr.capitalize()), righe([
            ('/specie/%s/' % s['slug'], s['nome'],
             '%s · %s' % (s['sci'], ('misura minima %d cm' % s['misuraMin'])
                          if s.get('misuraMin') else 'nessuna misura minima'))
            for s in v])))
    corpo = f"""<h1>Le specie</h1>
<div class="intro">{len(d['SPECIE'])} specie nelle acque della regione: cosa nuota dove, quando è
  attiva, a che profondità sta, con cosa si insidia e cosa dice la legge.</div>
{''.join(blocchi)}"""
    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'ItemList',
        'name': 'Specie ittiche dell\'Emilia-Romagna', 'numberOfItems': len(d['SPECIE']),
        'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': s['nome'],
                             'url': base + '/specie/%s/' % s['slug']}
                            for i, s in enumerate(sorted(d['SPECIE'].values(),
                                                         key=lambda s: s['nome']))]}]
    return u, pagina(base, u, tit, desc, corpo, ld, briciole)


# ---------------------------------------------------------------- regole

def pagina_regole(d, base):
    R = d['REGOLE']
    u = '/regole/'
    tit = titolo('Regole della pesca sportiva in Emilia-Romagna')
    desc = ('Licenze, attrezzi, limiti di prelievo, misure minime, periodi di divieto e zone '
            'delle acque in Emilia-Romagna, con i link ai testi ufficiali.')
    briciole = [('/', 'Oggi'), (None, 'Regole')]

    def gruppo(t, v, liv=False):
        voci = []
        for r in v:
            att = '<p class="att">%s</p>' % e(r['warn']) if r.get('warn') else ''
            voci.append('<div class="voce"><h3>%s</h3><div><p>%s</p>%s</div></div>'
                        % (e(r['t']), e(r['d']), att))
        return '<h2>%s</h2><div class="voci">%s</div>' % (e(t), ''.join(voci))

    tab = ''.join(
        '<tr><td><a href="/specie/%s/"><b>%s</b></a><span class="sci">%s</span></td>'
        '<td class="num" data-eti="Misura">%s</td>'
        '<td class="num" data-eti="Al giorno">%s</td>'
        '<td data-eti="Divieto">%s</td></tr>'
        % (s['slug'], e(s['nome']), e(s['sci']),
           (str(s['misuraMin']) + ' cm') if s.get('misuraMin') else '–',
           'vietata' if s.get('limiteGiorno') == 0 else (s.get('limiteGiorno') or '–'),
           e(s['divietoTesto']))
        for s in sorted(d['SPECIE'].values(), key=lambda s: s['nome']))

    zone = ''.join('<div class="voce"><h3>%s</h3><div><p>%s</p></div></div>'
                   % (e(c['nome']), e(c['desc'])) for c in d['CATEGORIE'].values())
    zone += ''.join('<div class="voce"><h3>%s (%s)</h3><div><p>%s</p></div></div>'
                    % (e(z['t']), e(z['sigla']), e(z['d'])) for z in R['zone'])

    fonti = ''.join('<li><a href="%s" target="_blank" rel="noopener noreferrer">%s</a></li>'
                    % (e(f['u']), e(f['t'])) for f in R['fonti'])

    corpo = f"""<h1>Le regole</h1>
<div class="intro">Licenze, attrezzi, limiti di prelievo, zone delle acque, divieti in vigore e
  sicurezza. Sintesi delle fonti regionali, con i link ai testi ufficiali.</div>
<p class="nota" style="margin-top:18px">{e(R['aggiornato'])} Questa è una sintesi:
  <b>fa fede solo il testo ufficiale</b> del Regolamento regionale e del calendario ittico della
  tua provincia.</p>
{gruppo('Avvisi in vigore', R['avvisi'])}
{gruppo('Licenze e permessi', R['licenza'])}
{gruppo('Attrezzi ammessi', R['attrezzi'])}
{gruppo('Limiti di prelievo', R['limiti'])}
<h2>Misure minime e divieti, specie per specie</h2>
<p class="mini tenue" style="max-width:60ch;margin-top:8px">Allegato 2 al Regolamento regionale
  1/2018, come modificato dal 1/2020. Le specie alloctone non hanno misure minime né divieti
  regionali.</p>
<div class="scorre" style="margin-top:16px"><table class="dati">
  <thead><tr><th>Specie</th><th>Misura minima</th><th>Capi al giorno</th><th>Divieto</th></tr></thead>
  <tbody>{tab}</tbody></table></div>
<h2>Zone delle acque</h2>
<div class="voci">{zone}</div>
{gruppo('Sicurezza', R['sicurezza'])}
<h2>Fonti ufficiali</h2>
<ul class="fonti-elenco">{fonti}</ul>
{cta('/spot/', 'Vedi tutti gli spot, provincia per provincia')}"""

    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'Article',
        'headline': 'Regole della pesca sportiva in Emilia-Romagna',
        'description': desc, 'url': base + u, 'inLanguage': 'it',
        'isPartOf': {'@type': 'WebSite', '@id': base + '/#sito'},
        'citation': [f['t'] for f in R['fonti']],
    }]
    return u, pagina(base, u, tit, desc, corpo, ld, briciole)


# ---------------------------------------------------------------- metodo e privacy

VOCI_METODO = [
    ('Stagione', "Ogni specie ha una curva di attività mensile costruita sulla sua biologia e sui "
     "periodi indicati dalla guida regionale. Un cavedano a settembre e un cavedano a gennaio non "
     "sono lo stesso pesce."),
    ("Temperatura dell'acqua", "È il fattore che pesa di più, e nessuno la misura spot per spot. "
     "La stimiamo con un modello a inerzia termica: l'acqua segue la media dell'aria degli ultimi "
     "giorni, smorzata verso la temperatura media annua alla quota dello spot. Finestra e "
     "smorzamento cambiano con l'ambiente: tre giorni e forte smorzamento per un torrente sorgivo, "
     "sette e quasi nessuno per un canale di pianura, quattordici per un bacino profondo. Ogni tipo "
     "ha un tetto. È una stima dichiarata, non una misura."),
    ('Portata', "Dato reale: portata giornaliera in metri cubi al secondo dal modello idrologico "
     "GloFAS, confrontata con la mediana delle settimane precedenti nello stesso punto. Un rialzo "
     "del 15–40% accende barbi e siluri; oltre il 260% l'indice crolla e compare l'avviso di piena; "
     "sotto il 45% è magra. Su laghi, cave, mare e canali di bonifica non viene usata."),
    ('Pioggia e torbidità', "Pioggia delle 72 ore precedenti, quella prevista e lo scarto di "
     "portata, per stimare quanto è velata l'acqua. Poi il confronto con la preferenza di ogni "
     "specie: il barbo la ama, il temolo la detesta."),
    ('Pressione, luce, luna', "La variazione barometrica sul giorno prima premia le specie che si "
     "attivano con la pressione in calo, ma un crollo oltre gli 8 hPa penalizza tutti. Il cielo "
     "coperto premia i crepuscolari. La luna conta solo per i predatori notturni."),
    ('Divieti e presenza reale', "Una specie in divieto o protetta non viene esclusa: resta "
     "pescabile in catch and release, ma pesa il 34% e la scheda lo dichiara. Dove la guida "
     "regionale scrive «rari», la specie pesa il 42%."),
    ('La somma', "62% della specie migliore più 38% della media delle prime tre, poi i "
     "modificatori d'ambiente (piena, magra, temporali, vento, mare mosso, acqua fresca in "
     "giornata torrida, stagione consigliata) e una compressione esponenziale su 100. Il 100 non "
     "è raggiungibile: nessun giorno è perfetto."),
]

NON_SA = [
    "La pressione di pesca: un no-kill famoso di domenica è un altro posto.",
    "Gli orari puntuali dei rilasci delle dighe: gli avvisi ci sono, gli orari no.",
    "La torbidità reale, le schiuse di insetti, le chiusure decise ieri.",
    "Lo stato delle strade di crinale e dei sentieri in inverno.",
    "I regolamenti provinciali aggiornati: cambiano ogni anno e vanno letti.",
]


def pagina_metodo(d, base):
    u = '/metodo/'
    tit = titolo("Come nasce l'indice del giorno")
    desc = ("I sei fattori che ordinano gli spot: stagione, temperatura dell'acqua, portata "
            "GloFAS, pioggia, pressione e divieti. Con i limiti dichiarati del modello.")
    briciole = [('/', 'Oggi'), (None, 'Metodo')]
    voci = ''.join('<div class="voce"><h3>%s</h3><div><p>%s</p></div></div>' % (e(t), e(v))
                   for t, v in VOCI_METODO)
    corpo = f"""<h1>Come nasce l'indice</h1>
<div class="intro">Sei fattori misurabili, pesati e moltiplicati fra loro, specie per specie.
  Qui c'è tutto, comprese le cose che il modello <em>non</em> sa.</div>
<p class="nota" style="margin-top:18px">L'indice è una misura locale, non un voto. Dice come si
  presenta quel punto in quel giorno, non se è un bel posto.</p>
<h2>I sei fattori</h2>
<div class="voci">{voci}</div>
<h2>Cosa il modello non sa</h2>
<ul class="mini lista-limiti">{''.join('<li>%s</li>' % e(x) for x in NON_SA)}</ul>
<h2>Le mappe</h2>
<p class="mini" style="max-width:72ch;margin-top:12px">Nessun tile, nessuna libreria di mappe.
  Confini, 68 corsi d'acqua, 95 specchi d'acqua, strade, sentieri e parcheggi sono stati scaricati
  una volta sola da OpenStreetMap, semplificati e incorporati nel sito come percorsi SVG. Funziona
  offline e non mostra il tuo indirizzo IP a nessun server di mappe.</p>
<p class="mini" style="max-width:72ch;margin-top:12px">Ogni spot porta due punti. La
  <b>coordinata della scheda</b> dice di che pezzo di fiume parlano il meteo e la portata: sta sul
  corso d'acqua, e su un fiume largo cade in mezzo alla corrente. Il <b>punto di accesso</b>,
  quello che aprono i tasti delle mappe, è dove una strada arriva alla sponda e ci si può
  fermare. È calcolato sulla sponda disegnata e non sulla mezzeria, scartando i punti in acqua,
  quelli sui ponti e quelli sulla riva opposta, e pesando briglie, guadi, scivoli, pennelli e
  greti. I due punti possono distare qualche centinaio di metri: la cella della portata è larga
  chilometri, il posto dove si tira è largo dieci metri. Dove la sponda non è disegnata in mappa,
  la scheda lo dice.</p>
<h2>Le previsioni</h2>
<p class="mini" style="max-width:72ch;margin-top:12px">Le previsioni non le chiama il tuo browser:
  le scarica un flusso automatico ogni due ore e finiscono in un file servito insieme alla pagina.
  Prima schermata immediata, nessun limite di richieste da superare, e il tuo indirizzo IP non
  arriva a nessun servizio esterno. Se quel file manca o ha più di nove ore, si torna a chiamare
  Open-Meteo dal browser. Vedi la <a href="/privacy/">pagina privacy</a>.</p>
<h2>Dove compare l'indice</h2>
<p class="mini" style="max-width:72ch;margin-top:12px">In due posti, e viene dallo stesso calcolo.
  Qui nell'applicazione si aggiorna mentre la usi, con i sette giorni e la mappa. Nella scheda di
  ogni spot è scritto direttamente nella pagina al momento della pubblicazione, con accanto la data
  e l'ora del rilevamento: una pagina statica non può ricalcolare niente da sola, quindi dice
  quando è stata scritta invece di far finta di essere di adesso. Le due strade caricano lo stesso
  motore e lo stesso file di previsioni: se i numeri non coincidessero, sarebbe un errore.</p>
{cta('/', "Vedi l'indice di oggi")}"""
    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'Article',
        'headline': "Come nasce l'indice del giorno di Dove Pesco",
        'description': desc, 'url': base + u, 'inLanguage': 'it',
        'isPartOf': {'@type': 'WebSite', '@id': base + '/#sito'}}]
    return u, pagina(base, u, tit, desc, corpo, ld, briciole)


def pagina_privacy(d, base):
    u = '/privacy/'
    tit = titolo('Privacy e dati')
    desc = ('Nessun account, nessun cookie, nessun profilo. Un solo conteggio delle visite, '
            'anonimo e ospitato qui. Ecco cosa viene raccolto e cosa no.')
    briciole = [('/', 'Oggi'), (None, 'Privacy')]
    # Questa pagina diceva «non ci sono statistiche o strumenti di analisi»
    # mentre in fondo a ogni pagina, questa compresa, c'era il conteggio delle
    # visite. Il conteggio e' rimasto, perche' serve e non profila nessuno; a
    # cambiare e' la pagina, che adesso lo dichiara. Una promessa che il codice
    # smentisce vale meno di nessuna promessa.
    corpo = """<h1>Privacy e dati</h1>
<div class="intro">Nessun account, nessun cookie, nessun profilo, nessuna pubblicità e nessun dato
  venduto. C'è una cosa sola che viene contata, ed è scritta qui sotto per intero.</div>
<h2>Cosa non succede</h2>
<div class="voci">
  <div class="voce"><h3>Nessun cookie e nessun profilo</h3><div><p>Non viene scritto nessun cookie,
    non viene assegnato nessun identificatore che ti segua da una visita all'altra e non viene
    costruito nessun profilo. Non c'è niente da accettare perché non c'è niente che ti
    riconosca.</p></div></div>
  <div class="voce"><h3>Nessuna pubblicità</h3><div><p>Nessun inserzionista, nessun pixel di
    remarketing, nessuno scambio di dati con terzi. Il sito non ha nulla da vendere e i dati di chi
    lo apre non sono in vendita.</p></div></div>
  <div class="voce"><h3>Nessuna libreria di terze parti</h3><div><p>I caratteri sono serviti dalla
    cartella del sito, incorporati nel foglio di stile. Non c'è nessuna libreria esterna e nessun
    server di mappe: la geometria è incorporata nel sito come percorsi SVG.</p></div></div>
  <div class="voce"><h3>Nessuna posizione</h3><div><p>La posizione del dispositivo non viene mai
    richiesta. Le mappe funzionano senza saperla.</p></div></div>
</div>
<h2>Cosa succede</h2>
<div class="voci">
  <div class="voce"><h3>Il conteggio delle visite</h3><div><p>C'è un solo script di statistiche, ed
    è <a href="https://umami.is/" target="_blank" rel="noopener noreferrer">Umami</a>, il programma
    libero che conta le visite. Non gira su un servizio di terzi: sta su
    <span class="num">s.dovepescare.com</span>, che è questo dominio, e i numeri restano lì. Manda
    l'indirizzo della pagina aperta, il suo titolo, la pagina da cui arrivi, la lingua del browser
    e la misura dello schermo. Non scrive cookie: usa il deposito locale per una cosa sola, cioè
    ricordare che hai chiesto di non essere contato. Per distinguere i visitatori di una giornata
    calcola un'impronta e la getta ogni notte, e l'indirizzo IP non viene conservato accanto alla
    visita. Serve a sapere quali spot la gente cerca e quali pagine non vale la pena scrivere. Un
    blocco pubblicità lo ferma e il sito funziona identico.</p></div></div>
  <div class="voce"><h3>Le previsioni</h3><div><p>Meteo e portata arrivano da un file preparato
    a monte e servito insieme alla pagina, aggiornato ogni quattro ore. Il tuo browser legge quel
    file e non parla con nessun servizio esterno: il tuo indirizzo IP non esce di qui. Sotto la
    data compare l'ora del rilevamento.</p></div></div>
  <div class="voce"><h3>La riserva</h3><div><p>Se quel file manca o ha più di nove ore (per
    esempio aprendo il sito da una cartella, senza server) si torna a chiamare Open-Meteo
    direttamente dal browser, a poche richieste per volta, con i dati tenuti in cache 45 minuti nel
    deposito locale del browser. Anche in quel caso l'unica destinazione è Open-Meteo, e passano
    solo coordinate: nessun dato personale.</p></div></div>
  <div class="voce"><h3>I tasti verso le mappe</h3><div><p>Ogni scheda ha due tasti che aprono il
    punto in OpenStreetMap o in Google Maps. Sono collegamenti normali: finché non li tocchi, da
    quei servizi non arriva e non parte niente. Toccandoli si apre il loro sito, che a quel punto
    segue le proprie regole, e il tuo browser non gli dice da dove vieni perché ogni pagina qui
    dichiara <span class="num">no-referrer</span>. Sul telefono c'è anche «Naviga», che passa le
    coordinate all'applicazione di navigazione già installata, senza uscire dal
    dispositivo.</p></div></div>
  <div class="voce"><h3>Il deposito locale</h3><div><p>Il browser conserva le previsioni e i filtri
    scelti nel proprio deposito locale, sul tuo dispositivo. Non vengono inviati da nessuna parte e
    si cancellano svuotando i dati del sito.</p></div></div>
  <div class="voce"><h3>I registri del server</h3><div><p>Il sito è pubblicato su GitHub Pages, che
    tiene i propri registri di accesso secondo le sue condizioni, e su questo non abbiamo
    controllo. Come ogni server del mondo, anche quello che riceve il conteggio vede l'indirizzo IP
    da cui arriva la richiesta nel momento in cui la riceve: la differenza è che non lo scrive
    accanto alla visita.</p></div></div>
</div>
<h2>Le fonti dei dati</h2>
<div class="voci">
  <div class="voce"><h3>Schede degli spot</h3><div><p>«Itinerari di pesca sportiva in
    Emilia-Romagna» della Regione Emilia-Romagna, espansa per località.</p></div></div>
  <div class="voce"><h3>Misure e divieti</h3><div><p>Allegato 2 del Regolamento regionale 1/2018,
    come modificato dal 1/2020. Vedi le <a href="/regole/">regole</a>.</p></div></div>
  <div class="voce"><h3>Meteo e portata</h3><div><p><a href="https://open-meteo.com/"
    target="_blank" rel="noopener noreferrer">Open-Meteo</a>, licenza CC BY 4.0, portata dal modello
    GloFAS.</p></div></div>
  <div class="voce"><h3>Cartografia</h3><div><p><a href="https://www.openstreetmap.org/copyright"
    target="_blank" rel="noopener noreferrer">OpenStreetMap</a>, licenza ODbL.</p></div></div>
</div>"""
    ld = [briciola_ld(base, briciole)]
    return u, pagina(base, u, tit, desc, corpo, ld, briciole)


# ---------------------------------------------------------------- index.html

def ritocca_indice(testo, d, base, hub=None):
    """Mette nell'applicazione il canonico, le schede social e il rifugio senza JS."""
    # Il titolo di ogni provincia porta alla sua pagina, non e' piu' testo morto:
    # da qui passa l'unico collegamento che le pagine /provincia/ ricevono dalla
    # home, che e' la pagina con piu' autorita' del sito.
    voci = []
    for sig, nome in d['PROVINCE'].items():
        v = sorted((s for s in d['SPOT'] if s['prov'] == sig), key=lambda s: s['nome'])
        if not v:
            continue
        voci.append('<h3><a href="provincia/%s/">%s</a></h3><p>%s</p>' % (
            slug(nome), e(nome), ' · '.join(
                '<a href="spot/%s/">%s</a>' % (s['slug'], e(s['nome'])) for s in v)))

    # e le specie: prima erano raggiungibili solo dagli spot che le dichiarano,
    # cosi' le piu' rare restavano in fondo alla coda del crawler
    specie = ' · '.join('<a href="specie/%s/">%s</a>' % (sp['slug'], e(sp['nome']))
                        for sp in sorted(d['SPECIE'].values(), key=lambda s: s['nome']))
    voci.append('<h3><a href="specie/">Le specie</a></h3><p>%s</p>' % specie)

    # e le pagine d'insieme, che sono quelle che rispondono alle ricerche per
    # nome di fiume e per comune
    hub = hub or {'acqua': {}, 'comune': {}}
    for chiave, eti, tit in (('acqua', 'acqua/', 'I corsi d\'acqua'),
                             ('comune', 'comune/', 'I comuni')):
        if hub[chiave]:
            voci.append('<h3><a href="%s">%s</a></h3><p>%s</p>' % (eti, tit, ' · '.join(
                '<a href="%s%s/">%s</a>' % (eti, sg, e(nome))
                for nome, sg in sorted(hub[chiave].items()))))

    # Dentro <noscript> resta solo l'avviso. L'elenco dei 277 indirizzi sta in
    # un <details>, cioe' nel documento vero: <noscript> il motore di ricerca lo
    # butta appena vede che JavaScript gira, e cosi' la home, la pagina con piu'
    # autorita' del sito, non passava un solo collegamento interno. Chiuso non
    # occupa spazio, e chi vuole l'elenco completo ora ce l'ha.
    rifugio = ("""<noscript>
  <div class="col senza-js">
    <h2>Serve JavaScript per l'indice del giorno</h2>
    <p class="mini">L'indice si calcola nel browser sui dati di oggi, quindi senza JavaScript non
      compare. Le schede degli spot sono pagine normali e si leggono comunque.</p>
  </div>
</noscript>

<details class="tutto-il-sito col">
  <summary>Tutti i %d spot e le %d specie, indirizzo per indirizzo</summary>
  <div class="senza-js">
    <p class="mini"><a href="spot/">tutti gli spot</a> · <a href="specie/">le specie</a> ·
      <a href="regole/">le regole</a> · <a href="metodo/">il metodo</a> ·
      <a href="privacy/">privacy</a></p>
    %s
  </div>
</details>""" % (len(d['SPOT']), len(d['SPECIE']), ''.join(voci)))

    ld = [
        {'@context': 'https://schema.org', '@type': 'WebSite', '@id': base + '/#sito',
         'name': 'Dove Pesco', 'alternateName': 'Dove Pesco Emilia-Romagna',
         'url': base + '/', 'inLanguage': 'it',
         'description': 'Indice giornaliero di %d spot di pesca in Emilia-Romagna, calcolato su '
                        'portata dei fiumi, temperatura stimata dell\'acqua, meteo e stagionalita\' '
                        'delle specie.' % len(d['SPOT'])},
        {'@context': 'https://schema.org', '@type': 'Dataset',
         'name': 'Spot di pesca dell\'Emilia-Romagna con indice giornaliero',
         'description': '%d spot su fiumi, torrenti, laghi, canali e mare, con coordinate, '
                        'ambiente, categoria delle acque, specie dichiarate, esche, tecniche e '
                        'regole locali. A ognuno è assegnato un indice giornaliero calcolato su '
                        'portata GloFAS, temperatura stimata dell\'acqua, pioggia delle 72 ore '
                        'precedenti, pressione, luce e luna.' % len(d['SPOT']),
         'url': base + '/', 'inLanguage': 'it',
         # Chi ha messo insieme la raccolta. Search Console lo chiedeva come
         # campo mancante: senza, la scheda del dataset resta senza attribuzione
         # e vale meno. E' il sito, non una persona: qui non c'e' un nome
         # proprio da esporre.
         'creator': {'@type': 'Organization', 'name': 'Dove Pesco', 'url': base + '/'},
         # due licenze, come dice il piede di ogni pagina: meteo e portata sono
         # CC BY 4.0, la cartografia e' ODbL
         'license': ['https://creativecommons.org/licenses/by/4.0/',
                     'https://opendatacommons.org/licenses/odbl/1-0/'],
         'spatialCoverage': {'@type': 'Place', 'name': 'Emilia-Romagna, Italia'},
         'variableMeasured': ['indice del giorno', 'temperatura stimata dell\'acqua',
                              'portata sulla mediana', 'torbidità stimata', 'specie attive'],
         'isBasedOn': ['https://open-meteo.com/', 'https://www.openstreetmap.org/',
                       'https://agricoltura.regione.emilia-romagna.it/pesca/pubblicazioni/'
                       'pesca-sportiva/itinerari-di-pesca-sportiva-in-emilia-romagna']},
    ]
    tag = ''.join('<script type="application/ld+json">%s</script>\n'
                  % json.dumps(b, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
                  for b in ld)

    # og:description diceva una cosa e la meta description un'altra, sulla stessa
    # pagina: chi condivideva il link leggeva un testo che nel risultato di
    # ricerca non compariva. Ora e' la stessa frase, presa da index.html.
    n = len(d['SPOT'])
    testa = f"""<link rel="canonical" href="{base}/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Dove Pesco">
<meta property="og:locale" content="it_IT">
<meta property="og:title" content="Dove pescare oggi in Emilia-Romagna: {n} spot">
<meta property="og:description" content="Ogni mattina l'indice del giorno per {n} spot dell'Emilia-Romagna: portata dei fiumi, temperatura dell'acqua, meteo e stagione delle specie.">
<meta property="og:url" content="{base}/">
<meta property="og:image" content="{base}/assets/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Dove Pesco: l'indice del giorno per gli spot di pesca dell'Emilia-Romagna">
<meta name="twitter:card" content="summary_large_image">
{tag}</head>"""

    if '<link rel="canonical"' in testo:
        sys.exit('index.html ha gia\' un canonico: il ritocco andrebbe applicato due volte')

    # index.html e' scritto a mano, perche' deve funzionare anche aperto con un
    # doppio clic: il numero degli spot ci sta per esteso, non come segnaposto.
    # Per questo era rimasto a 222 mentre gli spot erano 225, in quattro punti.
    # Un segnaposto si vedrebbe a doppio clic, quindi il numero resta scritto e
    # la pubblicazione si ferma quando non torna: e' l'unico modo per accorgersi
    # dello scarto senza contarli a mano.
    sbagliati = {int(x) for x in re.findall(r'(\d+)\s+spot', testo)} - {n}
    if sbagliati:
        sys.exit('index.html dice %s spot, ma gli spot sono %d: correggi index.html'
                 % (elenco([str(x) for x in sorted(sbagliati)], 'e'), n))
    testo = testo.replace('</head>', testa, 1)
    return testo.replace('</body>', rifugio + '\n\n</body>', 1)


# ---------------------------------------------------------------- pubblicazione

def con_prefisso(testo, pre):
    """Sposta i link interni sotto il percorso di pubblicazione.

    Le pagine si scrivono con link dalla radice (/spot/...): giusto per un
    dominio proprio, sbagliato per <utente>.github.io/<repo>/, dove il sito
    sta in una sottocartella. Qui i link prendono il prefisso giusto.
    """
    if not pre:
        return testo
    for a in ('href="/', 'src="/'):
        testo = testo.replace(a, a[:-1] + pre + '/')
    return testo


def scrivi(cartella, url, testo, pre=''):
    d = os.path.join(cartella, url.strip('/'))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(con_prefisso(testo, pre))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(BASE, '_sito'))
    ap.add_argument('--base', default=os.environ.get('DOMINIO', 'dovepescare.com'))
    ap.add_argument('--senza-indice', action='store_true', dest='senza_indice',
                    help="non calcolare l'indice del giorno (build piu' rapida)")
    a = ap.parse_args()
    base = a.base.strip().rstrip('/')
    if not base.startswith('http'):
        base = 'https://' + base
    # se il sito non sta alla radice del dominio, i link interni vanno spostati
    pre = '/' + base.split('/', 3)[3].strip('/') if base.count('/') > 2 else ''
    out = a.out

    d = leggi_dati()
    indirizzi(d)
    CONTA['spot'], CONTA['specie'] = len(d['SPOT']), len(d['SPECIE'])

    # I gruppi che meritano una pagina propria, e l'indirizzo di ognuno. Servono
    # prima di scrivere qualsiasi pagina, perche' le schede degli spot, le
    # province e le specie ci rimandano.
    g_acqua = raggruppa(d['SPOT'], 'acqua')
    g_comune = raggruppa(d['SPOT'], 'comune')
    hub = {'acqua': {k: slug(k) for k in g_acqua},
           'comune': {k: slug(k) for k in g_comune}}
    # Gli spot e le specie passano da indirizzi(), che gli scarti li risolve.
    # Questi no: due nomi che danno lo stesso slug scriverebbero nella stessa
    # cartella, e la seconda pagina cancellerebbe la prima senza dire niente.
    # Oggi non succede; il giorno che succede, meglio saperlo qui.
    for chiave, gruppo in hub.items():
        doppi = [s for s, n in collections.Counter(gruppo.values()).items() if n > 1]
        if doppi:
            sys.exit('due nomi di %s danno lo stesso indirizzo: %s'
                     % (chiave, elenco(sorted(doppi))))

    oggi = {} if a.senza_indice else leggi_indice()
    if oggi.get('spot'):
        sys.stderr.write('indice del giorno: %d spot su %d, giornata %s, rilevamento %s\n'
                         % (len(oggi['spot']), len(d['SPOT']), oggi['giorno'], oggi['generato']))
        for x in oggi.get('persi') or []:
            sys.stderr.write('  il motore si e\' fermato su %s\n' % x)
    else:
        sys.stderr.write('indice del giorno assente: le pagine escono senza il '
                         'blocco «come si presenta oggi».\n')

    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    # l'applicazione e i suoi materiali. index.html usa link relativi, quindi
    # funziona sia alla radice sia in sottocartella sia con un doppio clic.
    with open(os.path.join(BASE, 'index.html'), encoding='utf-8') as f:
        shutil.copytree(os.path.join(BASE, 'assets'), os.path.join(out, 'assets'))
        with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as g:
            g.write(ritocca_indice(f.read(), d, base, hub))
    # La home non passa da pagina(), quindi si segna a mano. La sua classifica
    # si rifa' ogni giorno nel browser, e Googlebot il JavaScript lo esegue:
    # quello che vede cambia davvero da un giorno all'altro.
    if oggi.get('spot'):
        FRESCHI['/'] = oggi['giorno']
    open(os.path.join(out, '.nojekyll'), 'w').close()

    # le pagine
    urls = ['/']
    accessi = leggi_accessi()
    if not accessi:
        sys.stderr.write('Nessun punto di accesso: i tasti mappa useranno la '
                         'coordinata della scheda. Lancia tools/accessi.py.\n')
    for s in d['SPOT']:
        u, t = pagina_spot(d, s, base, accessi, oggi, hub)
        scrivi(out, u, t, pre)
        urls.append(u)
    for sp in sorted(d['SPECIE'].values(), key=lambda s: s['nome']):
        u, t = pagina_specie(d, sp, base, hub)
        scrivi(out, u, t, pre)
        urls.append(u)
    for nome in sorted(g_acqua):
        u, t = pagina_acqua(d, nome, g_acqua[nome], base, oggi, hub)
        scrivi(out, u, t, pre)
        urls.append(u)
    for nome in sorted(g_comune):
        u, t = pagina_comune(d, nome, g_comune[nome], base, oggi, hub)
        scrivi(out, u, t, pre)
        urls.append(u)
    for sig in d['PROVINCE']:
        if any(s['prov'] == sig for s in d['SPOT']):
            u, t = pagina_provincia(d, sig, base, oggi, hub)
            scrivi(out, u, t, pre)
            urls.append(u)
    for u, t in (pagina_indice_spot(d, base),
                 pagina_indice_acqua(d, base, g_acqua, hub),
                 pagina_indice_comune(d, base, g_comune, hub),
                 pagina_indice_provincia(d, base),
                 pagina_indice_specie(d, base),
                 pagina_regole(d, base), pagina_metodo(d, base), pagina_privacy(d, base)):
        scrivi(out, u, t, pre)
        urls.append(u)

    # la pagina che GitHub Pages serve quando l'indirizzo non esiste: non va
    # indicizzata, ma i link vanno seguiti, perche' sono le vie d'uscita
    with open(os.path.join(out, '404.html'), 'w', encoding='utf-8') as f:
        f.write(con_prefisso(pagina(
            base, '/404.html', 'Pagina non trovata | Dove Pesco',
            'La pagina cercata non esiste. Torna all\'indice del giorno o all\'elenco '
            'degli spot.',
            '<h1>Questa pagina non c\'è</h1>'
            '<div class="intro">L\'indirizzo non esiste, o non esiste più. '
            'Da qui si riparte:</div>'
            + righe([('/', 'Indice del giorno', 'gli spot ordinati sui dati di oggi'),
                     ('/spot/', 'Tutti gli spot', 'provincia per provincia'),
                     ('/specie/', 'Le specie', 'misure, divieti, esche'),
                     ('/regole/', 'Le regole', 'licenze, limiti, zone')]),
            indicizza=False), pre))

    # sitemap e robots
    date = date_sezioni()
    if not any(date.values()):
        sys.stderr.write('nessuna data dai commit: sitemap senza <lastmod>. '
                         'In CI serve actions/checkout con fetch-depth: 0\n')
    with open(os.path.join(out, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in urls:
            lm = lastmod(u, date, FRESCHI)
            # <changefreq> e <priority> non ci sono piu': Google li dichiara
            # ignorati da anni, e la regola che li scriveva era pure al
            # contrario. Contava le barre dell'indirizzo, quindi dava 0.8 a
            # /privacy/ e /metodo/ e 0.6 a tutte le schede degli spot: le pagine
            # che portano le visite valevano meno della pagina della privacy.
            # Un campo ignorato scritto male non fa danno, ma tenerlo voleva dire
            # tramandare l'errore.
            f.write('<url><loc>%s%s</loc>%s</url>\n'
                    % (base, u, '<lastmod>%s</lastmod>' % lm if lm else ''))
        f.write('</urlset>\n')

    with open(os.path.join(out, 'robots.txt'), 'w', encoding='utf-8') as f:
        f.write('# Dove Pesco: tutto aperto, niente da nascondere.\n'
                'User-agent: *\nAllow: /\n\n'
                'Sitemap: %s/sitemap.xml\n' % base)

    if os.environ.get('DOMINIO'):
        with open(os.path.join(out, 'CNAME'), 'w') as f:
            f.write(os.environ['DOMINIO'].strip() + '\n')

    sys.stderr.write('%s, %d pagine, base %s\n' % (out, len(urls), base))


if __name__ == '__main__':
    main()
