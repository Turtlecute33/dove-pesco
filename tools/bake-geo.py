#!/usr/bin/env python3
"""
Scarica da OpenStreetMap la geometria che serve alla carta regionale e la
incorpora nel sito come percorsi SVG gia' proiettati.

Si lancia una volta sola: il sito poi funziona offline, senza server di tile
e senza alcuna chiamata a terzi.

    python3 tools/bake-geo.py

Dati: (c) OpenStreetMap contributors, ODbL.
"""
import urllib.request, urllib.parse, json, math, re, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nomi_acqua import chiave as chiave_acqua, combacia

MIRROR = ["https://maps.mail.ru/osm/tools/overpass/api/interpreter",
          "https://overpass-api.de/api/interpreter",
          "https://overpass.kumi.systems/api/interpreter",
          "https://overpass.private.coffee/api/interpreter",
          "https://overpass.monicz.dev/api/interpreter"]
UA = {'User-Agent': 'dove-pesco-static-site/1.0 (bake script, one-off)'}
BASE = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(BASE, 'assets', 'js', 'geo-regione.js')
CACHE = os.path.join(os.path.dirname(__file__), '.cache-geo.json')
FILE_DATI = ['data-spots-emilia.js', 'data-spots-romagna.js', 'data-spots-extra.js',
             'data-spots-centro.js']

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
    """Overpass strozza le richieste ravvicinate: si provano i mirror a
       rotazione e le risposte restano in .cache-geo.json, cosi' rilanciare lo
       script dopo un fallimento non riscarica quello che era gia' arrivato."""
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    if q in cache:
        sys.stderr.write('  %-28s %5d elementi  (in cache)\n' % (label, len(cache[q])))
        return cache[q]
    sys.stderr.write('  %-28s ' % label); sys.stderr.flush()
    t = time.time()
    for tentativo in range(4):
        for url in MIRROR:
            try:
                req = urllib.request.Request(url, data=urllib.parse.urlencode({'data': q}).encode(), headers=UA)
                els = json.load(urllib.request.urlopen(req, timeout=300))['elements']
                sys.stderr.write('%5d elementi  %4.1fs\n' % (len(els), time.time() - t))
                cache[q] = els
                json.dump(cache, open(CACHE, 'w'))
                return els
            except Exception:
                sys.stderr.write('.'); sys.stderr.flush()
        time.sleep(8 * (tentativo + 1))
    sys.stderr.write(' FALLITO\n')
    return []

# ---- le acque che le schede dichiarano ------------------------------------
def schede():
    """id, acqua dichiarata e coordinata di ogni spot: la carta regionale deve
       mostrare l'acqua di tutti, non solo dei fiumi maggiori."""
    out = []
    for f in FILE_DATI:
        t = open(os.path.join(BASE, 'assets', 'js', f)).read()
        for m in re.finditer(
                r"id: '([^']+)'[\s\S]{0,300}?acqua: '((?:[^'\\]|\\.)*)',\s*\n\s*"
                r"tipo: '(\w+)'[\s\S]{0,90}?lat: (-?[\d.]+), lon: (-?[\d.]+)", t):
            out.append({'id': m.group(1), 'acqua': m.group(2).replace("\\'", "'"),
                        'tipo': m.group(3), 'lat': float(m.group(4)), 'lon': float(m.group(5))})
    return out

def geom(e):
    """i pezzi di polilinea di un elemento Overpass, via o relazione"""
    g = [e['geometry']] if (e.get('type') == 'way' and e.get('geometry')) else \
        [m['geometry'] for m in e.get('members', []) if m.get('geometry')]
    return [x for x in g if len(x or ()) > 1]

def da_punto(seg, x, y):
    """quanto dista la polilinea proiettata dal punto, in unita' della carta"""
    best = float('inf')
    for i in range(len(seg) - 1):
        ax, ay = seg[i][0] - x, seg[i][1] - y
        bx, by = seg[i + 1][0] - x, seg[i + 1][1] - y
        dx, dy = bx - ax, by - ay
        n2 = dx * dx + dy * dy
        t = 0.0 if n2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / n2))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best

# 1 unita' della carta = un millesimo di grado di latitudine
UNITA = 110.54                    # metri
VICINO = 4000 / UNITA             # oltre questo un tratto omonimo non e' il suo
ADDOSSO = 400 / UNITA             # sotto questo il punto e' sull'acqua disegnata

def misura(spot, per_nome, soglia=VICINO):
    """Per ogni scheda, quanto dista il tratto piu' vicino fra quelli che
       portano il nome della sua acqua. Serve a due cose: sapere quali schede
       sono ancora senza acqua sulla carta, e quali hanno la coordinata fuori
       posto."""
    fuori = []
    for s in spot:
        if s['tipo'] == 'mare':
            continue
        k = chiave_acqua(s['acqua'])
        x, y = prj(s['lon'], s['lat'])
        d = min((da_punto(seg, x, y)
                 for nome, segs in per_nome.items() if combacia(nome, k)
                 for seg in segs), default=float('inf'))
        s['d_acqua'] = None if d == float('inf') else round(d * UNITA)
        if d > soglia:
            fuori.append(s)
    return fuori

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

def raccogli(els, per_nome=None):
    obiettivi = {n.lower(): n for n in FIUMI + CANALI}
    per_nome = {} if per_nome is None else per_nome
    for e in els:
        nome_osm = (e.get('tags') or {}).get('name')
        if not nome_osm:
            continue
        pulito = nome_pulito(nome_osm)
        nome = obiettivi.get(pulito.lower(), pulito)
        for g in geom(e):
            per_nome.setdefault(nome, []).append([prj(p['lon'], p['lat']) for p in g])
    return per_nome

def corsi(spot):
    """La rete principale della regione, piu' l'acqua di ogni scheda.

       Due passi. Prima i nomi di sempre, cercati per nome intero: precisi,
       nessun omonimo. Poi si guarda quali schede sono rimaste senza la loro
       acqua (le schede dicono «Torrente Limentra di Treppio», la mappa in quel
       punto scrive «Limentra», e per nome intero non si trovava nulla), e solo
       per quelle si cerca per parole, tenendo i tratti che passano davvero
       vicino alla scheda che li nomina. Un punto senza il suo fiume sembra un
       errore di coordinate anche quando la coordinata e' giusta."""
    rx = '|'.join(n.replace(' ', '\\\\s').replace("'", '.') for n in FIUMI)
    rxc = '|'.join(n.replace(' ', '\\\\s').replace("'", '.') for n in CANALI)
    per_nome = raccogli(query("""[out:json][timeout:600];
area(3600042611)->.r;
(
  way["waterway"~"^(river|stream|canal)$"]["name"~"^((Fiume|Torrente|Rio)\\\\s+)?(%s)$"](area.r);
  way["waterway"~"^(river|canal)$"]["name"~"^(%s)"](area.r);
  way["waterway"="canal"]["name"~"Destra\\\\s+Reno"](area.r);
);
out geom;""" % (rx, rxc), 'corsi d\'acqua'))

    # Qui la soglia è stretta: basta che il punto non abbia l'acqua *addosso*
    # perché valga la pena cercare il ramo giusto. Con la soglia larga, uno spot
    # sul Bidente di Corniolo passava per coperto dal Bidente di Ridracoli a un
    # chilometro e mezzo, e il suo ramo non veniva mai scaricato.
    scoperti = misura(spot, per_nome, ADDOSSO)
    if not scoperti:
        return per_nome
    parole = sorted({p for s in scoperti for p in chiave_acqua(s['acqua'])},
                    key=lambda w: (-len(w), w))
    sys.stderr.write('  %d schede senza la loro acqua: cerco %s\n'
                     % (len(scoperti), ', '.join(parole)))
    els = query("""[out:json][timeout:600];
area(3600042611)->.r;
way["waterway"~"^(river|stream|canal|drain)$"]
   ["name"~"(^|[^[:alnum:]])(%s)($|[^[:alnum:]])",i](area.r);
out geom;""" % '|'.join(parole), 'acque minori')

    # Cercando per parole si tira dietro ogni omonimo della regione: si tiene
    # un corso solo se passa davvero vicino alla scheda che lo nomina. Vicino
    # un tratto, dentro tutto il corso: mezzo torrente disegnato sarebbe
    # peggio di niente.
    for nome, segs in raccogli(els).items():
        for s in scoperti:
            if not combacia(nome, chiave_acqua(s['acqua'])):
                continue
            x, y = prj(s['lon'], s['lat'])
            if any(da_punto(seg, x, y) <= VICINO for seg in segs):
                per_nome.setdefault(nome, []).extend(segs)
                break
    return per_nome

# ---- 3. specchi d'acqua ----------------------------------------------------
def laghi(chiavi=()):
    """`chiavi` sono le parole con cui le schede nominano la propria acqua: uno
       specchio che combacia si tiene sempre, anche se è una pozza e anche se i
       novantacinque posti sono già presi. Un lago di montagna è piccolo, ma se
       una scheda ci pesca dentro deve stare sulla carta.

       Gli specchi nominati da una scheda si cercano anche per nome, senza
       chiedere il sottotipo: i laghetti di cava e gli invasi di montagna spesso
       portano solo `natural=water`, e col filtro sul sottotipo restavano fuori,
       e con loro restava fuori il lago su cui la scheda dice di pescare."""
    parole = '|'.join(sorted({p for k in chiavi for p in k}, key=lambda w: (-len(w), w)))
    per_nome = ("""
  way["natural"="water"]["name"~"(^|[^[:alnum:]])(%s)($|[^[:alnum:]])",i](area.r);
  rel["natural"="water"]["name"~"(^|[^[:alnum:]])(%s)($|[^[:alnum:]])",i](area.r);"""
                % (parole, parole)) if parole else ''
    q = """[out:json][timeout:600];
area(3600042611)->.r;
(
  way["natural"="water"]["water"~"^(lake|reservoir|pond|lagoon|oxbow|basin)$"](area.r);
  rel["natural"="water"]["water"~"^(lake|reservoir|pond|lagoon|oxbow|basin)$"](area.r);
  way["landuse"="reservoir"](area.r);%s
);
out geom;""" % per_nome
    els = query(q, 'specchi d\'acqua')
    out = []
    for e in els:
        nm = e.get('tags', {}).get('name', '')
        if nm.startswith(('Fiume', 'Torrente', 'Po di', 'Canale', 'Canal ', 'Scolo', 'Cavo', 'Rio ')):
            continue
        mio = any(combacia(nm, k) for k in chiavi)
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
            if area < (0.05 if mio else 1.2):      # scarta le pozze
                continue
            out.append({'n': e['tags'].get('name', ''), 'a': area,
                        'mio': mio, 'p': dp(pr, 0.4)})
    out.sort(key=lambda o: (not o['mio'], -o['a']))
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
        if len(tenuti) >= 95 and not o['mio']:
            break
    # si ridisegnano dal piu' grande al piu' piccolo, altrimenti una pozza
    # dentro una valle finisce sotto la valle e non si vede
    tenuti.sort(key=lambda o: -o['a'])
    return tenuti

# ---- 4. il mare ------------------------------------------------------------
# OpenStreetMap non disegna il mare: disegna la linea di riva, con la terra a
# sinistra e l'acqua a destra di come e' percorsa. Senza il mare i diciannove
# spot di costa restavano punti su un fondo color terra, addosso al nome del
# paese e senza un filo d'acqua intorno. Qui la riva si cuce, si taglia sul
# rettangolo della carta e si richiude lungo il bordo dalla parte del mare.

def cuci(vie):
    """OSM spezza la riva in decine di tratti: qui tornano linee sole"""
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

def taglia_rett(pts, rett):
    """i tratti della polilinea dentro il rettangolo, tagliati sul bordo"""
    x0, y0, x1, y1 = rett
    catene, cur = [], []
    for i in range(len(pts) - 1):
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        dx, dy = bx - ax, by - ay
        t0, t1, ok = 0.0, 1.0, True
        for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
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
        a = (ax + t0 * dx, ay + t0 * dy)
        b = (ax + t1 * dx, ay + t1 * dy)
        if cur and math.hypot(cur[-1][0] - a[0], cur[-1][1] - a[1]) < 0.5:
            cur.append(b)
        else:
            if len(cur) > 1: catene.append(cur)
            cur = [a, b]
        if t1 < 1.0:                      # esce dal rettangolo: la catena finisce qui
            catene.append(cur); cur = []
    if len(cur) > 1: catene.append(cur)
    return catene

def t_bordo(p, rett):
    """dove sta un punto lungo il bordo: 0→1 nord, 1→2 est, 2→3 sud, 3→4 ovest"""
    x0, y0, x1, y1 = rett
    x, y = p
    e = 0.6
    if abs(y - y0) <= e: return (x - x0) / (x1 - x0)
    if abs(x - x1) <= e: return 1 + (y - y0) / (y1 - y0)
    if abs(y - y1) <= e: return 2 + (x1 - x) / (x1 - x0)
    if abs(x - x0) <= e: return 3 + (y1 - y) / (y1 - y0)
    return None

def p_bordo(t, rett):
    x0, y0, x1, y1 = rett
    t %= 4.0
    if t < 1: return (x0 + t * (x1 - x0), y0)
    if t < 2: return (x1, y0 + (t - 1) * (y1 - y0))
    if t < 3: return (x1 - (t - 2) * (x1 - x0), y1)
    return (x0, y1 - (t - 3) * (y1 - y0))

def angoli(ta, tb, avanti, rett):
    """gli angoli del rettangolo fra due uscite, girando in un verso o nell'altro"""
    out, quanto = [], ((tb - ta) if avanti else (ta - tb)) % 4.0
    for k in range(1, 6):
        t = (math.floor(ta) + k) if avanti else (math.ceil(ta) - k)
        if (((t - ta) if avanti else (ta - t)) % 4.0 or 4.0) >= quanto:
            break
        out.append(p_bordo(t, rett))
    return out

def dentro(pt, poly):
    x, y = pt
    d = False
    for i in range(len(poly)):
        ax, ay = poly[i - 1]; bx, by = poly[i]
        if (ay > y) != (by > y) and x < ax + (y - ay) / (by - ay) * (bx - ax):
            d = not d
    return d

def mare(rett):
    els = query("""[out:json][timeout:300];
way["natural"="coastline"](43.85,12.05,45.45,13.00);
out geom;""", 'linea di riva')
    vie = [[prj(p['lon'], p['lat']) for p in e['geometry']]
           for e in els if len(e.get('geometry') or ()) > 1]
    x0, y0, x1, y1 = rett
    # una sonda nell'angolo di nord-est: da queste parti e' mare aperto, e il
    # poligono giusto e' quello che la contiene
    sonda = (x1 - (x1 - x0) * .01, y0 + (y1 - y0) * .01)
    fuori = []
    for catena in cuci(vie):
        for tratto in taglia_rett(catena, rett):
            tratto = dp(tratto, 0.7)
            ta, tb = t_bordo(tratto[0], rett), t_bordo(tratto[-1], rett)
            if ta is None or tb is None or abs(ta - tb) < 1e-9:
                continue                  # riva che nasce o muore dentro il riquadro
            if sum(math.dist(tratto[i], tratto[i + 1]) for i in range(len(tratto) - 1)) < 12:
                continue                  # un ritaglio, non una costa
            for avanti in (True, False):
                poly = tratto + angoli(tb, ta, avanti, rett)
                if len(poly) > 2 and dentro(sonda, poly):
                    fuori.append(poly); break
    return fuori

# ---- 5. citta' di riferimento ---------------------------------------------
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
    spot = schede()
    chiavi = {s['acqua']: chiave_acqua(s['acqua']) for s in spot if s['tipo'] != 'mare'}
    bordo = confine()
    fiumi = corsi(spot)
    specchi = laghi(chiavi.values())
    centri = citta()

    # la diagnosi vale su fiumi e specchi insieme: chi pesca in un lago non ha
    # un corso d'acqua sotto il punto, e non e' un errore
    tutte = {n: list(s) for n, s in fiumi.items()}
    for l in specchi:
        if l['n']:
            tutte.setdefault(l['n'], []).append(l['p'])
    senza_acqua = misura(spot, tutte)

    # bounding box complessivo
    tutti = [p for a in bordo for p in a]
    xs = [p[0] for p in tutti]; ys = [p[1] for p in tutti]
    bbox = [min(xs), min(ys), max(xs), max(ys)]

    # Il riquadro si allarga in verticale sugli schermi stretti (vedi mappa.js):
    # il mare va tagliato piu' largo del riquadro di partenza, altrimenti in
    # cima e in fondo resta una striscia color terra.
    acqua = mare([bbox[0] - 60, bbox[1] - 300, bbox[2] + 60, bbox[3] + 300])

    righe = []
    righe.append('/* Geometria della carta regionale: generata da tools/bake-geo.py')
    righe.append('   Dati: © OpenStreetMap contributors, licenza ODbL.')
    righe.append('   Proiezione equirettangolare centrata su %.2f N, %.2f E.' % (LAT0, LON0))
    righe.append('   NON modificare a mano: rilancia lo script. */')
    righe.append('')
    righe.append('const GEO_PROJ = { lat0: %s, lon0: %s, k: %.6f, scale: %s };' % (LAT0, LON0, K, SCALE))
    righe.append('const GEO_BBOX = [%s];' % ', '.join('%.1f' % v for v in bbox))
    righe.append('')
    righe.append('const GEO_MARE = [')
    for p in acqua:
        righe.append('  "%s",' % path(p, 1, True))
    righe.append('];')
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

    # Overpass a volte non risponde: meglio non scrivere niente che scrivere una
    # carta mezza vuota sopra quella che funzionava.
    if len(bordo) < 1 or len(fiumi) < 40 or len(specchi) < 40 or len(centri) < 9:
        sys.stderr.write('\nScarico incompleto (confine %d, fiumi %d, laghi %d, centri %d):\n'
                         'geo-regione.js NON e\' stato toccato. Rilancia lo script: quello che\n'
                         'e\' arrivato resta in %s.\n'
                         % (len(bordo), len(fiumi), len(specchi), len(centri),
                            os.path.basename(CACHE)))
        sys.exit(1)

    with open(OUT, 'w') as f:
        f.write('\n'.join(righe))

    kb = os.path.getsize(OUT) / 1024
    sys.stderr.write('\nScritto %s, %.0f KB\n' % (OUT, kb))
    sys.stderr.write('  confine   %d anelli, %d vertici\n' % (len(bordo), sum(len(a) for a in bordo)))
    sys.stderr.write('  mare      %d poligoni\n' % len(acqua))
    sys.stderr.write('  fiumi     %d nomi, %d segmenti\n' % (len(fiumi), n_seg))
    sys.stderr.write('  laghi     %d (di cui %d nominati da una scheda)\n'
                     % (len(specchi), sum(1 for l in specchi if l['mio'])))
    sys.stderr.write('  centri    %d\n' % len(centri))

    # ---- il controllo che mancava ----
    # La carta deve mostrare l'acqua di *ogni* spot: un punto senza il suo fiume
    # sembra un errore di coordinate anche quando la coordinata e' giusta. E se
    # l'acqua non c'e' nemmeno in OpenStreetMap, allora l'errore c'e' davvero.
    if senza_acqua:
        sys.stderr.write('\nATTENZIONE: %d schede non hanno la loro acqua entro 4 km,\n'
                         'nemmeno in OpenStreetMap: la coordinata, non la carta, e\' da\n'
                         'guardare.\n' % len(senza_acqua))
        for s in senza_acqua:
            sys.stderr.write('  - %-32s %-30s %.4f, %.4f\n'
                             % (s['id'], s['acqua'][:30], s['lat'], s['lon']))
    else:
        sys.stderr.write('\nOgni scheda ha la sua acqua sulla carta.\n')
    lontani = sorted((s for s in spot if (s.get('d_acqua') or 0) > 260),
                     key=lambda s: -s['d_acqua'])
    if lontani:
        sys.stderr.write('\nAltri %d spot stanno sull\'acqua giusta ma lontani dalla riva:\n'
                         % len(lontani))
        for s in lontani:
            sys.stderr.write('  - %-32s %-30s %5d m   %.4f, %.4f\n'
                             % (s['id'], s['acqua'][:30], s['d_acqua'], s['lat'], s['lon']))

if __name__ == '__main__':
    sys.setrecursionlimit(100000)
    main()
