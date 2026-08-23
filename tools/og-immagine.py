#!/usr/bin/env python3
"""Disegna assets/og.png, l'anteprima che compare quando si condivide un link.

WhatsApp, Telegram, Facebook e X non leggono l'SVG, quindi serve un PNG.
Non cambia mai: si rilancia solo se cambiano i colori o il marchio, e il
risultato va messo sotto controllo di versione. Non fa parte della
pubblicazione automatica.

  python3 tools/og-immagine.py        # serve cairosvg
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUORI = os.path.join(BASE, 'assets/og.png')

PANNA, CARTA, ACC, INK, INK3 = '#EFE9DD', '#FCFAF5', '#0E6B70', '#16201E', '#7B837D'

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="{PANNA}"/>
  <rect x="48" y="48" width="1104" height="534" rx="34" fill="{CARTA}"/>

  <!-- accenno d'acqua nell'angolo libero: tre onde, nessun dettaglio -->
  <g fill="none" stroke="{ACC}" stroke-width="9" stroke-linecap="round" opacity=".15">
    <path d="M876 424c34-24 68-24 102 0s68 24 102 0"/>
    <path d="M876 478c34-24 68-24 102 0s68 24 102 0"/>
    <path d="M876 532c34-24 68-24 102 0s68 24 102 0"/>
  </g>

  <!-- il pesce del marchio -->
  <g transform="translate(104 116) scale(3.05)" fill="none" stroke="{ACC}"
     stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
    <path d="M2.6 12c3.2-4.4 7-6.6 11.4-6.6 3.4 0 6.1 1.6 8.2 4.7-2.1 4.5-4.8 6.1-8.2
             6.1-4.4 0-8.2-2.2-11.4-4.2Z"/>
    <path d="m2.6 12 2.9-2.4M2.6 12l2.9 2.4"/>
    <circle cx="17.2" cy="10.6" r=".9" fill="{ACC}" stroke="none"/>
  </g>

  <text x="104" y="212" font-family="Georgia, 'Times New Roman', serif" font-size="34"
        fill="{ACC}" letter-spacing="6">DOVE PESCO</text>

  <text x="104" y="326" font-family="Georgia, 'Times New Roman', serif" font-size="82"
        font-weight="500" fill="{INK}">Dove pescare oggi</text>
  <text x="104" y="418" font-family="Georgia, 'Times New Roman', serif" font-size="82"
        font-weight="500" fill="{INK}">in Emilia-Romagna</text>

  <text x="104" y="492" font-family="Helvetica, Arial, sans-serif" font-size="30"
        fill="{INK3}">222 spot, ordinati ogni mattina su portata, acqua e meteo</text>
</svg>"""


def main():
    try:
        import cairosvg
    except ImportError:
        sys.exit('serve cairosvg:  pip install cairosvg')
    cairosvg.svg2png(bytestring=SVG.encode(), write_to=FUORI,
                     output_width=1200, output_height=630)
    sys.stderr.write('scritto %s — %.0f KB\n'
                     % (FUORI, os.path.getsize(FUORI) / 1024))


if __name__ == '__main__':
    main()
