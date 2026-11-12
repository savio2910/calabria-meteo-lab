# =============================================================================
# Calabria Meteo Lab - Pagina del viaggio (riepilogo, partenze, tappe, mappa)
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import html
import json

from meteo.config import leggi_static
from meteo.formato import data_it, icona_meteo_html, meteo, numero
from meteo.viaggio import LIVELLI, MEZZI, SOGLIE_VIAGGIO, fasce_da_evitare


def _etichetta(livello):
    if livello is None:
        return '<span class="cml-liv cml-liv-nd">⚪ Non disponibile</span>'
    simbolo, testo = LIVELLI[livello]
    return f'<span class="cml-liv cml-liv-{livello}">{simbolo} {testo}</span>'


def _durata(minuti):
    ore, resto = divmod(int(round(minuti)), 60)
    return f"{ore} h {resto:02d} min" if ore else f"{resto} min"


def criteri_viaggio(mezzo):
    """Criteri leggibili; ogni voce legge solo le soglie del proprio mezzo."""
    s, c = SOGLIE_VIAGGIO[mezzo], SOGLIE_VIAGGIO["comuni"]
    comuni = (f"Sempre 🔴 con temporali, neve o rischio ghiaccio "
              f"(temperatura ≤ {c['ghiaccio_temperatura']:.0f}° con precipitazioni).")
    testi = {
        "auto": lambda s: [
            f"🔴 raffiche ≥ {s['raffiche_sconsigliato']} km/h",
            f"🟠 pioggia ≥ {s['pioggia_discreto']:.0f} mm/h; nebbia; raffiche ≥ {s['raffiche_discreto']} km/h",
            f"🟡 pioggia ≥ {s['pioggia_buono']:.0f} mm/h; temperatura ≤ {s['freddo_buono']:.0f}° (possibile ghiaccio)",
        ],
        "moto": lambda s: [
            f"🔴 pioggia ≥ {s['pioggia_sconsigliato']:.0f} mm/h; raffiche ≥ {s['raffiche_sconsigliato']} km/h",
            f"🟠 pioggia ≥ {s['pioggia_discreto']} mm/h; vento ≥ {s['vento_discreto']} o raffiche ≥ {s['raffiche_discreto']} km/h; "
            f"nebbia; temperatura ≤ {s['freddo_discreto']:.0f}°",
            f"🟡 temperatura ≤ {s['freddo_buono']:.0f}°; viaggio con il buio",
        ],
        "bici": lambda s: [
            f"🔴 pioggia ≥ {s['pioggia_sconsigliato']:.0f} mm/h; raffiche ≥ {s['raffiche_sconsigliato']} km/h; "
            f"percepita > {s['caldo_sconsigliato']}°",
            f"🟠 pioggia ≥ {s['pioggia_discreto']} mm/h; vento ≥ {s['vento_discreto']} o raffiche ≥ {s['raffiche_discreto']} km/h; "
            f"nebbia; percepita < {s['percepita_discreto'][0]}° o > {s['percepita_discreto'][1]}°",
            f"🟡 vento ≥ {s['vento_buono']} km/h; viaggio con il buio",
        ],
    }
    return testi[mezzo](s) + [comuni]


def documento_viaggio(origine, destinazione, mezzo, percorso, valutazioni, scelta, consigliata):
    """Pagina HTML completa del viaggio per la partenza 'scelta'."""
    nome_mezzo, icona_mezzo = MEZZI[mezzo][0], MEZZI[mezzo][1]

    # Riepilogo
    if consigliata is not None:
        riepilogo = f"""
        <div class="v-consiglio">
          <span class="v-etichetta">PARTENZA CONSIGLIATA</span>
          <strong>{consigliata['partenza']:%H:%M}</strong>
          <span>arrivo verso le {consigliata['arrivo']:%H:%M} · {_etichetta(consigliata['livello'])}</span>
          <small>{html.escape(data_it(consigliata['partenza']).capitalize())} · peggior tratto:
          {html.escape(consigliata['motivo'])}{(' (' + html.escape(consigliata['dove']) + ')') if consigliata['livello'] else ''}</small>
          {('<small class="v-raffiche">💨 ' + html.escape(consigliata['avviso'][:1].upper() + consigliata['avviso'][1:])
            + ' (' + html.escape(consigliata['avviso_dove']) + ') secondo gli scenari degli ensemble</small>')
           if consigliata.get('avviso') else ''}
        </div>"""
    else:
        riepilogo = """
        <div class="v-consiglio v-consiglio-nd">
          <span class="v-etichetta">PARTENZA CONSIGLIATA</span>
          <strong>—</strong>
          <span>La previsione non copre tutto il viaggio nella fascia scelta: prova un giorno più vicino.</span>
        </div>"""

    evitare = fasce_da_evitare(valutazioni)
    testo_evitare = "".join(
        f"<li>🔴 Evita le partenze {da:%H:%M}–{a:%H:%M}: {html.escape(motivo)} ({html.escape(dove)})</li>"
        for da, a, motivo, dove in evitare
    )

    # Barra delle partenze
    caselle = "".join(
        f'<li class="v-partenza cml-liv-{v["livello"] if v["livello"] is not None else "nd"}'
        f'{" v-scelta" if v["partenza"] == scelta["partenza"] else ""}'
        f'{" v-consigliata" if consigliata is not None and v["partenza"] == consigliata["partenza"] else ""}" '
        f'title="{v["partenza"]:%H:%M} · {html.escape(LIVELLI[v["livello"]][1] if v["livello"] is not None else "non disponibile")}'
        f' – {html.escape(v["motivo"], quote=True)}'
        f'{(" · 💨 " + html.escape(v["avviso"], quote=True)) if v.get("avviso") else ""}">'
        f'<span>{v["partenza"]:%H:%M}</span></li>'
        for v in valutazioni
    )

    # Tappe passo passo
    righe = []
    for indice, tappa in enumerate(scelta["tappe"]):
        nome = "Partenza" if indice == 0 else ("Arrivo" if indice == len(scelta["tappe"]) - 1 else f"km {tappa['km']:.0f}")
        riga = tappa["meteo"]
        if riga is None:
            meteo_html = '<td class="c-scenario" colspan="4">Previsione non disponibile</td>'
        else:
            notte = riga.get("is_day") == 0
            meteo_html = f"""
              <td class="c-scenario"><span class="cml-table-icon">{icona_meteo_html(riga.get('weather_code'), notte)}</span>
                <span>{html.escape(meteo(riga.get('weather_code'))[1])}</span></td>
              <td class="c-temp" data-unita="°">{numero(riga.get('temperature_2m'), 0)}</td>
              <td class="c-dato" data-etichetta="Pioggia" data-unita=" mm">{numero(riga.get('precipitation'), 1)}</td>
              <td class="c-dato" data-etichetta="Vento">{numero(riga.get('wind_speed_10m'), 0, ' km/h')}
                · raffiche {numero(riga.get('wind_gusts_10m'), 0)}</td>"""
        righe.append(f"""
          <tr>
            <td class="c-ora">{tappa['passaggio']:%H:%M}</td>
            <td class="c-dato v-dove"><b>{html.escape(nome)}</b> {html.escape(tappa['strada'] or '')}
              <small>quota {numero(tappa['quota'], 0, ' m')}</small></td>
            {meteo_html}
            <td class="c-dato v-giudizio">{_etichetta(tappa['livello'])} <small>{html.escape(tappa['motivo'])}</small>
              {('<small class="v-raffiche">💨 ' + html.escape(tappa['avviso']) + '</small>') if tappa.get('avviso') else ''}</td>
          </tr>""")

    # Mappa
    traccia = [[round(lat, 5), round(lon, 5)] for lat, lon in percorso["coordinate"][:: max(1, len(percorso["coordinate"]) // 400)]]
    traccia.append([round(percorso["coordinate"][-1][0], 5), round(percorso["coordinate"][-1][1], 5)])
    punti_mappa = [
        {"lat": t["lat"], "lon": t["lon"], "livello": t["livello"],
         "testo": f"{t['passaggio']:%H:%M} · km {t['km']:.0f} · "
                  + (meteo(t['meteo'].get('weather_code'))[1] if t["meteo"] is not None else "n/d")
                  + f" · {LIVELLI[t['livello']][1] if t['livello'] is not None else 'n/d'} – {t['motivo']}"}
        for t in scelta["tappe"]
    ]
    dati_mappa = json.dumps({"traccia": traccia, "punti": punti_mappa}, ensure_ascii=False).replace("<", "\\u003c")

    avviso_stima = (
        '<p class="v-avviso">⚠️ Il servizio dei percorsi non ha risposto: tracciato e tempi sono <b>stimati in linea d\'aria</b> '
        "e possono essere molto diversi dalla strada reale.</p>" if percorso["stimato"] else ""
    )
    criteri = "".join(f"<li>{html.escape(c)}</li>" for c in criteri_viaggio(mezzo))

    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
{leggi_static("stile.css")}
{leggi_static("viaggio.css")}
</style></head>
<body><main id="cml-pagina">
<section class="cml-radar-box v-testa">
  <span class="cml-eyebrow">VIAGGIO · {icona_mezzo} {html.escape(nome_mezzo.upper())}</span>
  <h2>{html.escape(origine)} → {html.escape(destinazione)}</h2>
  <p>{numero(percorso['distanza_km'], 0, ' km')} · circa {_durata(percorso['durata_min'])} ·
     percorso: {html.escape(percorso['fonte'])}</p>
  {avviso_stima}
  {riepilogo}
  <ul class="v-evitare">{testo_evitare}</ul>
</section>

<section class="cml-radar-box">
  <h3 class="v-titolo">🕒 Tutte le partenze</h3>
  <p class="v-nota">Ogni casella è una partenza: il colore è il giudizio del tratto peggiore.
     Il riquadro scuro è la partenza mostrata sotto, la stella quella consigliata.</p>
  <ol class="v-partenze">{caselle}</ol>
</section>

<section class="cml-radar-box">
  <h3 class="v-titolo">🛣️ Passo passo · partenza alle {scelta['partenza']:%H:%M}</h3>
  <div class="cml-table-wrap">
    <table class="cml-table cml-tabella-oraria v-tabella">
      <thead><tr><th>Passaggio</th><th>Dove</th><th>Meteo</th><th>Temp. °C</th><th>Pioggia mm</th>
      <th>Vento</th><th>Giudizio</th></tr></thead>
      <tbody>{''.join(righe)}</tbody>
    </table>
  </div>
</section>

<section class="cml-radar-box">
  <h3 class="v-titolo">🗺️ Mappa del percorso</h3>
  <div id="v-mappa"></div>
</section>

<div class="cml-marine-note">
  ℹ️ Meteo ICON-2I (ItaliaMeteo–ARPAE) via Open-Meteo nei punti del percorso, all'ora di passaggio stimata.
  Criteri applicativi, non garanzie di sicurezza: segui sempre gli avvisi ufficiali e lo stato delle strade (ANAS, CCISS).
  <details><summary>Come è calcolato ({html.escape(nome_mezzo)})</summary><ul>{criteri}</ul></details>
</div>
</main>
<script>
(function () {{
  var D = {dati_mappa};
  if (typeof L === 'undefined') {{ document.getElementById('v-mappa').textContent = 'Mappa non disponibile.'; return; }}
  var colori = {{0: '#22a35a', 1: '#e3c11d', 2: '#f08a2c', 3: '#d63a47'}};
  var mappa = L.map('v-mappa', {{ scrollWheelZoom: false }});
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ attribution: '© OpenStreetMap' }}).addTo(mappa);
  var linea = L.polyline(D.traccia, {{ color: '#0b7f98', weight: 4, opacity: .8 }}).addTo(mappa);
  D.punti.forEach(function (p) {{
    L.circleMarker([p.lat, p.lon], {{ radius: 7, weight: 2, color: '#ffffff', fillOpacity: 1,
      fillColor: colori[p.livello] || '#9aabb5' }}).bindPopup(p.testo).addTo(mappa);
  }});
  mappa.fitBounds(linea.getBounds(), {{ padding: [20, 20] }});
}})();
</script>
</body></html>"""
