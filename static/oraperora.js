/* Calabria Meteo Lab - "Ora per ora": cambio del giorno tra le schede.
   Le righe orarie si aprono da sole (elementi <details>). */
(function () {
  'use strict';
  var schede = Array.prototype.slice.call(document.querySelectorAll('.oo-scheda'));
  if (!schede.length) return;

  function mostra(data, conFuoco) {
    schede.forEach(function (s) {
      var attiva = s.getAttribute('data-data') === data;
      s.setAttribute('aria-selected', String(attiva));
      s.tabIndex = attiva ? 0 : -1;
      if (attiva && conFuoco) s.focus();
      var pannello = document.getElementById(s.getAttribute('aria-controls'));
      if (pannello) pannello.hidden = !attiva;
    });
  }

  schede.forEach(function (s, i) {
    s.addEventListener('click', function () { mostra(s.getAttribute('data-data'), false); });
    s.addEventListener('keydown', function (e) {   // frecce tra le schede
      var j = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : null;
      if (j === null) return;
      e.preventDefault();
      mostra(schede[(j + schede.length) % schede.length].getAttribute('data-data'), true);
    });
  });

  /* Dalle schede dei giorni: apre quel giorno nell'elenco ora per ora */
  window.vaiAlGiorno = function (data) {
    if (!schede.some(function (s) { return s.getAttribute('data-data') === data; })) return;
    mostra(data, false);
    var sezione = document.getElementById('cml-ora-per-ora');
    if (sezione) sezione.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
})();
