#!/usr/bin/env python3
"""
Da quale cella di GloFAS si legge la portata di ogni spot.

GloFAS lavora su una griglia di 0,05 gradi, circa 5 km, e in ogni cella scorre
al piu' un fiume: quello che il modello ci ha messo, che non sempre e' quello
che ci passa davvero. Open-Meteo restituisce la cella piu' vicina alla
coordinata, e basta. Se il fiume del modello sta nella cella accanto, lo spot
legge il deflusso locale di un pezzo di campagna: 0,06 m3/s a Pontelagoscuro,
dove il Po ne porta mille.

Misurato sui 149 spot di fiume e torrente, a novembre 2026: 72 leggevano una
cella almeno cinque volte piu' povera di una delle otto intorno. Sette spot su
diciassette del Po stavano fra 0,06 e 0,17 m3/s. Lo scarto sulla mediana, che e'
quello che entra nell'indice, su numeri cosi' e' rumore: da 0,02 a 0,09 e' «piena».

Questo script chiede a GloFAS le nove celle intorno a ogni spot e sceglie:

  1. se la cella dello spot regge il confronto (almeno un quinto della piu'
     ricca), resta quella: e' su una rete, e di meglio intorno non c'e';
  2. altrimenti passa alla cella piu' ricca fra le nove;
  3. un affluente non deve leggere il Po: fuori dal Po e dal Po di Goro si
     scartano le celle oltre TETTO m3/s di media.

Dove sceglie la cella di un fiume vicino piu' grosso invece di quella del
torrente (succede alle confluenze), lo scarto resta quello dello stesso bacino
e delle stesse piogge: e' un indice peggiore del vero, e molto migliore di una
cella senza fiume. Le eccezioni decise a mano stanno in MANUALE.

Scrive la tabella in assets/js/data-index.js, fra i due segni CELLE_PORTATA.
La leggono tools/aggiorna-dati.py e, quando il browser va in rete da solo,
assets/js/api.js.

    python3 tools/celle-portata.py             # chiede a GloFAS e riscrive la tabella
    python3 tools/celle-portata.py --riscrivi  # dalla cache, senza rete
    python3 tools/celle-portata.py --prova     # stampa e non scrive

Va rilanciato quando si aggiunge uno spot di fiume o torrente, o si sposta una
coordinata. Circa 1.350 punti a 30 giorni l'uno: dieci richieste distanziate,
una decina di minuti, per restare sotto il limite al minuto di Open-Meteo.
"""
import json, os, re, sys, time, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from elenchi import BASE, CORSI, leggi_spot

FLOOD_URL = 'https://flood-api.open-meteo.com/v1/flood'
UA = {'User-Agent': 'dove-pesco-static-site/1.0 (scelta delle celle di portata)'}
CACHE = os.path.join(BASE, 'tools', '.cache-portata.json')
INDICE = os.path.join(BASE, 'assets', 'js', 'data-index.js')

PASSO = 0.05        # il lato della cella di GloFAS, in gradi
GIORNI = 30         # su quanti giorni si fa la media della portata
LOTTO = 150         # punti per richiesta: 150 x 3 = 450 chiamate, sotto le 600 al minuto
PAUSA = 62          # secondi fra una richiesta e l'altra: il limite e' al minuto
SOGLIA = 5          # la cella dello spot resta se vale almeno 1/SOGLIA della migliore
TETTO = 300         # m3/s di media oltre cui una cella e' il Po, non un affluente
SENZA_TETTO = ('Fiume Po', 'Po di Goro')

# Scelte a mano, come scarto (colonne verso est, righe verso nord) dalla cella
# dello spot. Ognuna con il suo perche'.
MANUALE = {
    # La cella dello spot porta 6 m3/s di un corso minore e supera la soglia;
    # il Taro, con il Ceno gia' dentro, e' quella a ovest (21 m3/s).
    'pr-taro-san-secondo': (-1, 0),
}

INIZIO = '/* CELLE_PORTATA:inizio (generato da tools/celle-portata.py, non modificare a mano) */'
FINE = '/* CELLE_PORTATA:fine */'


def chiedi(url):
    for giro in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            sys.stderr.write('    HTTP %s, riprovo fra %ds\n' % (e.code, PAUSA))
        except Exception as e:
            sys.stderr.write('    %s, riprovo fra %ds\n' % (type(e).__name__, PAUSA))
        time.sleep(PAUSA)
    return None


def scarica(corsi):
    punti = [{'id': s['id'], 'dx': dx, 'dy': dy,
              'lat': s['lat'] + dy * PASSO, 'lon': s['lon'] + dx * PASSO}
             for s in corsi for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
    lotti = [punti[i:i + LOTTO] for i in range(0, len(punti), LOTTO)]
    for n, lotto in enumerate(lotti, 1):
        sys.stderr.write('  celle, lotto %d/%d\n' % (n, len(lotti)))
        r = chiedi('%s?latitude=%s&longitude=%s&daily=river_discharge&past_days=%d&forecast_days=1'
                   % (FLOOD_URL, ','.join('%.4f' % p['lat'] for p in lotto),
                      ','.join('%.4f' % p['lon'] for p in lotto), GIORNI))
        if r is None:
            sys.exit('GloFAS non risponde: la tabella resta quella di prima.')
        for p, rj in zip(lotto, r if isinstance(r, list) else [r]):
            q = [v for v in (rj.get('daily') or {}).get('river_discharge', []) if v is not None]
            p['clat'], p['clon'] = rj.get('latitude'), rj.get('longitude')
            p['mean'] = sum(q) / len(q) if q else None
        if n < len(lotti):
            time.sleep(PAUSA)
    return punti


def scegli(corsi, punti):
    per_spot = {}
    for p in punti:
        per_spot.setdefault(p['id'], []).append(p)
    celle, righe = {}, []
    for s in corsi:
        nove = per_spot.get(s['id'])
        if not nove:
            righe.append((s, None, None, 'non in cache: rilancia senza --riscrivi'))
            continue
        sua = next(p for p in nove if p['dx'] == 0 and p['dy'] == 0)
        tetto = float('inf') if s['acqua'] in SENZA_TETTO else TETTO
        buone = sorted((p for p in nove if p['mean'] is not None and p['mean'] <= tetto),
                       key=lambda p: -p['mean'])
        scelta, come = sua, ''
        if s['id'] in MANUALE:
            scelta = next(p for p in nove if (p['dx'], p['dy']) == MANUALE[s['id']])
            come = 'a mano'
        elif buone and not (sua['mean'] is not None and sua['mean'] <= tetto
                            and sua['mean'] >= buone[0]['mean'] / SOGLIA):
            scelta, come = buone[0], 'spostata'
        if scelta is not sua:
            celle[s['id']] = [round(scelta['clat'], 3), round(scelta['clon'], 3)]
        righe.append((s, sua['mean'], scelta['mean'], come))
    return celle, righe


def scrivi(celle):
    blocco = [INIZIO, 'const CELLE_PORTATA = {']
    blocco += ["  '%s': [%.3f, %.3f]," % (k, v[0], v[1]) for k, v in sorted(celle.items())]
    blocco[-1] = blocco[-1].rstrip(',')
    blocco += ['};', FINE]
    testo = open(INDICE, encoding='utf-8').read()
    nuovo = '\n'.join(blocco)
    if INIZIO in testo:
        testo = re.sub(re.escape(INIZIO) + r'[\s\S]*?' + re.escape(FINE), lambda m: nuovo, testo)
    else:
        testo = testo.rstrip('\n') + '\n\n' + INTESTAZIONE + nuovo + '\n'
    with open(INDICE, 'w', encoding='utf-8') as f:
        f.write(testo)


INTESTAZIONE = """/* -----------------------------------------------------------------------------
   CELLE DI PORTATA
   GloFAS lavora su celle di 5 km e Open-Meteo restituisce quella più vicina
   alla coordinata, che spesso non è quella in cui il modello fa scorrere il
   fiume: a Pontelagoscuro rispondeva 0,06 m³/s, con il Po a mille nella cella
   accanto. Per gli spot elencati qui la portata si chiede al centro di una
   cella vicina, scelta da tools/celle-portata.py; per tutti gli altri alla
   coordinata dello spot. Meteo e quota restano sempre sulla coordinata dello
   spot.
   -------------------------------------------------------------------------- */
"""


def num(v):
    return '   n/d' if v is None else ('%6.0f' % v if v >= 100 else '%6.2f' % v)


def main():
    corsi = [s for s in leggi_spot() if s['tipo'] in CORSI]
    if '--riscrivi' in sys.argv:
        if not os.path.exists(CACHE):
            sys.exit('manca %s: rilancia senza --riscrivi' % CACHE)
        punti = json.load(open(CACHE))
    else:
        punti = scarica(corsi)
        if '--prova' not in sys.argv:
            json.dump(punti, open(CACHE, 'w'), separators=(',', ':'))
    celle, righe = scegli(corsi, punti)
    for s, prima, dopo, come in righe:
        if come:
            sys.stderr.write('  %-34s %-28s %s -> %s  %s\n'
                             % (s['id'], s['acqua'][:28], num(prima), num(dopo), come))
    sys.stderr.write('\n%d spot di fiume e torrente, %d leggono una cella vicina\n'
                     % (len(corsi), len(celle)))
    if '--prova' in sys.argv:
        return 0
    scrivi(celle)
    sys.stderr.write('Scritta la tabella in %s\n' % os.path.relpath(INDICE, BASE))
    return 0


if __name__ == '__main__':
    sys.exit(main())
