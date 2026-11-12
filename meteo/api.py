# =============================================================================
# Calabria Meteo Lab - Download delle previsioni (ICON-2I con riserva ICON-EU) e del mare, con nuovi tentativi.
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import math
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import streamlit as st

from meteo.config import API_MARE_URL, API_METEO_URL, FUSO_ORARIO, GIORNI_PREVISIONE, MODELLO_RISERVA, MODELLO_TERRESTRE, VARIABILI_CORRENTI, VARIABILI_GIORNALIERE, VARIABILI_MARINE_CORRENTI, VARIABILI_MARINE_GIORNALIERE, VARIABILI_MARINE_ORARIE, VARIABILI_ORARIE


def crea_sessione_http():
    """Sessione HTTP che riprova da sola su errori temporanei (429, 5xx)."""
    sessione = requests.Session()
    tentativi = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    sessione.mount("https://", HTTPAdapter(max_retries=tentativi))
    sessione.headers["User-Agent"] = "CalabriaMeteoLab/1.0"
    return sessione


HTTP = crea_sessione_http()


def _scarica_modello(parametri, modello):
    risposta = HTTP.get(
        API_METEO_URL,
        params={**parametri, "models": modello},
        timeout=25,
    )
    risposta.raise_for_status()
    return risposta.json()


def _completa_con_riserva(principale, riserva):
    """Riempie i valori mancanti di ICON-2I con ICON-EU. Restituisce gli orari sostituiti."""
    orari_sostituiti = set()

    for blocco in ("hourly", "daily"):
        dati_p = principale.get(blocco) or {}
        dati_r = riserva.get(blocco) or {}
        indice_r = {t: i for i, t in enumerate(dati_r.get("time", []))}

        for i, istante in enumerate(dati_p.get("time", [])):
            j = indice_r.get(istante)
            if j is None:
                continue
            for variabile, valori in dati_p.items():
                if variabile == "time" or variabile not in dati_r:
                    continue
                if valori[i] is None and dati_r[variabile][j] is not None:
                    valori[i] = dati_r[variabile][j]
                    if blocco == "hourly":
                        orari_sostituiti.add(istante)

    corrente_p = principale.get("current") or {}
    for variabile, valore in (riserva.get("current") or {}).items():
        if corrente_p.get(variabile) is None and valore is not None:
            corrente_p[variabile] = valore

    return sorted(orari_sostituiti)


@st.cache_data(ttl=1800, show_spinner=False)
def scarica_previsione_terrestre(latitudine, longitudine):
    parametri = {
        "latitude": latitudine,
        "longitude": longitudine,
        "timezone": "Europe/Rome",
        "forecast_days": GIORNI_PREVISIONE,
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "current": ",".join(VARIABILI_CORRENTI),
        "hourly": ",".join(VARIABILI_ORARIE),
        "daily": ",".join(VARIABILI_GIORNALIERE),
    }

    try:
        dati = _scarica_modello(parametri, MODELLO_TERRESTRE)
        dati["_fonte"] = "ICON-2I"
        dati["_scaricato_alle"] = datetime.now(FUSO_ORARIO).isoformat()
    except requests.RequestException:
        dati = None

    mancano_valori = dati is None or any(
        valore is None
        for variabile, valori in (dati.get("hourly") or {}).items()
        if variabile != "time"
        for valore in valori
    )

    if not mancano_valori:
        dati["_ore_riserva"] = []
        return dati

    try:
        riserva = _scarica_modello(parametri, MODELLO_RISERVA)
    except requests.RequestException as exc:
        if dati is not None:
            dati["_ore_riserva"] = []
            return dati  # meglio ICON-2I incompleto che nessun dato
        raise RuntimeError(
            "Previsioni non disponibili al momento: ICON-2I e ICON-EU non rispondono. "
            "Riprova tra qualche minuto."
        ) from exc

    if dati is None:
        riserva["_fonte"] = "ICON-EU (riserva: ICON-2I non disponibile)"
        riserva["_scaricato_alle"] = datetime.now(FUSO_ORARIO).isoformat()
        riserva["_ore_riserva"] = list((riserva.get("hourly") or {}).get("time", []))
        return riserva

    dati["_ore_riserva"] = _completa_con_riserva(dati, riserva)
    return dati


def distanza_haversine_km(lat1, lon1, lat2, lon2):
    raggio_terra_km = 6371.0088

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return raggio_terra_km * c


@st.cache_data(ttl=900, show_spinner=False)
def scarica_previsione_mare(latitudine, longitudine):
    parametri = {
        "latitude": latitudine,
        "longitude": longitudine,
        "timezone": "Europe/Rome",
        "forecast_days": GIORNI_PREVISIONE,
        "cell_selection": "sea",
        "current": ",".join(VARIABILI_MARINE_CORRENTI),
        "hourly": ",".join(VARIABILI_MARINE_ORARIE),
        "daily": ",".join(VARIABILI_MARINE_GIORNALIERE),
    }

    try:
        risposta = HTTP.get(
            API_MARE_URL,
            params=parametri,
            timeout=25,
        )

        risposta.raise_for_status()

        dati_mare = risposta.json()

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Errore nella ricezione della previsione marina: {exc}"
        ) from exc

    latitudine_mare = float(
        dati_mare.get("latitude", latitudine)
    )

    longitudine_mare = float(
        dati_mare.get("longitude", longitudine)
    )

    distanza_km = distanza_haversine_km(
        latitudine,
        longitudine,
        latitudine_mare,
        longitudine_mare,
    )

    return dati_mare, distanza_km
