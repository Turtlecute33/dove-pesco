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

MIRROR = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
UA = {'User-Agent': 'dove-pesco-static-site/1.0 (bake script, one-off)'}
BASE = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(BASE, 'assets', 'js', 'geo-locale.js')
CACHE = os.path.join(os.path.dirname(__file__), '.cache-locale.json')   # per riprendere

RAGGIO = 1800          # metri, semilato della finestra
EPS = 9.0              # semplificazione, metri
LOTTO = 6              # spot per interrogazione
VICINO = 70.0          # metri: distanza strada-acqua per un punto di accesso
CLUSTER = 150.0        # metri: raggio di raggruppamento dei punti di accesso
VERSIONE = 2           # formato della cache: cambiandolo, le carte si rifanno

# ---- lettura degli spot dai file dati -------------------------------------
def leggi_spot():
    testo = ''
    for f in ('data-spots-emilia.js', 'data-spots-romagna.js', 'data-spots-extra.js',
              'data-spots-centro.js'):
        testo += open(os.path.join(BASE, 'assets', 'js', f)).read()
    spot = []
    for m in re.finditer(r"id:\s*'([^']+)'[\s\S]{0,600}?acqua:\s*'((?:[^'\\]|\\.)*)'"
                         r"[\s\S]{0,200}?lat:\s*(-?[\d.]+),\s*lon:\s*(-?[\d.]+)", testo):
        spot.append({'id': m.group(1), 'acqua': m.group(2).replace("\\'", "'"),
                     'lat': float(m.group(3)), 'lon': float(m.group(4))})
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
                d = json.load(urllib.request.urlopen(req, timeout=150))
                return d['elements']
            except Exception as e:
                ultimo = '%s@%s' % (type(e).__name__, url.split('/')[2].split('.')[0])
                sys.stderr.write('.'); sys.stderr.flush()
        time.sleep(15 + 20 * giro)
    sys.stderr.write(' [%s FALLITO: %s] ' % (etichetta, ultimo))
    return []

STRADE = {
    'motorway': 1, 'motorway_link': 1, 'trunk': 1, 'trunk_link': 1,
    'primary': 1, 'primary_link': 1, 'secondary': 1, 'secondary_link': 1,
    'tertiary': 2, 'tertiary_link': 2, 'unclassified': 2, 'residential': 2,
    'living_street': 2, 'service': 3, 'track': 3, 'path': 3, 'footway': 3,
    'cycleway': 3, 'bridleway': 3,
}
ACQUA_GROSSA = ('river', 'canal')

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
    return '[out:json][timeout:600];\n(\n%s\n);\nout geom;' % '\n'.join(parti)

# ---- punti di accesso ------------------------------------------------------
def punti_accesso(acqua, strade, centro_r):
    """dove una strada o un sentiero arriva a meno di VICINO metri dall'acqua"""
    if not acqua:
        return []
    cella = VICINO
    griglia = {}
    for seg in acqua:
        for x, y in seg:
            griglia.setdefault((int(x // cella), int(y // cella)), []).append((x, y))

    def vicino_acqua(x, y):
        gx, gy = int(x // cella), int(y // cella)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for wx, wy in griglia.get((gx + i, gy + j), ()):
                    if (wx - x) ** 2 + (wy - y) ** 2 <= VICINO * VICINO:
                        return True
        return False

    candidati = []
    for cls, seg in strade:
        passo = 1 if cls == 3 else 1
        for k in range(0, len(seg), passo):
            x, y = seg[k]
            if abs(x) > centro_r or abs(y) > centro_r:
                continue
            if vicino_acqua(x, y):
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
        chiave = chiave_acqua(s.get('acqua'))
        in_mare = bool({'mare', 'adriatico'} & chiave)

        for e in elementi:
            t = e.get('tags', {})
            if e['type'] == 'node':
                if not (la0 <= e['lat'] <= la1 and lo0 <= e['lon'] <= lo1):
                    continue
                x, y = prj(e['lon'], e['lat'])
                if t.get('amenity') == 'parking':
                    parcheggi.append((x, y))
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
                    if mem.get('role') != 'outer' or not mem.get('geometry'):
                        continue
                    gm = mem['geometry']
                    if max(q['lat'] for q in gm) < la0 or min(q['lat'] for q in gm) > la1: continue
                    if max(q['lon'] for q in gm) < lo0 or min(q['lon'] for q in gm) > lo1: continue
                    tr = dp([prj(q['lon'], q['lat']) for q in gm], EPS * 2.6)
                    xs = [q[0] for q in tr]; ys = [q[1] for q in tr]
                    if len(tr) > 3 and (max(xs) - min(xs)) * (max(ys) - min(ys)) > 4000:
                        (mia_aree if combacia(t.get('name'), chiave) else aree).append(tr)
                continue

            g = e.get('geometry')
            if not g:
                continue
            # scarta subito cio' che non sfiora la finestra
            if max(p['lat'] for p in g) < la0 or min(p['lat'] for p in g) > la1: continue
            if max(p['lon'] for p in g) < lo0 or min(p['lon'] for p in g) > lo1: continue

            pts = [prj(p['lon'], p['lat']) for p in g]

            if t.get('natural') == 'coastline':
                coste.append(pts)         # si cuciono e si tagliano dopo, tutte insieme
            elif t.get('waterway'):
                grande = t['waterway'] in ACQUA_GROSSA
                mio = combacia(t.get('name'), chiave)
                for tr in ritaglia(pts, RAGGIO):
                    tr = dp(tr, EPS)
                    (mia if mio else acq_g if grande else acq_p).append(tr)
            elif t.get('natural') == 'water' or t.get('landuse') == 'reservoir':
                tr = dp(pts, EPS * 2.6)
                xs = [p[0] for p in tr]; ys = [p[1] for p in tr]
                if len(tr) > 3 and (max(xs) - min(xs)) * (max(ys) - min(ys)) > 4000:
                    (mia_aree if combacia(t.get('name'), chiave) else aree).append(tr)
            elif t.get('amenity') == 'parking':
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                parcheggi.append((sum(xs) / len(xs), sum(ys) / len(ys)))
            elif t.get('highway') in STRADE:
                cls = STRADE[t['highway']]
                # sterrate e sentieri servono solo nei pressi dello spot
                limite = RAGGIO if cls < 3 else RAGGIO * 0.62
                for tr in ritaglia(pts, limite):
                    tr = dp(tr, EPS if cls < 3 else EPS * 1.4)
                    if len(tr) < 2:
                        continue
                    (r1 if cls == 1 else r2 if cls == 2 else r3).append(tr)
                    strade_tutte.append((cls, tr))

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
        accessi = punti_accesso(mia + acq_g + acq_p + coste, strade_tutte, RAGGIO * 0.92)

        # raggruppa i parcheggi vicini
        pk = []
        for x, y in sorted(parcheggi, key=lambda p: math.hypot(*p)):
            if abs(x) > RAGGIO or abs(y) > RAGGIO:
                continue
            if all((x - a) ** 2 + (y - b) ** 2 > 120 ** 2 for a, b in pk):
                pk.append((x, y))
            if len(pk) >= 8:
                break

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
            'pk': [[int(round(x)), int(round(y))] for x, y in pk],
            'lb': [[int(round(x)), int(round(y)), n, r] for x, y, n, r in luoghi[:7]],
            'ac': [[int(round(x)), int(round(y)), c] for x, y, c in accessi],
        }
    return risultati

# ---- principale ------------------------------------------------------------
def main():
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
    for n, lotto in enumerate(lotti, 1):
        t = time.time()
        sys.stderr.write('  lotto %2d/%d (%d) ' % (n, len(lotti), len(lotto)))
        sys.stderr.flush()
        els = query(costruisci_query(lotto), 'lotto %d' % n)
        if not els:
            sys.stderr.write('vuoto, salto\n'); continue
        tutto.update(elabora(lotto, els))
        json.dump(dict(tutto, __v=VERSIONE), open(CACHE, 'w'))
        sys.stderr.write('%5d elementi %5.1fs  [%d/%d]\n' % (len(els), time.time() - t, len(tutto), len(spot)))
        time.sleep(3.0)

    tutto = {k: v for k, v in tutto.items() if k in {s['id'] for s in spot}}

    righe = ['/* Mini-carte locali — generate da tools/bake-locale.py',
             '   Dati: © OpenStreetMap contributors, licenza ODbL.',
             '   Origine di ogni carta: le coordinate dello spot. Unita: metri.',
             '   wm il corso d\'acqua della scheda · ma il suo specchio · ws il mare',
             '   wg altri fiumi e canali · wp rii e fossi · wa altri specchi d\'acqua',
             '   r1 strade principali · r2 secondarie · r3 sterrate e sentieri',
             '   pk parcheggi · lb etichette · ac punti in cui la strada tocca l\'acqua',
             '   NON modificare a mano: rilancia lo script. */',
             '',
             'const GEO_RAGGIO = %d;' % RAGGIO,
             'const GEO_LOCALE = {']
    for sid in sorted(tutto):
        d = tutto[sid]
        campi = []
        for k in ('wm', 'ma', 'ws', 'wg', 'wp', 'wa', 'r1', 'r2', 'r3'):
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
    sys.stderr.write('\nScritto %s — %.0f KB (%.1f KB per spot)\n' % (OUT, kb, kb / max(1, len(tutto))))
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
