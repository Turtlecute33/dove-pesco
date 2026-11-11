#!/usr/bin/env python3
"""
Scarica meteo e portata per tutti gli spot e li scrive in un unico file
statico: assets/dati/previsioni.json

A cosa serve. Se ogni visitatore chiama Open-Meteo dal proprio browser, il
limite gratuito e' per indirizzo IP e mille utenti sono mille quote diverse:
funziona. Ma il primo caricamento resta lento, e chi ricarica spesso o sta
dietro a un IP condiviso incassa un 429. Con questo file il sito non chiama
piu' nessuno: legge un JSON gia' pronto, servito insieme alla pagina.

Lo lancia GitHub Actions ogni quattro ore (.github/workflows/dati.yml). I dati
sono giornalieri: piu' spesso di cosi' non cambierebbe niente, e ogni giro in
meno e' una connessione in meno che puo' incagliarsi.

Due connessioni in tutto, una per servizio. Prima erano dieci, a lotti di 40
spot: ogni lotto dopo il primo si incagliava al primo tentativo e riusciva solo
al secondo, e con un tetto di 180 secondi un giro arrivava a venti minuti. La
causa non e' un rifiuto di Open-Meteo (non arriva mai un 429, arriva sempre un
URLError esattamente allo scadere del tetto), ma una connessione che si apre e
non risponde piu'. Gli indirizzi di uscita di GitHub Actions sono condivisi fra
molti, e connessioni ravvicinate dallo stesso indirizzo vengono lasciate cadere
senza risposta. Meno connessioni, meno occasioni di incagliarsi; e un tetto
basso fa costare poco quelle che si incagliano comunque.

Tre connessioni da quando c'e' il mare: la terza chiede la temperatura di
superficie e l'onda per i soli spot di mare. Se non arriva il file esce lo
stesso, e su quegli spot il motore torna a stimare l'acqua dall'aria.

    python3 tools/aggiorna-dati.py            # scrive il file
    python3 tools/aggiorna-dati.py --prova    # solo una dozzina di spot

Dati: Open-Meteo, licenza CC BY 4.0. Portata dal modello idrologico GloFAS.
"""
import json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from elenchi import BASE, CORSI, leggi_spot, punto_portata

OUT = os.path.join(BASE, 'assets', 'dati', 'previsioni.json')

METEO_URL = 'https://api.open-meteo.com/v1/forecast'
FLOOD_URL = 'https://flood-api.open-meteo.com/v1/flood'
MARE_URL = 'https://marine-api.open-meteo.com/v1/marine'
UA = {'User-Agent': 'dove-pesco-static-site/1.0 (aggiornamento periodico dei dati)'}

LOTTO = 250         # tutti gli spot in una richiesta sola: Open-Meteo li accetta
                    # insieme (222 coordinate = 3,8 KB di indirizzo, risposta in
                    # mezzo secondo). Il taglio a lotti resta per sicurezza, se un
                    # giorno gli spot diventassero troppi per un solo indirizzo.
PAUSA = 4           # secondi fra una richiesta e l'altra: non e' il limite al
                    # minuto a dare problemi, sono le connessioni ravvicinate
TETTO = 25          # secondi di attesa per una risposta. Open-Meteo risponde in
                    # meno di un secondo: oltre il mezzo minuto non arrivera' piu'
RIPROVE = [0, 15, 45]   # il primo ritentativo subito: serve una connessione
                        # nuova, non un'attesa. Storicamente il primo bastava
                        # sempre. Nel caso peggiore: 4 tentativi x 25s + 60s di
                        # attese = 160s per servizio. Meteo e portata, 325s in
                        # tutto, stanno dentro il tetto di 7 minuti del passo
                        # nel workflow; il mare viene per ultimo e ha un solo
                        # ritentativo, cosi' non puo' portare il giro oltre.
RIPROVE_MARE = [0]
PASSATI = 14        # giorni indietro: la finestra piu' lunga del modello
                    # dell'acqua (un bacino) e' di 14 giorni. Con 10 veniva
                    # tagliata, e lo stesso giorno dava un'acqua diversa visto
                    # da oggi o visto da tre giorni prima.
AVANTI = 7          # giorni di previsione
PORT_PASSATI = 45   # giorni indietro per la mediana della portata

VARIABILI = ['weather_code', 'temperature_2m_max', 'temperature_2m_min', 'temperature_2m_mean',
             'precipitation_sum', 'wind_speed_10m_max', 'wind_direction_10m_dominant',
             'pressure_msl_mean', 'cloud_cover_mean', 'sunrise', 'sunset']

# nome breve nel file <- nome della variabile Open-Meteo
CAMPI = [('wmo', 'weather_code', 0), ('tmax', 'temperature_2m_max', 1),
         ('tmin', 'temperature_2m_min', 1), ('tmed', 'temperature_2m_mean', 1),
         ('pio', 'precipitation_sum', 1), ('ven', 'wind_speed_10m_max', 1),
         ('dir', 'wind_direction_10m_dominant', 0), ('pre', 'pressure_msl_mean', 1),
         ('nuv', 'cloud_cover_mean', 0)]


def chiedi(url, etichetta, riprove=RIPROVE):
    """Una richiesta, con qualche ritentativo se la connessione si incaglia."""
    for giro, pausa in enumerate([0] + riprove):
        if giro:
            sys.stderr.write('    riprovo (%d di %d)%s\n'
                             % (giro, len(riprove), ', dopo %ds' % pausa if pausa else ' subito'))
            time.sleep(pausa)
        avvio = time.time()
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TETTO) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            corpo = ''
            try:
                corpo = e.read().decode()[:120]
            except Exception:
                pass
            sys.stderr.write('    %s: HTTP %s %s\n' % (etichetta, e.code, corpo))
            if e.code not in (429, 500, 502, 503, 504):
                return None
        except Exception as e:
            # quanto e' durata dice cosa e' successo: al secondo e' un rifiuto,
            # al tetto e' una connessione aperta e mai risposta
            sys.stderr.write('    %s: %s dopo %.0fs\n'
                             % (etichetta, type(e).__name__, time.time() - avvio))
    return None


def arr(v, n):
    if v is None:
        return None
    return int(round(v)) if n == 0 else round(float(v), n)


def a_lotti(seq, n):
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def scarica_meteo(spot, dati):
    lotti = a_lotti(spot, LOTTO)
    for n, lotto in enumerate(lotti, 1):
        sys.stderr.write('  meteo, lotto %d/%d (%d spot)\n' % (n, len(lotti), len(lotto)))
        u = ('%s?latitude=%s&longitude=%s&daily=%s&past_days=%d&forecast_days=%d'
             '&timezone=Europe%%2FRome'
             % (METEO_URL, ','.join('%.4f' % s['lat'] for s in lotto),
                ','.join('%.4f' % s['lon'] for s in lotto),
                ','.join(VARIABILI), PASSATI, AVANTI))
        r = chiedi(u, 'meteo %d' % n)
        if r is None:
            continue
        risposte = r if isinstance(r, list) else [r]
        for s, rj in zip(lotto, risposte):
            d = (rj or {}).get('daily')
            if not d:
                continue
            v = {'q': arr(rj.get('elevation'), 0)}
            for breve, lungo, dec in CAMPI:
                v[breve] = [arr(x, dec) for x in d.get(lungo, [])]
            v['alba'] = [(x or '')[11:16] for x in d.get('sunrise', [])]
            v['tram'] = [(x or '')[11:16] for x in d.get('sunset', [])]
            dati['spot'].setdefault(s['id'], {}).update(v)
            dati['giorni'] = d['time']
        if n < len(lotti):
            time.sleep(PAUSA)


def scarica_mare(spot, dati):
    """Temperatura di superficie e onda massima, per i soli spot di mare.

    La temperatura arriva ora per ora: nel file va la media del giorno, sugli
    stessi giorni del meteo. cell_selection=sea chiede la cella d'acqua piu'
    vicina: un molo sta sul bordo, e la cella piu' vicina puo' essere di terra.
    """
    mare = [s for s in spot if s['tipo'] == 'mare' and s['id'] in dati['spot']]
    if not mare or not dati['giorni']:
        return
    sys.stderr.write('  mare (%d spot)\n' % len(mare))
    u = ('%s?latitude=%s&longitude=%s&hourly=sea_surface_temperature&daily=wave_height_max'
         '&past_days=%d&forecast_days=%d&timezone=Europe%%2FRome&cell_selection=sea'
         % (MARE_URL, ','.join('%.4f' % s['lat'] for s in mare),
            ','.join('%.4f' % s['lon'] for s in mare), PASSATI, AVANTI))
    r = chiedi(u, 'mare', RIPROVE_MARE)
    if r is None:
        sys.stderr.write('    il mare non risponde: su quegli spot l\'acqua resta stimata\n')
        return
    for s, rj in zip(mare, r if isinstance(r, list) else [r]):
        ore, giorno = (rj or {}).get('hourly') or {}, (rj or {}).get('daily') or {}
        per_giorno = {}
        for t, v in zip(ore.get('time', []), ore.get('sea_surface_temperature', [])):
            if v is not None:
                per_giorno.setdefault(t[:10], []).append(v)
        onda = dict(zip(giorno.get('time', []), giorno.get('wave_height_max', [])))
        tsm = [arr(sum(per_giorno[g]) / len(per_giorno[g]), 1) if g in per_giorno else None
               for g in dati['giorni']]
        if any(v is not None for v in tsm):
            dati['spot'][s['id']]['tsm'] = tsm
            dati['spot'][s['id']]['onda'] = [arr(onda.get(g), 2) for g in dati['giorni']]


def scarica_portata(spot, dati):
    """Solo fiumi e torrenti: GloFAS non modella laghi, cave, mare e canali.

    La coordinata e' quella dello spot, tranne dove tools/celle-portata.py ha
    trovato che la cella dello spot non e' quella in cui GloFAS fa scorrere il
    fiume: li' si chiede il centro della cella vicina (vedi punto_portata).
    """
    corsi = [s for s in spot if s['tipo'] in CORSI]
    lotti = a_lotti(corsi, LOTTO)
    for n, lotto in enumerate(lotti, 1):
        sys.stderr.write('  portata, lotto %d/%d (%d spot)\n' % (n, len(lotti), len(lotto)))
        u = ('%s?latitude=%s&longitude=%s&daily=river_discharge&past_days=%d&forecast_days=%d'
             % (FLOOD_URL, ','.join('%.4f' % punto_portata(s)[0] for s in lotto),
                ','.join('%.4f' % punto_portata(s)[1] for s in lotto), PORT_PASSATI, AVANTI))
        r = chiedi(u, 'portata %d' % n)
        if r is None:
            continue
        risposte = r if isinstance(r, list) else [r]
        for s, rj in zip(lotto, risposte):
            d = (rj or {}).get('daily')
            if not d or not d.get('river_discharge'):
                continue
            if s['id'] in dati['spot']:
                # tre decimali sotto il metro cubo: su un torrente da 0,2 m3/s
                # due decimali erano scalini del 5% nello scarto sulla mediana
                dati['spot'][s['id']]['por'] = [arr(x, 3 if x is not None and x < 1 else 2)
                                                for x in d['river_discharge']]
                dati['giorniPortata'] = d['time']
        if n < len(lotti):
            time.sleep(PAUSA)


def main():
    spot = leggi_spot()
    if '--prova' in sys.argv:
        # uno ogni tanti, piu' il primo di ogni ambiente: cosi' la prova passa
        # anche dal mare e dalla portata, che altrimenti poteva non toccare
        scelti = {s['id'] for s in spot[::max(1, len(spot) // 12)]}
        for tipo in {s['tipo'] for s in spot}:
            scelti.add(next(s['id'] for s in spot if s['tipo'] == tipo))
        spot = [s for s in spot if s['id'] in scelti]
    sys.stderr.write('Aggiorno le previsioni per %d spot\n' % len(spot))

    dati = {'generato': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            'fonte': 'Open-Meteo (CC BY 4.0); portata dal modello idrologico GloFAS; '
                     'mare dal servizio Marine di Open-Meteo',
            'giorni': [], 'giorniPortata': [], 'spot': {}}

    scarica_meteo(spot, dati)
    time.sleep(PAUSA)      # i servizi sono su macchine diverse, ma una connessione
    scarica_portata(spot, dati)   # appena dopo l'altra costa poco evitarla
    time.sleep(PAUSA)
    scarica_mare(spot, dati)

    con_meteo = sum(1 for v in dati['spot'].values() if v.get('tmax'))
    con_portata = sum(1 for v in dati['spot'].values() if v.get('por'))
    con_mare = sum(1 for v in dati['spot'].values() if v.get('tsm'))
    quota = con_meteo / max(1, len(spot))
    sys.stderr.write('\nMeteo su %d spot su %d (%.0f%%), portata su %d, mare su %d\n'
                     % (con_meteo, len(spot), quota * 100, con_portata, con_mare))
    # Uno spot che manca dal file resta senza indice del giorno, e prima non lo
    # diceva nessuno: i laghi S. Anna ci sono rimasti due settimane.
    senza = [s['id'] for s in spot if not dati['spot'].get(s['id'], {}).get('tmax')]
    if senza:
        sys.stderr.write('Senza meteo: %s\n' % ', '.join(senza))

    if quota < 0.6:
        sys.stderr.write('Troppi buchi: non scrivo il file, resta buono il precedente.\n')
        return 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(dati, f, separators=(',', ':'))
    kb = os.path.getsize(OUT) / 1024
    sys.stderr.write('Scritto %s, %.0f KB (%.1f KB per spot)\n' % (OUT, kb, kb / max(1, con_meteo)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
