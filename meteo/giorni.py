# =============================================================================
# Calabria Meteo Lab - Prossimi giorni in forma compatta (stile app meteo)
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Una riga per giorno: giorno, icona, allerta, pioggia, minima, barra colorata
# minima-massima (sulla stessa scala per tutti i giorni) e massima. Toccando la
# riga si apre il dettaglio (probabilità, indicatori, vento, sole e luna).

import html

import pandas as pd

from meteo.allerta import LIVELLI_ALLERTA, descrivi_livelli
from meteo.dati import valuta_rischio_locale
from meteo.formato import data_it, icona_meteo_html, meteo, numero, ora_it

# Colori della temperatura (°C -> colore), interpolati tra un punto e l'altro
SCALA_TEMPERATURA = [
    (-10, (104, 84, 214)), (0, (64, 132, 222)), (8, (52, 178, 205)), (14, (76, 186, 122)),
    (20, (232, 196, 58)), (26, (244, 141, 40)), (32, (226, 72, 43)), (40, (168, 30, 62)),
]
NOMI_BREVI = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
MESI_BREVI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
INDICE_APP = {"giallo": ("◔", "attenzione"), "arancione": ("◑", "attenzione alta"), "rosso": ("●", "attenzione molto alta")}


def colore_temperatura(gradi):
    """Colore CSS (rgb) di una temperatura."""
    if gradi is None or pd.isna(gradi):
        return "rgb(160,176,186)"
    gradi = float(gradi)
    if gradi <= SCALA_TEMPERATURA[0][0]:
        r, g, b = SCALA_TEMPERATURA[0][1]
        return f"rgb({r},{g},{b})"
    for (t1, c1), (t2, c2) in zip(SCALA_TEMPERATURA, SCALA_TEMPERATURA[1:]):
        if gradi <= t2:
            f = (gradi - t1) / (t2 - t1)
            r, g, b = (round(a + (bb - a) * f) for a, bb in zip(c1, c2))
            return f"rgb({r},{g},{b})"
    r, g, b = SCALA_TEMPERATURA[-1][1]
    return f"rgb({r},{g},{b})"


def _float(valore):
    try:
        valore = float(valore)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(valore) else valore


def barra_temperatura_html(minima, massima, scala_min, scala_max, attuale=None):
    """Barra minima-massima sulla scala comune; 'attuale' aggiunge il pallino della temperatura di adesso."""
    if minima is None or massima is None:
        return '<span class="gg-barra gg-barra-vuota"></span>'
    ampiezza = max(scala_max - scala_min, 1.0)
    sinistra = (minima - scala_min) / ampiezza * 100
    larghezza = max((massima - minima) / ampiezza * 100, 4)
    pallino = ""
    if attuale is not None and minima - 3 <= attuale <= massima + 3:
        posizione = min(max((attuale - scala_min) / ampiezza * 100, 0), 100)
        pallino = f'<i class="gg-adesso" style="left:{posizione:.1f}%" title="Adesso {attuale:.0f}°"></i>'
    return (f'<span class="gg-barra" aria-hidden="true"><span class="gg-barra-pieno" style="left:{sinistra:.1f}%;'
            f'width:{larghezza:.1f}%;background:linear-gradient(90deg,{colore_temperatura(minima)},'
            f'{colore_temperatura(massima)})"></span>{pallino}</span>')


def _nome_giorno(data, indice):
    if indice == 0:
        return "Oggi"
    if indice == 1:
        return "Domani"
    return NOMI_BREVI[data.weekday()]


def _codice(riga):
    codice = riga.get("weather_code_prevalente", riga.get("weather_code"))
    try:
        return 3 if codice is None or pd.isna(codice) else int(float(codice))
    except (TypeError, ValueError):
        return 3


def _pioggia_riga(riga, probabilita_giorno):
    """Testo della pioggia nella riga: probabilità degli ensemble o, senza, i millimetri."""
    mm = _float(riga.get("precipitation_sum")) or 0.0
    if probabilita_giorno and probabilita_giorno.get("pioggia") is not None:
        p = probabilita_giorno["pioggia"] * 100
        if p < 10 and mm < 0.5:
            return '<span class="gg-pioggia gg-nulla">—</span>'
        return f'<span class="gg-pioggia" title="{mm:.1f} mm previsti">💧{p:.0f}%</span>'
    if mm < 0.5:
        return '<span class="gg-pioggia gg-nulla">—</span>'
    return f'<span class="gg-pioggia">💧{mm:.0f} mm</span>'


def giorni_html(giorni, ore, corrente=None, probabilita=None, allerta=None, indicatori=None,
                allerta_giorno_html=None, probabilita_giorno_html=None, indicatori_giorno_html=None):
    """Sezione "Prossimi giorni" compatta (le funzioni *_html del dettaglio sono passate da pagina.py)."""
    righe_giorni = list(giorni.iterrows())
    minime = [_float(r.get("temperature_2m_min")) for _, r in righe_giorni]
    massime = [_float(r.get("temperature_2m_max")) for _, r in righe_giorni]
    valori = [v for v in minime + massime if v is not None]
    scala_min, scala_max = (min(valori), max(valori)) if valori else (0.0, 1.0)
    attuale = _float((corrente or {}).get("temperature_2m"))
    giornaliere = (probabilita or {}).get("giornaliere") or {}

    righe = []
    for indice, (_, riga) in enumerate(righe_giorni):
        data = pd.Timestamp(riga["time"]).date()
        codice = _codice(riga)
        descrizione = meteo(codice)[1]
        minima, massima = minime[indice], massime[indice]

        # Pallino dell'allerta ufficiale e indice meteo dell'app
        pallino_allerta = ""
        if allerta and allerta.get("disponibile") and data in (allerta.get("giorni") or {}):
            livello_allerta, testo_allerta = descrivi_livelli(allerta["giorni"][data])
            if livello_allerta > 0:
                pallino_allerta = (f'<span class="gg-allerta gg-allerta-{livello_allerta}" '
                                   f'title="{html.escape(testo_allerta, quote=True)}">{LIVELLI_ALLERTA[livello_allerta][0]}</span>')
        livello_app, rischio = valuta_rischio_locale(riga)
        indice_app = ""
        if livello_app in INDICE_APP:
            simbolo, testo = INDICE_APP[livello_app]
            indice_app = (f'<p class="gg-indice gg-indice-{livello_app}">{simbolo} Indice meteo dell\'app: {testo}'
                          f' · {html.escape(rischio)} <small>(stima automatica, non un\'allerta ufficiale)</small></p>')

        nome = _nome_giorno(data, indice)
        data_breve = f"{data.day} {MESI_BREVI[data.month - 1]}"
        dettagli = [
            ("🌧️ Pioggia", numero(riga.get("precipitation_sum"), 1, " mm")),
            ("💨 Vento", f'{numero(riga.get("wind_speed_10m_max"), 0, " km/h")} {html.escape(str(riga.get("Da", "")))}'),
            ("🌬️ Raffiche", numero(riga.get("wind_gusts_10m_max"), 0, " km/h")),
            ("☁️ Nuvole", numero(riga.get("cloud_cover_diurno"), 0, " %")),
        ]
        righe.append(f"""
      <details class="gg-giorno" id="scheda-{data}"{' open' if indice == 0 and pallino_allerta else ''}>
        <summary aria-label="{html.escape(data_it(data), quote=True)}: {html.escape(descrizione, quote=True)}, minima {numero(minima, 0)}, massima {numero(massima, 0)} gradi">
          <span class="gg-nome"><b>{nome}</b><small>{data_breve}</small></span>
          <span class="gg-icona" title="{html.escape(descrizione, quote=True)}">{icona_meteo_html(codice)}{pallino_allerta}</span>
          {_pioggia_riga(riga, giornaliere.get(data))}
          <span class="gg-min">{numero(minima, 0, "°")}</span>
          {barra_temperatura_html(minima, massima, scala_min, scala_max, attuale if indice == 0 else None)}
          <span class="gg-max">{numero(massima, 0, "°")}</span>
          <span class="gg-freccia" aria-hidden="true"></span>
        </summary>
        <div class="gg-dettaglio">
          <p class="gg-descrizione"><b>{html.escape(descrizione)}</b> · {html.escape(str(riga.get("Fase lunare", "")))}</p>
          {allerta_giorno_html(data, allerta) if allerta_giorno_html else ''}
          {indice_app}
          {probabilita_giorno_html(data, probabilita) if probabilita_giorno_html else ''}
          {indicatori_giorno_html(data, ore, indicatori) if indicatori_giorno_html else ''}
          <dl class="gg-valori">{''.join(f'<div><dt>{e}</dt><dd>{v}</dd></div>' for e, v in dettagli)}</dl>
          <p class="gg-astro">☀️ {ora_it(riga.get("sunrise"))} – {ora_it(riga.get("sunset"))}
             <span>🌙 {ora_it(riga.get("moonrise"))} – {ora_it(riga.get("moonset"))}</span></p>
          <button type="button" class="gg-vai" onclick="window.vaiAlGiorno && vaiAlGiorno('{data}')">Vedi {nome.lower() if indice < 2 else data_it(data).split(' ')[0]} ora per ora →</button>
        </div>
      </details>""")

    return f"""
  <section class="cml-sezione gg-sezione" id="cml-giorni">
    <h2 class="cml-titolo-sezione">📅 Prossimi giorni</h2>
    <div class="gg-elenco">{''.join(righe)}</div>
  </section>"""
