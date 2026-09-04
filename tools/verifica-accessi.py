#!/usr/bin/env python3
"""
Il punto di accesso e' davvero un posto dove ci si ferma a pescare?

Misura assets/js/geo-accessi.js contro la mini-carta, e mette la stessa misura
accanto alla coordinata della scheda: senza il confronto, un numero da solo non
dice se siamo migliorati.

    python3 tools/verifica-accessi.py
    python3 tools/verifica-accessi.py --rete    # controprova su OpenStreetMap

Esce con codice 1 solo sulle due misure binarie: il punto nell'acqua e il
punto sulla riva di la'. Le altre sono distanze misurate su un disegno
semplificato a 23 m: sotto quella soglia non dicono niente, e trasformarle in
un cancello vuol dire farsi bloccare dal rumore.
"""
import json, math, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom
from accessi import (CACHE, CACHE_V2, OUT, LARGO_RIVA, LOCALE, PONTE_VICINO, leggi_spot,
                     geometrie, normalizza, ancora, combacia_nome)

RIF = os.path.join(os.path.dirname(__file__), '.metrica-accessi.json')


def quantili(v):
    if not v:
        return '-'
    v = sorted(v)
    p90 = v[min(len(v) - 1, int(len(v) * 0.9))]
    return 'mediana %4.0f m · p90 %4.0f m · max %5.0f m' % (
        statistics.median(v), p90, v[-1])


def leggi_accessi():
    if not os.path.exists(OUT):
        sys.exit('Manca %s: lancia prima tools/accessi.py' % OUT)
    testo = open(OUT).read()
    fuori = {}
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga.startswith('"'):
            continue
        sid = riga.split('"')[1]
        dati = json.loads(riga[riga.index('['):riga.rindex(']') + 1])
        fuori[sid] = dati
    return fuori


def misura(punti, spot, carte, etichetta):
    """punti: id -> (x, y) in metri locali della carta di quello spot"""
    d_riva, d_riva_asse = [], []
    in_acqua, riva_sbagliata, su_ponte = [], [], []
    for s in spot:
        g = carte.get(s['id'])
        p = punti.get(s['id'])
        if not g or p is None:
            continue
        assi, riva, anelli = geometrie(s, g)
        # La sponda vale come metro solo se e' quella di qui. Dove il pezzo di
        # riva riconosciuto piu' vicino sta oltre LOCALE, di sponda non ne
        # abbiamo: si misura dalla mezzeria e lo si dice, invece di spacciare
        # per errore la distanza da un tratto lontano un chilometro.
        d, piede = geom.piu_vicino(p, riva) if riva else (float('inf'), None)
        if riva and d <= LOCALE:
            d_riva.append(d)
            if geom.riva_di_la(p, piede, assi):
                riva_sbagliata.append(s['id'])
        elif assi:
            d_riva_asse.append(geom.piu_vicino(p, assi)[0])
        if geom.in_acqua(p, assi, riva, anelli):
            in_acqua.append(s['id'])
        # Un guado o una briglia sono attraversamenti anche loro: la geometria
        # non li distingue da un ponte, ma sono il posto dove si pesca. Contarli
        # fra i difetti gonfierebbe la misura con dei successi.
        passaggio = any(k in ('guado', 'briglia', 'diga', 'chiusa')
                        and math.dist(p, (x, y)) <= 60
                        for x, y, k, n in (g.get('st') or []))
        if not passaggio and any(math.dist(p, (x, y)) < PONTE_VICINO
                                 for x, y in (g.get('bg') or [])):
            su_ponte.append(s['id'])
    print('\n%s' % etichetta)
    print('  distanza dalla sponda disegnata (%d spot):  %s'
          % (len(d_riva), quantili(d_riva)))
    print('  dalla sola mezzeria, senza sponda (%d spot): %s'
          % (len(d_riva_asse), quantili(d_riva_asse)))
    print('  DENTRO l\'acqua:            %3d' % len(in_acqua))
    print('  sulla riva di la\':         %3d' % len(riva_sbagliata))
    print('  su un ponte:               %3d' % len(su_ponte))
    return {'d_riva': d_riva, 'in_acqua': in_acqua,
            'riva_sbagliata': riva_sbagliata, 'su_ponte': su_ponte}


def controprova(spot, acc, quanti=40):
    """La prova che non si fa da soli: si chiede a OpenStreetMap.

    Tutto il resto misura il punto contro il nostro disegno semplificato a
    23 m, cioe' contro la stessa geometria che il punteggio ha scelto di
    minimizzare. Qui invece si chiede al server, per il punto vero in gradi,
    dentro quali aree cade: se fra queste c'e' natural=water, il punto e'
    nell'acqua e la nostra copia semplificata stava mentendo.

    Un campione, non tutti: e' un servizio pubblico e gratuito.
    """
    import urllib.request, urllib.parse, time
    mirror = 'https://overpass-api.de/api/interpreter'
    ua = {'User-Agent': 'dove-pesco-static-site/1.0 (verifica, one-off)'}
    scelti = [s for s in spot if s['id'] in acc]
    scelti = scelti[::max(1, len(scelti) // quanti)][:quanti]
    print('\nControprova su OpenStreetMap (%d spot, punto vero in gradi)' % len(scelti))
    bagnati, asciutti, muti = [], 0, 0
    for s in scelti:
        lat, lon = acc[s['id']][0], acc[s['id']][1]
        q = ('[out:json][timeout:60];is_in(%.5f,%.5f)->.a;'
             '(way.a["natural"="water"];rel.a["natural"="water"];'
             'way.a["landuse"="reservoir"];rel.a["landuse"="reservoir"];);out tags;'
             % (lat, lon))
        d = None
        for tentativo in range(4):
            try:
                req = urllib.request.Request(mirror, headers=ua,
                                             data=urllib.parse.urlencode({'data': q}).encode())
                d = json.load(urllib.request.urlopen(req, timeout=90))
                break
            except Exception as e:
                # 429 vuol dire "stai chiedendo troppo": si aspetta, non si insiste
                time.sleep(5 * (tentativo + 1) ** 2)
                ultimo = type(e).__name__
        if d is None:
            muti += 1
            sys.stderr.write('  %s: %s\n' % (s['id'], ultimo))
            continue
        if d.get('elements'):
            nomi = ', '.join(sorted({e.get('tags', {}).get('name', 'senza nome')
                                     for e in d['elements']}))
            bagnati.append('%s (%s)' % (s['id'], nomi))
        else:
            asciutti += 1
        time.sleep(1.5)
    print('  asciutti: %d · dentro l\'acqua secondo il server: %d · senza risposta: %d'
          % (asciutti, len(bagnati), muti))
    for b in bagnati:
        print('    %s' % b)
    return len(bagnati)


def main():
    carte = {}
    if os.path.exists(CACHE_V2):
        carte = json.load(open(CACHE_V2)); carte.pop('__v', None)
    if os.path.exists(CACHE):
        nuove = json.load(open(CACHE)); nuove.pop('__v', None)
        carte.update(nuove)
    if not carte:
        sys.exit('Nessuna mini-carta: lancia prima tools/bake-locale.py')
    carte = {k: normalizza(v) for k, v in carte.items()}
    spot = leggi_spot()
    acc = leggi_accessi()

    print('Spot: %d · con mini-carta: %d · con punto di accesso: %d'
          % (len(spot), len(carte), len(acc)))

    # il pin della scheda, in metri locali, e' l'origine di ogni carta
    prima = misura({s['id']: (0.0, 0.0) for s in spot}, spot, carte,
                   'PRIMA: la coordinata della scheda (quella che i tasti aprivano)')

    dopo_punti = {}
    for s in spot:
        a = acc.get(s['id'])
        if a:
            dopo_punti[s['id']] = geom.in_metri(a[0], a[1], s['lat'], s['lon'])
    dopo = misura(dopo_punti, spot, carte,
                  'DOPO: il punto di accesso di assets/js/geo-accessi.js')

    # copertura e spostamento
    conta = {1: 0, 2: 0, 3: 0}
    for a in acc.values():
        conta[a[2]] = conta.get(a[2], 0) + 1
    sposta = [math.hypot(*p) for p in dopo_punti.values()]
    print('\nCopertura e fedelta\'')
    print('  confidenza 3: %3d · 2: %3d · 1: %3d · senza punto: %3d'
          % (conta.get(3, 0), conta.get(2, 0), conta.get(1, 0), len(spot) - len(acc)))
    print('  spostamento dal pin della scheda:           %s' % quantili(sposta))

    # Accordo col testo: la sola prova che non riusa la geometria su cui il
    # punteggio e' stato costruito. Si guardano i manufatti con un nome (la
    # diga, la chiusa, il pontile che la scheda cita) e non le etichette dei
    # paesi: un paese sta legittimamente a un chilometro dalla riva, e
    # contarlo trasformerebbe la misura in rumore.
    def accordo(punti):
        d = t = 0
        for s in spot:
            chiave, nega = ancora(s)
            g, p = carte.get(s['id']), punti.get(s['id'])
            if not g or p is None or nega or not chiave:
                continue
            citati = [(x, y) for x, y, k, n in (g.get('st') or [])
                      if n and combacia_nome(n, chiave)]
            if not citati:
                continue
            t += 1
            if min(math.dist(p, q) for q in citati) <= 300:
                d += 1
        return d, t

    d1, t1 = accordo({s['id']: (0.0, 0.0) for s in spot})
    d2, t2 = accordo(dopo_punti)
    if t2:
        print('  cade vicino al manufatto che la scheda nomina: %d/%d (%.0f%%), '
              'prima %d/%d' % (d2, t2, 100.0 * d2 / t2, d1, t1))

    # il punto deve stare dentro il riquadro che la carta disegna, o la carta e
    # il tasto tornano a indicare due posti diversi
    fuori_carta = [s['id'] for s in spot if dopo_punti.get(s['id'])
                   and max(abs(dopo_punti[s['id']][0]),
                           abs(dopo_punti[s['id']][1])) > 1500]
    if fuori_carta:
        print('  FUORI dal riquadro disegnato: %s' % ', '.join(fuori_carta))

    if '--rete' in sys.argv:
        controprova(spot, acc)

    # La misura con cui si apriva la diagnosi: quanto dista il pin della scheda
    # dal punto in cui una strada tocca DAVVERO la sua acqua. E' il numero che
    # il README cita come "prima", e va potuto rilanciare come tutti gli altri.
    lontani, senza = [], 0
    for s in spot:
        g = carte.get(s['id'])
        if not g:
            continue
        assi, riva, _ = geometrie(s, g)
        bersaglio = riva + assi
        if not bersaglio:
            continue
        gr = geom.Griglia(geom.densifica(bersaglio, 20.0), cella=80.0)
        vicini = [math.hypot(*p)
                  for cls, b, nome, d in (g.get('rv') or []) if cls
                  for linea in geom.densifica(geom.linee(d), 20.0) for p in linea
                  if gr.vicino(p, 40.0)[0] <= 40.0]
        if vicini:
            lontani.append(min(vicini))
        else:
            senza += 1
    print('  quanto dista il pin da dove una strada tocca la sua acqua: %s'
          % quantili(lontani))
    print('  spot senza nessun accesso raggiungibile: %d' % senza)

    # il verdetto, solo sulle due misure binarie
    rotti = len(dopo['in_acqua']) + len(dopo['riva_sbagliata'])
    print('\nVerdetto')
    for k, nome in (('in_acqua', 'dentro l\'acqua'),
                    ('riva_sbagliata', 'sulla riva di la\'')):
        if dopo[k]:
            print('  %s: %s' % (nome, ', '.join(dopo[k][:12])))
    print('  prima %d punti nell\'acqua → dopo %d'
          % (len(prima['in_acqua']), len(dopo['in_acqua'])))
    json.dump({'in_acqua': len(dopo['in_acqua']),
               'riva_sbagliata': len(dopo['riva_sbagliata']),
               'copertura': len(acc)}, open(RIF, 'w'))
    if rotti:
        sys.exit(1)
    print('  nessun punto nell\'acqua e nessuno sulla riva sbagliata.')


if __name__ == '__main__':
    main()
