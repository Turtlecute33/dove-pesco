#!/usr/bin/env python3
"""Prepara la cartella da pubblicare: pagine statiche, sitemap e robots.txt.

Il sito resta l'applicazione a pagina singola. L'indice del giorno si calcola
nel browser, come prima. Queste pagine servono a dare un indirizzo proprio a
ogni spot, a ogni specie e a ogni provincia: un motore di ricerca non puo'
indicizzare uno stato interno del programma, quindi con il solo index.html i
222 spot restano invisibili.

In ogni pagina entrano solo i fatti che non cambiano: acqua, fondale, accessi,
specie, esche, regole. L'indice del giorno non entra, perche' cambia ogni ora:
c'e' un link che apre lo spot nell'applicazione.

  python3 tools/genera-pagine.py                    # scrive in _sito/
  python3 tools/genera-pagine.py --out /tmp/prova
  python3 tools/genera-pagine.py --base https://esempio.it
"""

import argparse
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

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATI = ['data-species.js', 'data-spots-emilia.js', 'data-spots-romagna.js',
        'data-spots-extra.js', 'data-spots-centro.js', 'data-index.js',
        'data-rules.js']

TIPI = {
    'fiume': 'Fiume', 'torrente': 'Torrente', 'lago': 'Lago',
    'bacino': 'Bacino', 'canale': 'Canale', 'cava': 'Cava', 'mare': 'Mare',
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
    gen = FONTI['fisse']
    date = {}
    for sez, file in FONTI.items():
        v = [d for d in (data_commit(f) for f in file + gen) if d]
        date[sez] = max(v) if v else None
    v = [d for d in date.values() if d]
    date['home'] = max(v) if v else None
    return date


def lastmod(u, date):
    """La data da mettere in sitemap per questo indirizzo."""
    if u == '/':
        return date['home']
    if u.startswith('/specie'):
        return date['specie']
    if u.startswith('/spot') or u.startswith('/provincia'):
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


def taglia(t, n):
    """Accorcia a n caratteri senza spezzare una parola."""
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) <= n:
        return t
    return t[:n].rsplit(' ', 1)[0].rstrip(' ,.;:–-') + '…'


def elenco(v, cong='e'):
    """['a','b','c'] -> 'a, b e c'"""
    v = [x for x in v if x]
    if not v:
        return ''
    if len(v) == 1:
        return v[0]
    return ', '.join(v[:-1]) + ' ' + cong + ' ' + v[-1]


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


def pagina(base, url, titolo, desc, corpo, ld=None, briciole=None, indicizza=True):
    """Impagina una pagina statica. url comincia e finisce con /."""
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
        blocchi = ld if isinstance(ld, list) else [ld]
        ldjson = ''.join(
            '<script type="application/ld+json">%s</script>\n'
            % json.dumps(b, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
            for b in blocchi)

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titolo)}</title>
<meta name="description" content="{e(desc)}">
{testa_ind}
<meta name="color-scheme" content="light">
<meta name="referrer" content="no-referrer">
<meta name="theme-color" content="#EFE9DD">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Dove Pesco">
<meta property="og:locale" content="it_IT">
<meta property="og:title" content="{e(titolo)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(base + url)}">
<meta property="og:image" content="{e(base)}/assets/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
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
 </div>
</main>

<footer class="piede">
  <div class="col largo">
   <div class="piede-in">
    <div class="piede-g">
      <div>
        <span class="occhio">Dove Pesco</span>
        <p class="mini tenue" style="margin-top:9px">222 spot in Emilia-Romagna, ordinati ogni
          mattina sui dati del giorno. Dati aperti, nessun tracciamento.</p>
        <ul>
          <li><a href="/">Indice del giorno</a></li>
          <li><a href="/spot/">Tutti gli spot</a></li>
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


# ---------------------------------------------------------------- pagine spot

def pagina_spot(d, s, base, accessi=None):
    prov = d['PROVINCE'][s['prov']]
    cat = d['CATEGORIE'][s['categoria']]
    tipo = TIPI.get(s['tipo'], s['tipo'].capitalize())
    rari = set(d['RARITA'].get(s['id'], []))
    sp_ids = [x for x in s.get('specie', []) if x in d['SPECIE']]

    titolo = '%s: dove pescare a %s | Dove Pesco' % (s['nome'], s['comune'])
    if len(titolo) > 62:
        titolo = '%s: pesca a %s (%s)' % (s['nome'], s['comune'], s['prov'])
    if len(titolo) > 62:
        titolo = taglia('%s: pesca (%s)' % (s['nome'], s['prov']), 62)

    # la descrizione si accorcia dalla coda: prima i fatti, poi i richiami
    nomi = [d['SPECIE'][x]['nome'] for x in sp_ids]
    testa = 'Pescare a %s, %s (%s): accessi, fondale, esche e regole.' % (
        s['nome'], s['comune'], prov)
    desc = testa
    for coda in (' Le %d specie dichiarate: %s.' % (len(nomi), elenco(nomi[:3]).lower())
                 if nomi else '', ' Indice del giorno su portata e meteo.'):
        if coda and len(desc) + len(coda) <= 158:
            desc += coda

    briciole = [('/', 'Oggi'), ('/spot/', 'Spot'),
                ('/provincia/%s/' % slug(prov), prov), (None, s['nome'])]

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

    corpo = f"""<span class="occhio acc">{e(tipo)} · {e(prov)}</span>
<h1>{e(s['nome'])}</h1>
<div class="luogo">{e(s['comune'])}, {e(prov)} · {e(s['acqua'])}</div>
<div class="segni">{''.join(segni)}</div>
<div class="intro">{' '.join(apre)}</div>
{cta('/#spot/' + s['id'], "Vedi l'indice di oggi per questo spot")}
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
        'geo': {'@type': 'GeoCoordinates', 'latitude': round(s['lat'], 5),
                'longitude': round(s['lon'], 5)},
        'address': {'@type': 'PostalAddress', 'addressLocality': s['comune'],
                    'addressRegion': prov, 'addressCountry': 'IT'},
        'isAccessibleForFree': True,
        'publicAccess': True,
        **({'amenityFeature': [{'@type': 'LocationFeatureSpecification',
                                'name': 'Postazioni accessibili', 'value': True}]}
           if s.get('disabili') else {}),
    }]
    return '/spot/%s/' % s['slug'], pagina(base, '/spot/%s/' % s['slug'], titolo, desc,
                                           corpo, ld, briciole)


# ---------------------------------------------------------------- pagine specie

def pagina_specie(d, sp, base):
    dove = [s for s in d['SPOT'] if sp['id'] in (s.get('specie') or [])]
    titolo = taglia('%s: pesca in Emilia-Romagna | Dove Pesco' % sp['nome'], 62)
    desc = taglia('%s (%s): misura minima, periodo di divieto, temperatura, esche e tecniche. '
                  '%d spot in Emilia-Romagna dove si trova.'
                  % (sp['nome'], sp['sci'], len(dove)), 158)
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
<h1>{e(sp['nome'])}</h1>
<div class="luogo sci-tit">{e(sp['sci'])}</div>
<div class="segni">{''.join(segni)}</div>
{cta('/#specie', 'Apri la scheda con il disegno e i confronti')}
<h2>Regole e biologia</h2>
<div class="voci">{dati_html}</div>
{prof_html}
{modo_html}
{dritte_html}
{dove_html}
{sim_html}
<p class="mini tenue" style="margin-top:26px;max-width:72ch">Misure minime, limiti e periodi di
  divieto dall'Allegato 2 del <a href="/regole/">Regolamento regionale 1/2018</a>, come modificato
  dal 1/2020. I calendari ittici provinciali possono essere più restrittivi.</p>"""

    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'Article',
        'headline': '%s (%s): regole, biologia e spot in Emilia-Romagna' % (sp['nome'], sp['sci']),
        'description': desc,
        'url': base + '/specie/%s/' % sp['slug'],
        'inLanguage': 'it',
        'isPartOf': {'@type': 'WebSite', '@id': base + '/#sito'},
        'about': {'@type': 'Thing', 'name': sp['nome'],
                  'alternateName': sp['sci']},
    }]
    u = '/specie/%s/' % sp['slug']
    return u, pagina(base, u, titolo, desc, corpo, ld, briciole)


# ---------------------------------------------------------------- province

def pagina_provincia(d, sigla, base):
    nome = d['PROVINCE'][sigla]
    sp = sorted((s for s in d['SPOT'] if s['prov'] == sigla), key=lambda s: s['nome'])
    u = '/provincia/%s/' % slug(nome)
    titolo = taglia('Dove pescare in provincia di %s: %d spot' % (nome, len(sp)), 62)
    desc = taglia('I %d spot di pesca della provincia di %s: fiumi, torrenti, laghi e canali, '
                  'con accessi, specie e regole. Indice del giorno su portata e meteo.'
                  % (len(sp), nome), 158)
    briciole = [('/', 'Oggi'), ('/spot/', 'Spot'), ('/provincia/', 'Province'), (None, nome)]

    per_tipo = {}
    for s in sp:
        per_tipo.setdefault(s['tipo'], []).append(s)
    conte = elenco(['%d %s' % (len(v), TIPI.get(k, k).lower() + ('i' if len(v) > 1
                    and TIPI.get(k, k).lower().endswith('e') else ''))
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
    blocchi = []
    for a in sorted(acque, key=lambda a: (-len(acque[a]), a)):
        v = acque[a]
        blocchi.append('<h3 class="sotto-tit">%s <span class="tenue">%d</span></h3>%s'
                       % (e(a), len(v), righe([
                           ('/spot/%s/' % s['slug'], s['nome'],
                            '%s · %s%s' % (s['comune'], TIPI.get(s['tipo'], s['tipo']).lower(),
                                           ', no kill' if s.get('noKill') else ''))
                           for s in sorted(v, key=lambda s: s['nome'])])))

    nk = [s for s in sp if s.get('noKill')]
    bimbi = [s for s in sp if s.get('bimbi')]
    acc = [s for s in sp if s.get('disabili')]
    scorci = []
    for t, v in (('No kill', nk), ('Con i bambini', bimbi), ('Postazioni accessibili', acc)):
        if v:
            scorci.append('<div class="voce"><h3>%s</h3><div><p>%s</p></div></div>'
                          % (e(t), ' · '.join('<a href="/spot/%s/">%s</a>'
                                              % (s['slug'], e(s['nome'])) for s in v)))

    corpo = f"""<span class="occhio acc">Emilia-Romagna</span>
<h1>Dove pescare in provincia di {e(nome)}</h1>
<div class="intro">{len(sp)} spot in provincia di {e(nome)}: {e(conte)}.
  Per ognuno: come arrivare, i punti di accesso, il fondale, le specie dichiarate, le esche e le
  regole locali.</div>
{cta('/', "Vedi l'indice di oggi, spot per spot")}
{('<h2>Scorciatoie</h2><div class="voci">' + ''.join(scorci) + '</div>') if scorci else ''}
<h2>Le specie piu diffuse</h2>
{top_html}
<h2>Tutti gli spot, per corso d'acqua</h2>
{''.join(blocchi)}
<p class="mini tenue" style="margin-top:26px;max-width:72ch">Zone, divieti e categorie delle acque
  cambiano ogni anno: controlla il calendario ittico della provincia di {e(nome)} e il
  <a href="/regole/">quadro delle regole</a>.</p>"""

    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'ItemList',
        'name': 'Spot di pesca in provincia di %s' % nome,
        'numberOfItems': len(sp),
        'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': s['nome'],
             'url': base + '/spot/%s/' % s['slug']} for i, s in enumerate(sp)],
    }]
    return u, pagina(base, u, titolo, desc, corpo, ld, briciole)


# ---------------------------------------------------------------- indici

def pagina_indice_provincia(d, base):
    """/provincia/ esisteva come cartella e non come pagina: chi tagliava
       l'indirizzo a mano, e chi lo indovinava, trovava un 404. Le nove
       province, invece, sono una domanda che la gente fa."""
    u = '/provincia/'
    titolo = 'Dove pescare in Emilia-Romagna, provincia per provincia | Dove Pesco'
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
    return u, pagina(base, u, titolo, desc, corpo, ld, briciole)


def pagina_indice_spot(d, base):
    u = '/spot/'
    titolo = 'Tutti i 222 spot di pesca in Emilia-Romagna | Dove Pesco'
    desc = ('L\'elenco completo: 222 spot di pesca in Emilia-Romagna su fiumi, torrenti, laghi, '
            'canali e mare, provincia per provincia, con accessi, specie e regole.')
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
    return u, pagina(base, u, titolo, desc, corpo, ld, briciole)


def pagina_indice_specie(d, base):
    u = '/specie/'
    titolo = 'Le 40 specie ittiche dell\'Emilia-Romagna | Dove Pesco'
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
    return u, pagina(base, u, titolo, desc, corpo, ld, briciole)


# ---------------------------------------------------------------- regole

def pagina_regole(d, base):
    R = d['REGOLE']
    u = '/regole/'
    titolo = 'Regole della pesca sportiva in Emilia-Romagna | Dove Pesco'
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
{cta('/spot/', 'Vedi i 222 spot, provincia per provincia')}"""

    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'Article',
        'headline': 'Regole della pesca sportiva in Emilia-Romagna',
        'description': desc, 'url': base + u, 'inLanguage': 'it',
        'isPartOf': {'@type': 'WebSite', '@id': base + '/#sito'},
        'citation': [f['t'] for f in R['fonti']],
    }]
    return u, pagina(base, u, titolo, desc, corpo, ld, briciole)


# ---------------------------------------------------------------- metodo e privacy

VOCI_METODO = [
    ('Stagione', "Ogni specie ha una curva di attività mensile costruita sulla sua biologia e sui "
     "periodi indicati dalla guida regionale. Un cavedano a settembre e un cavedano a gennaio non "
     "sono lo stesso pesce."),
    ("Temperatura dell'acqua", "È il fattore che pesa di più, e nessuno la misura su 222 punti. "
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
    titolo = "Come nasce l'indice del giorno | Dove Pesco"
    desc = ("I sei fattori che ordinano i 222 spot: stagione, temperatura dell'acqua, portata "
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
  arriva a nessun servizio esterno. Se quel file manca o ha più di cinque ore, si torna a chiamare
  Open-Meteo dal browser. Vedi la <a href="/privacy/">pagina privacy</a>.</p>
{cta('/', "Vedi l'indice di oggi")}"""
    ld = [briciola_ld(base, briciole), {
        '@context': 'https://schema.org', '@type': 'Article',
        'headline': "Come nasce l'indice del giorno di Dove Pesco",
        'description': desc, 'url': base + u, 'inLanguage': 'it',
        'isPartOf': {'@type': 'WebSite', '@id': base + '/#sito'}}]
    return u, pagina(base, u, titolo, desc, corpo, ld, briciole)


def pagina_privacy(d, base):
    u = '/privacy/'
    titolo = 'Privacy e dati | Dove Pesco'
    desc = ('Nessun account, cookie, tracciamento, font o script di terze parti. Il browser non '
            'chiama nessun servizio esterno e la posizione non viene mai richiesta.')
    briciole = [('/', 'Oggi'), (None, 'Privacy')]
    corpo = """<h1>Privacy e dati</h1>
<div class="intro">Nessun account, nessun cookie, nessun tracciamento, nessun font e nessuno script
  di terze parti. Non c'è niente da accettare perché non viene raccolto niente.</div>
<h2>Cosa non succede</h2>
<div class="voci">
  <div class="voce"><h3>Nessun tracciamento</h3><div><p>Non ci sono cookie, pixel, statistiche,
    identificatori o strumenti di analisi. Il sito non sa chi sei e non prova a scoprirlo.</p></div></div>
  <div class="voce"><h3>Nessuna terza parte</h3><div><p>I caratteri sono serviti dalla cartella del
    sito, incorporati nel foglio di stile. Non c'è nessuna libreria esterna e nessun server di
    mappe: la geometria è incorporata nel sito come percorsi SVG.</p></div></div>
  <div class="voce"><h3>Nessuna posizione</h3><div><p>La posizione del dispositivo non viene mai
    richiesta. Le mappe funzionano senza saperla.</p></div></div>
</div>
<h2>Cosa succede</h2>
<div class="voci">
  <div class="voce"><h3>Le previsioni</h3><div><p>Meteo e portata arrivano da un file preparato a
    monte e servito insieme alla pagina, aggiornato ogni due ore. Il tuo browser legge quel file e
    non parla con nessun servizio esterno: il tuo indirizzo IP non esce di qui. Sotto la data compare
    l'ora del rilevamento.</p></div></div>
  <div class="voce"><h3>La riserva</h3><div><p>Se quel file manca o ha più di cinque ore (per
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
    tiene i propri registri di accesso secondo le sue condizioni. Su questo non abbiamo controllo:
    è l'unico punto in cui passa qualcosa di tuo.</p></div></div>
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
    return u, pagina(base, u, titolo, desc, corpo, ld, briciole)


# ---------------------------------------------------------------- index.html

def ritocca_indice(testo, d, base):
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

    # Dentro <noscript> resta solo l'avviso. L'elenco dei 277 indirizzi sta in
    # un <details>, cioe' nel documento vero: <noscript> il motore di ricerca lo
    # butta appena vede che JavaScript gira, e cosi' la home, la pagina con piu'
    # autorita' del sito, non passava un solo collegamento interno. Chiuso non
    # occupa spazio, e chi vuole l'elenco completo ora ce l'ha.
    rifugio = ("""<noscript>
  <div class="col senza-js">
    <h2>Serve JavaScript per l'indice del giorno</h2>
    <p class="mini">L'indice si calcola nel browser sui dati di oggi, quindi senza JavaScript non
      compare. Le schede dei 222 spot sono pagine normali e si leggono comunque.</p>
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

    testa = f"""<link rel="canonical" href="{base}/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Dove Pesco">
<meta property="og:locale" content="it_IT">
<meta property="og:title" content="Dove pescare oggi in Emilia-Romagna: 222 spot">
<meta property="og:description" content="Ogni mattina l'indice del giorno per 222 spot, su portata dei fiumi, temperatura dell'acqua, meteo e stagionalita' delle specie.">
<meta property="og:url" content="{base}/">
<meta property="og:image" content="{base}/assets/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
{tag}</head>"""

    if '<link rel="canonical"' in testo:
        sys.exit('index.html ha gia\' un canonico: il ritocco andrebbe applicato due volte')
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
    a = ap.parse_args()
    base = a.base.strip().rstrip('/')
    if not base.startswith('http'):
        base = 'https://' + base
    # se il sito non sta alla radice del dominio, i link interni vanno spostati
    pre = '/' + base.split('/', 3)[3].strip('/') if base.count('/') > 2 else ''
    out = a.out

    d = leggi_dati()
    indirizzi(d)

    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    # l'applicazione e i suoi materiali. index.html usa link relativi, quindi
    # funziona sia alla radice sia in sottocartella sia con un doppio clic.
    with open(os.path.join(BASE, 'index.html'), encoding='utf-8') as f:
        shutil.copytree(os.path.join(BASE, 'assets'), os.path.join(out, 'assets'))
        with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as g:
            g.write(ritocca_indice(f.read(), d, base))
    open(os.path.join(out, '.nojekyll'), 'w').close()

    # le pagine
    urls = ['/']
    accessi = leggi_accessi()
    if not accessi:
        sys.stderr.write('Nessun punto di accesso: i tasti mappa useranno la '
                         'coordinata della scheda. Lancia tools/accessi.py.\n')
    for s in d['SPOT']:
        u, t = pagina_spot(d, s, base, accessi)
        scrivi(out, u, t, pre)
        urls.append(u)
    for sp in sorted(d['SPECIE'].values(), key=lambda s: s['nome']):
        u, t = pagina_specie(d, sp, base)
        scrivi(out, u, t, pre)
        urls.append(u)
    for sig in d['PROVINCE']:
        if any(s['prov'] == sig for s in d['SPOT']):
            u, t = pagina_provincia(d, sig, base)
            scrivi(out, u, t, pre)
            urls.append(u)
    for fn in (pagina_indice_spot, pagina_indice_provincia, pagina_indice_specie,
               pagina_regole, pagina_metodo, pagina_privacy):
        u, t = fn(d, base)
        scrivi(out, u, t, pre)
        urls.append(u)

    # la pagina che GitHub Pages serve quando l'indirizzo non esiste: non va
    # indicizzata, ma i link vanno seguiti, perche' sono le vie d'uscita
    with open(os.path.join(out, '404.html'), 'w', encoding='utf-8') as f:
        f.write(con_prefisso(pagina(
            base, '/404.html', 'Pagina non trovata | Dove Pesco',
            'La pagina cercata non esiste. Torna all\'indice del giorno o all\'elenco '
            'dei 222 spot.',
            '<h1>Questa pagina non c\'è</h1>'
            '<div class="intro">L\'indirizzo non esiste, o non esiste più. '
            'Da qui si riparte:</div>'
            + righe([('/', 'Indice del giorno', 'i 222 spot ordinati sui dati di oggi'),
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
            pr = '1.0' if u == '/' else ('0.8' if u.count('/') == 2 else '0.6')
            fr = 'daily' if u == '/' else 'monthly'
            lm = lastmod(u, date)
            # l'ordine degli elementi lo impone lo schema: loc, lastmod, changefreq, priority
            f.write('<url><loc>%s%s</loc>%s<changefreq>%s</changefreq>'
                    '<priority>%s</priority></url>\n'
                    % (base, u, '<lastmod>%s</lastmod>' % lm if lm else '', fr, pr))
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
