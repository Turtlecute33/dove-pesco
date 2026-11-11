/* =============================================================================
   CONDIVIDI
   -----------------------------------------------------------------------------
   Il tasto che manda uno spot a un amico. A pesca si va spesso in due, e la
   gita si decide in un gruppo di messaggi: il link della scheda, con l'indice
   del giorno scritto accanto, è la cosa più utile da mandare.

   Usa la condivisione del sistema (navigator.share): sul telefono apre il
   pannello con le app di messaggi, e il sito non sa né dove va né a chi.
   Dove manca, come in Firefox sul computer, il tasto copia testo e link.
   Dove manca anche quello, il tasto non compare: nasce con hidden e lo
   accende solo questo script, così senza JavaScript non resta un tasto morto.

   Le pagine statiche lo chiamano da sole al caricamento; l'applicazione lo
   richiama a ogni scheda che disegna (ui.js, collegaRisposta).
   ========================================================================== */

const CONDIVIDI = (() => {

  const condivide = () => typeof navigator.share === 'function';
  const copia = () => !!(navigator.clipboard && window.isSecureContext);

  function collega(radice) {
    (radice || document).querySelectorAll('[data-condividi]').forEach((b) => {
      if (b.dataset.collegato) return;
      const dati = {
        title: b.dataset.titolo || document.title,
        text: b.dataset.testo || '',
        url: new URL(b.dataset.url || location.href, location.href).href,
      };
      const eti = b.querySelector('span') || b;

      if (condivide()) {
        /* chiudere il pannello senza scegliere rifiuta la promessa: non è un errore */
        b.onclick = () => navigator.share(dati).catch(() => {});
      } else if (copia()) {
        eti.textContent = 'Copia il link';
        b.onclick = () => navigator.clipboard
          .writeText((dati.text ? dati.text + ' ' : '') + dati.url)
          .then(() => {
            eti.textContent = 'Link copiato';
            setTimeout(() => { eti.textContent = 'Copia il link'; }, 2000);
          }, () => {});
      } else {
        return;
      }

      b.dataset.collegato = '1';
      b.hidden = false;
      const riga = b.closest('[data-condividi-riga]');
      if (riga) riga.hidden = false;
    });
  }

  collega(document);
  return { collega };
})();
