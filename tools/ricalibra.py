#!/usr/bin/env python3
"""
Ricalibra le coordinate delle stazioni in due passi, incrociando due fonti.

  1. ANCORA: Nominatim, cercando la localita' che il nome della stazione
     dichiara ("Trebbia a Bobbio" → Bobbio). Se Nominatim ha risposto solo col
     centro del comune, l'ancora resta la coordinata scritta a mano: il
     municipio e' quasi sempre piu' lontano dall'acqua della mia stima.

  2. AGGANCIO: Overpass, cercando la geometria del corso d'acqua che la scheda
     dichiara nel campo "acqua", e spostando la stazione sul punto piu' vicino
     di QUELL'acqua. Se il punto piu' vicino e' oltre il limite, non si muove
     nulla e lo spot finisce nell'elenco da guardare a mano.

    python3 tools/ricalibra.py             # diagnosi
    python3 tools/ricalibra.py --correggi  # riscrive i file dati

Poi: svuota la cache delle mini-carte e rilancia tools/bake-locale.py.
Dati: (c) OpenStreetMap contributors, ODbL.
"""
import urllib.request, urllib.parse, json, math, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nomi_acqua import chiave as chiave_acqua, combacia, cerca

BASE = os.path.join(os.path.dirname(__file__), '..')
D = os.path.dirname(__file__)
C_GEO = os.path.join(D, '.cache-geocodifica.json')
C_SNAP = os.path.join(D, '.cache-snap.json')
C_LOC = os.path.join(D, '.cache-locale.json')
FILE_DATI = ['data-spots-emilia.js', 'data-spots-romagna.js', 'data-spots-extra.js',
              'data-spots-centro.js']

MIRROR = ["https://maps.mail.ru/osm/tools/overpass/api/interpreter",
          "https://overpass-api.de/api/interpreter",
          "https://overpass.kumi.systems/api/interpreter"]
UA = {'User-Agent': 'dove-pesco-static-site/1.0 (ricalibrazione una volta sola)'}
RAGGIO = int(os.environ.get('RAGGIO', 2500))   # metri: entro quanto cercare l'acqua
LIMITE = int(os.environ.get('LIMITE', 1200))   # metri: oltre questo non ci fidiamo
LOTTO = 10
PROV = {'PC': 'Piacenza', 'PR': 'Parma', 'RE': 'Reggio Emilia', 'MO': 'Modena', 'BO': 'Bologna',
        'FE': 'Ferrara', 'RA': 'Ravenna', 'FC': 'Forlì-Cesena', 'RN': 'Rimini'}

def leggi():
    out = []
    for f in FILE_DATI:
        t = open(os.path.join(BASE, 'assets', 'js', f)).read()
        for m in re.finditer(
                r"id: '([^']+)', nome: '((?:[^'\\]|\\.)*)',\s*\n\s*comune: '((?:[^'\\]|\\.)*)', prov: '(\w+)',"
                r" acqua: '((?:[^'\\]|\\.)*)',\s*\n\s*tipo: '(\w+)'[\s\S]{0,90}?lat: (-?[\d.]+), lon: (-?[\d.]+)", t):
            out.append({'id': m.group(1), 'nome': m.group(2).replace("\\'", "'"),
                        'comune': m.group(3).replace("\\'", "'"), 'prov': m.group(4),
                        'acqua': m.group(5).replace("\\'", "'"), 'tipo': m.group(6),
                        'lat': float(m.group(7)), 'lon': float(m.group(8)),
                        'latraw': m.group(7), 'lonraw': m.group(8), 'file': f})
    return out

def dist(la1, lo1, la2, lo2):
    return math.hypot((lo2 - lo1) * 111320.0 * math.cos(math.radians(la1)), (la2 - la1) * 110540.0)

def interroga(q):
    for giro in range(3):
        for u in MIRROR:
            try:
                r = urllib.request.Request(u, data=urllib.parse.urlencode({'data': q}).encode(), headers=UA)
                return json.load(urllib.request.urlopen(r, timeout=180))['elements']
            except Exception:
                sys.stderr.write('.'); sys.stderr.flush()
        time.sleep(10 + 10 * giro)
    return []

def vicino(geoms, la, lo):
    kx = 111320.0 * math.cos(math.radians(la))
    best, bd = None, float('inf')
    for g in geoms:
        for i in range(len(g) - 1):
            ax = (g[i]['lon'] - lo) * kx;     ay = (g[i]['lat'] - la) * 110540.0
            bx = (g[i+1]['lon'] - lo) * kx;   by = (g[i+1]['lat'] - la) * 110540.0
            dx, dy = bx - ax, by - ay
            n2 = dx*dx + dy*dy
            t = 0.0 if n2 == 0 else max(0.0, min(1.0, -(ax*dx + ay*dy) / n2))
            px, py = ax + t*dx, ay + t*dy
            d = math.hypot(px, py)
            if d < bd: bd, best = d, (la + py/110540.0, lo + px/kx)
    return best, bd

def main():
    correggi = '--correggi' in sys.argv
    # Gli spot di mare hanno "Mare Adriatico" nel campo acqua: nessun corso
    # d'acqua da cercare per nome, ma una riva sì. Si agganciano a quella,
    # altrimenti restano in mezzo al paese a un chilometro dalla battigia.
    spot = leggi()
    geo = json.load(open(C_GEO)) if os.path.exists(C_GEO) else {}

    # ---- passo 1: scegli l'ancora ----
    for s in spot:
        # Nominatim su questi toponimi becca troppo spesso una via omonima
        # invece del posto: come ancora resta la coordinata di partenza, e
        # l'aggancio all'acqua dichiarata la corregge di poche centinaia di metri.
        s['ala'], s['alo'], s['fonte'] = s['lat'], s['lon'], 'stima'

    # ---- passo 2: aggancia all'acqua dichiarata, partendo dall'ancora ----
    snap = json.load(open(C_SNAP)) if os.path.exists(C_SNAP) else {}
    chiave = lambda s: '%s@%.5f,%.5f' % (s['id'], s['ala'], s['alo'])
    manca = [s for s in spot if chiave(s) not in snap]
    lotti = [manca[i:i+LOTTO] for i in range(0, len(manca), LOTTO)]
    for n, lotto in enumerate(lotti, 1):
        parti = []
        for s in lotto:
            a = 'around:%d,%.5f,%.5f' % (RAGGIO, s['ala'], s['alo'])
            if s['tipo'] == 'mare':
                parti.append('way["natural"="coastline"](%s);' % a)
                continue
            # Cerchiamo per le parole caratteristiche del nome, non per il nome
            # intero: OSM chiama "Limentra" quello che la scheda chiama
            # "Torrente Limentra di Treppio". Il confronto vero si fa dopo.
            nu = '|'.join(cerca(s['acqua']))
            if not nu: continue
            parti.append('way["waterway"]["name"~"%s",i](%s);' % (nu, a))
            parti.append('way["natural"="water"]["name"~"%s",i](%s);' % (nu, a))
            parti.append('rel["natural"="water"]["name"~"%s",i](%s);' % (nu, a))
        sys.stderr.write('  lotto %2d/%d ' % (n, len(lotti))); sys.stderr.flush()
        els = interroga('[out:json][timeout:300];\n(\n%s\n);\nout geom;' % '\n'.join(parti)) if parti else []
        con_nome, riva = [], []
        for e in els:
            g = [e['geometry']] if (e['type'] == 'way' and e.get('geometry')) else \
                [m['geometry'] for m in e.get('members', []) if m.get('geometry')]
            if e.get('tags', {}).get('natural') == 'coastline':
                riva.extend(g)
            else:
                con_nome.append((e.get('tags', {}).get('name', ''), g))
        for s in lotto:
            if s['tipo'] == 'mare':
                gs = riva
            else:
                nomi = chiave_acqua(s['acqua'])
                gs = [x for nm, g in con_nome if combacia(nm, nomi) for x in g]
            pt, d = vicino(gs, s['ala'], s['alo']) if gs else (None, None)
            snap[chiave(s)] = {'lat': round(pt[0], 5), 'lon': round(pt[1], 5), 'd': round(d)} if pt else None
        json.dump(snap, open(C_SNAP, 'w'))
        sys.stderr.write(' %4d elementi\n' % len(els))
        time.sleep(2)

    # ---- esito ----
    muovi, fermi, guarda = [], [], []
    for s in spot:
        c = snap.get(chiave(s))
        if c and c['d'] <= LIMITE:
            nl, no = c['lat'], c['lon']
            spo = dist(s['lat'], s['lon'], nl, no)
            (muovi if spo > 60 else fermi).append((s, nl, no, spo, c['d']))
        else:
            guarda.append((s, c['d'] if c else None))

    print('\nInvariate: %d' % len(fermi))
    print('Ricalibrate: %d' % len(muovi))
    print('Da guardare a mano (acqua dichiarata non trovata entro %d m): %d\n' % (LIMITE, len(guarda)))
    for s, d in guarda:
        print('  ?  %-30s %-34s  acqua: %-28s %s'
              % (s['id'], s['nome'][:34], s['acqua'][:28], ('%d m' % d) if d else 'non trovata'))
    print()
    for s, nl, no, spo, dw in sorted(muovi, key=lambda r: -r[3]):
        print('  %-30s %-32s sposto %5.0f m → %.4f, %.4f   %s'
              % (s['id'], s['nome'][:32], spo, nl, no,
                 ('su %s a %d m' % (s['acqua'][:22], dw)) if dw is not None else 'solo localita\''))

    if not correggi:
        print('\nDiagnosi soltanto. Per riscrivere i file: --correggi')
        return

    per_file = {}
    for s, nl, no, spo, dw in muovi: per_file.setdefault(s['file'], []).append((s, nl, no))
    for f, voci in per_file.items():
        p = os.path.join(BASE, 'assets', 'js', f)
        t = open(p).read()
        for s, nl, no in voci:
            pat = re.compile(r"(id: '%s'[\s\S]{0,1200}?lat: )%s(, lon: )%s"
                             % (re.escape(s['id']), re.escape(s['latraw']), re.escape(s['lonraw'])))
            t2 = pat.sub(lambda m: '%s%.4f%s%.4f' % (m.group(1), nl, m.group(2), no), t, count=1)
            if t2 == t: print('  ATTENZIONE: non corretto %s' % s['id'])
            t = t2
        open(p, 'w').write(t)
    if os.path.exists(C_LOC):
        loc = json.load(open(C_LOC))
        for s, nl, no, spo, dw in muovi: loc.pop(s['id'], None)
        json.dump(loc, open(C_LOC, 'w'))
    print('\nRicalibrate %d stazioni. Ora rilancia tools/bake-locale.py' % len(muovi))

if __name__ == '__main__':
    main()
