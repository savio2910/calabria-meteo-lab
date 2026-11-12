# =============================================================================
# Calabria Meteo Lab - Mappa "La Calabria adesso"
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Sagoma disegnata della Calabria (confini ISTAT semplificati, risorse/
# mappa_calabria.json) con il tempo di adesso in 11 punti tra capoluoghi,
# montagne e coste, scaricati con una sola richiesta (ICON-2I) ogni 30 minuti.
# Toccando un punto si apre la sua previsione.

import html
import json
import math
from functools import lru_cache

import requests
import streamlit as st

from meteo.api import HTTP_FACOLTATIVO as HTTP
from meteo.config import API_METEO_URL, CARTELLA_APP, MODELLO_TERRESTRE
from meteo.formato import meteo, numero
from meteo.icone import icona_svg

# nome, lat, lon, collegamento (comune dell'elenco o None = per coordinate), posizione dell'etichetta
PUNTI = [
    ("Cosenza", 39.298, 16.254, "Cosenza (CS)", "s"),
    ("Sila", 39.340, 16.447, None, "a"),
    ("Pollino", 39.860, 16.070, None, "s"),
    ("Sibari", 39.748, 16.454, None, "d"),
    ("Crotone", 39.081, 17.127, "Crotone (KR)", "a"),
    ("Catanzaro", 38.905, 16.594, "Catanzaro (CZ)", "d"),
    ("Soverato", 38.688, 16.549, "Soverato (CZ)", "d"),
    ("Vibo", 38.676, 16.100, "Vibo Valentia (VV)", "d"),
    ("Tropea", 38.677, 15.898, "Tropea (VV)", "s"),
    ("Aspromonte", 38.168, 15.831, None, "d"),
    ("Reggio", 38.111, 15.647, "Reggio di Calabria (RC)", "b"),
]
LARGHEZZA, ALTEZZA = 58, 34          # etichetta (unità del disegno)
VICINO_KM = 8.0


@lru_cache(maxsize=1)
def contorni():
    return json.loads((CARTELLA_APP / "risorse" / "mappa_calabria.json").read_text(encoding="utf-8"))


def proietta(latitudine, longitudine, geo=None):
    geo = geo or contorni()
    return ((longitudine - geo["lon0"]) * geo["coseno"] * geo["k"], (geo["lat1"] - latitudine) * geo["k"])


@st.cache_data(ttl=1800, show_spinner=False)
def scarica_punti():
    """[(temperatura, weather_code, is_day)] per i PUNTI (None dove non disponibile)."""
    try:
        risposta = HTTP.get(API_METEO_URL, params={
            "latitude": ",".join(f"{p[1]:.3f}" for p in PUNTI),
            "longitude": ",".join(f"{p[2]:.3f}" for p in PUNTI),
            "current": "temperature_2m,weather_code,is_day",
            "models": MODELLO_TERRESTRE, "timezone": "Europe/Rome",
        }, timeout=10)
        risposta.raise_for_status()
        dati = risposta.json()
    except (requests.RequestException, ValueError):
        return [None] * len(PUNTI)
    dati = dati if isinstance(dati, list) else [dati]
    risultato = []
    for punto in dati[:len(PUNTI)]:
        c = punto.get("current") or {}
        risultato.append((c.get("temperature_2m"), c.get("weather_code"), c.get("is_day", 1)))
    return risultato + [None] * (len(PUNTI) - len(risultato))


def _distanza_km(a, b):
    return math.hypot((a[0] - b[0]) * 111.0, (a[1] - b[1]) * 111.0 * math.cos(math.radians(a[0])))


def _etichetta(x, y, posizione, nome, valori, collegamento, lat, lon, scelta=False):
    dx, dy = {"d": (7, -ALTEZZA / 2), "s": (-LARGHEZZA - 7, -ALTEZZA / 2),
              "b": (-LARGHEZZA / 2, 7), "a": (-LARGHEZZA / 2, -ALTEZZA - 7)}[posizione]
    temperatura, codice, giorno = valori or (None, None, 1)
    descrizione = meteo(codice)[1] if codice is not None else "dati non disponibili"
    attributi = (f'data-luogo="{html.escape(collegamento, quote=True)}"' if collegamento
                 else f'data-lat="{lat:.3f}" data-lon="{lon:.3f}"')
    testo = f"{nome}: {descrizione}, {numero(temperatura, 0, ' gradi')}"
    icona = icona_svg(codice, notte=not giorno).replace('<svg class="cml-ico', f'<svg x="{x + dx + 4:.1f}" y="{y + dy + 13:.1f}" width="19" height="19" class="cml-ico', 1)
    return f"""
    <a class="mp-punto{' mp-scelto' if scelta else ''}" href="#" {attributi} aria-label="{html.escape(testo, quote=True)}">
      <line x1="{x:.1f}" y1="{y:.1f}" x2="{x + dx + (LARGHEZZA if posizione == 's' else 0 if posizione == 'd' else LARGHEZZA / 2):.1f}" y2="{y + dy + (ALTEZZA / 2 if posizione in 'sd' else 0 if posizione == 'b' else ALTEZZA):.1f}" class="mp-filo"/>
      <circle cx="{x:.1f}" cy="{y:.1f}" r="3" class="mp-pallino"/>
      <rect x="{x + dx:.1f}" y="{y + dy:.1f}" width="{LARGHEZZA}" height="{ALTEZZA}" rx="9" class="mp-bolla"/>
      <text x="{x + dx + LARGHEZZA / 2:.1f}" y="{y + dy + 10.5:.1f}" text-anchor="middle" class="mp-nome">{html.escape(nome)}</text>
      {icona}
      <text x="{x + dx + 25:.1f}" y="{y + dy + 27:.1f}" class="mp-temp">{numero(temperatura, 0, '°')}</text>
    </a>"""


def mappa_html(luogo, latitudine, longitudine, corrente=None):
    """Sezione con la mappa (vuota se la sagoma non è disponibile)."""
    try:
        geo = contorni()
    except (OSError, ValueError):
        return ""
    valori = scarica_punti()
    regioni = "".join(
        f'<path d="{percorso}" class="{"mp-calabria" if nome == "Calabria" else "mp-vicina"}"/>'
        for nome, percorso in geo["regioni"].items()
    )
    vicino = None
    for i, p in enumerate(PUNTI):
        if _distanza_km((latitudine, longitudine), (p[1], p[2])) <= VICINO_KM:
            vicino = i
            break

    etichette = []
    for i, (nome, lat, lon, collegamento, posizione) in enumerate(PUNTI):
        x, y = proietta(lat, lon, geo)
        etichette.append(_etichetta(x, y, posizione, nome, valori[i], collegamento, lat, lon, scelta=i == vicino))

    qui = ""
    w, h = geo["viewbox"][2], geo["viewbox"][3]
    x, y = proietta(latitudine, longitudine, geo)
    if vicino is None and 0 <= x <= w and 0 <= y <= h:
        corrente = corrente or {}
        posizione = "s" if x > w * 0.55 else "d"
        qui = _etichetta(x, y, posizione, str(luogo).split(" (")[0][:11], (corrente.get("temperature_2m"),
                         corrente.get("weather_code"), corrente.get("is_day", 1)), None, latitudine, longitudine, scelta=True)

    elenco = "".join(
        f'<li><a href="#" class="mp-punto-elenco" '
        f'{f"data-luogo={chr(34)}{html.escape(p[3], quote=True)}{chr(34)}" if p[3] else f"data-lat={chr(34)}{p[1]:.3f}{chr(34)} data-lon={chr(34)}{p[2]:.3f}{chr(34)}"}>'
        f'<span>{html.escape(p[0])}</span>{icona_svg(v[1] if v else None, notte=bool(v) and not v[2])}'
        f'<b>{numero(v[0] if v else None, 0, "°")}</b></a></li>'
        for p, v in zip(PUNTI, valori)
    )
    return f"""
  <section class="cml-sezione mp-sezione" id="cml-mappa">
    <h2 class="cml-titolo-sezione">🗺️ La Calabria adesso</h2>
    <div class="mp-corpo">
      <svg class="mp-svg" viewBox="-8 -4 {w + 16:.0f} {h + 8:.0f}" role="group" aria-label="Mappa della Calabria con il tempo di adesso">
        <rect x="-8" y="-4" width="{w + 16:.0f}" height="{h + 8:.0f}" class="mp-mare"/>
        {regioni}
        {''.join(etichette)}
        {qui}
      </svg>
      <ul class="mp-elenco">{elenco}</ul>
    </div>
    <p class="mp-nota">Tocca un punto per aprirne la previsione · modello ICON-2I</p>
  </section>"""
