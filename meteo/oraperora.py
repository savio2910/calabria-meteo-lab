# =============================================================================
# Calabria Meteo Lab - Sezione "Ora per ora": un unico grafico sui 3 giorni
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Sostituisce le tabelle orarie dentro i giorni, i tre grafici per giorno e
# l'"Esploratore": un solo grafico con quattro viste (temperatura, pioggia,
# vento, nuvole) e il dettaglio dell'ora toccata. Il disegno è in
# static/oraperora.js.

import json

import pandas as pd

from meteo.formato import data_it, direzione, meteo, valore_finito
from meteo.indicatori import SOGLIE_INDICATORI, livello, quota_neve, valore_ora


def _numero(valore, decimali=1):
    v = valore_finito(valore, None)
    return None if v is None else round(v, decimali)


def _neve_ora(riga, indicatori):
    pioggia = valore_finito(riga.get("precipitation"), 0.0)
    if pioggia < SOGLIE_INDICATORI["pioggia_mm"]:
        return None
    quota = quota_neve(valore_ora(indicatori, riga["time"], "zero_termico"))
    return quota if quota is not None and quota <= SOGLIE_INDICATORI["neve_quota_massima_m"] else None


def dati_ore(ore, probabilita=None, indicatori=None):
    """Una riga per ora con tutto ciò che serve al grafico e al dettaglio."""
    orarie = (probabilita or {}).get("orarie") or {}
    righe = []
    for _, riga in ore.iterrows():
        istante = pd.Timestamp(riga["time"])
        prob = orarie.get(istante) or {}
        icona, descrizione = meteo(riga.get("weather_code"))
        righe.append({
            "t": istante.strftime("%Y-%m-%dT%H:%M"),
            "data": istante.strftime("%Y-%m-%d"),
            "ora": istante.strftime("%H:%M"),
            "giorno": data_it(istante).capitalize(),
            "icona": icona,
            "cielo": descrizione,
            "notte": bool(riga.get("Notte", False)),
            "temp": _numero(riga.get("temperature_2m")),
            "percepita": _numero(riga.get("apparent_temperature")),
            "pioggia": _numero(riga.get("precipitation")),
            "prob": None if prob.get("pioggia") is None else round(prob["pioggia"] * 100),
            "temporali": None if prob.get("temporali") is None else round(prob["temporali"] * 100),
            "vento": _numero(riga.get("wind_speed_10m"), 0),
            "raffiche": _numero(riga.get("wind_gusts_10m"), 0),
            "da": direzione(riga.get("wind_direction_10m")),
            "nubi": _numero(riga.get("cloud_cover"), 0),
            "umidita": _numero(riga.get("relative_humidity_2m"), 0),
            # quota neve solo se in quell'ora è prevista precipitazione (e sotto i 2000 m)
            "neve": _neve_ora(riga, indicatori),
            "cape": livello(valore_ora(indicatori, istante, "cape"), SOGLIE_INDICATORI["cape"]),
            "uv": _numero(valore_ora(indicatori, istante, "uv"), 0),
            "polveri": _numero(valore_ora(indicatori, istante, "polveri"), 0),
        })
    return righe


def sezione_ora_per_ora_html(ore, probabilita=None, indicatori=None):
    righe = dati_ore(ore, probabilita, indicatori)
    giorni = []
    for riga in righe:
        if not giorni or giorni[-1][0] != riga["data"]:
            giorni.append((riga["data"], riga["giorno"]))
    etichette = ["Oggi", "Domani"]
    pulsanti_giorni = "".join(
        f'<button type="button" class="oo-giorno" data-data="{data}">'
        f'{etichette[i] if i < len(etichette) else nome.split(" ")[0]}</button>'
        for i, (data, nome) in enumerate(giorni)
    )
    dati_json = json.dumps(righe, ensure_ascii=False).replace("<", "\\u003c")
    return f"""
<section class="cml-radar-box oo" aria-labelledby="oo-titolo">
  <div class="oo-testa">
    <div>
      <span class="cml-eyebrow">PROSSIME 72 ORE</span>
      <h2 id="oo-titolo">🕒 Ora per ora</h2>
    </div>
    <div class="oo-viste" role="tablist" aria-label="Cosa mostrare nel grafico">
      <button type="button" role="tab" class="oo-vista" data-vista="temperatura" aria-selected="true">🌡️ Temperatura</button>
      <button type="button" role="tab" class="oo-vista" data-vista="pioggia" aria-selected="false">🌧️ Pioggia</button>
      <button type="button" role="tab" class="oo-vista" data-vista="vento" aria-selected="false">💨 Vento</button>
      <button type="button" role="tab" class="oo-vista" data-vista="nuvole" aria-selected="false">☁️ Nuvole</button>
    </div>
  </div>

  <div class="oo-giorni" aria-label="Vai al giorno">{pulsanti_giorni}</div>

  <div class="oo-scorri" id="oo-scorri" tabindex="0"
       aria-label="Grafico ora per ora: usa le frecce sinistra e destra per cambiare ora">
    <div class="oo-tela" id="oo-tela"><canvas id="oo-grafico" role="img"
         aria-label="Andamento ora per ora della variabile scelta"></canvas></div>
  </div>

  <div class="oo-dettaglio" id="oo-dettaglio" aria-live="polite"></div>

  <p class="oo-piede">Tocca il grafico per vedere un'ora · le fasce scure sono le ore di buio ·
    <a href="#" id="oo-csv">scarica i dati (CSV)</a></p>
</section>
<script>window.CML_ORE = {dati_json};</script>
"""
