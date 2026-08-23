#!/usr/bin/env python3
"""Reincorpora i woff2 di assets/fonts in assets/css/caratteri.css come data URI.
Serve perche' il sito deve funzionare anche aperto con un doppio clic (file://),
dove il browser rifiuta i font caricati da file esterni.
Rilancialo solo se cambi i caratteri."""
import base64, re, os, sys
B = os.path.join(os.path.dirname(__file__), '..')
faces = open(os.path.join(B, 'assets/fonts/_faces.css')).read().strip().split('\n')
out = ["/* Caratteri incorporati come data URI — generato da tools/inline-font.py",
       "   Fraunces e Archivo, licenza SIL Open Font 1.1. */", ""]
for f in faces:
    m = re.search(r"url\('\.\./fonts/([^']+)'\)", f)
    if not m: continue
    d = base64.b64encode(open(os.path.join(B, 'assets/fonts', m.group(1)), 'rb').read()).decode()
    out.append(f.replace(m.group(0), "url('data:font/woff2;base64,%s')" % d))
p = os.path.join(B, 'assets/css/caratteri.css')
open(p, 'w').write('\n'.join(out) + '\n')
sys.stderr.write('scritto %s — %.0f KB\n' % (p, os.path.getsize(p) / 1024))
