#!/usr/bin/env python3
"""
Genera una mini-carta per ogni spot: il tratto d'acqua, le strade, i sentieri,
i parcheggi, i paesi vicini e i punti in cui una strada arriva a toccare l'acqua.

Serve a rispondere alla domanda pratica: "il fiume e' lungo venti chilometri,
io dove mi fermo con la macchina?"

    python3 tools/bake-locale.py [--solo id-spot]

Dati: (c) OpenStreetMap contributors, ODbL.
"""
import urllib.request, urllib.parse, json, math, time, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom

# I mirror in ordine di preferenza. Il primo era maps.mail.ru: le coordinate di
# 222 posti di pesca passavano da un servizio di terzi senza motivo, quando
# quello ufficiale risponde uguale. Tolto.
MIRROR = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
UA = {'User-Agent': 'dove-pesco-static-site/1.0 (bake script, one-off)'}
BASE = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(BASE, 'assets', 'js', 'geo-locale.js')

RAGGIO = 1800          # metri, semilato della finestra
EPS = 9.0              # semplificazione, metri
LOTTO = 3              # spot per interrogazione: la query e' piu' larga di prima
PAUSA = 8.0            # secondi fra un lotto e l'altro: e' un servizio pubblico
VICINO = 70.0          # metri: distanza strada-acqua per un punto di accesso
CLUSTER = 150.0        # metri: raggio di raggruppamento dei punti di accesso
VERSIONE = 3           # formato della cache: cambiandolo, le carte si rifanno

# La cache porta il numero di formato nel nome. Prima si chiamava sempre allo
# stesso modo, e alzare VERSIONE la sovrascriveva al primo lotto riuscito: se
# la rete cadeva a meta', restava una cache monca e l'unica copia di quella
# vecchia era persa. Ora le due convivono, e si torna indietro cancellando.
CACHE = os.path.join(os.path.dirname(__file__), '.cache-locale.%d.json' % VERSIONE)

# ---- lettura degli spot dai file dati -------------------------------------
def leggi_spot():
    testo = ''
    for f in ('data-spots-emilia.js', 'data-spots-romagna.js', 'data-spots-extra.js',
              'data-spots-centro.js'):
        testo += open(os.path.join(BASE, 'assets', 'js', f)).read()
    spot = []
    for m in re.finditer(r"id:\s*'([^']+)'[\s\S]{0,600}?acqua:\s*'((?:[^'\\]|\\.)*)'"
                         r"[\s\S]{0,80}?tipo:\s*'(\w+)'"
                         r"[\s\S]{0,200}?lat:\s*(-?[\d.]+),\s*lon:\s*(-?[\d.]+)", testo):
        spot.append({'id': m.group(1), 'acqua': m.group(2).replace("\\'", "'"),
                     'tipo': m.group(3),
                     'lat': float(m.group(4)), 'lon': float(m.group(5))})
    visti, out = set(), []
    for s in spot:
        if s['id'] not in visti:
            visti.add(s['id']); out.append(s)
    return out

# ---- il corso d'acqua dichiarato dalla scheda ------------------------------
# Ogni spot dichiara la sua acqua ("Torrente Setta", "Fiume Po", "Mare
# Adriatico"). In una finestra di 3,6 km di rii e fossi ce ne sono a decine:
# senza il nome, quello su cui si pesca e' una riga come le altre. Il confronto
# fra il nome della scheda e quello di OpenStreetMap sta in tools/nomi_acqua.py.
from nomi_acqua import chiave as chiave_acqua, combacia

# ---- geometria -------------------------------------------------------------
def proiettore(lat0, lon0):
    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 110540.0
    return lambda lon, lat: ((lon - lon0) * kx, -(lat - lat0) * ky)

def dp(pts, eps):
    if len(pts) < 3:
        return pts
    pila = [(0, len(pts) - 1)]
    tieni = [False] * len(pts)
    tieni[0] = tieni[-1] = True
    while pila:
        i, j = pila.pop()
        ax, ay = pts[i]; bx, by = pts[j]
        dx, dy = bx - ax, by - ay
        n2 = dx * dx + dy * dy
        imax, dmax = -1, eps
        for k in range(i + 1, j):
            px, py = pts[k]
            if n2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / n2))
                d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > dmax:
                imax, dmax = k, d
        if imax >= 0:
            tieni[imax] = True
            pila.append((i, imax)); pila.append((imax, j))
    return [p for p, t in zip(pts, tieni) if t]

def ritaglia(pts, r):
    """spezza una polilinea nei tronconi che ricadono nella finestra"""
    fuori = lambda p: abs(p[0]) > r or abs(p[1]) > r
    out, cur = [], []
    for i, p in enumerate(pts):
        dentro = not fuori(p)
        vicino_bordo = abs(p[0]) < r * 1.35 and abs(p[1]) < r * 1.35
        if dentro or (vicino_bordo and cur):
            cur.append(p)
        elif cur:
            if len(cur) > 1: out.append(cur)
            cur = []
    if len(cur) > 1:
        out.append(cur)
    return out

# ---- il mare ---------------------------------------------------------------
# OpenStreetMap non disegna il mare: disegna la linea di riva, con la terra a
# sinistra e l'acqua a destra di come e' percorsa. Sui 22 spot di mare questo
# lasciava la carta tutta color terra, con il punto in mezzo al niente. Qui la
# riva viene tagliata sul quadrato della finestra e richiusa lungo il bordo dal
# lato dell'acqua: ne esce un poligono, che e' il mare.

def cuci(vie):
    """OpenStreetMap spezza la riva in decine di tratti: qui tornano una linea
       sola, nel verso in cui sono disegnati, perche' e' il verso che dice da
       che parte sta l'acqua."""
    k = lambda p: (round(p[0], 1), round(p[1], 1))
    per_inizio, fini = {}, set()
    for v in vie:
        per_inizio.setdefault(k(v[0]), []).append(v)
        fini.add(k(v[-1]))
    usate, catene = set(), []
    partenze = [v for v in vie if k(v[0]) not in fini] or list(vie)
    for v in partenze + list(vie):
        if id(v) in usate:
            continue
        catena = list(v); usate.add(id(v))
        while True:
            dopo = next((w for w in per_inizio.get(k(catena[-1]), ()) if id(w) not in usate), None)
            if dopo is None:
                break
            usate.add(id(dopo)); catena += dopo[1:]
        catene.append(catena)
    return catene

def taglia_quadrato(pts, r):
    """i tratti della polilinea dentro il quadrato, tagliati esattamente sul bordo"""
    catene, cur = [], []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        dx, dy = x1 - x0, y1 - y0
        t0, t1, ok = 0.0, 1.0, True
        for p, q in ((-dx, x0 + r), (dx, r - x0), (-dy, y0 + r), (dy, r - y0)):
            if p == 0:
                if q < 0: ok = False; break
            else:
                t = q / p
                if p < 0:
                    if t > t1: ok = False; break
                    t0 = max(t0, t)
                else:
                    if t < t0: ok = False; break
                    t1 = min(t1, t)
        if not ok:
            if len(cur) > 1: catene.append(cur)
            cur = []
            continue
        a = (x0 + t0 * dx, y0 + t0 * dy)
        b = (x0 + t1 * dx, y0 + t1 * dy)
        if cur and math.hypot(cur[-1][0] - a[0], cur[-1][1] - a[1]) < 0.5:
            cur.append(b)
        else:
            if len(cur) > 1: catene.append(cur)
            cur = [a, b]
        if t1 < 1.0:                      # esce dalla finestra: la catena finisce qui
            catene.append(cur); cur = []
    if len(cur) > 1: catene.append(cur)
    return catene

def t_bordo(p, r):
    """dove sta un punto lungo il bordo: 0→1 lato nord, 1→2 est, 2→3 sud, 3→4 ovest"""
    x, y = p
    e = 0.6
    if abs(y + r) <= e: return (x + r) / (2 * r)
    if abs(x - r) <= e: return 1 + (y + r) / (2 * r)
    if abs(y - r) <= e: return 2 + (r - x) / (2 * r)
    if abs(x + r) <= e: return 3 + (r - y) / (2 * r)
    return None

def p_bordo(t, r):
    t %= 4.0
    if t < 1: return (-r + t * 2 * r, -r)
    if t < 2: return (r, -r + (t - 1) * 2 * r)
    if t < 3: return (r - (t - 2) * 2 * r, r)
    return (-r, r - (t - 3) * 2 * r)

def lungo_bordo(ta, tb, avanti, r):
    """i punti del bordo fra due uscite, girando in un verso o nell'altro.
       Il passo e' un sottomultiplo del lato, cosi' gli angoli ci cascano esatti."""
    passo, out = 0.05, []
    dist = ((tb - ta) if avanti else (ta - tb)) % 4.0
    k = 1
    while k < 100:
        t = (math.floor(ta / passo) + k) * passo if avanti else (math.ceil(ta / passo) - k) * passo
        if (((t - ta) if avanti else (ta - t)) % 4.0) >= dist:
            break
        out.append(p_bordo(t, r)); k += 1
    return out

def dentro_poligono(pt, poly):
    x, y = pt
    d = False
    for i in range(len(poly)):
        ax, ay = poly[i - 1]; bx, by = poly[i]
        if (ay > y) != (by > y) and x < ax + (y - ay) / (by - ay) * (bx - ax):
            d = not d
    return d

def poligoni_mare(coste, r, strade=()):
    """da linee di riva a superfici d'acqua"""
    campioni = [p for _, seg in strade for p in seg[::4]]
    fuori = []
    for catena in coste:
        ta, tb = t_bordo(catena[0], r), t_bordo(catena[-1], r)
        if ta is None or tb is None or abs(ta - tb) < 1e-9:
            continue                      # riva che nasce o muore dentro la finestra
        # Un tratto di venti metri che entra e riesce dallo stesso lato e' un
        # ritaglio, non una costa: chiuderlo riempirebbe mezza finestra d'acqua.
        lunga = sum(math.dist(catena[i], catena[i + 1]) for i in range(len(catena) - 1))
        if lunga < 60:
            continue
        # il mare sta a destra del verso di percorrenza: in questa proiezione,
        # dove la y cresce verso sud, quella destra diventa la normale (-dy, dx)
        i = len(catena) // 2
        (ax, ay), (bx, by) = catena[max(0, i - 1)], catena[min(len(catena) - 1, i + 1)]
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy) or 1.0
        mx, my = (ax + bx) / 2, (ay + by) / 2
        for salto in (90.0, 25.0):
            px, py = mx - dy / n * salto, my + dx / n * salto
            if abs(px) < r and abs(py) < r:
                break
        # Il verso di OSM basta quasi sempre, ma su una foce o dietro un molo la
        # normale cade dalla parte sbagliata e il mare si rovescia sul paese.
        # Chi decide allora sono le strade: quelle stanno sulla terra, e il lato
        # buono e' quello che ne contiene meno.
        scelte = []
        for avanti in (True, False):
            poly = catena + lungo_bordo(tb, ta, avanti, r)
            if len(poly) < 3:
                continue
            quota = (sum(1 for p in campioni if dentro_poligono(p, poly)) / len(campioni)
                     if campioni else None)
            scelte.append((quota, dentro_poligono((px, py), poly), poly))
        if not scelte:
            continue
        if len(scelte) == 2 and scelte[0][0] is not None and abs(scelte[0][0] - scelte[1][0]) > 0.08:
            fuori.append(min(scelte, key=lambda s: s[0])[2])
        else:
            for quota, verso, poly in scelte:
                if verso:
                    fuori.append(poly); break
    return fuori

def dal_punto(linee):
    """quanto dista dallo spot, che sta nell'origine, la piu' vicina di queste linee"""
    bd = float('inf')
    for linea in linee:
        for i in range(len(linea) - 1):
            ax, ay = linea[i]; bx, by = linea[i + 1]
            dx, dy = bx - ax, by - ay
            n2 = dx * dx + dy * dy
            t = 0.0 if n2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / n2))
            bd = min(bd, math.hypot(ax + t * dx, ay + t * dy))
    return bd

def d_path(pts, close=False):
    if len(pts) < 2:
        return ''
    f = lambda v: str(int(round(v)))
    out = ['M%s %s' % (f(pts[0][0]), f(pts[0][1]))]
    px, py = pts[0]
    for x, y in pts[1:]:
        dx, dy = int(round(x)) - int(round(px)), int(round(y)) - int(round(py))
        if dx == 0 and dy == 0:
            continue
        out.append('l%d %d' % (dx, dy))
        px, py = x, y
    if close:
        out.append('Z')
    return ''.join(out) if len(out) > 1 else ''

# ---- rete ------------------------------------------------------------------
def query(q, etichetta):
    """Prova i mirror a rotazione con tempi di attesa brevi: se uno strozza,
       si passa al successivo invece di restare appesi."""
    ultimo = None
    for giro in range(3):
        for url in MIRROR:
            try:
                req = urllib.request.Request(url, data=urllib.parse.urlencode({'data': q}).encode(), headers=UA)
                d = json.load(urllib.request.urlopen(req, timeout=180))
                # Overpass risponde 200 anche quando si arrende a meta': lo dice
                # solo in 'remark'. Una risposta monca entrava in cache come
                # buona e ci restava per sempre, con mezza carta mancante.
                nota = d.get('remark') or ''
                if 'timed out' in nota or 'exceeded' in nota or 'error' in nota.lower():
                    ultimo = 'monca@%s' % url.split('/')[2].split('.')[0]
                    sys.stderr.write('~'); sys.stderr.flush()
                    continue
                return d['elements']
            except Exception as e:
                ultimo = '%s@%s' % (type(e).__name__, url.split('/')[2].split('.')[0])
                sys.stderr.write('.'); sys.stderr.flush()
        time.sleep(15 + 20 * giro)
    sys.stderr.write(' [%s FALLITO: %s] ' % (etichetta, ultimo))
    return []

# La classe serve a due cose diverse: come disegnare la strada, e se ci si puo'
# fermare. Prima motorway e secondary stavano insieme in classe 1, e un punto
# di accesso poteva finire sulla corsia di emergenza di un'autostrada. La 0 si
# disegna come la 1 ma non produce mai un posto dove fermarsi.
STRADE = {
    'motorway': 0, 'motorway_link': 0, 'trunk': 0, 'trunk_link': 0,
    'primary': 1, 'primary_link': 1, 'secondary': 1, 'secondary_link': 1,
    'tertiary': 2, 'tertiary_link': 2, 'unclassified': 2, 'residential': 2,
    'living_street': 2, 'service': 3, 'track': 3, 'path': 3, 'footway': 3,
    'cycleway': 3, 'bridleway': 3,
}
ACQUA_GROSSA = ('river', 'canal')

# I manufatti che dicono "qui si pesca" o almeno "qui si arriva all'acqua".
# leisure=fishing in Italia non esiste sui fiumi (390 oggetti in tutto il
# paese, quasi tutti laghetti a pagamento): il segnale vero e' la struttura
# sulla riva. Sul Po il pennello e' taggato man_made=pier, non groyne.
STRUTTURE = {
    ('leisure', 'fishing'): 'pesca',        ('ford', '*'): 'guado',
    ('leisure', 'slipway'): 'scivolo',      ('waterway', 'weir'): 'briglia',
    ('waterway', 'dam'): 'diga',            ('man_made', 'pier'): 'pontile',
    ('man_made', 'groyne'): 'pennello',     ('man_made', 'breakwater'): 'scogliera',
    ('man_made', 'quay'): 'banchina',       ('waterway', 'lock_gate'): 'chiusa',
    ('natural', 'beach'): 'spiaggia',       ('natural', 'shingle'): 'ghiaia',
    ('natural', 'sand'): 'greto',           ('leisure', 'marina'): 'darsena',
    ('tourism', 'camp_site'): 'campeggio',  ('tourism', 'picnic_site'): 'sosta',
    ('waterway', 'fish_pass'): 'scala',     # segnale negativo: li' e' vietato
}

# bandiere di una strada, a bit: quello che decide se ci si puo' fermare
PONTE, PRIVATA, ARGINE, SCONNESSA = 1, 2, 4, 8


def bandiere(t):
    """Cosa sappiamo di questa strada oltre a dove passa. I tag arrivano gia'
       con 'out geom': leggerli non costa un byte di rete in piu'."""
    b = 0
    if t.get('bridge') or t.get('tunnel') or t.get('layer'):
        b |= PONTE
    if (t.get('access') in ('private', 'no')
            or t.get('motor_vehicle') in ('private', 'no')):
        b |= PRIVATA
    if t.get('embankment') == 'yes' or t.get('man_made') in ('dyke', 'embankment'):
        b |= ARGINE
    if t.get('tracktype') in ('grade4', 'grade5'):
        b |= SCONNESSA
    return b


def dedup(voci):
    """Lo stesso manufatto arriva piu' volte: una linea corta da tre punti
       uguali, un pontile disegnato come via e come area."""
    visti, fuori = set(), []
    for v in voci:
        k = tuple(v)
        if k not in visti:
            visti.add(k); fuori.append(v)
    return fuori


def sosta(t):
    """0 parcheggio libero, 1 privato, 2 a pagamento. Prima erano tutti uguali."""
    if t.get('access') in ('private', 'no', 'customers'):
        return 1
    if t.get('fee') in ('yes', 'y'):
        return 2
    return 0

def bbox(s):
    dlat = RAGGIO / 110540.0
    dlon = RAGGIO / (111320.0 * math.cos(math.radians(s['lat'])))
    return (s['lat'] - dlat, s['lon'] - dlon, s['lat'] + dlat, s['lon'] + dlon)

def costruisci_query(lotto):
    parti = []
    for s in lotto:
        b = '%.5f,%.5f,%.5f,%.5f' % bbox(s)
        parti.append('way["waterway"~"^(river|stream|canal|ditch|drain)$"](%s);' % b)
        parti.append('way["natural"="coastline"](%s);' % b)
        parti.append('way["natural"="water"](%s);' % b)
        parti.append('rel["natural"="water"](%s);' % b)
        parti.append('way["landuse"="reservoir"](%s);' % b)
        parti.append('way["highway"~"^(%s)$"](%s);' % ('|'.join(STRADE), b))
        parti.append('way["amenity"="parking"](%s);' % b)
        parti.append('node["amenity"="parking"](%s);' % b)
        parti.append('node["place"~"^(town|village|hamlet|isolated_dwelling|locality|suburb)$"](%s);' % b)
        # I manufatti sulla riva, e cio' che sbarra la strada per arrivarci.
        # nw invece di nwr dove la relazione non esiste in pratica: ogni "r" e'
        # una ricerca in piu' per il server, e questa e' un'istanza pubblica.
        # Il greto resta nwr perche' li' i multipoligoni ci sono davvero.
        parti.append('nw["man_made"~"^(pier|groyne|breakwater|quay)$"](%s);' % b)
        parti.append('nw["leisure"~"^(slipway|fishing|marina)$"](%s);' % b)
        parti.append('nwr["natural"~"^(beach|shingle|sand)$"](%s);' % b)
        parti.append('nw["waterway"~"^(weir|dam|lock_gate|fish_pass)$"](%s);' % b)
        parti.append('nw["ford"](%s);' % b)
        parti.append('nw["tourism"~"^(camp_site|picnic_site)$"](%s);' % b)
        parti.append('node["barrier"~"^(gate|lift_gate|bollard|block)$"](%s);' % b)
    return '[out:json][timeout:600];\n(\n%s\n);\nout geom;' % '\n'.join(parti)

# ---- punti di accesso ------------------------------------------------------
def punti_accesso(acqua, strade, centro_r, assi=(), rive=(), anelli=(), ponti=()):
    """Dove una strada o un sentiero arriva a meno di VICINO metri dall'acqua.

    Tre correzioni rispetto a prima, tutte e tre necessarie perche' il conto
    torni sui fiumi larghi.

    La prima: si misura contro la riva, non contro l'asse del canale. Sul Po
    l'arginale dista 67-138 m dalla linea di mezzeria e 0-50 m dalla sponda: la
    strada c'era sempre stata, la misura la mancava.

    La seconda: le polilinee si infittiscono a 20 m prima di misurare. Prima si
    confrontavano i soli vertici, e un arginale rettilineo con due vertici a
    400 m di distanza non produceva nessun punto.

    La terza: un punto dentro l'acqua o su un ponte non e' un posto dove ci si
    ferma a pescare.
    """
    if not acqua:
        return []
    griglia = geom.Griglia(geom.densifica(acqua, 20.0), cella=VICINO)
    candidati = []
    for cls, seg in strade:
        if cls == 0:                 # in autostrada non ci si ferma
            continue
        for x, y in geom.densifica([seg], 20.0)[0]:
            if abs(x) > centro_r or abs(y) > centro_r:
                continue
            d, _ = griglia.vicino((x, y), VICINO)
            if d > VICINO:
                continue
            if geom.in_acqua((x, y), assi, rive, anelli):
                continue
            if any(math.dist((x, y), p) < 45 for p in ponti):
                continue
            candidati.append((math.hypot(x, y), x, y, cls))
    candidati.sort()
    tenuti = []
    for d, x, y, cls in candidati:
        if all((x - tx) ** 2 + (y - ty) ** 2 > CLUSTER * CLUSTER for tx, ty, _ in tenuti):
            tenuti.append((x, y, cls))
        if len(tenuti) >= 7:
            break
    return tenuti

# ---- elaborazione di un lotto ---------------------------------------------
def elabora(lotto, elementi):
    risultati = {}
    for s in lotto:
        la0, lo0, la1, lo1 = bbox(s)
        prj = proiettore(s['lat'], s['lon'])
        acq_g, acq_p, aree = [], [], []
        mia, mia_aree, coste = [], [], []      # il corso d'acqua della scheda, e la riva
        r1, r2, r3 = [], [], []
        parcheggi, luoghi, strade_tutte = [], [], []
        strutture, barriere, vie = [], [], []
        chiave = chiave_acqua(s.get('acqua'))
        # Il tipo della scheda dice se si pesca in mare, non il nome dell'acqua:
        # "Foce del Bevano" e "Sacca di Goro" sono mare senza dirlo, e restavano
        # senza il poligono del mare, cioe' senza la riva su cui si sta.
        in_mare = s.get('tipo') == 'mare' or bool({'mare', 'adriatico'} & chiave)
        # Uno specchio da 60 x 60 m e' un laghetto: per una cava o un lago e' il
        # caso d'uso, non il rumore da scartare.
        min_area = 900 if s.get('tipo') in ('cava', 'lago') else 4000

        def struttura(t):
            """come si chiama, se e' un manufatto che porta all'acqua"""
            if t.get('ford'):
                return 'guado'
            for (k, v), nome in STRUTTURE.items():
                if v != '*' and t.get(k) == v:
                    return nome
            return None

        for e in elementi:
            t = e.get('tags', {})
            if e['type'] == 'node':
                if not (la0 <= e['lat'] <= la1 and lo0 <= e['lon'] <= lo1):
                    continue
                x, y = prj(e['lon'], e['lat'])
                k = struttura(t)
                if k:
                    strutture.append((x, y, k, t.get('name')))
                elif t.get('amenity') == 'parking':
                    parcheggi.append((x, y, sosta(t)))
                elif t.get('barrier'):
                    barriere.append((x, y))
                elif t.get('place'):
                    nome = t.get('name')
                    if nome:
                        rango = 1 if t['place'] in ('town', 'village') else 2
                        luoghi.append((x, y, nome, rango))
                continue

            if e['type'] == 'relation':
                if t.get('natural') != 'water':
                    continue
                for mem in e.get('members', []):
                    # role=inner e' un'isola: e' terra dentro l'acqua, e contarla
                    # come acqua metteva il pin in mezzo al fiume per non finire
                    # su una golena.
                    if mem.get('role') != 'outer' or not mem.get('geometry'):
                        continue
                    gm = mem['geometry']
                    if max(q['lat'] for q in gm) < la0 or min(q['lat'] for q in gm) > la1: continue
                    if max(q['lon'] for q in gm) < lo0 or min(q['lon'] for q in gm) > lo1: continue
                    mio = combacia(t.get('name'), chiave)
                    tr = dp([prj(q['lon'], q['lat']) for q in gm], EPS if mio else EPS * 2.6)
                    xs = [q[0] for q in tr]; ys = [q[1] for q in tr]
                    if len(tr) > 3 and (max(xs) - min(xs)) * (max(ys) - min(ys)) > min_area:
                        (mia_aree if mio else aree).append(tr)
                continue

            g = e.get('geometry')
            if not g:
                continue
            # scarta subito cio' che non sfiora la finestra
            if max(p['lat'] for p in g) < la0 or min(p['lat'] for p in g) > la1: continue
            if max(p['lon'] for p in g) < lo0 or min(p['lon'] for p in g) > lo1: continue

            pts = [prj(p['lon'], p['lat']) for p in g]
            k = struttura(t)

            if t.get('natural') == 'coastline':
                coste.append(pts)         # si cuciono e si tagliano dopo, tutte insieme
            elif t.get('waterway') in ('river', 'stream', 'canal', 'ditch', 'drain'):
                grande = t['waterway'] in ACQUA_GROSSA
                mio = combacia(t.get('name'), chiave)
                for tr in ritaglia(pts, RAGGIO):
                    tr = dp(tr, EPS)
                    (mia if mio else acq_g if grande else acq_p).append(tr)
            elif k and not t.get('highway'):
                # un manufatto disegnato come linea o area: ne basta il centro,
                # piu' gli estremi, che sulla scogliera sono la punta
                for q in (pts[0], pts[len(pts) // 2], pts[-1]):
                    strutture.append((q[0], q[1], k, t.get('name')))
            elif t.get('natural') == 'water' or t.get('landuse') == 'reservoir':
                mio = combacia(t.get('name'), chiave)
                # La riva della propria acqua si semplifica come le strade, non
                # come lo sfondo: e' il bordo su cui si misura tutto il resto.
                tr = dp(pts, EPS if mio else EPS * 2.6)
                xs = [p[0] for p in tr]; ys = [p[1] for p in tr]
                if len(tr) > 3 and (max(xs) - min(xs)) * (max(ys) - min(ys)) > min_area:
                    (mia_aree if mio else aree).append(tr)
            elif t.get('amenity') == 'parking':
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                parcheggi.append((sum(xs) / len(xs), sum(ys) / len(ys), sosta(t)))
            elif t.get('highway') in STRADE:
                cls = STRADE[t['highway']]
                # sterrate e sentieri servono solo nei pressi dello spot
                limite = RAGGIO if cls < 3 else RAGGIO * 0.62
                for tr in ritaglia(pts, limite):
                    tr = dp(tr, EPS if cls < 3 else EPS * 1.4)
                    if len(tr) < 2:
                        continue
                    (r1 if cls <= 1 else r2 if cls == 2 else r3).append(tr)
                    strade_tutte.append((cls, tr))
                    vie.append((cls, bandiere(t), t.get('name') or t.get('ref') or '',
                                d_path(tr)))

        riva = [dp(tr, EPS) for catena in cuci(coste)
                for tr in taglia_quadrato(catena, RAGGIO) if len(tr) > 1]
        coste = riva
        mare = poligoni_mare(coste, RAGGIO, strade_tutte)

        # Un nome che combacia a due chilometri non e' l'acqua di questo spot:
        # e' un altro tratto, o un altro ramo con lo stesso nome. Se ce n'e'
        # dell'altra molto piu' vicina, l'aggancio si scioglie e la geometria
        # torna fra le linee normali, senza etichetta.
        d_mia = min(dal_punto(mia), dal_punto(mia_aree))
        d_altra = min(dal_punto(acq_g), dal_punto(acq_p), dal_punto(aree))
        if (mia or mia_aree) and d_mia > 500 and d_mia > 3 * max(d_altra, 1.0):
            acq_g.extend(mia); aree.extend(mia_aree)
            mia, mia_aree = [], []
        if in_mare:
            mia += coste                  # in mare la riva e' il posto dove si pesca

        # La sponda del proprio fiume, anche quando OpenStreetMap non le ha
        # dato un nome: senza questa riga il Po resta un filo in mezzo al nulla.
        riva = mia_aree + geom.riva_di(mia, aree, 200.0)
        if in_mare:
            riva += mare
        # dove una strada taglia l'acqua: e' un ponte, e sopra non si pesca
        ponti = geom.incroci([t for _, t in strade_tutte], mia + acq_g + acq_p)
        # Gli anelli chiusi si passano anche qui: senza, questa parte e
        # tools/accessi.py usavano due definizioni diverse di "nell'acqua", e i
        # segni numerati sulla carta cadevano dove il tasto non sarebbe andato.
        anelli, _ = geom.cuci_anelli(mia_aree + aree)
        accessi = punti_accesso(riva or mia, strade_tutte, RAGGIO * 0.92,
                                assi=mia, rive=riva, anelli=anelli, ponti=ponti)

        # raggruppa i parcheggi vicini
        pk = []
        for x, y, a in sorted(parcheggi, key=lambda p: math.hypot(p[0], p[1])):
            if abs(x) > RAGGIO or abs(y) > RAGGIO:
                continue
            if all((x - b) ** 2 + (y - c) ** 2 > 120 ** 2 for b, c, _ in pk):
                pk.append((x, y, a))
            if len(pk) >= 8:
                break

        vicini = lambda pts, lim: [(x, y) for x, y, *_ in pts
                                   if abs(x) <= lim and abs(y) <= lim]
        luoghi.sort(key=lambda l: (l[3], math.hypot(l[0], l[1])))
        risultati[s['id']] = {
            'wm': ' '.join(filter(None, (d_path(p) for p in mia))),
            'ma': ' '.join(filter(None, (d_path(p, True) for p in mia_aree))),
            'ws': ' '.join(filter(None, (d_path(p, True) for p in mare))),
            'wg': ' '.join(filter(None, (d_path(p) for p in acq_g))),
            'wp': ' '.join(filter(None, (d_path(p) for p in acq_p))),
            'wa': ' '.join(filter(None, (d_path(p, True) for p in aree))),
            'r1': ' '.join(filter(None, (d_path(p) for p in r1))),
            'r2': ' '.join(filter(None, (d_path(p) for p in r2))),
            'r3': ' '.join(filter(None, (d_path(p) for p in r3))),
            'pk': [[int(round(x)), int(round(y)), a] for x, y, a in pk],
            'lb': [[int(round(x)), int(round(y)), n, r] for x, y, n, r in luoghi[:7]],
            'ac': [[int(round(x)), int(round(y)), c] for x, y, c in accessi],
            # i campi che servono a tools/accessi.py, non al disegno: restano
            # nella cache e non entrano in geo-locale.js, che il browser scarica
            'st': dedup([[int(round(x)), int(round(y)), k, n or '']
                         for x, y, k, n in strutture
                         if abs(x) <= RAGGIO and abs(y) <= RAGGIO]),
            'xb': [[int(round(x)), int(round(y))] for x, y in vicini(barriere, RAGGIO)],
            'bg': [[int(round(x)), int(round(y))] for x, y in ponti],
            'rv': [[c, b, n, d] for c, b, n, d in vie if d],
        }
    return risultati

# ---- principale ------------------------------------------------------------
def tutte_le_carte(nuove=None):
    """Le mini-carte da pubblicare: la cache nuova dove c'e', la precedente per
       il resto. Il file servito al browser deve contenere tutti e 222 gli spot
       anche quando Overpass ne ha resi solo una parte."""
    tutto = {}
    for p in (os.path.join(os.path.dirname(__file__), '.cache-locale.json'), CACHE):
        if os.path.exists(p):
            c = json.load(open(p)); c.pop('__v', None); tutto.update(c)
    if nuove:
        tutto.update(nuove)
    return tutto


def main():
    if '--riscrivi' in sys.argv:
        # Rigenera geo-locale.js da cio' che e' gia' in cache, senza toccare la
        # rete: serve quando cambia solo il modo di scrivere la carta.
        tutto = tutte_le_carte()
        if not tutto:
            sys.exit('Nessuna cache da cui riscrivere.')
        sys.stderr.write('Riscrivo da %d carte in cache, senza rete\n' % len(tutto))
        scrivi(tutto, leggi_spot())
        return

    solo = None
    if '--solo' in sys.argv:
        solo = sys.argv[sys.argv.index('--solo') + 1]
    spot = leggi_spot()
    if solo:
        spot = [s for s in spot if s['id'] == solo]
    sys.stderr.write('Mini-carte per %d spot, finestra %d×%d m\n' % (len(spot), RAGGIO * 2, RAGGIO * 2))

    tutto = {}
    if os.path.exists(CACHE) and '--pulisci' not in sys.argv:
        tutto = json.load(open(CACHE))
        # una cache di un formato precedente non ha i campi nuovi: si rifa' tutto
        if tutto.pop('__v', 1) != VERSIONE:
            sys.stderr.write('Cache di un formato vecchio: rifaccio le carte da capo\n')
            tutto = {}
        else:
            sys.stderr.write('Riprendo: %d stazioni gia\' in cache\n' % len(tutto))

    mancanti = [s for s in spot if s['id'] not in tutto]
    lotti = [mancanti[i:i + LOTTO] for i in range(0, len(mancanti), LOTTO)]
    vuoti = 0
    for n, lotto in enumerate(lotti, 1):
        t = time.time()
        sys.stderr.write('  lotto %2d/%d (%d) ' % (n, len(lotti), len(lotto)))
        sys.stderr.flush()
        els = query(costruisci_query(lotto), 'lotto %d' % n)
        if not els:
            # Un lotto vuoto vuol dire quasi sempre "429: stai chiedendo
            # troppo". Insistere allo stesso passo brucia la quota e allunga il
            # blocco: si rallenta, si riprova una volta, e dopo tre vuoti di
            # fila ci si ferma. La cache e' incrementale, quindi chi rilancia
            # domani non perde niente, mentre attraversare tutta la lista
            # dormendo non produce nulla e tiene occupata la macchina un'ora.
            attesa = min(600, 60 * 2 ** vuoti)
            vuoti += 1
            sys.stderr.write('vuoto, aspetto %ds\n' % attesa)
            time.sleep(attesa)
            els = query(costruisci_query(lotto), 'lotto %d (secondo tentativo)' % n)
        if not els:
            if vuoti >= 3:
                sys.stderr.write('\nTre lotti vuoti di fila: Overpass non risponde. '
                                 'Mi fermo, la cache resta e il prossimo giro riprende '
                                 'da qui (%d/%d).\n' % (len(tutto), len(spot)))
                break
            continue
        vuoti = 0
        tutto.update(elabora(lotto, els))
        json.dump(dict(tutto, __v=VERSIONE), open(CACHE, 'w'))
        sys.stderr.write('%5d elementi %5.1fs  [%d/%d]\n' % (len(els), time.time() - t, len(tutto), len(spot)))
        time.sleep(PAUSA)

    if solo:
        # --solo serve a guardare una carta, non a pubblicarne una sola: prima
        # riscriveva geo-locale.js con quell'unico spot dentro, e le altre 221
        # sparivano dal sito senza un avviso.
        sys.stderr.write('Solo %s: la carta e\' in cache, %s non viene toccato\n'
                         % (solo, os.path.basename(OUT)))
        return

    # Si pubblica unendo la cache precedente: se un lotto e' fallito, gli spot
    # che mancano alla cache nuova ci sono ancora nella vecchia. Senza questa
    # riga un giro con Overpass a mezzo servizio riscriveva geo-locale.js con
    # le sole carte del giro, e le altre sparivano dal sito senza un avviso.
    scrivi(tutte_le_carte(tutto), spot)


def cuci_acque(d):
    """Rimette insieme i contorni d'acqua, e separa cio' che si riempie da cio'
       che si disegna come una linea.

    Un lago o un fiume grande arriva da OpenStreetMap a pezzi, un membro della
    relazione per volta, e ogni pezzo finiva sulla carta come una superficie a
    se'. Il browser, per riempire, chiude d'ufficio anche un arco aperto: da li'
    le macchie d'azzurro larghe chilometri, con dentro le strade e il nome di un
    paese. Rimessi in fila per gli estremi tornano l'anello che erano; quello
    che resta aperto e' una sponda tagliata dal riquadro, e va disegnata come
    una linea, non come un lago.
    """
    anelli, aperti = geom.cuci_anelli(geom.linee(d))
    return (' '.join(filter(None, (d_path(p, True) for p in anelli))),
            ' '.join(filter(None, (d_path(p) for p in aperti))))


def scrivi(tutto, spot):
    mancanti = [s['id'] for s in spot if s['id'] not in tutto]
    if mancanti:
        sys.exit('Mancano %d carte su %d: non pubblico un file monco.\n  %s\n'
                 'Rilancia tools/bake-locale.py finche\' la cache non e\' completa.'
                 % (len(mancanti), len(spot), ', '.join(mancanti[:20])))
    # Copia: scrivi() non deve modificare i record che il chiamante ha in mano,
    # o una seconda chiamata ricucirebbe contorni gia' ricuciti e cancellerebbe
    # le sponde calcolate al primo giro.
    tutto = {k: dict(v) for k, v in tutto.items() if k in {s['id'] for s in spot}}
    ricucite = 0
    for sid, d in tutto.items():
        # Gli archi dell'acqua della scheda restano separati da quelli di
        # sfondo: se finissero insieme, un bacino il cui contorno il riquadro
        # taglia perderebbe il colore e il nome in legenda.
        for k, dove in (('ma', 'mb'), ('wa', 'wb')):
            d.setdefault(dove, '')
            if not d.get(k):
                continue
            prima = len(geom.linee(d[k]))
            d[k], resto = cuci_acque(d[k])
            d[dove] = resto
            ricucite += prima - len(geom.linee(d[k])) - len(geom.linee(resto))
    sys.stderr.write('Contorni d\'acqua ricuciti: %d pezzi in meno\n' % ricucite)

    righe =['/* Mini-carte locali: generate da tools/bake-locale.py',
             '   Dati: © OpenStreetMap contributors, licenza ODbL.',
             '   Origine di ogni carta: le coordinate dello spot. Unita: metri.',
             '   wm il corso d\'acqua della scheda · ma il suo specchio · ws il mare',
             '   wg altri fiumi e canali · wp rii e fossi · wa altri specchi d\'acqua',
             '   mb e wb sponde tagliate dal riquadro: linee, non superfici',
             '   r1 strade principali · r2 secondarie · r3 sterrate e sentieri',
             '   pk parcheggi (0 libero, 1 privato, 2 a pagamento) · lb etichette',
             '   ac punti in cui la strada arriva alla riva',
             '   NON modificare a mano: rilancia lo script. */',
             '',
             'const GEO_RAGGIO = %d;' % RAGGIO,
             'const GEO_LOCALE = {']
    for sid in sorted(tutto):
        d = tutto[sid]
        campi = []
        for k in ('wm', 'ma', 'mb', 'ws', 'wg', 'wp', 'wa', 'wb', 'r1', 'r2', 'r3'):
            if d.get(k):
                campi.append('%s:"%s"' % (k, d[k]))
        for k in ('pk', 'ac'):
            if d[k]:
                campi.append('%s:%s' % (k, json.dumps(d[k], separators=(',', ':'))))
        if d['lb']:
            campi.append('lb:%s' % json.dumps(d['lb'], separators=(',', ':'), ensure_ascii=False))
        righe.append('"%s":{%s},' % (sid, ','.join(campi)))
    righe.append('};')

    with open(OUT, 'w') as f:
        f.write('\n'.join(righe))
    kb = os.path.getsize(OUT) / 1024
    sys.stderr.write('\nScritto %s, %.0f KB (%.1f KB per spot)\n' % (OUT, kb, kb / max(1, len(tutto))))
    vuoti = [k for k, v in tutto.items()
             if not any(v.get(c) for c in ('wm', 'ma', 'ws', 'wg', 'wp', 'wa'))]
    if vuoti:
        sys.stderr.write('Senza acqua nella finestra: %s\n' % ', '.join(vuoti))
    senza_mia = [k for k, v in tutto.items()
                 if not any(v.get(c) for c in ('wm', 'ma', 'ws'))]
    if senza_mia:
        sys.stderr.write('Senza il corso d\'acqua della scheda (%d): %s\n'
                         % (len(senza_mia), ', '.join(senza_mia)))
    senza_acc = [k for k, v in tutto.items() if not v['ac']]
    sys.stderr.write('Senza punti di accesso calcolati: %d\n' % len(senza_acc))

if __name__ == '__main__':
    main()
