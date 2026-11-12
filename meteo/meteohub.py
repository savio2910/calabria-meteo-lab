# =============================================================================
# Calabria Meteo Lab - Modelli MeteoHub (MOLOCH, WRF, BOLAM) per un punto
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# I file GRIB dei modelli sono troppo grandi per l'app: ogni mattina
# l'elaborazione automatica (elaborazione/meteohub_calabria.py, GitHub Actions)
# li riduce alla Calabria e pubblica nel ramo "dati" del repository:
#   meteohub/ultima.json  descrizione (griglia, modelli, corse, variabili)
#   meteohub/ultima.bin   per ogni punto della griglia, tutti i modelli e le ore
# Qui si scaricano solo i byte del punto richiesto (richiesta HTTP "Range").

import numpy as np
import pandas as pd
import requests
import streamlit as st

from meteo.api import HTTP_FACOLTATIVO as HTTP

URL_DATI = "https://raw.githubusercontent.com/savio2910/calabria-meteo-lab/dati/meteohub/"
ETA_MASSIMA_CORSA_ORE = 36        # corse più vecchie non vengono usate
FUSO = "Europe/Rome"


@st.cache_data(ttl=900, show_spinner=False)
def leggi_indice():
    try:
        risposta = HTTP.get(URL_DATI + "ultima.json", timeout=8)
        risposta.raise_for_status()
        return risposta.json()
    except (requests.RequestException, ValueError):
        return None


def indice_punto(indice, latitudine, longitudine):
    """Posizione del punto di griglia più vicino, o None se fuori dalla Calabria."""
    g = indice["griglia"]
    riga = int(round((latitudine - g["lat0"]) / g["passo"]))
    colonna = int(round((longitudine - g["lon0"]) / g["passo"]))
    if not (0 <= riga < g["ny"] and 0 <= colonna < g["nx"]):
        return None
    return riga * g["nx"] + colonna


def decodifica(indice, record, adesso_utc=None):
    """{nome modello: DataFrame orario (ora locale, colonne come Open-Meteo)} da un record di byte."""
    valori = np.frombuffer(record, dtype="<i2")
    versione = int(np.frombuffer(record[:4], dtype="<i4")[0])
    if versione != indice["versione"]:
        raise ValueError("file in aggiornamento")
    adesso_utc = pd.Timestamp.now(tz="UTC") if adesso_utc is None else pd.Timestamp(adesso_utc)
    modelli = {}
    for m in indice["modelli"]:
        corsa = pd.Timestamp(m["corsa"])
        if corsa.tzinfo is None:
            corsa = corsa.tz_localize("UTC")
        if adesso_utc - corsa > pd.Timedelta(hours=ETA_MASSIMA_CORSA_ORE):
            continue
        ore = m["ore"]
        tempi = (corsa + pd.to_timedelta(np.arange(ore), unit="h")).tz_convert(FUSO).tz_localize(None)
        inizio = m["inizio_byte"] // 2
        colonne = {}
        for k, variabile in enumerate(m["variabili"]):
            interi = valori[inizio + k * ore: inizio + (k + 1) * ore].astype(float)
            interi[interi == indice.get("mancante", -32768)] = np.nan
            scala, scarto = m["scale"][variabile]
            colonne[variabile] = interi / scala + scarto
        tabella = pd.DataFrame(colonne, index=tempi)
        if tabella.notna().any().any():
            modelli[m["nome"]] = tabella
    return modelli


@st.cache_data(ttl=900, show_spinner=False)
def scarica_modelli_meteohub(latitudine, longitudine):
    """{nome modello: DataFrame orario} per MOLOCH, WRF e BOLAM ({} se non disponibili)."""
    indice = leggi_indice()
    if not indice:
        return {}
    punto = indice_punto(indice, latitudine, longitudine)
    if punto is None:
        return {}
    for tentativo in range(2):
        dimensione = indice["byte_per_punto"]
        inizio = punto * dimensione
        try:
            risposta = HTTP.get(URL_DATI + "ultima.bin", timeout=8,
                                headers={"Range": f"bytes={inizio}-{inizio + dimensione - 1}"})
            risposta.raise_for_status()
            if risposta.status_code != 206 or len(risposta.content) != dimensione:
                return {}
            return decodifica(indice, risposta.content)
        except requests.RequestException:
            return {}
        except ValueError:
            # descrizione e dati di due elaborazioni diverse: si rilegge la descrizione
            leggi_indice.clear()
            indice = leggi_indice()
            if not indice or tentativo:
                return {}
    return {}
