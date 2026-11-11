"""
Gli spot, letti da assets/js con node invece che con un'espressione regolare.

aggiorna-dati.py li cercava nel sorgente con una regex che voleva `tipo:` entro
200 caratteri da `id:`. Quando una scheda ha preso il campo `titolo`, quei 200
caratteri non sono bastati piu': i laghi S. Anna sono usciti dal file delle
previsioni e sono rimasti senza indice del giorno, senza che niente lo dicesse.
Una regex sul sorgente si rompe ogni volta che una scheda cambia forma; node
legge gli elenchi come li legge il browser.
"""
import json, os, subprocess, sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
FILE_DATI = ['data-spots-emilia.js', 'data-spots-romagna.js', 'data-spots-extra.js',
             'data-spots-centro.js', 'data-index.js']

# Gli ambienti che hanno una portata: GloFAS non modella laghi, cave, mare e
# canali di bonifica.
CORSI = ('fiume', 'torrente')


def leggi_spot():
    """[{id, tipo, acqua, lat, lon, cella}]: `cella` e' [lat, lon] del punto da
    cui leggere la portata quando non e' quello dello spot (vedi
    tools/celle-portata.py), altrimenti None."""
    js = r"""
      const fs = require('fs'), vm = require('vm'), p = require('path');
      const cartella = p.join(process.env.RADICE, 'assets/js');
      const src = %s.map(f => fs.readFileSync(p.join(cartella, f), 'utf8')).join('\n');
      process.stdout.write(vm.runInContext(src + `
        ;JSON.stringify(SPOT.map(s => ({ id: s.id, tipo: s.tipo, acqua: s.acqua,
          lat: s.lat, lon: s.lon,
          cella: (typeof CELLE_PORTATA !== 'undefined' && CELLE_PORTATA[s.id]) || null })));`,
        vm.createContext({})));
    """ % json.dumps(FILE_DATI)
    try:
        raw = subprocess.run(['node', '-e', js], check=True, capture_output=True,
                             text=True, env={**os.environ, 'RADICE': BASE}).stdout
    except FileNotFoundError:
        sys.exit('serve node per leggere gli elenchi in assets/js')
    except subprocess.CalledProcessError as e:
        sys.exit('node non ha letto gli elenchi:\n' + e.stderr)
    return json.loads(raw)


def punto_portata(s):
    """(lat, lon) da chiedere a GloFAS per questo spot."""
    return tuple(s['cella']) if s.get('cella') else (s['lat'], s['lon'])
