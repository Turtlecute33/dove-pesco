#!/usr/bin/env python3
"""
Scarica da OpenStreetMap la geometria che serve alla carta regionale e la
incorpora nel sito come percorsi SVG gia' proiettati.

Si lancia una volta sola: il sito poi funziona offline, senza server di tile
e senza alcuna chiamata a terzi.

    python3 tools/bake-geo.py

Dati: (c) OpenStreetMap contributors, ODbL.
"""
import urllib.request, urllib.parse, json, math, time, sys, os

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {'User-Agent': 'dove-pesco-static-site/1.0 (bake script, one-off)'}
OUT = os.path.join(os.path.dirname(__file__), '..', 'assets', 'js', 'geo-regione.js')

# ---- proiezione: equirettangolare centrata sulla regione -------------------
LAT0, LON0 = 44.50, 11.05
K = math.cos(math.radians(LAT0))
SCALE = 1000.0            # unita' SVG per grado di latitudine

def prj(lon, lat):
    return ((lon - LON0) * K * SCALE, -(lat - LAT0) * SCALE)

# ---- Douglas-Peucker -------------------------------------------------------
def dp(pts, eps):
    if len(pts) < 3:
        return pts
    ax, ay = pts[0]; bx, by = pts[-1]
    dx, dy = bx - ax, by - ay
    n2 = dx * dx + dy * dy
    imax, dmax = 0, -1.0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        if n2 == 0:
            d = math.hypot(px - ax, py - ay)
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / n2))
            d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        if d > dmax:
            imax, dmax = i, d
    if dmax > eps:
        return dp(pts[:imax + 1], eps)[:-1] + dp(pts[imax:], eps)
    return [pts[0], pts[-1]]

def path(pts, prec=1, close=False):
    if len(pts) < 2:
        return ''
    f = lambda v: ('%.*f' % (prec, v)).rstrip('0').rstrip('.') or '0'
    out = ['M%s %s' % (f(pts[0][0]), f(pts[0][1]))]
    px, py = pts[0]
    for x, y in pts[1:]:
        out.append('l%s %s' % (f(x - px), f(y - py)))
        px, py = x, y
    if close:
        out.append('Z')
    return ''.join(out)

def query(q, label):
    sys.stderr.write('  %-28s ' % label); sys.stderr.flush()
    t = time.time()
    for tentativo in range(4):
        try:
            req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({'data': q}).encode(), headers=UA)
            d = json.load(urllib.request.urlopen(req, timeout=300))
            sys.stderr.write('%5d elementi  %4.1fs\n' % (len(d['elements']), time.time() - t))
            return d['elements']
        except Exception as e:
            sys.stderr.write('[ritento: %s] ' % type(e).__name__); sys.stderr.flush()
            time.sleep(8 * (tentativo + 1))
    sys.stderr.write('FALLITO\n')
    return []

# ---- 1. confine regionale --------------------------------------------------
def confine():
    els = query("""[out:json][timeout:300];
rel(42611); out geom;""", 'confine regione')
    anelli = []
    for e in els:
        if e['type'] != 'relation':
            continue
        segs = [m['geometry'] for m in e.get('members', [])
                if m.get('role') in ('outer', '') and m.get('geometry')]
        # ricompone gli anelli concatenando i segmenti che si toccano
        while segs:
            cur = [(p['lon'], p['lat']) for p in segs.pop(0)]
            cambiato = True
            while cambiato:
                cambiato = False
                for i, s in enumerate(segs):
                    pts = [(p['lon'], p['lat']) for p in s]
                    if abs(pts[0][0] - cur[-1][0]) < 1e-7 and abs(pts[0][1] - cur[-1][1]) < 1e-7:
                        cur += pts[1:]; segs.pop(i); cambiato = True; break
                    if abs(pts[-1][0] - cur[-1][0]) < 1e-7 and abs(pts[-1][1] - cur[-1][1]) < 1e-7:
                        cur += pts[::-1][1:]; segs.pop(i); cambiato = True; break
                    if abs(pts[-1][0] - cur[0][0]) < 1e-7 and abs(pts[-1][1] - cur[0][1]) < 1e-7:
                        cur = pts[:-1] + cur; segs.pop(i); cambiato = True; break
                    if abs(pts[0][0] - cur[0][0]) < 1e-7 and abs(pts[0][1] - cur[0][1]) < 1e-7:
                        cur = pts[::-1][:-1] + cur; segs.pop(i); cambiato = True; break
            if len(cur) > 40:
                anelli.append(cur)
    anelli.sort(key=len, reverse=True)
    return [dp([prj(*p) for p in a], 1.2) for a in anelli[:3]]

# ---- 2. corsi d'acqua ------------------------------------------------------
FIUMI = ['Po', 'Trebbia', 'Nure', 'Arda', 'Tidone', 'Chiavenna', 'Ongina', 'Stirone',
         'Taro', 'Ceno', 'Parma', 'Baganza', 'Enza', 'Crostolo', 'Secchia', 'Dolo',
         'Dragone', 'Secchiello', 'Panaro', 'Scoltenna', 'Leo', 'Tiepido', 'Samoggia',
         'Reno', 'Setta', 'Sambro', 'Limentra di Treppio', 'Savena', 'Idice', 'Zena',
         'Sillaro', 'Quaderna', 'Santerno', 'Senio', 'Lamone', 'Marzeno', 'Tramazzo',
         'Sintria', 'Montone', 'Rabbi', 'Bidente', 'Ronco', 'Fiumi Uniti', 'Voltre',
         'Savio', 'Borello', 'Bevano', 'Pisciatello', 'Rubicone', 'Uso', 'Marecchia',
         'Ausa', 'Marano', 'Conca', 'Ventena', 'Tavollo', 'Panaro Vecchio']
CANALI = ['Cavo Napoleonico', 'Canale Emiliano Romagnolo', 'Canale Destra Reno',
          'Po di Volano', 'Po di Goro', 'Canale Boicelli', 'Canale Circondariale',
          'Cavo Lama', 'Cavo Fiuma', 'Collettore Acque Alte', 'Canale Navigabile',
          'Idrovia Ferrarese', 'Canale di Bonifica in destra di Reno', 'Scolo Riolo',
          'Canale Lorgana', 'Canale Botte', 'Reno Morto', 'Po di Primaro']

# in OSM lo stesso corso compare come "Secchia", "Fiume Secchia", "Torrente Arda"…
PREFISSI = ('Fiume ', 'Torrente ', 'Rio ', 'Il ', 'Lo ')

def nome_pulito(n):
    for p in PREFISSI:
        if n.startswith(p):
            return n[len(p):]
    return n

def corsi():
    obiettivi = {n.lower(): n for n in FIUMI + CANALI}
    rx = '|'.join(n.replace(' ', '\\\\s').replace("'", '.') for n in FIUMI)
    rxc = '|'.join(n.replace(' ', '\\\\s').replace("'", '.') for n in CANALI)
    q = """[out:json][timeout:300];
area(3600042611)->.r;
(
  way["waterway"~"^(river|stream|canal)$"]["name"~"^((Fiume|Torrente|Rio)\\\\s+)?(%s)$"](area.r);
  way["waterway"~"^(river|canal)$"]["name"~"^(%s)"](area.r);
  way["waterway"="canal"]["name"~"Destra\\\\s+Reno"](area.r);
);
out geom;""" % (rx, rxc)
    els = query(q, 'corsi d\'acqua')
    per_nome = {}
    for e in els:
        g = e.get('geometry')
        if not g or len(g) < 2:
            continue
        grezzo = e['tags'].get('name', '?')
        pulito = nome_pulito(grezzo)
        nome = obiettivi.get(pulito.lower(), pulito)
        per_nome.setdefault(nome, []).append([prj(p['lon'], p['lat']) for p in g])
    return per_nome

# ---- 3. specchi d'acqua ----------------------------------------------------
def laghi():
    q = """[out:json][timeout:300];
area(3600042611)->.r;
(
  way["natural"="water"]["water"~"^(lake|reservoir|pond|lagoon|oxbow|basin)$"](area.r);
  rel["natural"="water"]["water"~"^(lake|reservoir|pond|lagoon|oxbow|basin)$"](area.r);
  way["landuse"="reservoir"](area.r);
);
out geom;"""
    els = query(q, 'specchi d\'acqua')
    out = []
    for e in els:
        nm = e.get('tags', {}).get('name', '')
        if nm.startswith(('Fiume', 'Torrente', 'Po di', 'Canale', 'Canal ', 'Scolo', 'Cavo', 'Rio ')):
            continue
        if e['type'] == 'way':
            g = e.get('geometry') or []
            anelli = [[(p['lon'], p['lat']) for p in g]]
        else:
            anelli = [[(p['lon'], p['lat']) for p in m['geometry']]
                      for m in e.get('members', [])
                      if m.get('role') == 'outer' and m.get('geometry')]
        for a in anelli:
            if len(a) < 5:
                continue
            pr = [prj(*p) for p in a]
            xs = [p[0] for p in pr]; ys = [p[1] for p in pr]
            area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            if area < 1.2:      # scarta le pozze
                continue
            out.append({'n': e['tags'].get('name', ''), 'a': area, 'p': dp(pr, 0.4)})
    out.sort(key=lambda o: -o['a'])
    # le grandi valli sono spezzate in decine di poligoni: ne bastano i piu' estesi
    conta, tenuti = {}, []
    for o in out:
        chiave = o['n'] or '_'
        limite = 8 if chiave.startswith(('Valle', 'Pialassa', 'Sacca', 'Vene')) else 2
        if conta.get(chiave, 0) >= limite:
            continue
        conta[chiave] = conta.get(chiave, 0) + 1
        if o['n'].lower() in ('in caso di piena', 'lago di cava'):
            o['n'] = ''
        tenuti.append(o)
        if len(tenuti) >= 95:
            break
    return tenuti

# ---- 4. citta' di riferimento ---------------------------------------------
def citta():
    q = """[out:json][timeout:180];
area(3600042611)->.r;
node["place"~"^(city|town)$"]["population"](area.r);
out;"""
    els = query(q, 'centri abitati')
    out = []
    for e in els:
        try:
            pop = int(''.join(c for c in e['tags'].get('population', '0') if c.isdigit()) or 0)
        except ValueError:
            pop = 0
        if pop < 20000:
            continue
        x, y = prj(e['lon'], e['lat'])
        out.append({'n': e['tags']['name'], 'p': pop, 'x': round(x, 1), 'y': round(y, 1)})
    out.sort(key=lambda o: -o['p'])
    return out[:26]

# ---- scrittura -------------------------------------------------------------
def main():
    sys.stderr.write('Scarico da OpenStreetMap (una volta sola)\n')
    bordo = confine()
    fiumi = corsi()
    specchi = laghi()
    centri = citta()

    # bounding box complessivo
    tutti = [p for a in bordo for p in a]
    xs = [p[0] for p in tutti]; ys = [p[1] for p in tutti]
    bbox = [min(xs), min(ys), max(xs), max(ys)]

    righe = []
    righe.append('/* Geometria della carta regionale — generata da tools/bake-geo.py')
    righe.append('   Dati: © OpenStreetMap contributors, licenza ODbL.')
    righe.append('   Proiezione equirettangolare centrata su %.2f N, %.2f E.' % (LAT0, LON0))
    righe.append('   NON modificare a mano: rilancia lo script. */')
    righe.append('')
    righe.append('const GEO_PROJ = { lat0: %s, lon0: %s, k: %.6f, scale: %s };' % (LAT0, LON0, K, SCALE))
    righe.append('const GEO_BBOX = [%s];' % ', '.join('%.1f' % v for v in bbox))
    righe.append('')
    righe.append('const GEO_CONFINE = [')
    for a in bordo:
        righe.append('  "%s",' % path(a, 1, True))
    righe.append('];')
    righe.append('')

    # i fiumi principali si disegnano piu' spessi
    MAGGIORI = {'Po', 'Reno', 'Secchia', 'Panaro', 'Taro', 'Trebbia', 'Enza', 'Savio',
                'Marecchia', 'Lamone', 'Montone', 'Ronco', 'Santerno', 'Idice', 'Po di Volano',
                'Po di Goro', 'Canale Emiliano Romagnolo', 'Fiumi Uniti', 'Bidente'}
    righe.append('const GEO_FIUMI = [')
    n_seg = 0
    for nome, segs in sorted(fiumi.items()):
        semp = [dp(s, 0.9) for s in segs]
        semp = [s for s in semp if len(s) > 1]
        if not semp:
            continue
        n_seg += len(semp)
        rango = 1 if nome in MAGGIORI else 2
        d = ' '.join(path(s, 1) for s in semp)
        righe.append('  { n: %s, r: %d, d: "%s" },' % (json.dumps(nome, ensure_ascii=False), rango, d))
    righe.append('];')
    righe.append('')

    righe.append('const GEO_LAGHI = [')
    for l in specchi:
        righe.append('  { n: %s, d: "%s" },' % (json.dumps(l['n'], ensure_ascii=False), path(l['p'], 2, True)))
    righe.append('];')
    righe.append('')

    righe.append('const GEO_CITTA = [')
    for c in centri:
        righe.append('  { n: %s, x: %s, y: %s, p: %d },' % (json.dumps(c['n'], ensure_ascii=False), c['x'], c['y'], c['p']))
    righe.append('];')
    righe.append('')

    with open(OUT, 'w') as f:
        f.write('\n'.join(righe))

    kb = os.path.getsize(OUT) / 1024
    sys.stderr.write('\nScritto %s — %.0f KB\n' % (OUT, kb))
    sys.stderr.write('  confine   %d anelli, %d vertici\n' % (len(bordo), sum(len(a) for a in bordo)))
    sys.stderr.write('  fiumi     %d nomi, %d segmenti\n' % (len(fiumi), n_seg))
    sys.stderr.write('  laghi     %d\n' % len(specchi))
    sys.stderr.write('  centri    %d\n' % len(centri))

if __name__ == '__main__':
    sys.setrecursionlimit(100000)
    main()
