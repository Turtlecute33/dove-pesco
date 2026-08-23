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

# ---- lettura degli spot dai file dati -------------------------------------
def leggi_spot():
    testo = ''
    for f in ('data-spots-emilia.js', 'data-spots-romagna.js', 'data-spots-extra.js',
              'data-spots-centro.js'):
        testo += open(os.path.join(BASE, 'assets', 'js', f)).read()
    spot = []
    for m in re.finditer(r"id:\s*'([^']+)'[\s\S]{0,2000}?lat:\s*(-?[\d.]+),\s*lon:\s*(-?[\d.]+)", testo):
        spot.append({'id': m.group(1), 'lat': float(m.group(2)), 'lon': float(m.group(3))})
    visti, out = set(), []
    for s in spot:
        if s['id'] not in visti:
            visti.add(s['id']); out.append(s)
    return out

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
        r1, r2, r3 = [], [], []
        parcheggi, luoghi, strade_tutte = [], [], []

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
                        aree.append(tr)
                continue

            g = e.get('geometry')
            if not g:
                continue
            # scarta subito cio' che non sfiora la finestra
            if max(p['lat'] for p in g) < la0 or min(p['lat'] for p in g) > la1: continue
            if max(p['lon'] for p in g) < lo0 or min(p['lon'] for p in g) > lo1: continue

            pts = [prj(p['lon'], p['lat']) for p in g]

            if t.get('waterway'):
                grande = t['waterway'] in ACQUA_GROSSA
                for tr in ritaglia(pts, RAGGIO):
                    tr = dp(tr, EPS)
                    (acq_g if grande else acq_p).append(tr)
            elif t.get('natural') == 'water' or t.get('landuse') == 'reservoir':
                tr = dp(pts, EPS * 2.6)
                xs = [p[0] for p in tr]; ys = [p[1] for p in tr]
                if len(tr) > 3 and (max(xs) - min(xs)) * (max(ys) - min(ys)) > 4000:
                    aree.append(tr)
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

        accessi = punti_accesso(acq_g + acq_p, strade_tutte, RAGGIO * 0.92)

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
        json.dump(tutto, open(CACHE, 'w'))
        sys.stderr.write('%5d elementi %5.1fs  [%d/%d]\n' % (len(els), time.time() - t, len(tutto), len(spot)))
        time.sleep(3.0)

    tutto = {k: v for k, v in tutto.items() if k in {s['id'] for s in spot}}

    righe = ['/* Mini-carte locali — generate da tools/bake-locale.py',
             '   Dati: © OpenStreetMap contributors, licenza ODbL.',
             '   Origine di ogni carta: le coordinate dello spot. Unita: metri.',
             '   wg fiumi e canali · wp rii e fossi · wa specchi d\'acqua',
             '   r1 strade principali · r2 secondarie · r3 sterrate e sentieri',
             '   pk parcheggi · lb etichette · ac punti in cui la strada tocca l\'acqua',
             '   NON modificare a mano: rilancia lo script. */',
             '',
             'const GEO_RAGGIO = %d;' % RAGGIO,
             'const GEO_LOCALE = {']
    for sid in sorted(tutto):
        d = tutto[sid]
        campi = []
        for k in ('wg', 'wp', 'wa', 'r1', 'r2', 'r3'):
            if d[k]:
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
    vuoti = [k for k, v in tutto.items() if not v['wg'] and not v['wp'] and not v['wa']]
    if vuoti:
        sys.stderr.write('Senza acqua nella finestra: %s\n' % ', '.join(vuoti))
    senza_acc = [k for k, v in tutto.items() if not v['ac']]
    sys.stderr.write('Senza punti di accesso calcolati: %d\n' % len(senza_acc))

if __name__ == '__main__':
    main()
