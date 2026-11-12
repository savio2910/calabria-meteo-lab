# =============================================================================
# Calabria Meteo Lab - Sezione mare (visiva e in parole semplici)
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import html
from datetime import datetime

import pandas as pd

from meteo.config import FUSO_ORARIO
from meteo.dati import stato_mare_da_onda
from meteo.formato import data_it, direzione, numero, ora_it

# Scala dello stato del mare (altezza d'onda in m) usata per la barra
SCALA_MARE = [
    ("Calmo", 0.0, 0.1), ("Quasi calmo", 0.1, 0.5), ("Poco mosso", 0.5, 1.25),
    ("Mosso", 1.25, 2.5), ("Molto mosso", 2.5, 4.0), ("Agitato", 4.0, 6.0),
]
NOMI_DIREZIONE = {"N": "nord", "NE": "nord-est", "E": "est", "SE": "sud-est",
                  "S": "sud", "SO": "sud-ovest", "O": "ovest", "NO": "nord-ovest"}


def _float(valore):
    try:
        valore = float(valore)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(valore) else valore


def barra_stato_mare_html(altezza):
    """Barra a sei tratti (da calmo ad agitato) con l'indicatore dell'altezza attuale."""
    tratti = "".join(f'<span class="mr-tratto mr-tratto-{i}" title="{nome}: {a:g}–{b:g} m"></span>'
                     for i, (nome, a, b) in enumerate(SCALA_MARE))
    indicatore = ""
    if altezza is not None:
        for i, (_, a, b) in enumerate(SCALA_MARE):
            if altezza < b or i == len(SCALA_MARE) - 1:
                frazione = min(max((altezza - a) / (b - a), 0), 1)
                indicatore = f'<i class="mr-indicatore" style="left:{(i + frazione) / len(SCALA_MARE) * 100:.1f}%"></i>'
                break
    etichette = "".join(f"<span>{nome}</span>" for nome, _, _ in SCALA_MARE)
    return (f'<div class="mr-scala" role="img" aria-label="Stato del mare">'
            f'<div class="mr-barra">{tratti}{indicatore}</div><div class="mr-etichette">{etichette}</div></div>')


def bussola_onde_html(gradi):
    """Bussola con la freccia che indica DOVE VANNO le onde (arrivano da 'gradi')."""
    if gradi is None:
        return ""
    verso = (gradi + 180) % 360
    return f"""
      <svg class="mr-bussola" viewBox="0 0 120 120" role="img" aria-label="Onde da {direzione(gradi)}">
        <circle cx="60" cy="60" r="52" class="mr-bussola-cerchio"/>
        <text x="60" y="20" text-anchor="middle">N</text><text x="103" y="64" text-anchor="middle">E</text>
        <text x="60" y="108" text-anchor="middle">S</text><text x="17" y="64" text-anchor="middle">O</text>
        <g transform="rotate({verso:.0f} 60 60)">
          <path d="M60 22 L71 48 L63 45 L63 90 L57 90 L57 45 L49 48 Z" class="mr-bussola-freccia"/>
        </g>
      </svg>"""


def _tabella_trioraria(orarie):
    if orarie.empty or "time" not in orarie:
        return ""
    adesso = pd.Timestamp(datetime.now(FUSO_ORARIO).replace(tzinfo=None))
    triorarie = orarie.loc[(orarie["time"].dt.hour % 3 == 0) & (orarie["time"] >= adesso.floor("h"))].sort_values("time")
    blocchi = []
    for data, gruppo in triorarie.groupby(triorarie["time"].dt.date):
        righe = []
        for _, r in gruppo.iterrows():
            stato, icona, classe = stato_mare_da_onda(r.get("wave_height"))
            righe.append(f"""
            <tr><td class="c-ora">{ora_it(r.get("time"))}</td>
              <td class="c-scenario"><span class="cml-marine-forecast-status {classe}" style="margin:0;">{icona} {html.escape(stato)}</span></td>
              <td class="c-temp" data-unita=" m">{numero(r.get("wave_height"), 1)}</td>
              <td class="c-dato" data-etichetta="Onde da">{direzione(r.get("wave_direction"))}</td>
              <td class="c-dato" data-etichetta="Acqua" data-unita="°">{numero(r.get("sea_surface_temperature"), 0)}</td></tr>""")
        blocchi.append(f"""
          <div class="cml-marine-forecast-date">{html.escape(data_it(data).title())}</div>
          <div class="cml-table-wrap"><table class="cml-table cml-tabella-mare">
            <thead><tr><th>Ora</th><th>Stato del mare</th><th>Onde m</th><th>Da</th><th>Acqua °C</th></tr></thead>
            <tbody>{''.join(righe)}</tbody></table></div>""")
    if not blocchi:
        return ""
    return f"""
        <details class="cml-fisarmonica mr-ore">
          <summary class="cml-fisarmonica-titolo">🕒 Il mare ogni 3 ore</summary>
          {''.join(blocchi)}
        </details>"""


def mare_html(dati_mare, distanza_mare_km=None):
    """Sezione del mare ('' se non ci sono dati marini)."""
    if not isinstance(dati_mare, dict) or not dati_mare.get("current"):
        return ""
    c = dati_mare["current"]
    orarie = pd.DataFrame(dati_mare.get("hourly", {}))
    if not orarie.empty and "time" in orarie:
        orarie["time"] = pd.to_datetime(orarie["time"])

    altezza = _float(c.get("wave_height"))
    gradi = _float(c.get("wave_direction"))
    periodo = _float(c.get("wave_period"))
    vento = _float(c.get("wind_wave_height"))
    fondo = _float(c.get("swell_wave_height"))
    acqua = _float(c.get("sea_surface_temperature"))
    stato, icona, classe = stato_mare_da_onda(altezza)

    frasi = []
    if gradi is not None:
        frasi.append(f"Onde da {NOMI_DIREZIONE.get(direzione(gradi), direzione(gradi))}")
    if vento is not None and fondo is not None:
        if fondo > max(vento * 1.5, 0.3):
            frasi.append(f"soprattutto onda lunga arrivata da lontano ({numero(fondo, 1, ' m')}), mare del vento locale {numero(vento, 1, ' m')}")
        else:
            frasi.append(f"formate soprattutto dal vento locale ({numero(vento, 1, ' m')}), onda lunga da lontano {numero(fondo, 1, ' m')}")
    descrizione = ", ".join(frasi) + "." if frasi else ""

    return f"""
  <section class="cml-sezione mr-sezione" id="cml-mare">
    <h2 class="cml-titolo-sezione">🌊 Mare</h2>
    <div class="mr-scheda">
      <div class="mr-stato {classe}"><span>{icona}</span><b>{html.escape(stato)}</b></div>
      {barra_stato_mare_html(altezza)}
      <div class="mr-centro">
        {bussola_onde_html(gradi)}
        <dl class="mr-numeri">
          <div><dt>Onde</dt><dd>{numero(altezza, 1, ' m')}</dd></div>
          <div><dt>Acqua</dt><dd>{numero(acqua, 0, '°')}</dd></div>
          <div><dt>Un'onda ogni</dt><dd>{numero(periodo, 0, ' s')}</dd></div>
        </dl>
      </div>
      <p class="mr-frase">{html.escape(descrizione)}</p>
      <p class="mr-nota">Punto di mare più vicino a circa {numero(distanza_mare_km, 1, ' km')}.</p>
    </div>
    {_tabella_trioraria(orarie)}
  </section>"""
