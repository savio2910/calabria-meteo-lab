/* Calabria Meteo Lab - riquadro "Adesso": cielo dinamico e menu rapido.
   Il cielo è disegnato dai dati reali (window.CML_CIELO):
   ora rispetto ad alba e tramonto, posizione di sole e luna, fase lunare,
   nuvolosità, pioggia/neve/nebbia/temporale, velocità e direzione del vento.
   È una rappresentazione, non una simulazione meteorologica. */
(function () {
  'use strict';

  var D = window.CML_CIELO || {};
  var sezione = document.getElementById('cml-adesso');
  var tela = document.getElementById('cml-cielo');
  var pulsantePausa = document.getElementById('cml-cielo-pausa');
  if (!sezione || !tela || !tela.getContext) return;
  var ctx = tela.getContext('2d');

  /* ---------- Tempo: minuti da stringhe locali "YYYY-MM-DDTHH:MM" ---------- */
  function minuti(testo) {
    if (!testo) return null;
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(testo);
    if (!m) return null;
    return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) / 60000;
  }
  var ora = minuti(D.ora);
  var alba = minuti(D.alba);
  var tramonto = minuti(D.tramonto);
  var nuvole = Math.max(0, Math.min(100, D.nuvole || 0)) / 100;
  var pioggia = Math.max(0, D.pioggia || 0);
  var codice = D.codice;
  var vento = Math.max(0, D.vento || 0);
  // Il vento arriva DA direzioneVento: la componente verso est è -sin(direzione)
  var versoEst = -Math.sin(((D.direzioneVento || 270) * Math.PI) / 180);

  var temporale = [95, 96, 99].indexOf(codice) >= 0;
  var neve = [71, 73, 75, 77, 85, 86].indexOf(codice) >= 0;
  var nebbia = [45, 48].indexOf(codice) >= 0;
  var piove = !neve && (pioggia >= 0.1 || [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82].indexOf(codice) >= 0 || temporale);

  /* ---------- Sole: frazione del giorno e crepuscolo ---------- */
  var giorno = ora !== null && alba !== null && tramonto !== null && ora >= alba && ora <= tramonto;
  var frazioneSole = giorno ? (ora - alba) / (tramonto - alba) : 0;
  var altezzaSole = giorno ? Math.sin(Math.PI * frazioneSole) : 0;
  var crepuscolo = 0;
  if (ora !== null && alba !== null && tramonto !== null) {
    var distanza = Math.min(Math.abs(ora - alba), Math.abs(ora - tramonto));
    crepuscolo = Math.max(0, 1 - distanza / 50);
  }

  /* ---------- Luna: visibile tra sorgere e tramonto ---------- */
  var luna = null;
  (function () {
    var sorge = minuti(D.sorgeLuna), tramonta = minuti(D.tramontaLuna);
    if (ora === null || (sorge === null && tramonta === null)) return;
    if (sorge === null) sorge = tramonta - 12 * 60;
    if (tramonta === null) tramonta = sorge + 12 * 60;
    if (tramonta < sorge) {           // la luna era già alta da ieri
      if (ora <= tramonta) sorge = tramonta - 12 * 60;
      else tramonta = sorge + 12 * 60;
    }
    if (ora < sorge || ora > tramonta) return;
    var f = (ora - sorge) / (tramonta - sorge);
    luna = { frazione: f, altezza: Math.sin(Math.PI * f), fase: D.faseLuna == null ? 0.5 : D.faseLuna };
  })();

  /* ---------- Colori ---------- */
  function mescola(a, b, t) {
    return [0, 1, 2].map(function (i) { return Math.round(a[i] + (b[i] - a[i]) * t); });
  }
  function rgb(c, alfa) { return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + (alfa == null ? 1 : alfa) + ')'; }

  var NOTTE = [[8, 20, 42], [28, 45, 82]];
  var GIORNO = [[38, 116, 196], [150, 205, 240]];
  var TRAMONTO = [[60, 62, 120], [240, 150, 110]];
  var COPERTO_G = [[104, 124, 140], [176, 190, 200]];
  var COPERTO_N = [[20, 26, 36], [44, 52, 64]];

  function coloriCielo() {
    var base = giorno ? GIORNO : NOTTE;
    var alto = mescola(base[0], TRAMONTO[0], crepuscolo * 0.7);
    var basso = mescola(base[1], TRAMONTO[1], crepuscolo * 0.85);
    var grigio = Math.pow(nuvole, 1.3) * 0.85 + (piove || neve ? 0.15 : 0);
    var coperto = giorno ? COPERTO_G : COPERTO_N;
    return [mescola(alto, coperto[0], Math.min(1, grigio)), mescola(basso, coperto[1], Math.min(1, grigio))];
  }

  /* ---------- Elementi casuali ma stabili ---------- */
  var seme = 7;
  function caso() { seme = (seme * 16807) % 2147483647; return (seme - 1) / 2147483646; }
  var stelle = [];
  for (var s = 0; s < 80; s++) stelle.push({ x: caso(), y: caso() * 0.7, r: 0.5 + caso() * 1.1, fase: caso() * 6.28 });
  var numeroNuvole = Math.round(1 + nuvole * 11);
  var nubi = [];
  for (var n = 0; n < numeroNuvole; n++) {
    nubi.push({ x: caso(), y: 0.08 + caso() * 0.45, scala: 0.6 + caso() * 0.9, velocita: 0.6 + caso() * 0.8 });
  }
  var particelle = [];
  var numeroParticelle = 0;
  if (piove) numeroParticelle = Math.round(Math.min(260, 25 + pioggia * 45));
  if (neve) numeroParticelle = Math.round(Math.min(160, 30 + pioggia * 30));
  for (var p = 0; p < numeroParticelle; p++) particelle.push({ x: caso(), y: caso(), v: 0.7 + caso() * 0.6 });

  /* ---------- Disegno ---------- */
  var W = 0, H = 0, t = 0, ultimo = 0, lampo = 0, prossimoLampo = 4;

  function nuvola(x, y, scala, colore) {
    ctx.fillStyle = colore;
    ctx.beginPath();
    var r = 26 * scala;
    ctx.arc(x, y, r, 0, 6.29);
    ctx.arc(x + r * 0.9, y - r * 0.35, r * 0.85, 0, 6.29);
    ctx.arc(x + r * 1.8, y, r * 0.95, 0, 6.29);
    ctx.arc(x + r * 0.9, y + r * 0.3, r * 0.9, 0, 6.29);
    ctx.fill();
  }

  function disegnaLuna(x, y, r, fase) {
    // Parte illuminata = mezzo disco + mezza ellisse (il terminatore).
    // k = 1 luna nuova, 0 quarto, -1 luna piena. Calante: immagine speculare.
    var k = Math.cos(2 * Math.PI * fase);
    var opacita = (giorno ? 0.55 : 0.95) * (1 - nuvole * 0.6);
    ctx.save();
    ctx.translate(x, y);
    if (fase >= 0.5) ctx.scale(-1, 1);
    ctx.fillStyle = 'rgba(250,240,205,' + opacita * 0.12 + ')';   // luce cinerea
    ctx.beginPath(); ctx.arc(0, 0, r, 0, 6.29); ctx.fill();
    ctx.fillStyle = 'rgba(250,240,205,' + opacita + ')';
    ctx.beginPath();
    ctx.arc(0, 0, r, -Math.PI / 2, Math.PI / 2, false);
    ctx.ellipse(0, 0, Math.abs(k) * r, r, 0, Math.PI / 2, -Math.PI / 2, k > 0);
    ctx.fill();
    ctx.restore();
  }

  function colline() {
    ctx.fillStyle = giorno ? 'rgba(30,70,60,0.55)' : 'rgba(6,14,22,0.75)';
    ctx.beginPath(); ctx.moveTo(0, H);
    for (var x = 0; x <= W; x += 20) ctx.lineTo(x, H * 0.84 - Math.sin(x / W * 5.2 + 1) * H * 0.05 - Math.sin(x / W * 13) * H * 0.015);
    ctx.lineTo(W, H); ctx.fill();
    ctx.fillStyle = giorno ? 'rgba(20,52,46,0.75)' : 'rgba(3,8,14,0.85)';
    ctx.beginPath(); ctx.moveTo(0, H);
    for (var x2 = 0; x2 <= W; x2 += 20) ctx.lineTo(x2, H * 0.92 - Math.sin(x2 / W * 3.1 + 2.2) * H * 0.04);
    ctx.lineTo(W, H); ctx.fill();
  }

  function disegna() {
    var Hc = Math.min(H, 420);   // altezza dell'arco del cielo per sole e luna
    var colori = coloriCielo();
    var g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, rgb(colori[0])); g.addColorStop(1, rgb(colori[1]));
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

    // Stelle (di notte, più visibili con cielo sereno)
    if (!giorno && nuvole < 0.85) {
      stelle.forEach(function (st) {
        var a = (1 - nuvole) * (1 - crepuscolo) * (0.45 + 0.35 * Math.sin(t * 1.3 + st.fase));
        ctx.fillStyle = 'rgba(255,255,255,' + Math.max(0, a) + ')';
        ctx.beginPath(); ctx.arc(st.x * W, st.y * H, st.r, 0, 6.29); ctx.fill();
      });
    }

    // Sole lungo l'arco del giorno
    if (giorno) {
      var sx = W * (0.08 + 0.84 * frazioneSole), sy = Hc * 0.82 - altezzaSole * Hc * 0.62;
      var alone = ctx.createRadialGradient(sx, sy, 4, sx, sy, 90);
      var trasparenza = 1 - nuvole * 0.85;
      alone.addColorStop(0, 'rgba(255,236,170,' + 0.75 * trasparenza + ')');
      alone.addColorStop(1, 'rgba(255,236,170,0)');
      ctx.fillStyle = alone; ctx.fillRect(sx - 90, sy - 90, 180, 180);
      ctx.fillStyle = 'rgba(255,226,140,' + trasparenza + ')';
      ctx.beginPath(); ctx.arc(sx, sy, 22, 0, 6.29); ctx.fill();
    }

    // Luna nella sua posizione e con la sua fase
    if (luna) {
      disegnaLuna(W * (0.08 + 0.84 * luna.frazione), Hc * 0.8 - luna.altezza * Hc * 0.6, 16, luna.fase);
    }

    // Nuvole che si spostano con il vento reale
    var spostamento = (6 + vento * 0.9) * versoEst;
    var tonoNube = piove || neve || temporale ? (giorno ? '150,160,170' : '55,62,74') : (giorno ? '250,252,255' : '120,130,150');
    nubi.forEach(function (nb) {
      var larghezza = W + 200;
      var x = ((nb.x * larghezza + t * spostamento * nb.velocita) % larghezza + larghezza) % larghezza - 100;
      nuvola(x, nb.y * H, nb.scala * (0.8 + nuvole * 0.6), 'rgba(' + tonoNube + ',' + (0.35 + nuvole * 0.5) + ')');
    });

    // Nebbia: bande orizzontali
    if (nebbia) {
      for (var b = 0; b < 4; b++) {
        var y = H * (0.45 + b * 0.13) + Math.sin(t * 0.2 + b) * 8;
        var banda = ctx.createLinearGradient(0, y - 30, 0, y + 30);
        banda.addColorStop(0, 'rgba(230,236,240,0)'); banda.addColorStop(0.5, 'rgba(230,236,240,0.45)'); banda.addColorStop(1, 'rgba(230,236,240,0)');
        ctx.fillStyle = banda; ctx.fillRect(0, y - 30, W, 60);
      }
    }

    colline();

    // Pioggia inclinata dal vento, oppure neve
    if (piove) {
      var inclinazione = versoEst * Math.min(1, vento / 40) * 10;
      ctx.strokeStyle = 'rgba(210,232,255,0.55)'; ctx.lineWidth = 1.2; ctx.beginPath();
      particelle.forEach(function (gc) {
        var y = ((gc.y * H + t * 420 * gc.v) % (H + 20)) - 10;
        var x = ((gc.x * W + inclinazione * (y / 14)) % W + W) % W;
        ctx.moveTo(x, y); ctx.lineTo(x + inclinazione, y + 14);
      });
      ctx.stroke();
    } else if (neve) {
      ctx.fillStyle = 'rgba(255,255,255,0.85)';
      particelle.forEach(function (fc) {
        var y = ((fc.y * H + t * 35 * fc.v) % (H + 10)) - 5;
        var x = ((fc.x * W + Math.sin(t + fc.x * 20) * 10 + t * versoEst * vento * 0.4) % W + W) % W;
        ctx.beginPath(); ctx.arc(x, y, 1.6 + fc.v, 0, 6.29); ctx.fill();
      });
    }

    // Temporale: lampo tenue e raro (mai con "riduci movimento")
    if (lampo > 0) {
      ctx.fillStyle = 'rgba(235,240,255,' + 0.22 * lampo + ')';
      ctx.fillRect(0, 0, W, H);
    }
  }

  /* ---------- Animazione leggera ---------- */
  var riduciMovimento = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var inPausa = riduciMovimento;
  var richiesta = 0;

  function visibile() {
    if (document.hidden) return false;
    try {
      var cornice = window.frameElement;
      if (cornice) {
        var rc = cornice.getBoundingClientRect(), rs = sezione.getBoundingClientRect();
        var alto = rc.top + rs.top, basso = rc.top + rs.bottom;
        return basso > 0 && alto < window.parent.innerHeight;
      }
    } catch (e) { /* riquadro non accessibile: si considera visibile */ }
    return true;
  }

  function fotogramma(adesso) {
    richiesta = 0;
    if (inPausa || !visibile()) { ultimo = 0; return; }
    var dt = ultimo ? Math.min((adesso - ultimo) / 1000, 0.05) : 0;
    ultimo = adesso; t += dt;
    if (temporale) {
      prossimoLampo -= dt;
      if (prossimoLampo <= 0) { lampo = 1; prossimoLampo = 6 + Math.random() * 8; }
      lampo = Math.max(0, lampo - dt * 5);
    }
    disegna();
    richiesta = requestAnimationFrame(fotogramma);
  }

  function avvia() { if (!richiesta && !inPausa) richiesta = requestAnimationFrame(fotogramma); }

  function ridimensiona() {
    var r = tela.getBoundingClientRect();
    W = Math.max(1, r.width); H = Math.max(1, r.height);
    var d = Math.min(window.devicePixelRatio || 1, 1.5);
    tela.width = Math.round(W * d); tela.height = Math.round(H * d);
    ctx.setTransform(d, 0, 0, d, 0, 0);
    disegna();
  }

  function aggiornaPulsante() {
    pulsantePausa.textContent = inPausa ? '▶' : '⏸';
    pulsantePausa.setAttribute('aria-pressed', String(inPausa));
    pulsantePausa.setAttribute('aria-label', inPausa ? "Avvia l'animazione del cielo" : "Metti in pausa l'animazione del cielo");
  }

  pulsantePausa.addEventListener('click', function () {
    inPausa = !inPausa; aggiornaPulsante();
    if (!inPausa) avvia();
  });
  aggiornaPulsante();

  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(ridimensiona).observe(tela);
  ridimensiona();
  document.addEventListener('visibilitychange', avvia);
  setInterval(avvia, 700);   // riprende quando il riquadro torna sullo schermo
  avvia();
})();

/* ---------- Menu rapido: in alto su computer, barra fissa in basso su telefono ---------- */
(function () {
  'use strict';
  var menu = document.getElementById('cml-menu-rapido');
  if (!menu) return;

  function vai(id) {
    var destinazione = document.getElementById(id);
    if (!destinazione) return;
    if (destinazione.tagName === 'DETAILS') destinazione.open = true;
    destinazione.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  menu.addEventListener('click', function (evento) {
    var link = evento.target.closest('a[data-vai]');
    if (!link) return;
    evento.preventDefault();
    vai(link.getAttribute('data-vai'));
  });

  var cornice = null;
  try { cornice = window.frameElement; } catch (e) { cornice = null; }
  if (!cornice) return;

  var telefono = window.matchMedia && window.matchMedia('(max-width: 680px)').matches;
  if (telefono) {
    try { if (barraInBasso()) return; } catch (e) { /* si resta col menu in alto */ }
  }

  // Computer: il menu segue lo scorrimento della pagina Streamlit (equivalente di "sticky").
  var partenza = 0;
  function misuraPartenza() {
    var precedente = menu.style.transform; menu.style.transform = '';
    partenza = menu.getBoundingClientRect().top + window.scrollY;
    menu.style.transform = precedente;
  }
  function segui() {
    var visibileDa = Math.max(0, -cornice.getBoundingClientRect().top);
    var limite = document.body.scrollHeight - menu.offsetHeight - 8;
    var spostamento = Math.max(0, Math.min(visibileDa - partenza + 6, limite - partenza));
    menu.style.transform = spostamento > 0 ? 'translateY(' + spostamento + 'px)' : '';
    menu.classList.toggle('cml-menu-sospeso', spostamento > 0);
  }
  misuraPartenza();
  try {
    window.parent.document.addEventListener('scroll', segui, { capture: true, passive: true });
    window.parent.addEventListener('resize', function () { misuraPartenza(); segui(); });
  } catch (e) { /* non accessibile: il menu resta in cima */ }
  segui();

  // Telefono: barra fissa in basso nella pagina principale (fissa rispetto allo schermo).
  function barraInBasso() {
    var genitore = window.parent.document;
    var finestra = window.parent;
    ['cml-barra-in-basso', 'cml-barra-stile'].forEach(function (id) {
      var vecchio = genitore.getElementById(id);
      if (vecchio) vecchio.remove();
    });

    var stile = genitore.createElement('style');
    stile.id = 'cml-barra-stile';
    stile.textContent =
      '#cml-barra-in-basso{position:fixed;left:8px;right:8px;bottom:calc(8px + env(safe-area-inset-bottom));' +
      'z-index:999999;display:flex;gap:2px;padding:5px;border:1px solid #d5e4e9;border-radius:20px;' +
      'background:rgba(255,255,255,.96);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);' +
      'box-shadow:0 8px 28px rgba(16,43,59,.22)}' +
      '#cml-barra-in-basso[hidden]{display:none}' +
      '#cml-barra-in-basso button{flex:1 1 0;min-width:0;display:flex;flex-direction:column;align-items:center;gap:2px;' +
      'padding:6px 2px;border:0;border-radius:14px;background:none;color:#102b3b;' +
      'font:700 11px/1.1 system-ui,-apple-system,"Segoe UI",sans-serif;cursor:pointer}' +
      '#cml-barra-in-basso button span:first-child{font-size:20px;line-height:1}' +
      '#cml-barra-in-basso button[aria-current="true"]{background:#e3f1f6;color:#0b5f7a}' +
      '#cml-barra-in-basso button:focus-visible{outline:3px solid #00a6dd;outline-offset:-3px}' +
      '[data-testid="stMain"] .block-container,[data-testid="stMainBlockContainer"]{padding-bottom:96px !important}';
    genitore.head.appendChild(stile);

    var barra = genitore.createElement('nav');
    barra.id = 'cml-barra-in-basso';
    barra.setAttribute('aria-label', 'Sezioni della previsione');
    var voci = Array.prototype.slice.call(menu.querySelectorAll('a[data-vai]'));
    voci.forEach(function (link) {
      var bottone = genitore.createElement('button');
      bottone.type = 'button';
      bottone.setAttribute('data-vai', link.getAttribute('data-vai'));
      var icona = link.querySelector('.cml-menu-icona');
      var testo = link.querySelector('.cml-menu-testo');
      var i = genitore.createElement('span'); i.setAttribute('aria-hidden', 'true'); i.textContent = icona ? icona.textContent : '';
      var t = genitore.createElement('span'); t.textContent = testo ? testo.textContent : link.textContent;
      bottone.appendChild(i); bottone.appendChild(t);
      bottone.addEventListener('click', function () { vai(link.getAttribute('data-vai')); });
      barra.appendChild(bottone);
    });
    genitore.body.appendChild(barra);
    menu.classList.add('cml-menu-in-basso');
    document.body.classList.add('cml-con-barra');

    function togli() { barra.remove(); stile.remove(); }
    window.addEventListener('pagehide', togli);

    // Visibile solo quando la previsione è sullo schermo (non nella scheda Viaggio)
    if (finestra.IntersectionObserver) {
      new finestra.IntersectionObserver(function (voci) {
        barra.hidden = !voci[0].isIntersecting;
      }).observe(cornice);
    }

    // Sezione in cui ci si trova
    var bottoni = Array.prototype.slice.call(barra.querySelectorAll('button'));
    function evidenzia() {
      if (!cornice.isConnected) { togli(); return; }
      var alto = cornice.getBoundingClientRect().top;
      var soglia = finestra.innerHeight * 0.35;
      var attivo = null;
      bottoni.forEach(function (b) {
        var sezione = document.getElementById(b.getAttribute('data-vai'));
        if (sezione && alto + sezione.getBoundingClientRect().top <= soglia) attivo = b;
      });
      bottoni.forEach(function (b) { b.setAttribute('aria-current', b === attivo ? 'true' : 'false'); });
    }
    genitore.addEventListener('scroll', evidenzia, { capture: true, passive: true });
    evidenzia();
    return true;
  }
})();

/* ---------- Fisarmoniche: su telefono partono chiuse ---------- */
(function () {
  'use strict';
  if (!window.matchMedia || !window.matchMedia('(max-width: 680px)').matches) return;
  document.querySelectorAll('details[data-chiudi-su-telefono]').forEach(function (d) {
    d.removeAttribute('open');
  });
})();
