/* Calabria Meteo Lab - grafico unico "Ora per ora".
   Quattro viste (temperatura, pioggia, vento, nuvole), fasce scure per le ore
   di buio, linea a mezzanotte, ora selezionata evidenziata e dettaglio sotto. */
(function () {
  'use strict';
  var righe = window.CML_ORE || [];
  var tela = document.getElementById('oo-grafico');
  var contenitore = document.getElementById('oo-tela');
  var scorri = document.getElementById('oo-scorri');
  var dettaglio = document.getElementById('oo-dettaglio');
  if (!righe.length || !tela || !contenitore) return;

  var vista = 'temperatura';
  var scelta = 0;
  var grafico = null;
  var haProbabilita = righe.some(function (r) { return typeof r.prob === 'number'; });

  function fmt(v, unita, decimali) {
    if (typeof v !== 'number' || !isFinite(v)) return '—';
    return v.toLocaleString('it-IT', { minimumFractionDigits: decimali || 0, maximumFractionDigits: decimali || 0 }) + (unita || '');
  }

  // un'etichetta ogni 3 ore, ogni 6 sugli schermi stretti
  function passoEtichette() { return window.innerWidth < 680 ? 6 : 3; }

  /* ---------- Viste ---------- */
  function serie(chiave) { return righe.map(function (r) { return r[chiave]; }); }

  function configurazione() {
    var assi = { x: { ticks: { maxRotation: 0, autoSkip: false, color: '#607987',
      callback: function (v, i) { return (+righe[i].ora.slice(0, 2)) % passoEtichette() === 0 ? righe[i].ora.slice(0, 2) : ''; } },
      grid: { display: false } } };
    var dati = [];
    if (vista === 'temperatura') {
      dati = [
        { label: 'Temperatura °C', data: serie('temp'), borderColor: '#f26e17', backgroundColor: 'rgba(242,110,23,.12)', fill: true, tension: .35, pointRadius: 0, borderWidth: 2.5 },
        { label: 'Percepita °C', data: serie('percepita'), borderColor: '#f6a66b', borderDash: [5, 4], tension: .35, pointRadius: 0, borderWidth: 1.6 }
      ];
      assi.y = { ticks: { color: '#607987', callback: function (v) { return v + '°'; } }, grid: { color: '#edf2f6' } };
    } else if (vista === 'pioggia') {
      dati = [{ type: 'bar', label: 'Pioggia mm', data: serie('pioggia'), backgroundColor: '#2f86d6', borderRadius: 3, yAxisID: 'y' }];
      assi.y = { beginAtZero: true, suggestedMax: 2, ticks: { color: '#607987', callback: function (v) { return v + ' mm'; } }, grid: { color: '#edf2f6' } };
      if (haProbabilita) {
        dati.push({ type: 'line', label: 'Probabilità %', data: serie('prob'), borderColor: '#6a3fb5', tension: .3, pointRadius: 0, borderWidth: 2, yAxisID: 'y1' });
        assi.y1 = { position: 'right', min: 0, max: 100, ticks: { color: '#6a3fb5', callback: function (v) { return v + '%'; } }, grid: { display: false } };
      }
    } else if (vista === 'vento') {
      dati = [
        { label: 'Vento km/h', data: serie('vento'), borderColor: '#0b7f98', backgroundColor: 'rgba(11,127,152,.10)', fill: true, tension: .3, pointRadius: 0, borderWidth: 2.5 },
        { label: 'Raffiche km/h', data: serie('raffiche'), borderColor: '#7fb8c8', borderDash: [5, 4], tension: .3, pointRadius: 0, borderWidth: 1.6 }
      ];
      assi.y = { beginAtZero: true, ticks: { color: '#607987' }, grid: { color: '#edf2f6' } };
    } else {
      dati = [{ label: 'Nuvole %', data: serie('nubi'), borderColor: '#71889a', backgroundColor: 'rgba(113,136,154,.22)', fill: true, tension: .3, pointRadius: 0, borderWidth: 2 }];
      assi.y = { min: 0, max: 100, ticks: { color: '#607987', callback: function (v) { return v + '%'; } }, grid: { color: '#edf2f6' } };
    }
    return {
      type: 'line',
      data: { labels: serie('ora'), datasets: dati },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { color: '#284d5a', boxWidth: 14, usePointStyle: true } }, tooltip: { enabled: false } },
        scales: assi,
        onClick: function (evento, elementi, ch) {
          var x = ch.scales.x.getValueForPixel(evento.x);
          if (typeof x === 'number') seleziona(Math.max(0, Math.min(righe.length - 1, Math.round(x))));
        }
      },
      plugins: [sfondo]
    };
  }

  /* Fasce di buio, linee di mezzanotte con il nome del giorno, ora scelta */
  var sfondo = {
    id: 'ooSfondo',
    beforeDatasetsDraw: function (ch) {
      var c = ch.ctx, area = ch.chartArea, x = ch.scales.x, passo = (x.getPixelForValue(1) - x.getPixelForValue(0)) || 0;
      c.save();
      righe.forEach(function (r, i) {
        if (r.notte) { c.fillStyle = 'rgba(20,37,73,.07)'; c.fillRect(x.getPixelForValue(i) - passo / 2, area.top, passo, area.bottom - area.top); }
        if (i > 0 && r.ora === '00:00') {
          var px = x.getPixelForValue(i) - passo / 2;
          c.strokeStyle = '#b7c9d3'; c.lineWidth = 1; c.beginPath(); c.moveTo(px, area.top); c.lineTo(px, area.bottom); c.stroke();
          c.fillStyle = '#284d5a'; c.font = '600 12px system-ui, sans-serif'; c.fillText(r.giorno.split(' ').slice(0, 2).join(' '), px + 4, area.top + 13);
        }
      });
      var sx = x.getPixelForValue(scelta);
      c.fillStyle = 'rgba(11,127,152,.14)'; c.fillRect(sx - Math.max(passo, 6) / 2, area.top, Math.max(passo, 6), area.bottom - area.top);
      c.strokeStyle = '#0b7f98'; c.lineWidth = 2; c.beginPath(); c.moveTo(sx, area.top); c.lineTo(sx, area.bottom); c.stroke();
      c.restore();
    }
  };

  /* ---------- Dettaglio dell'ora ---------- */
  var LIVELLI_CAPE = ['basso', 'moderato', 'alto', 'molto alto'];
  function extra(r) {
    var righe = '';
    if (typeof r.neve === 'number') righe += '<li>❄️ Quota neve <b>circa ' + fmt(r.neve, ' m') + '</b></li>';
    if (typeof r.cape === 'number' && r.cape >= 1) righe += '<li>⛈️ Potenziale temporalesco <b>' + LIVELLI_CAPE[r.cape] + '</b></li>';
    if (typeof r.uv === 'number' && r.uv >= 3) righe += '<li>☀️ Indice UV <b>' + r.uv + '</b></li>';
    if (typeof r.polveri === 'number' && r.polveri >= 50) righe += '<li>🏜️ Polveri sahariane <b>' + r.polveri + ' µg/m³</b></li>';
    return righe;
  }

  function mostraDettaglio() {
    var r = righe[scelta];
    var pioggia = fmt(r.pioggia, ' mm', 1) + (typeof r.prob === 'number' ? ' · probabilità ' + r.prob + '%' : '');
    var temporali = typeof r.temporali === 'number' && r.temporali >= 30 ? '<li>⚡ Temporali nella zona: <b>' + r.temporali + '%</b></li>' : '';
    dettaglio.innerHTML =
      '<div class="oo-d-testa"><span class="oo-d-icona">' + (r.icona || '') + '</span><div><strong>' + r.giorno + ' · ' + r.ora +
      '</strong><span>' + r.cielo + (r.notte ? ' · notte' : '') + '</span></div><b class="oo-d-temp">' + fmt(r.temp, '°') + '</b></div>' +
      '<ul><li>🌡️ Percepita <b>' + fmt(r.percepita, '°') + '</b></li><li>🌧️ Pioggia <b>' + pioggia + '</b></li>' + temporali +
      '<li>💨 Vento <b>' + fmt(r.vento, ' km/h') + '</b> da ' + r.da + ' · raffiche ' + fmt(r.raffiche, ' km/h') + '</li>' +
      '<li>☁️ Nuvole <b>' + fmt(r.nubi, '%') + '</b> · 💧 umidità ' + fmt(r.umidita, '%') + '</li>' + extra(r) + '</ul>';
    document.querySelectorAll('.oo-giorno').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-data') === r.data));
    });
  }

  function seleziona(indice, centra) {
    scelta = indice;
    if (grafico) grafico.draw();
    mostraDettaglio();
    if (centra && scorri.scrollWidth > scorri.clientWidth) {
      var x = grafico ? grafico.scales.x.getPixelForValue(indice) : 0;
      scorri.scrollTo({ left: Math.max(0, x - scorri.clientWidth / 3), behavior: 'smooth' });
    }
  }

  /* ---------- Disegno e larghezza ---------- */
  function adattaLarghezza() {
    // il grafico occupa sempre la larghezza disponibile (assi sempre visibili)
    contenitore.style.width = '100%';
  }

  function disegna() {
    if (typeof Chart === 'undefined') { contenitore.textContent = 'Grafico non disponibile.'; mostraDettaglio(); return; }
    if (grafico) grafico.destroy();
    adattaLarghezza();
    grafico = new Chart(tela, configurazione());
    mostraDettaglio();
  }

  document.querySelectorAll('.oo-vista').forEach(function (b) {
    b.addEventListener('click', function () {
      vista = b.getAttribute('data-vista');
      document.querySelectorAll('.oo-vista').forEach(function (x) { x.setAttribute('aria-selected', String(x === b)); });
      disegna();
    });
  });

  document.querySelectorAll('.oo-giorno').forEach(function (b) {
    b.addEventListener('click', function () { vaiAlGiorno(b.getAttribute('data-data'), false); });
  });

  scorri.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight') { e.preventDefault(); seleziona(Math.min(righe.length - 1, scelta + 1), true); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); seleziona(Math.max(0, scelta - 1), true); }
  });

  document.getElementById('oo-csv').addEventListener('click', function (e) {
    e.preventDefault();
    var chiavi = ['t', 'temp', 'percepita', 'pioggia', 'prob', 'temporali', 'vento', 'raffiche', 'da', 'nubi', 'umidita', 'cielo'];
    var testo = '﻿' + [chiavi.join(';')].concat(righe.map(function (r) {
      return chiavi.map(function (k) { return r[k] == null ? '' : r[k]; }).join(';');
    })).join('\r\n');
    var url = URL.createObjectURL(new Blob([testo], { type: 'text/csv;charset=utf-8;' }));
    var a = document.createElement('a'); a.href = url; a.download = 'previsione-oraria.csv'; a.click();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  });

  var attesa = 0;
  window.addEventListener('resize', function () {
    clearTimeout(attesa);
    attesa = setTimeout(function () { if (grafico) { adattaLarghezza(); grafico.resize(); } }, 150);
  });

  /* Dalle schede dei giorni: porta al grafico su quel giorno (ore 12 se disponibile) */
  function vaiAlGiorno(data, scorriPagina) {
    var indici = righe.map(function (r, i) { return r.data === data ? i : -1; }).filter(function (i) { return i >= 0; });
    if (!indici.length) return;
    var mezzogiorno = indici.filter(function (i) { return righe[i].ora === '12:00'; })[0];
    seleziona(mezzogiorno !== undefined ? mezzogiorno : indici[0], true);
    if (scorriPagina !== false) {
      var sezione = document.getElementById('cml-ora-per-ora');
      if (sezione) sezione.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }
  window.vaiAlGiorno = vaiAlGiorno;

  disegna();
})();
