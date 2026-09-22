#!/usr/bin/env python3
"""
Avvisa i motori di ricerca che aderiscono a IndexNow (Bing, Yandex, Seznam,
Naver, Yep) che le pagine del sito sono cambiate.

A cosa serve. Un mese dopo la pubblicazione Bing aveva in indice una
cinquantina delle 367 pagine. Da Bing prendono i risultati anche DuckDuckGo e
Yahoo, quindi le altre trecento mancavano in tre motori, non in uno. IndexNow e' il modo che Bing indica per
dirgli «queste pagine ci sono e sono cambiate» senza aspettare che passi.

Parte solo dopo un push su main (.github/workflows/dati.yml), cioe' quando e'
cambiato il sito. Non parte ai giri delle previsioni ogni quattro ore: li'
cambia l'indice del giorno, e avvisare sei volte al giorno per 367 pagine e'
proprio l'abuso che il protocollo chiede di evitare.

Manda solo gli indirizzi pubblici della sitemap. Nessun dato di chi visita il
sito passa da qui. La chiave in tools/indexnow.txt non e' un segreto: sta per
forza in chiaro alla radice del sito, dove i motori la leggono per verificare
che l'avviso venga davvero dal proprietario del dominio.

    DOMINIO=dovepescare.com python3 tools/avvisa-motori.py
"""
import json, os, re, sys, time, urllib.error, urllib.request

BASE = os.path.join(os.path.dirname(__file__), '..')
PUNTO = 'https://api.indexnow.org/indexnow'
UA = {'User-Agent': 'dove-pesco-static-site/1.0 (avviso IndexNow dopo la pubblicazione)'}
TETTO = 30
MASSIMO = 10000     # il protocollo accetta fino a 10.000 indirizzi per richiesta
RIPROVE = [0, 60, 120]  # secondi prima di ogni tentativo, solo se la risposta e' 403


def leggi(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TETTO) as r:
        return r.read().decode('utf-8')


def main():
    dominio = os.environ.get('DOMINIO', '').strip().strip('/')
    if not dominio:
        print('DOMINIO non impostato: il sito non ha un dominio suo, niente da avvisare.')
        return
    with open(os.path.join(BASE, 'tools', 'indexnow.txt')) as f:
        chiave = f.read().strip()
    if not re.fullmatch(r'[0-9a-f]{32}', chiave):
        sys.exit('tools/indexnow.txt non contiene una chiave valida (32 cifre esadecimali)')
    sito = 'https://' + dominio

    # Il motore, ricevuto l'avviso, va a leggere la chiave sul sito. Se non la
    # trova l'avviso e' scartato, quindi prima di mandarlo si controlla che la
    # pubblicazione appena finita l'abbia messa davvero al suo posto.
    try:
        pubblicata = leggi('%s/%s.txt' % (sito, chiave)).strip()
    except urllib.error.HTTPError as e:
        sys.exit('la chiave non e\' su %s/%s.txt (%d): niente avviso' % (sito, chiave, e.code))
    if pubblicata != chiave:
        sys.exit('la chiave pubblicata su %s non corrisponde a tools/indexnow.txt' % sito)

    urls = re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', leggi(sito + '/sitemap.xml'))
    urls = [u for u in urls if u.startswith(sito + '/')][:MASSIMO]
    if not urls:
        sys.exit('la sitemap di %s non ha indirizzi' % sito)

    corpo = json.dumps({'host': dominio, 'key': chiave,
                        'keyLocation': '%s/%s.txt' % (sito, chiave),
                        'urlList': urls}).encode('utf-8')
    req = urllib.request.Request(PUNTO, data=corpo, method='POST', headers={
        **UA, 'Content-Type': 'application/json; charset=utf-8'})
    # 200 vuol dire ricevuto, 202 ricevuto con la chiave ancora da verificare.
    # 403 e' la chiave che il motore non ha trovato. Al primo avviso e' successo
    # subito dopo la pubblicazione, con il file gia' al suo posto, e la stessa
    # richiesta pochi minuti dopo ha preso 202: il motore aveva letto la chiave
    # prima che la cache la servisse. Quindi sul 403 si riprova, ma poco: il
    # workflow tiene occupato il gruppo «pages» finche' questo passo non
    # finisce, e un'attesa lunga qui ritarderebbe la pubblicazione successiva.
    # Ogni altro errore ferma il passo, che ha continue-on-error: il sito e'
    # gia' pubblicato comunque.
    for attesa in RIPROVE:
        time.sleep(attesa)
        try:
            with urllib.request.urlopen(req, timeout=TETTO) as r:
                print('IndexNow: %d indirizzi mandati, risposta %d' % (len(urls), r.status))
                return
        except urllib.error.HTTPError as e:
            if e.code != 403:
                raise
            print('IndexNow: 403, la chiave non risulta ancora verificata')
    sys.exit('IndexNow: 403 anche dopo %d tentativi' % len(RIPROVE))


if __name__ == '__main__':
    main()
