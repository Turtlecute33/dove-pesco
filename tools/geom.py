#!/usr/bin/env python3
"""
La geometria delle mini-carte, in un posto solo.

Le carte di assets/js/geo-locale.js parlano in metri, con l'origine sulle
coordinate dello spot e la y verso sud. Qui stanno le funzioni che le leggono
e le misurano: erano copiate in tre script, ognuno con la sua versione.

Due avvertenze che valgono per chiunque misuri su queste carte.

La prima: un anello che si chiude con una corda lunga non e' un poligono. Il
ritaglio del riquadro taglia i contorni d'acqua, e d_path li richiude con una
retta che sul terreno non esiste: su pr-taro-fornovo quella retta e' lunga
16 km. Chiedere "sono dentro l'acqua?" a un poligono cosi' risponde di un lato
inventato. Qui un anello del genere torna aperto: e' una riva, non un contorno.

La seconda: i contorni d'acqua sono semplificati a 23 m e le strade a 9. Sotto
i 25 m non si misura niente di sensato, per quanto si scrivano decimali.
"""
import math
import re

CORDA_FINTA = 60.0      # metri: oltre questa, la chiusura di un anello e' inventata
EPS_AREE = 23.4         # la semplificazione dei contorni d'acqua in bake-locale.py
EPS_STRADE = 12.6       # quella delle strade di classe 3, la piu' grossolana
BORDO = 8.0             # metri: sul bordo dell'acqua si e' sulla riva, non dentro
LOCALE = 200.0          # oltre, la sponda riconosciuta non e' piu' quella di qui


# ---- lettura dei percorsi --------------------------------------------------
def percorsi(d):
    """Le polilinee di 'M x y l dx dy ... Z', in metri: lista di (punti, chiuso)."""
    fuori, cur, x, y = [], None, 0.0, 0.0

    def consegna(chiudi):
        if not cur or len(cur) < 2:
            return
        if chiudi and math.dist(cur[0], cur[-1]) <= CORDA_FINTA:
            fuori.append((cur + [cur[0]], True))
        else:
            fuori.append((cur, False))

    for t in re.findall(r'[MlZ][^MlZ]*', d or ''):
        n = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', t[1:])]
        if t[0] == 'M':
            consegna(False)
            cur = None
            if len(n) >= 2:
                x, y = n[0], n[1]
                cur = [(x, y)]
        elif t[0] == 'l' and cur is not None:
            for i in range(0, len(n) - 1, 2):
                x += n[i]; y += n[i + 1]
                cur.append((x, y))
        elif t[0] == 'Z':
            consegna(True)
            cur = None
    consegna(False)
    return fuori


def linee(d):
    """Tutte le polilinee, aperte e chiuse: quello su cui si misura una distanza."""
    return [p for p, _ in percorsi(d)]


def poligoni(d):
    """Solo gli anelli che si chiudono davvero: quello su cui si chiede dentro/fuori."""
    return [p for p, chiuso in percorsi(d) if chiuso]


def cuci_anelli(pezzi, tol=1.5):
    """Ricuce i contorni d'acqua spezzati, e dice quali si chiudono davvero.

    Un lago o un fiume grande, in OpenStreetMap, e' una relazione: il suo
    contorno arriva a pezzi, un membro `outer` per volta. Ogni pezzo, da solo,
    e' un arco che non si chiude, e il browser, per riempirlo, lo chiude
    d'ufficio con una retta. Da li' le macchie d'azzurro larghe chilometri, con
    dentro le strade e il nome di un paese: acqua che non esiste, disegnata
    sopra la terra su cui si va a pescare.

    Rimessi in fila per gli estremi, quei pezzi tornano l'anello che erano.
    dp() non tocca mai il primo e l'ultimo punto, quindi gli estremi combaciano
    ancora dopo la semplificazione.

    Torna (anelli_chiusi, archi_aperti).
    """
    k = lambda p: (round(p[0] / tol), round(p[1] / tol))
    resto = [list(p) for p in pezzi if len(p) > 1]
    anelli, aperti = [], []
    while resto:
        catena = resto.pop(0)
        mosso = True
        while mosso and k(catena[0]) != k(catena[-1]):
            mosso = False
            for i, altro in enumerate(resto):
                if k(altro[0]) == k(catena[-1]):
                    catena += altro[1:]; resto.pop(i); mosso = True; break
                if k(altro[-1]) == k(catena[-1]):
                    catena += altro[::-1][1:]; resto.pop(i); mosso = True; break
                if k(altro[-1]) == k(catena[0]):
                    catena = altro[:-1] + catena; resto.pop(i); mosso = True; break
                if k(altro[0]) == k(catena[0]):
                    catena = altro[::-1][:-1] + catena; resto.pop(i); mosso = True; break
        if k(catena[0]) == k(catena[-1]) and len(catena) > 3:
            anelli.append(catena)
        else:
            aperti.append(catena)
    return anelli, aperti


def riempiti(d):
    """Le superfici come le colora il browser.

    SVG, per riempire, chiude d'ufficio ogni sottopercorso: anche un contorno
    che il riquadro ha tagliato e che non si chiude viene dipinto d'azzurro.
    Quindi la macchia d'acqua che si vede sulla carta comprende anche gli archi
    aperti, e un punto li' dentro *sembra* in mezzo al fiume, che e' esattamente
    la cosa di cui ci si lamenta. Per decidere dove mandare chi guida vale
    questa figura, non quella geometricamente pulita: la carta e il tasto devono
    raccontare la stessa cosa.
    """
    return [p for p, _ in percorsi(d) if len(p) > 2]


# ---- misure ----------------------------------------------------------------
def densifica(ls, passo=20.0):
    """Spezza i segmenti lunghi. Senza, un arginale rettilineo con due soli
       vertici a 400 m di distanza non ha nessun punto vicino all'acqua."""
    fuori = []
    for linea in ls:
        if len(linea) < 2:
            continue
        out = [linea[0]]
        for i in range(len(linea) - 1):
            ax, ay = linea[i]; bx, by = linea[i + 1]
            d = math.hypot(bx - ax, by - ay)
            for k in range(1, int(d // passo) + 1):
                t = k * passo / d
                out.append((ax + t * (bx - ax), ay + t * (by - ay)))
            out.append((bx, by))
        fuori.append(out)
    return fuori


def dist_punto_seg(px, py, ax, ay, bx, by):
    """(distanza, piede) dal punto al segmento."""
    dx, dy = bx - ax, by - ay
    n2 = dx * dx + dy * dy
    t = 0.0 if n2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / n2))
    fx, fy = ax + t * dx, ay + t * dy
    return math.hypot(fx - px, fy - py), (fx, fy)


def piu_vicino(p, ls):
    """(distanza, piede) fra un punto e la piu' vicina di queste polilinee."""
    px, py = p
    bd, bp = float('inf'), None
    for linea in ls:
        for i in range(len(linea) - 1):
            d, f = dist_punto_seg(px, py, linea[i][0], linea[i][1],
                                  linea[i + 1][0], linea[i + 1][1])
            if d < bd:
                bd, bp = d, f
    return bd, bp


def dentro(p, polys):
    """Il punto sta dentro uno di questi anelli. Solo anelli veri: vedi percorsi()."""
    px, py = p
    for poly in polys:
        colpi = False
        n = len(poly)
        for i in range(n):
            ax, ay = poly[i]; bx, by = poly[(i + 1) % n]
            if (ay > py) != (by > py):
                if ax + (py - ay) * (bx - ax) / (by - ay) > px:
                    colpi = not colpi
        if colpi:
            return True
    return False


def taglia(a, b, c, d):
    """I due segmenti ab e cd si incrociano davvero, estremi esclusi.

    Il tocco su un estremo non e' un incrocio. Senza questa distinzione la
    risposta dipendeva dal verso in cui la way era disegnata: lo stesso punto
    veniva scartato o tenuto a seconda di come OpenStreetMap aveva orientato la
    linea, e su un fiume la mezzeria tocca il piede della perpendicolare per
    costruzione, cioe' quasi sempre.
    """
    def lato(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2 = lato(c, d, a), lato(c, d, b)
    d3, d4 = lato(a, b, c), lato(a, b, d)
    if 0.0 in (d1, d2, d3, d4):
        return False
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def incrocio(a, b, c, d):
    """Il punto in cui ab taglia cd, o None."""
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    den = rx * sy - ry * sx
    if den == 0:
        return None
    t = ((c[0] - a[0]) * sy - (c[1] - a[1]) * sx) / den
    return (a[0] + t * rx, a[1] + t * ry)


def attraversa(p, q, ls):
    """Il segmento pq taglia una di queste linee."""
    for linea in ls:
        for i in range(len(linea) - 1):
            if taglia(p, q, linea[i], linea[i + 1]):
                return True
    return False


def riva_di_la(p, piede, assi, minimo=20.0, massimo=LOCALE):
    """Per arrivare all'acqua da qui bisogna scavalcare la mezzeria: la sponda
       che si sta guardando e' quella di la', a un fiume di distanza.

    Sotto `minimo` la domanda non ha senso e la risposta e' sempre no: su un
    portocanale la banchina e la mezzeria sono la stessa linea a un metro di
    distanza, e un passo di un metro non scavalca un fiume.

    Sopra `massimo` nemmeno: quella sponda non e' la sponda di qui, e' un pezzo
    di riva riconosciuto un chilometro piu' in la'. La stessa soglia di
    in_acqua(), e per lo stesso motivo.
    """
    if not piede or not assi:
        return False
    d = math.dist(p, piede)
    if d < minimo or d > massimo:
        return False
    # Se il piede sta sulla mezzeria, la mezzeria non si puo' attraversare per
    # arrivarci: la domanda non ha oggetto. Senza questa riga la risposta si
    # decideva sull'ultimo bit del calcolo: lo stesso punto, misurato in due
    # modi che danno lo stesso piede, veniva scartato una volta su due.
    if piu_vicino(piede, assi)[0] < 1.0:
        return False
    return attraversa(p, piede, assi)


def incroci(strade, acque):
    """I punti in cui una strada taglia l'acqua: sono ponti, non posti dove
       si pesca. Il pin di uno spot non deve finire in mezzo a un ponte.

    Si restituisce l'incrocio vero, non la mezzeria del segmento di strada:
    dopo la semplificazione un rettilineo puo' essere lungo centinaia di metri,
    e il suo punto di mezzo puo' cadere lontanissimo dal ponte.
    """
    fuori = []
    for s in strade:
        for i in range(len(s) - 1):
            a, b = s[i], s[i + 1]
            for w in acque:
                for j in range(len(w) - 1):
                    if taglia(a, b, w[j], w[j + 1]):
                        p = incrocio(a, b, w[j], w[j + 1])
                        if p:
                            fuori.append(p)
                        break
    return fuori


class Griglia:
    """Indice a celle per non confrontare tutto con tutto."""

    def __init__(self, ls, cella=60.0):
        self.cella = cella
        self.celle = {}
        for linea in ls:
            for i in range(len(linea) - 1):
                a, b = linea[i], linea[i + 1]
                for cx in range(int(min(a[0], b[0]) // cella), int(max(a[0], b[0]) // cella) + 1):
                    for cy in range(int(min(a[1], b[1]) // cella), int(max(a[1], b[1]) // cella) + 1):
                        self.celle.setdefault((cx, cy), []).append((a, b))

    def vicino(self, p, rmax):
        """(distanza, piede) dal punto, guardando solo le celle a portata."""
        px, py = p
        passi = int(rmax // self.cella) + 1
        gx, gy = int(px // self.cella), int(py // self.cella)
        bd, bp = float('inf'), None
        for i in range(-passi, passi + 1):
            for j in range(-passi, passi + 1):
                for a, b in self.celle.get((gx + i, gy + j), ()):
                    d, f = dist_punto_seg(px, py, a[0], a[1], b[0], b[1])
                    if d < bd:
                        bd, bp = d, f
        return bd, bp


def lunghezza(linea):
    return sum(math.dist(linea[i], linea[i + 1]) for i in range(len(linea) - 1))


def riva_di(assi, contorni, largo=200.0):
    """La sponda del corso d'acqua della scheda, presa un pezzo alla volta.

    OpenStreetMap disegna un fiume grande due volte: la linea di mezzeria, che
    porta il nome, e il contorno delle sponde, quasi sempre senza nome. Il
    contorno senza nome finiva fra gli specchi d'acqua di sfondo e non lo
    guardava nessuno, ed e' proprio la riva su cui si sta in piedi. Su tutti e
    23 gli spot del Po la sponda c'era, e non era mai stata usata.

    Non si adotta il contorno intero: sul Po e' un arco da 31 km che il
    riquadro taglia, comprende lanche e isole e non si chiude mai. Si tengono i
    suoi pezzi che corrono accanto all'asse, entro `largo`. Cosi' la sponda si
    riconosce dove serve, e una pozza a un chilometro resta fuori senza dover
    decidere niente su tutto il resto.
    """
    if not assi:
        return []
    g = Griglia(assi, cella=max(60.0, largo / 2))
    fuori = []
    for linea in contorni:
        cur = []
        for i in range(len(linea) - 1):
            a, b = linea[i], linea[i + 1]
            mezzo = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if g.vicino(mezzo, largo)[0] <= largo:
                cur = (cur or [a]) + [b]
            elif cur:
                if len(cur) > 1:
                    fuori.append(cur)
                cur = []
        if len(cur) > 1:
            fuori.append(cur)
    return fuori


def in_acqua(p, assi, rive, anelli=(), locale=LOCALE):
    """Il punto sta nell'acqua, non sulla riva. Due prove, in quest'ordine.

    Dove il contorno si chiude davvero (un lago, una cava, uno specchio tutto
    dentro il riquadro) vale il dentro/fuori, che e' esatto.

    Su un fiume no: il contorno e' un arco che il riquadro taglia, e chiuderlo
    per forza inventa un lato lungo chilometri. Li' bastano la mezzeria e la
    sponda: chi e' all'asciutto ha la sponda piu' vicina della mezzeria, chi e'
    in acqua ha la mezzeria piu' vicina.

    Ma il confronto vale solo se la sponda e' quella di qui. La sponda si
    riconosce a pezzi, e il pezzo piu' vicino puo' stare a un chilometro, sul
    tratto sbagliato: allora "la mezzeria e' piu' vicina della sponda" e' vero
    per tutta la finestra, e ogni punto risulta annegato. Oltre `locale` non
    sappiamo quanto e' largo il fiume, e chi non sa non condanna: un corso
    d'acqua senza sponda disegnata e' stretto, e stargli a fianco e' giusto.
    """
    if anelli and dentro(p, anelli):
        # Sul bordo la domanda non ha una risposta: dentro o fuori dipende
        # dall'arrotondamento, e il bordo e' proprio il posto dove si sta in
        # piedi a pescare. Sotto BORDO si e' sulla riva, non nell'acqua: con
        # una geometria semplificata a 23 m, otto sono una tolleranza prudente.
        if not rive or piu_vicino(p, rive)[0] > BORDO:
            return True
    if not assi or not rive:
        return False
    d_riva = piu_vicino(p, rive)[0]
    if d_riva > locale:
        return False
    return piu_vicino(p, assi)[0] < d_riva


# ---- avanti e indietro fra metri e gradi -----------------------------------
def a_gradi(x, y, lat0, lon0):
    """Dai metri locali alla latitudine e longitudine. La y va verso sud."""
    return (lat0 - y / 110540.0,
            lon0 + x / (111320.0 * math.cos(math.radians(lat0))))


def in_metri(lat, lon, lat0, lon0):
    """Da latitudine e longitudine ai metri locali della carta di quello spot."""
    return ((lon - lon0) * 111320.0 * math.cos(math.radians(lat0)),
            -(lat - lat0) * 110540.0)
