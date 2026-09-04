#!/usr/bin/env python3
"""
Dove ci si ferma davvero, per ognuno dei 222 spot.

La coordinata di una scheda risponde alla domanda "che tempo fa e quanta acqua
scende": e' quella che sceglie la cella di Open-Meteo e quella della portata, e
non si tocca. Ma non risponde alla domanda "dove parcheggio e da dove tiro", ed
e' quella che apre chi preme "Naviga": su 82 spot su 222 quel tasto apriva un
punto in mezzo all'acqua.

Qui si calcola il secondo punto e si scrive a parte, in assets/js/geo-accessi.js.
Nessuna rete: si legge la mini-carta gia' scaricata da tools/bake-locale.py.

    python3 tools/accessi.py
    python3 tools/accessi.py --solo bo-reno-casalecchio --spiega
    python3 tools/accessi.py --elenco          # gli spot da guardare a mano

Le correzioni fatte a mano stanno in tools/accessi-verificati.json e comandano
su tutto: una rigenerazione non le cancella.

Dati: (c) OpenStreetMap contributors, ODbL.
"""
import json, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom
from nomi_acqua import GENERICI, ACCENTI

BASE = os.path.join(os.path.dirname(__file__), '..')
CACHE = os.path.join(os.path.dirname(__file__), '.cache-locale.3.json')
# La carta del formato precedente: non ha i manufatti ne' i tag delle strade,
# ma ha l'acqua e le strade, e con quelle il grosso del conto si fa lo stesso.
# Serve perche' Overpass e' spesso irraggiungibile: senza questo ripiego, il
# punto di accesso dipenderebbe dal fatto che un servizio pubblico risponda.
CACHE_V2 = os.path.join(os.path.dirname(__file__), '.cache-locale.json')
MANO = os.path.join(os.path.dirname(__file__), 'accessi-verificati.json')
OUT = os.path.join(BASE, 'assets', 'js', 'geo-accessi.js')
FILE_DATI = ('data-spots-emilia.js', 'data-spots-romagna.js',
             'data-spots-extra.js', 'data-spots-centro.js')

D_RIVA = 40.0          # metri dalla sponda perche' un punto sia "sull'acqua"
D_RIVA_ASSE = 60.0     # senza sponda disegnata si misura dalla mezzeria
R_MAX = 700.0          # metri: oltre, non e' piu' il tratto che la scheda descrive
R_MAX_LARGO = 1200.0   # l'ultimo allargamento, e la confidenza scende
PASSO = 20.0           # densificazione delle polilinee
LARGO_RIVA = 200.0     # quanto lontano dall'asse puo' stare la sua sponda
PONTE_VICINO = 45.0    # metri da un attraversamento: sopra un ponte non si pesca
LOCALE = geom.LOCALE   # la soglia sta in geom.py, qui solo il richiamo

# Quanto vale trovarsi accanto a un manufatto. Il guado e lo scivolo sono i due
# posti in cui una strada entra in acqua per definizione; sul Po il pennello e'
# taggato pontile. La scala di risalita e' l'unico segnale negativo affidabile:
# la legge vieta di pescarci vicino.
VALE = {
    'pesca': 40, 'guado': 35, 'scivolo': 30, 'briglia': 28, 'diga': 28,
    'pontile': 28, 'pennello': 25, 'scogliera': 25, 'banchina': 22,
    'chiusa': 20, 'ghiaia': 18, 'greto': 18, 'spiaggia': 18, 'darsena': 12,
    'campeggio': 10, 'sosta': 10, 'scala': -25,
}
PONTE, PRIVATA, ARGINE, SCONNESSA = 1, 2, 4, 8

# Il testo che promette poco: dove la scheda stessa dice che si scende male,
# il nome che cita non vale come conferma.
NEGA = re.compile(r'imperv|difficil|scars|poco accessibil|vietat|proibit|'
                  r'non praticabil|pericolos', re.I)


# ---- lettura degli spot ----------------------------------------------------
def leggi_spot():
    """Gli spot con i campi che servono qui. Si ferma se non sono 225: le
       regex di questo repo hanno gia' perso schede in silenzio."""
    testo = ''
    for f in FILE_DATI:
        testo += open(os.path.join(BASE, 'assets', 'js', f)).read()
    blocchi = re.split(r"\n\{\n(?=\s*id: ')", testo)
    spot = []
    for b in blocchi:
        m = re.search(r"id: '([^']+)'", b)
        if not m:
            continue
        campo = lambda k: (re.search(r"%s: '((?:[^'\\]|\\.)*)'" % k, b) or [None, ''])[1]
        c = re.search(r'lat: (-?[\d.]+), lon: (-?[\d.]+)', b)
        if not c:
            continue
        spot.append({
            'id': m.group(1),
            'nome': campo('nome').replace("\\'", "'"),
            'acqua': campo('acqua').replace("\\'", "'"),
            'tipo': campo('tipo'),
            'accesso': campo('accesso').replace("\\'", "'"),
            'comeArrivare': campo('comeArrivare').replace("\\'", "'"),
            'lat': float(c.group(1)), 'lon': float(c.group(2)),
            'latraw': c.group(1), 'lonraw': c.group(2),
        })
    visti, fuori = set(), []
    for s in spot:
        if s['id'] not in visti:
            visti.add(s['id']); fuori.append(s)
    if len(fuori) < 225:
        sys.exit('Letti solo %d spot: la regex ha perso qualcosa, non proseguo.'
                 % len(fuori))
    return fuori


# ---- il testo della scheda -------------------------------------------------
def parole(t):
    t = (t or '').lower().translate(ACCENTI)
    return {p for p in re.sub(r'[^a-z0-9]+', ' ', t).split()
            if len(p) > 3 and p not in GENERICI}


def ancora(s):
    """Le parole con cui la scheda indica il punto, e se si sconsiglia da sola.

    Di 'comeArrivare' si leggono solo le ultime due proposizioni: 167 schede su
    222 ci mettono una strada provinciale, che e' l'itinerario da casa e non il
    posto dove ci si ferma.
    """
    pezzi = re.split(r'[;.]', s.get('comeArrivare') or '')
    coda = ' '.join([p for p in pezzi if p.strip()][-2:])
    testo = ' '.join((s.get('nome') or '', s.get('accesso') or '', coda))
    return parole(testo), bool(NEGA.search(s.get('accesso') or ''))


def combacia_nome(nome_osm, chiave):
    """Il nome di una via o di un manufatto e quello scritto nella scheda.
       Piu' severo di nomi_acqua.combacia: 'Via Roma' non deve valere ovunque."""
    if not nome_osm or not chiave:
        return 0.0
    p = parole(nome_osm)
    if not p:
        return 0.0
    if p <= chiave:
        return 1.0
    # Una parola lunga in comune basta. Prima si guardava solo la piu' lunga,
    # scelta con max() su un insieme: a parita' di lunghezza vinceva quella che
    # l'ordine di iterazione metteva per prima, e quell'ordine cambia a ogni
    # processo. Il file generato usciva diverso da un lancio all'altro.
    if any(len(w) >= 5 and w in chiave for w in p):
        return 0.6
    return 0.0


def normalizza(g):
    """Porta la carta del formato vecchio alla forma che il punteggio si aspetta.

    Del formato nuovo mancano i manufatti (st), le barriere (xb) e i tag delle
    strade (rv): quello che resta sono le strade per classe e l'acqua, e con
    quelle si fanno la sponda, lo scarto dei punti in acqua e quello della riva
    opposta, cioe' la parte che raddrizza i pin. Gli attraversamenti non sono
    nel dato vecchio ma si ricavano qui, incrociando strade e acqua.
    """
    g = dict(g)
    if 'rv' not in g:
        # Nella carta vecchia r1 mescola autostrade e superstrade con le
        # provinciali: quel bake metteva motorway e trunk in classe 1. Non
        # essendo piu' separabili, r1 diventa classe 0 e non produce punti dove
        # fermarsi: meglio due spot in meno che un pin sulla corsia di
        # emergenza della A1.
        g['rv'] = [[cls, 0, '', g[k]] for k, cls in (('r1', 0), ('r2', 2), ('r3', 3))
                   if g.get(k)]
        g['st'] = g.get('st') or []
        g['xb'] = g.get('xb') or []
        # Il tipo di parcheggio nella carta vecchia non c'e'. Ignoto non vuol
        # dire libero: si mette None e il punteggio lo tratta come via di mezzo.
        g['pk'] = [[p[0], p[1], p[2] if len(p) > 2 else None] for p in (g.get('pk') or [])]
    if 'bg' not in g:
        strade = [l for k in ('r1', 'r2', 'r3') for l in geom.linee(g.get(k))]
        acque = [l for k in ('wm', 'wg', 'wp') for l in geom.linee(g.get(k))]
        g['bg'] = [[int(x), int(y)] for x, y in geom.incroci(strade, acque)]
    if 'wb' not in g:
        # Gli stessi contorni ricuciti che bake-locale.py --riscrivi mette in
        # geo-locale.js: la carta che si vede e il punto che si apre devono
        # nascere dalla stessa figura, o tornano a raccontarsi cose diverse.
        aperti = []
        for k in ('ma', 'wa'):
            if not g.get(k):
                continue
            anelli, resto = geom.cuci_anelli(geom.linee(g[k]))
            g[k] = ' '.join(filter(None, (_percorso(p, True) for p in anelli)))
            aperti += resto
        g['wb'] = ' '.join(filter(None, (_percorso(p) for p in aperti)))
    return g


def _percorso(pts, chiudi=False):
    """Rimette una polilinea nel formato 'M x y l dx dy' delle mini-carte."""
    if len(pts) < 2:
        return ''
    fuori = ['M%d %d' % (round(pts[0][0]), round(pts[0][1]))]
    px, py = pts[0]
    for x, y in pts[1:]:
        dx, dy = round(x) - round(px), round(y) - round(py)
        if dx or dy:
            fuori.append('l%d %d' % (dx, dy))
        px, py = x, y
    if chiudi:
        fuori.append('Z')
    return ''.join(fuori) if len(fuori) > 1 else ''


# ---- il calcolo di uno spot ------------------------------------------------
def geometrie(s, g):
    """Asse, sponda e anelli chiusi della sua acqua, in metri locali.

    Torna anche gli anelli veri a parte: dove il contorno si chiude davvero, il
    dentro/fuori e' esatto e va usato al posto del confronto fra le distanze.
    """
    assi = geom.linee(g.get('wm'))
    contorni = geom.linee(g.get('ma')) + geom.linee(g.get('wa')) + geom.linee(g.get('wb'))
    riva = geom.linee(g.get('ma')) + geom.riva_di(assi, contorni, LARGO_RIVA)
    # L'acqua da evitare e' quella che la carta colora: gli anelli veri, quelli
    # che restano dopo aver ricucito i pezzi della relazione. Gli archi rimasti
    # aperti (wb) sono sponde tagliate dal riquadro e non si riempiono ne' qui
    # ne' nel disegno: se si riempissero, un punto all'asciutto risulterebbe in
    # mezzo al fiume tutte e due le volte.
    anelli = (geom.poligoni(g.get('ma')) + geom.poligoni(g.get('wa'))
              + geom.poligoni(g.get('ws')))
    if s['tipo'] == 'mare':
        riva += geom.linee(g.get('ws'))
    if not riva and s['tipo'] in ('lago', 'bacino', 'cava'):
        # Acqua ferma che OpenStreetMap non nomina: una cava, un laghetto. Si
        # adotta il contorno che circonda il pin; se nessuno lo circonda, il
        # piu' lungo li' attorno, anche se il riquadro l'ha tagliato e non si
        # chiude: una riva tagliata resta una riva.
        chiusi = geom.poligoni(g.get('wa'))
        vicini = [p for p in chiusi if geom.dentro((0, 0), [p])]
        if not vicini:
            vicini = sorted((p for p in contorni
                             if geom.piu_vicino((0, 0), [p])[0] < 400),
                            key=geom.lunghezza, reverse=True)[:1]
        riva = vicini
    return assi, riva, anelli


def candidati(s, g, assi, riva, anelli, d_riva, r_max, solo_piedi=False):
    """I punti di strada da cui si arriva alla sua acqua."""
    solo_asse = not riva
    # Si misura dalla sponda dove la sponda c'e', e dalla mezzeria dove non
    # c'e': le due insieme, non l'una al posto dell'altra. La sponda trovata
    # accanto all'asse puo' stare a un chilometro da qui (e' la sponda di un
    # altro tratto), e misurare solo da quella lasciava senza accesso tredici
    # spot che avevano la strada a quattro metri dall'acqua.
    # Chi finisce troppo vicino alla mezzeria di un fiume largo e' in acqua, e
    # lo scarta in_acqua() due righe piu' sotto.
    bersaglio = riva + assi
    if not bersaglio:
        return []
    griglia = geom.Griglia(geom.densifica(bersaglio, PASSO), cella=80.0)
    # Una seconda griglia sulla sola sponda: la domanda "sto guardando la riva
    # di la'?" si misura verso la sponda, non verso la mezzeria. Col piede preso
    # dal bersaglio misto il segmento finiva sull'asse, che non si puo'
    # attraversare, e la risposta dipendeva dal verso della way.
    g_riva = geom.Griglia(geom.densifica(riva, PASSO), cella=80.0) if riva else None
    ponti = [(x, y) for x, y in (g.get('bg') or [])]
    fuori = []
    for cls, bandiere, nome, d in (g.get('rv') or []):
        if cls == 0:                       # in autostrada non ci si ferma
            continue
        if solo_piedi and cls != 3:
            continue
        for linea in geom.densifica(geom.linee(d), PASSO):
            for p in linea:
                if math.hypot(p[0], p[1]) > r_max:
                    continue
                dr, _ = griglia.vicino(p, d_riva)
                if dr > d_riva:
                    continue
                if geom.in_acqua(p, assi, riva, anelli, locale=LOCALE):
                    continue
                if g_riva:
                    _, piede = g_riva.vicino(p, LOCALE)
                    if geom.riva_di_la(p, piede, assi, massimo=LOCALE):
                        continue
                sul_ponte = any(math.dist(p, q) < PONTE_VICINO for q in ponti)
                fuori.append({'p': p, 'cls': cls, 'b': bandiere, 'nome': nome,
                              'd_riva': dr, 'ponte': sul_ponte,
                              'd_pin': math.hypot(p[0], p[1])})
    return fuori


def punteggio(c, s, g, riva_fitta, chiave, nega):
    """Quanto vale questo punto, e perche'. Il motivo piu' pesante si pubblica."""
    v, motivi = 0.0, []

    d = c['d_riva']
    v += 30 if d <= 15 else 25 if d <= 40 else 12 if d <= 90 else 5

    v += {3: 22, 2: 20, 1: 5}.get(c['cls'], 0)

    # il manufatto piu' vicino, piu' meta' del secondo
    vicini = sorted(((VALE.get(k, 0), k, n)
                     for x, y, k, n in (g.get('st') or [])
                     if math.dist(c['p'], (x, y)) <= 120), reverse=True)
    if vicini:
        v += vicini[0][0]
        if vicini[0][0] > 0:
            motivi.append(vicini[0][1])
        if len(vicini) > 1:
            v += vicini[1][0] / 2.0
    # la scala di risalita vieta la pesca anche un po' piu' in la'
    if any(k == 'scala' and math.dist(c['p'], (x, y)) <= 100
           for x, y, k, n in (g.get('st') or [])):
        v -= 25

    pk = sorted(((math.dist(c['p'], (x, y)), -1 if a is None else a)
                 for x, y, a in (g.get('pk') or [])))
    if pk:
        dp, tipo_pk = pk[0]
        # 0 libero · -1 ignoto (carta vecchia) · 1 privato · 2 a pagamento
        vicino = {0: 18, -1: 9}.get(tipo_pk, 5)
        if dp <= 250:
            v += vicino
            motivi.append('parcheggio' if tipo_pk in (0, -1) else
                          'parcheggio privato' if tipo_pk == 1 else
                          'parcheggio a pagamento')
        elif dp <= 600:
            v += {0: 9, -1: 5}.get(tipo_pk, 3)

    # quanta riva serve questa stessa strada: un punto solo puo' essere un caso
    if riva_fitta:
        serviti = sum(PASSO for linea in riva_fitta for q in linea
                      if math.dist(c['p'], q) <= 60)
        v += min(15.0, serviti / 25.0)

    if chiave and not nega:
        peso = combacia_nome(c['nome'], chiave)
        for x, y, k, n in (g.get('st') or []):
            if n and math.dist(c['p'], (x, y)) <= 200:
                peso = max(peso, combacia_nome(n, chiave))
        if peso:
            v += 25 * peso
            motivi.append('come dice la scheda')
    if nega:
        v -= 10

    b = c['b']
    # Un guado, una briglia o una diga sono attraversamenti anche loro, ma sono
    # il posto dove si pesca, non un viadotto: li' la penale non si applica.
    passaggio = any(k in ('guado', 'briglia', 'diga', 'chiusa')
                    and math.dist(c['p'], (x, y)) <= 60
                    for x, y, k, n in (g.get('st') or []))
    if (c['ponte'] or (b & PONTE)) and not passaggio:
        v -= 8 if s['tipo'] == 'canale' else 20
        # da un ponte di canale si scende, da un viadotto sul Po no
    if b & ARGINE and c['d_riva'] > 60:
        v -= 8                              # e' la strada per arrivarci, non l'arrivo
    if b & PRIVATA:
        v -= 15                             # a piedi si passa, in macchina no
    if b & SCONNESSA:
        v -= 5
    if any(math.dist(c['p'], (x, y)) <= 40 for x, y in (g.get('xb') or [])):
        v -= 10
        motivi.append('sbarra')

    # La scheda descrive un tratto, non il fiume intero: allontanarsi dal pin
    # costa. Il tetto va raggiunto dentro la finestra, o il termine serve solo a
    # rompere i pari merito fra due punti della stessa strada.
    v -= min(15.0, c['d_pin'] / 45.0)
    return v, motivi


def scegli(s, g):
    """Il punto di accesso di uno spot: (x, y, confidenza, motivo) o None."""
    assi, riva, anelli = geometrie(s, g)
    chiave, nega = ancora(s)
    solo_asse = not riva
    d_base = D_RIVA_ASSE if solo_asse else D_RIVA
    # una volta sola: infittire la riva dentro il punteggio voleva dire rifarlo
    # per ognuno dei candidati, che su un lago sono centocinquanta
    riva_fitta = geom.densifica(riva, PASSO) if riva else []

    # si allarga solo quando serve, e ogni allargamento costa un livello
    giri = [(d_base, R_MAX, False, 0), (d_base * 2.25, R_MAX, False, 1),
            (150.0, R_MAX, True, 2), (d_base * 2.25, R_MAX_LARGO, False, 2)]
    for d_riva, r_max, piedi, costo in giri:
        cs = candidati(s, g, assi, riva, anelli, d_riva, r_max, piedi)
        if not cs:
            continue
        for c in cs:
            c['v'], c['motivi'] = punteggio(c, s, g, riva_fitta, chiave, nega)
        cs.sort(key=lambda c: -c['v'])
        best = cs[0]
        # Confidenza, e soprattutto il PERCHE': f=2 aveva quattro cause diverse
        # e la scheda ne raccontava sempre una sola, che per meta' degli spot
        # era falsa. La causa esce insieme al numero.
        f, causa = 3, ''
        # "senza sponda" si decide sul punto scelto, non sulla finestra intera:
        # basta un frammento di riva riconosciuto in un angolo del riquadro
        # perche' l'intero spot sembri misurato sulla sponda.
        lontano = (not riva) or geom.piu_vicino(best['p'], riva)[0] > LOCALE
        if lontano:
            f, causa = 2, 'mezzeria'
        elif best['ponte']:
            f, causa = 2, 'ponte'
        elif best['cls'] == 1:
            f, causa = 2, 'strada grossa'
        if best['d_riva'] > 90 or costo >= 2:
            f, causa = 1, 'allargato'
        if costo and f > 1:
            f, causa = f - 1, causa or 'allargato'
        motivo = best['motivi'][0] if best['motivi'] else (
            'sterrata sulla riva' if best['cls'] == 3 else 'strada sulla riva')
        return best['p'], f, motivo, causa, best['v'], len(cs)
    return None


# ---- scrittura -------------------------------------------------------------
def main():
    carte = {}
    if os.path.exists(CACHE_V2):
        carte = json.load(open(CACHE_V2)); carte.pop('__v', None)
    vecchie = len(carte)
    if os.path.exists(CACHE):
        nuove = json.load(open(CACHE)); nuove.pop('__v', None)
        carte.update(nuove)          # la carta nuova vince, dove c'e'
    else:
        nuove = {}
    if not carte:
        sys.exit('Nessuna mini-carta: lancia prima tools/bake-locale.py')
    sys.stderr.write('Carte: %d col dato nuovo (manufatti e tag), %d col vecchio\n'
                     % (len(nuove), max(0, vecchie - len(set(nuove) & set(carte)))))
    mano = {}
    if os.path.exists(MANO):
        mano = {k: v for k, v in json.load(open(MANO)).items()
                if not k.startswith('__')}
    spot = leggi_spot()
    solo = sys.argv[sys.argv.index('--solo') + 1] if '--solo' in sys.argv else None
    spiega = '--spiega' in sys.argv

    fuori, conta, deboli = {}, {1: 0, 2: 0, 3: 0}, []
    for s in spot:
        if solo and s['id'] != solo:
            continue
        g = carte.get(s['id'])
        # una correzione a mano comanda su tutto, ma solo se il pin non si e'
        # mosso da quando qualcuno l'ha guardata
        m = mano.get(s['id'])
        if m:
            pin = '%s,%s' % (s['latraw'], s['lonraw'])
            if m.get('p') and m['p'] != pin:
                sys.stderr.write('%-32s pin cambiato da quando fu verificato '
                                 '(%s -> %s): rifaccio il conto\n'
                                 % (s['id'], m['p'], pin))
            else:
                fuori[s['id']] = [round(m['lat'], 5), round(m['lon'], 5),
                                  m.get('f', 3), m.get('m', 'controllato a mano'),
                                  'mano']
                conta[m.get('f', 3)] = conta.get(m.get('f', 3), 0) + 1
                continue
        if not g:
            deboli.append((s['id'], 'senza mini-carta')); continue
        r = scegli(s, normalizza(g))
        if not r:
            deboli.append((s['id'], 'nessuna strada arriva alla sua acqua')); continue
        (x, y), f, motivo, causa, v, n = r
        lat, lon = geom.a_gradi(x, y, s['lat'], s['lon'])
        fuori[s['id']] = [round(lat, 5), round(lon, 5), f, motivo, causa]
        conta[f] = conta.get(f, 0) + 1
        if spiega:
            print('%-32s f=%d %-14s %-22s punteggio %5.1f  su %3d candidati  '
                  'sposta %4.0f m'
                  % (s['id'], f, causa or '-', motivo, v, n, math.hypot(x, y)))

    if solo:
        return

    righe = ["/* Il punto di accesso di ogni spot: generato da tools/accessi.py",
             '   Dati: (c) OpenStreetMap contributors, licenza ODbL.',
             '',
             "   Non e' la coordinata della scheda: quella dice di che pezzo di",
             '   fiume parlano il meteo e la portata, e sui fiumi larghi cade in',
             "   mezzo all'acqua. Questa dice dove ci si ferma con la macchina e",
             '   da dove si tira. La aprono i tasti OpenStreetMap, Google Maps e',
             '   Naviga, e nientaltro.',
             '',
             '   [lat, lon, confidenza, motivo, causa]',
             '   confidenza 3 sponda disegnata e strada su cui ci si ferma',
             '              2 buono; la causa dice cosa manca',
             '              1 trovato allargando le soglie: tratto giusto, punto',
             '                non esatto',
             '   causa      mezzeria · ponte · strada grossa · allargato · mano',
             '',
             '   Le correzioni a mano stanno in tools/accessi-verificati.json e',
             '   vincono su questo file. NON modificare a mano: rilancia lo script. */',
             '',
             'const ACCESSI = {']
    for sid in sorted(fuori):
        lat, lon, f, m, causa = fuori[sid]
        righe.append('"%s":[%.5f,%.5f,%d,"%s","%s"],' % (sid, lat, lon, f, m, causa))
    righe.append('};')
    with open(OUT, 'w') as fh:
        fh.write('\n'.join(righe) + '\n')

    tot = len(spot)
    sys.stderr.write('\nScritto %s, %d spot su %d (%.1f KB)\n'
                     % (OUT, len(fuori), tot, os.path.getsize(OUT) / 1024))
    sys.stderr.write('  confidenza 3: %d · 2: %d · 1: %d\n'
                     % (conta.get(3, 0), conta.get(2, 0), conta.get(1, 0)))
    if deboli:
        sys.stderr.write('  senza punto (%d), il tasto resta sulla coordinata '
                         'della scheda:\n' % len(deboli))
        for sid, perche in deboli:
            sys.stderr.write('    %-32s %s\n' % (sid, perche))


if __name__ == '__main__':
    main()
