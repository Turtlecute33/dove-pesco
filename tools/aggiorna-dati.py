#!/usr/bin/env python3
"""
Scarica meteo e portata per tutti gli spot e li scrive in un unico file
statico: assets/dati/previsioni.json

A cosa serve. Se ogni visitatore chiama Open-Meteo dal proprio browser, il
limite gratuito e' per indirizzo IP e mille utenti sono mille quote diverse:
funziona. Ma il primo caricamento resta lento, e chi ricarica spesso o sta
dietro a un IP condiviso incassa un 429. Con questo file il sito non chiama
piu' nessuno: legge un JSON gia' pronto, servito insieme alla pagina.

Lo lancia GitHub Actions ogni due ore (.github/workflows/dati.yml). Il costo
per Open-Meteo e' di una dozzina di giri al giorno invece che uno per utente.

    python3 tools/aggiorna-dati.py            # scrive il file
    python3 tools/aggiorna-dati.py --prova    # solo i primi 12 spot

Dati: Open-Meteo, licenza CC BY 4.0. Portata dal modello idrologico GloFAS.
"""
import json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

BASE = os.path.join(os.path.dirname(__file__), '..')
FILE_DATI = ['data-spots-emilia.js', 'data-spots-romagna.js', 'data-spots-extra.js',
             'data-spots-centro.js']
OUT = os.path.join(BASE, 'assets', 'dati', 'previsioni.json')

METEO_URL = 'https://api.open-meteo.com/v1/forecast'
FLOOD_URL = 'https://flood-api.open-meteo.com/v1/flood'
UA = {'User-Agent': 'dove-pesco-static-site/1.0 (aggiornamento periodico dei dati)'}

LOTTO = 40          # spot per richiesta: Open-Meteo accetta piu' coordinate insieme
PAUSA = 6           # secondi fra un lotto e l'altro, per stare lontani dal limite al minuto
RIPROVE = [20, 60, 120, 240]
PASSATI = 10        # giorni indietro (servono alla temperatura dell'acqua)
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


def leggi_spot():
    testo = ''
    for f in FILE_DATI:
        testo += open(os.path.join(BASE, 'assets', 'js', f)).read()
    visti, out = set(), []
    for m in re.finditer(r"id: '([^']+)'[\s\S]{0,200}?tipo: '(\w+)'[\s\S]{0,90}?"
                         r"lat: (-?[\d.]+), lon: (-?[\d.]+)", testo):
        if m.group(1) in visti:
            continue
        visti.add(m.group(1))
        out.append({'id': m.group(1), 'tipo': m.group(2),
                    'lat': float(m.group(3)), 'lon': float(m.group(4))})
    return out


def chiedi(url, etichetta):
    """Una richiesta, con pause crescenti se Open-Meteo dice di aspettare."""
    for giro, pausa in enumerate([0] + RIPROVE):
        if pausa:
            sys.stderr.write('    attendo %ds e riprovo\n' % pausa)
            time.sleep(pausa)
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
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
            sys.stderr.write('    %s: %s\n' % (etichetta, type(e).__name__))
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


def scarica_portata(spot, dati):
    """Solo fiumi e torrenti: GloFAS non modella laghi, cave, mare e canali."""
    corsi = [s for s in spot if s['tipo'] in ('fiume', 'torrente')]
    lotti = a_lotti(corsi, LOTTO)
    for n, lotto in enumerate(lotti, 1):
        sys.stderr.write('  portata, lotto %d/%d (%d spot)\n' % (n, len(lotti), len(lotto)))
        u = ('%s?latitude=%s&longitude=%s&daily=river_discharge&past_days=%d&forecast_days=%d'
             % (FLOOD_URL, ','.join('%.4f' % s['lat'] for s in lotto),
                ','.join('%.4f' % s['lon'] for s in lotto), PORT_PASSATI, AVANTI))
        r = chiedi(u, 'portata %d' % n)
        if r is None:
            continue
        risposte = r if isinstance(r, list) else [r]
        for s, rj in zip(lotto, risposte):
            d = (rj or {}).get('daily')
            if not d or not d.get('river_discharge'):
                continue
            if s['id'] in dati['spot']:
                dati['spot'][s['id']]['por'] = [arr(x, 2) for x in d['river_discharge']]
                dati['giorniPortata'] = d['time']
        if n < len(lotti):
            time.sleep(PAUSA)


def main():
    spot = leggi_spot()
    if '--prova' in sys.argv:
        spot = spot[:12]
    sys.stderr.write('Aggiorno le previsioni per %d spot\n' % len(spot))

    dati = {'generato': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            'fonte': 'Open-Meteo (CC BY 4.0); portata dal modello idrologico GloFAS',
            'giorni': [], 'giorniPortata': [], 'spot': {}}

    scarica_meteo(spot, dati)
    scarica_portata(spot, dati)

    con_meteo = sum(1 for v in dati['spot'].values() if v.get('tmax'))
    con_portata = sum(1 for v in dati['spot'].values() if v.get('por'))
    quota = con_meteo / max(1, len(spot))
    sys.stderr.write('\nMeteo su %d spot su %d (%.0f%%), portata su %d\n'
                     % (con_meteo, len(spot), quota * 100, con_portata))

    if quota < 0.6:
        sys.stderr.write('Troppi buchi: non scrivo il file, resta buono il precedente.\n')
        return 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(dati, f, separators=(',', ':'))
    kb = os.path.getsize(OUT) / 1024
    sys.stderr.write('Scritto %s — %.0f KB (%.1f KB per spot)\n' % (OUT, kb, kb / max(1, con_meteo)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
