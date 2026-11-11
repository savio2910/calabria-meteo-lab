# =============================================================================
# Calabria Meteo Lab - Ricerca delle località calabresi e comuni costieri.
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import unicodedata

import pandas as pd
import requests
import streamlit as st
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim

from meteo.api import HTTP
from meteo.config import ALIASES, API_GEOCODING_URL, COMUNI_RAPIDI, FILE_COMUNI_COSTIERI


def normalizza_comune(nome):
    if nome is None:
        return ""

    testo = str(nome).strip().casefold()

    testo = testo.replace("’", "'")
    testo = testo.replace("`", "'")
    testo = testo.replace("-", " ")
    testo = testo.replace("_", " ")

    testo = unicodedata.normalize("NFKD", testo)

    testo = "".join(
        carattere
        for carattere in testo
        if not unicodedata.combining(carattere)
    )

    testo = " ".join(testo.split())

    alias = {
        "reggio di calabria": "reggio calabria",
        "corigliano rossano": "corigliano rossano",
        "isola capo rizzuto": "isola di capo rizzuto",
        "sant ilario dello ionio": "sant ilario dello ionio",
    }

    return alias.get(testo, testo)


def geocodifica_open_meteo(nome):
    risposta = HTTP.get(
        API_GEOCODING_URL,
        params={
            "name": nome,
            "count": 20,
            "language": "it",
            "countryCode": "IT",
            "format": "json",
        },
        timeout=15,
    )
    risposta.raise_for_status()

    for risultato in risposta.json().get("results", []) or []:
        if str(risultato.get("admin1", "")).casefold() == "calabria":
            return (
                risultato["name"],
                float(risultato["latitude"]),
                float(risultato["longitude"]),
                risultato.get("admin3") or risultato["name"],
            )
    return None


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def carica_comuni_costieri():
    if not FILE_COMUNI_COSTIERI.exists():
        raise FileNotFoundError(
            "Manca il file comuni_costieri_calabria.csv. "
            "Inseriscilo nella stessa cartella di app.py."
        )

    dataframe = pd.read_csv(FILE_COMUNI_COSTIERI)

    if "comune" not in dataframe.columns:
        raise ValueError(
            "Il file comuni_costieri_calabria.csv deve contenere "
            "una colonna chiamata 'comune'."
        )

    elenco = (
        dataframe["comune"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    return {
        normalizza_comune(comune)
        for comune in elenco
        if comune
    }


def comune_e_costiero(comune_amministrativo, elenco_costieri):
    return (
        normalizza_comune(comune_amministrativo)
        in elenco_costieri
    )


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def geocodifica_calabria(nome):
    try:
        trovato = geocodifica_open_meteo(nome)
    except requests.RequestException:
        trovato = None

    if trovato:
        return trovato
    
    try:
        geocoder = Nominatim(
            user_agent="calabria_meteo_lab_v23",
            timeout=30,
        )

        risposta = geocoder.geocode(
            f"{nome}, Calabria, Italia",
            exactly_one=True,
            addressdetails=True,
            timeout=15,
        )

    except (GeocoderServiceError, GeocoderTimedOut) as exc:
        raise RuntimeError(
            "Servizio di geolocalizzazione temporaneamente non disponibile. "
            "Riprova tra qualche minuto."
        ) from exc

    if risposta is None:
        raise ValueError(
            f"Località «{nome}» non trovata. "
            "Controlla il nome e riprova."
        )

    indirizzo = risposta.raw.get("address", {})

    regione = str(
        indirizzo.get("state", "")
        or indirizzo.get("region", "")
    ).casefold()

    latitudine = float(risposta.latitude)
    longitudine = float(risposta.longitude)

    in_calabria_geometrica = (
        37.75 <= latitudine <= 40.15
        and 15.60 <= longitudine <= 17.25
    )

    is_calabria = (
        "calabria" in regione
        or in_calabria_geometrica
    )

    if not is_calabria:
        raise ValueError(
            f"❌ «{nome}» non è in Calabria. "
            "L'applicazione funziona solo per località calabresi."
        )

    nome_risolto = (
        indirizzo.get("city")
        or indirizzo.get("town")
        or indirizzo.get("village")
        or indirizzo.get("municipality")
        or nome.title()
    )

    comune_amministrativo = (
        indirizzo.get("municipality")
        or indirizzo.get("city")
        or indirizzo.get("town")
        or indirizzo.get("village")
        or nome_risolto
    )

    return (
        nome_risolto,
        latitudine,
        longitudine,
        comune_amministrativo,
    )


def risolvi_localita(testo):
    nome = str(testo).strip()

    if not nome:
        raise ValueError(
            "Inserisci il nome di un comune, frazione o località della Calabria."
        )

    indice = {
        comune.casefold(): comune
        for comune in COMUNI_RAPIDI
    }

    nome_normalizzato = ALIASES.get(
        nome.casefold(),
        nome,
    )

    chiave = nome_normalizzato.casefold()

    if chiave in indice:
        comune = indice[chiave]
        latitudine, longitudine = COMUNI_RAPIDI[comune]

        return (
            comune,
            latitudine,
            longitudine,
            comune,
        )

    return geocodifica_calabria(nome_normalizzato)
