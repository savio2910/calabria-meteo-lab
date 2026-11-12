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
from meteo.config import (
    ALIASES,
    API_GEOCODING_URL,
    COMUNI_RAPIDI,
    FILE_COMUNI_CALABRIA,
    FILE_COMUNI_COSTIERI,
)


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


def geocodifica_open_meteo(nome, provincia=None):
    """Cerca la località con il geocoding di Open-Meteo, solo in Calabria.

    Tra i risultati calabresi preferisce, nell'ordine: nome identico nella
    provincia indicata, nome identico, primo risultato.
    """
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

    calabresi = [
        r for r in (risposta.json().get("results", []) or [])
        if str(r.get("admin1", "")).casefold() == "calabria"
    ]
    if not calabresi:
        return None

    cercato = normalizza_comune(nome)
    provincia_norm = normalizza_comune(provincia) if provincia else ""

    def punteggio(risultato):
        stesso_nome = normalizza_comune(risultato.get("name")) == cercato
        stessa_provincia = bool(provincia_norm) and provincia_norm in normalizza_comune(
            risultato.get("admin2", "")
        )
        return (stesso_nome and stessa_provincia, stesso_nome)

    migliore = max(calabresi, key=punteggio)  # a parità vince l'ordine di Open-Meteo
    return (
        migliore["name"],
        float(migliore["latitude"]),
        float(migliore["longitude"]),
        migliore.get("admin3") or migliore["name"],
    )


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
def geocodifica_calabria(nome, provincia=None):
    try:
        trovato = geocodifica_open_meteo(nome, provincia)
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


@st.cache_data(show_spinner=False)
def carica_elenco_comuni():
    """Comuni calabresi (fonte ISTAT) per i suggerimenti della ricerca.

    Restituisce un dizionario ordinato {etichetta: (comune, provincia)},
    con etichette come "Cosenza (CS)".
    """
    dataframe = pd.read_csv(FILE_COMUNI_CALABRIA, dtype=str)
    return {
        f"{riga.comune} ({riga.sigla})": (riga.comune, riga.provincia)
        for riga in dataframe.itertuples(index=False)
    }


def risolvi_comune(comune, provincia=None):
    """Coordinate di un comune scelto dal menu (prima l'elenco rapido, poi il geocoding)."""
    nome_rapido = ALIASES.get(comune.casefold(), comune)
    for rapido, (latitudine, longitudine) in COMUNI_RAPIDI.items():
        if normalizza_comune(rapido) == normalizza_comune(nome_rapido):
            return rapido, latitudine, longitudine, comune

    _, latitudine, longitudine, _ = geocodifica_calabria(comune, provincia)
    return comune, latitudine, longitudine, comune


def in_calabria(latitudine, longitudine):
    """Controllo approssimato: rettangolo che contiene la Calabria."""
    return 37.75 <= latitudine <= 40.15 and 15.55 <= longitudine <= 17.25


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def localita_da_posizione(latitudine, longitudine):
    """Nome e comune per le coordinate dell'utente (geocoding inverso OpenStreetMap).

    Se il servizio non risponde restituisce un nome generico: la previsione
    funziona comunque con le coordinate.
    """
    if not in_calabria(latitudine, longitudine):
        raise ValueError(
            "La tua posizione non risulta in Calabria: "
            "l'applicazione funziona solo per località calabresi."
        )

    try:
        risposta = Nominatim(user_agent="calabria_meteo_lab_v23", timeout=15).reverse(
            (latitudine, longitudine), zoom=14, addressdetails=True, language="it"
        )
    except (GeocoderServiceError, GeocoderTimedOut):
        risposta = None

    indirizzo = risposta.raw.get("address", {}) if risposta is not None else {}
    comune = (
        indirizzo.get("municipality")
        or indirizzo.get("city")
        or indirizzo.get("town")
        or indirizzo.get("village")
    )
    nome = (
        indirizzo.get("village")
        or indirizzo.get("town")
        or indirizzo.get("city")
        or comune
        or "La tua posizione"
    )
    return nome, comune


def trova_comune_scritto(testo, elenco_comuni):
    """Riconosce un comune scritto a mano (es. "Trop" + Invio -> "Tropea (VV)").

    Restituisce l'etichetta del menu se il testo corrisponde a un comune per
    nome esatto o, in mancanza, se è l'inizio del nome di un solo comune.
    Altrimenti None: il testo viene cercato come frazione o località.
    """
    def chiave(nome):
        # ignora maiuscole, accenti, trattini e apostrofi ("all'Ionio" = "all ionio")
        return " ".join(normalizza_comune(nome).replace("'", " ").split())

    cercato = chiave(testo)
    if not cercato:
        return None

    esatti = [e for e, (comune, _) in elenco_comuni.items() if chiave(comune) == cercato]
    if len(esatti) == 1:
        return esatti[0]
    if esatti:
        return None  # stesso nome in più province: decide il geocoding

    iniziali = [e for e, (comune, _) in elenco_comuni.items() if chiave(comune).startswith(cercato)]
    return iniziali[0] if len(iniziali) == 1 else None
