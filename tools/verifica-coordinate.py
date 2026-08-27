#!/usr/bin/env python3
"""
Controlla che ogni stazione sia davvero sull'acqua.

Per ciascuno spot misura, nella sua mini-carta gia' scaricata, la distanza dal
centro all'acqua che la scheda dichiara — il tratto che bake-locale.py ha
riconosciuto per nome, o la riva del mare. Solo se la carta non l'ha riconosciuta
vale il corso d'acqua piu' vicino, qualunque sia. Se la distanza supera la soglia
la coordinata e' sbagliata: la si aggancia al punto piu' vicino di quell'acqua.

    python3 tools/verifica-coordinate.py            # solo diagnosi
    python3 tools/verifica-coordinate.py --correggi # riscrive i file dati

Dopo una correzione va rilanciato tools/bake-locale.py per ricentrare le carte.
"""
import json, math, os, re, sys

BASE = os.path.join(os.path.dirname(__file__), '..')
CACHE = os.path.join(os.path.dirname(__file__), '.cache-locale.json')
FILE_DATI = ['data-spots-emilia.js', 'data-spots-romagna.js', 'data-spots-extra.js',
              'data-spots-centro.js']
SOGLIA = 260.0          # metri: oltre questa distanza la coordinata non va bene

def leggi_spot():
    spot = []
    for f in FILE_DATI:
        testo = open(os.path.join(BASE, 'assets', 'js', f)).read()
        for m in re.finditer(
                r"id: '([^']+)', nome: '((?:[^'\\]|\\.)*)'[\s\S]{0,1200}?"
                r"tipo: '(\w+)'[\s\S]{0,80}?lat: (-?[\d.]+), lon: (-?[\d.]+)", testo):
            spot.append({'id': m.group(1), 'nome': m.group(2).replace("\\'", "'"),
                         'tipo': m.group(3), 'lat': float(m.group(4)), 'lon': float(m.group(5)),
                         'file': f})
    return spot

def punti(d):
    """percorsi nel formato che generiamo noi: M x y seguito da l dx dy"""
    linee, cur, x, y = [], None, 0, 0
    for t in re.findall(r'[MlZ][^MlZ]*', d or ''):
        n = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', t[1:])]
        if t[0] == 'M':
            if cur and len(cur) > 1: linee.append(cur)
            if len(n) >= 2: x, y = n[0], n[1]; cur = [(x, y)]
        elif t[0] == 'l' and cur is not None:
            for i in range(0, len(n) - 1, 2):
                x += n[i]; y += n[i + 1]; cur.append((x, y))
    if cur and len(cur) > 1: linee.append(cur)
    return linee

def piu_vicino(linee):
    """punto della polilinea piu' vicino all'origine, con la sua distanza"""
    best, bd = None, float('inf')
    for linea in linee:
        for i in range(len(linea) - 1):
            ax, ay = linea[i]; bx, by = linea[i + 1]
            dx, dy = bx - ax, by - ay
            n2 = dx * dx + dy * dy
            t = 0.0 if n2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / n2))
            px, py = ax + t * dx, ay + t * dy
            d = math.hypot(px, py)
            if d < bd: bd, best = d, (px, py)
    return best, bd

def main():
    correggi = '--correggi' in sys.argv
    if not os.path.exists(CACHE):
        sys.exit('Manca %s: lancia prima tools/bake-locale.py' % CACHE)
    carte = json.load(open(CACHE))
    spot = leggi_spot()

    fuori, ok, senza = [], 0, []
    for s in spot:
        g = carte.get(s['id'])
        if not g:
            senza.append(s['id']); continue
        # se la mini-carta sa qual e' il corso d'acqua della scheda, la misura
        # e' quella: essere a due passi da un fosso qualsiasi non conta
        pm, dm = piu_vicino(punti(g.get('wm')))     # il corso d'acqua dichiarato
        pma, dma = piu_vicino(punti(g.get('ma')))   # il suo specchio d'acqua
        # la riva del mare conta solo dove si pesca in mare: altrove e' il
        # bordo della finestra, non l'acqua dello spot
        ps, ds = piu_vicino(punti(g.get('ws'))) if s['tipo'] == 'mare' else (None, float('inf'))
        scelto, dist, tipo = pm, dm, 'acqua della scheda'
        if dma < dist: scelto, dist, tipo = pma, dma, 'specchio'
        if ds < dist:  scelto, dist, tipo = ps, ds, 'riva'
        if scelto is None:
            pg, dg = piu_vicino(punti(g.get('wg')))     # fiumi e canali
            pp, dp = piu_vicino(punti(g.get('wp')))     # rii e fossi
            pa, da = piu_vicino(punti(g.get('wa')))     # bordo degli specchi d'acqua
            scelto, dist, tipo = pg, dg, 'fiume'
            if dp < dist * .55: scelto, dist, tipo = pp, dp, 'rio'
            if da < dist:       scelto, dist, tipo = pa, da, 'specchio'
        if dist > SOGLIA:
            fuori.append((s, scelto, dist, tipo))
        else:
            ok += 1

    print('Stazioni sull\'acqua entro %d m: %d' % (SOGLIA, ok))
    if senza: print('Senza mini-carta: %s' % ', '.join(senza))
    print('Da correggere: %d\n' % len(fuori))

    modifiche = {}
    for s, pt, d, tipo in sorted(fuori, key=lambda r: -r[2]):
        if pt is None:
            print('  %-30s %-44s NESSUNA ACQUA nel riquadro' % (s['id'], s['nome'][:44]))
            continue
        # dalle coordinate locali (metri) alla latitudine e longitudine
        dlat = -pt[1] / 110540.0
        dlon = pt[0] / (111320.0 * math.cos(math.radians(s['lat'])))
        nlat, nlon = round(s['lat'] + dlat, 4), round(s['lon'] + dlon, 4)
        print('  %-30s %-40s %5.0f m → %s  (%.4f, %.4f)'
              % (s['id'], s['nome'][:40], d, tipo, nlat, nlon))
        modifiche.setdefault(s['file'], []).append((s['id'], s['lat'], s['lon'], nlat, nlon))

    if not correggi:
        print('\nDiagnosi soltanto. Per riscrivere i file: --correggi')
        return

    for f, voci in modifiche.items():
        p = os.path.join(BASE, 'assets', 'js', f)
        t = open(p).read()
        for sid, la, lo, nla, nlo in voci:
            pat = re.compile(r"(id: '%s'[\s\S]{0,1200}?lat: )%s(, lon: )%s" % (re.escape(sid), la, lo))
            t2 = pat.sub(lambda m: '%s%s%s%s' % (m.group(1), nla, m.group(2), nlo), t, count=1)
            if t2 == t: print('  ATTENZIONE: non ho potuto correggere %s' % sid)
            t = t2
        open(p, 'w').write(t)
    print('\nCorretti %d spot. Ora rilancia tools/bake-locale.py (svuota prima la cache di quelli mossi).'
          % sum(len(v) for v in modifiche.values()))

    # toglie dalla cache gli spot spostati, cosi' il bake li rifa'
    for f, voci in modifiche.items():
        for sid, *_ in voci: carte.pop(sid, None)
    json.dump(carte, open(CACHE, 'w'))

if __name__ == '__main__':
    main()
