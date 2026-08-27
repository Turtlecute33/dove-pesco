#!/usr/bin/env python3
"""
Confronta il nome dell'acqua di una scheda con quello che scrive OpenStreetMap.

Le schede dicono "Torrente Limentra di Treppio", OpenStreetMap in quel punto
scrive "Limentra"; le schede dicono "Collettore Acque Alte", OpenStreetMap
"Canale Collettore delle Acque Alte". Confrontare le stringhe intere non
funziona: si confrontano le parole che restano dopo aver buttato i generici
(fiume, torrente, canale, di, del...). Se una parola coincide, e' la stessa
acqua — dentro una finestra di pochi chilometri non ci sono omonimi.

Serve a due script, quindi sta qui e non dentro uno dei due:
  tools/bake-locale.py   disegna in grande l'acqua della scheda
  tools/ricalibra.py     aggancia la coordinata a quell'acqua
"""
import re

GENERICI = {
    'fiume', 'fiumi', 'torrente', 'rio', 'rii', 'canale', 'canal', 'cavo', 'fosso',
    'scolo', 'condotto', 'collettore', 'lago', 'laghi', 'laghetto', 'laghetti',
    'bacino', 'invaso', 'diga', 'dighe', 'cava', 'cave', 'foce', 'foci', 'porto',
    'portocanale', 'molo', 'moli', 'spiaggia', 'pontile', 'sacca', 'valle', 'valli',
    'casse', 'cassa', 'espansione', 'di', 'del', 'dei', 'della', 'delle', 'dello',
    'da', 'dal', 'd', 'l', 'la', 'il', 'lo', 'le', 'i', 'gli', 'e', 'a', 'in', 'su',
    'vecchio', 'nuovo', 'grande', 'piccolo', 'sinistra', 'destra',
}
ACCENTI = str.maketrans('àáâãäèéêëìíîïòóôõöùúûüçñ', 'aaaaaeeeeiiiiooooouuuucn')


def parole(nome):
    """le parole che identificano l'acqua, senza i generici"""
    n = (nome or '').lower().translate(ACCENTI)
    n = re.sub(r"[^a-z0-9]+", ' ', n)
    return {p for p in n.split() if p and p not in GENERICI}


def combacia(nome_osm, chiave):
    """il nome di OSM e quello della scheda parlano della stessa acqua"""
    return bool(chiave) and bool(parole(nome_osm) & chiave)


# Dove il nome della scheda e quello di OpenStreetMap non hanno nemmeno una
# parola in comune. Sono quasi tutti invasi e canali di bonifica: il nome che
# usa chi pesca non e' quello scritto in mappa.
ALIAS = {
    'Casse di espansione del Secchia': ['Secchia'],
    'Casse di espansione del Panaro': ['Panaro'],
    'Ex cave del Marecchia': ['Marecchia'],
    'Bacino di Gazzano': ['Lago di Fontanaluccia'],
    'Invaso di Ridracoli': ['Lago di Ridracoli'],
    'Lago del Molato': ['Lago di Trebecco', 'Tidone'],
    'Laghi Cerretani': ['Lago Pranda'],
    'Laghi Gemini': ['Lagoni'],
    'Bacino di Mignano': ['Lago di Mignano'],
    'Bacino di Suviana': ['Lago di Suviana'],
    'Bacino del Brasimone': ['Lago del Brasimone'],
    'Bacino di Santa Maria': ['Lago di Santa Maria', 'Limentra di Treppio'],
    'Cavo Fiuma': ['Cavo Fiuma Parmigiana-Moglia'],
    'Canale Destra Reno': ['Canale di Bonifica Destra Reno'],
    'Idrovia ferrarese': ['Po di Volano'],
    'Canale Navigabile': ['Canale Navigabile Migliarino-Porto Garibaldi'],
    'Canali Botte e Lorgana': ['Canale Lorgana'],
    'Laghetti di Castrola': ['Limentra di Treppio'],
    'Lago di Castel dell\'Alpi': ['Savena'],
    'Lago di Quarto': ['Fiume Savio'],
    'Lago di Ponte': ['Torrente Tramazzo'],
    'Lago di Pometo': ['Taro'],
    'Laghi Pozzo Rosso, Rosso Basso, Rosso Alto': ['Rio Sanguinario'],
    'Laghetto del Gelso': ['Uso'],
    'Lago della Fiera': ['Ausa'],
    'Bidentino': ['Bidente di Pietrapazza'],
    'Sacca di Goro': ['Po di Goro'],
    'Collettore Acque Alte': ['Canale Collettore delle Acque Alte'],
    'Canale Circondariale': ['Gramigna', 'Fattibello'],
}


def chiave(acqua):
    """le parole con cui riconoscere quell'acqua, alias compresi"""
    t = parole(acqua)
    for a in ALIAS.get(acqua, ()):
        t |= parole(a)
    return t


def distintivo(nome):
    """la parola piu' caratteristica: quella da dare a Overpass per cercare"""
    p = sorted(parole(nome), key=lambda w: (-len(w), w))
    return p[0] if p else None


def cerca(acqua, quante=3):
    """i termini da dare a Overpass: le parole piu' lunghe, che sbagliano meno"""
    return sorted(chiave(acqua), key=lambda w: (-len(w), w))[:quante]
