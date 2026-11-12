# =============================================================================
# Calabria Meteo Lab - Taratura delle previsioni con le stazioni
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Le correzioni sono calcolate ogni giorno da elaborazione/allena_correzioni.py
# confrontando le previsioni passate con le stazioni (Protezione Civile e
# sinottiche) e pubblicate nel ramo "dati" (correzioni/correzioni.json).
#
# Per una località si usano le stazioni entro 25 km e a quota simile (al
# massimo 300 m di differenza), pesate per distanza e dislivello. Ogni modello
# viene corretto PRIMA di essere combinato: temperatura (per scadenza e fascia
# oraria), pioggia, vento medio e raffiche (fattori). Se nessuna stazione è
# adatta, la previsione non viene toccata.

import math

import numpy as np
import pandas as pd
import requests
import streamlit as st

from meteo.api import HTTP_FACOLTATIVO as HTTP

URL_CORREZIONI = "https://raw.githubusercontent.com/savio2910/calabria-meteo-lab/dati/correzioni/correzioni.json"
RAGGIO_KM = 25.0
MAX_DISLIVELLO_M = 300.0
MAX_STAZIONI = 4
SCALA_DISTANZA_KM = 10.0
SCALA_DISLIVELLO_M = 150.0
FUSO = "Europe/Rome"
CAMPIONI_PESI = 500          # ore di confronto a cui i pesi appresi contano quanto quelli di partenza

# variabile (come Open-Meteo) -> (correzione, tipo)
VARIABILI = {
    "temperature_2m": ("temperatura", "somma"),
    "apparent_temperature": ("temperatura", "somma"),
    "precipitation": ("pioggia", "fattore"),
    "wind_speed_10m": ("vento", "fattore"),
    "wind_gusts_10m": ("raffica", "fattore"),
}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def leggi_correzioni():
    try:
        risposta = HTTP.get(URL_CORREZIONI, timeout=10)
        risposta.raise_for_status()
        return risposta.json()
    except (requests.RequestException, ValueError):
        return None


def distanza_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def stazioni_vicine(correzioni, latitudine, longitudine, quota=None):
    """[(stazione, peso, distanza_km, dislivello_m)] delle stazioni adatte, le più vicine prima."""
    if not correzioni:
        return []
    candidate = []
    for s in correzioni.get("stazioni", []):
        d = distanza_km(latitudine, longitudine, s["lat"], s["lon"])
        if d > RAGGIO_KM:
            continue
        dislivello = None
        if quota is not None and s.get("quota") is not None:
            dislivello = abs(float(s["quota"]) - float(quota))
            if dislivello > MAX_DISLIVELLO_M:
                continue
        peso = math.exp(-d / SCALA_DISTANZA_KM) * math.exp(-(dislivello or 0.0) / SCALA_DISLIVELLO_M)
        candidate.append((s, peso, d, dislivello))
    candidate.sort(key=lambda c: -c[1])
    return candidate[:MAX_STAZIONI]


def _scadenze_e_fasce(tempi, adesso):
    """Giorno di scadenza (0/1/2) e fascia di 3 ore UTC per ogni istante locale."""
    tempi = pd.DatetimeIndex(pd.to_datetime(tempi))
    giorni = np.clip(((tempi - pd.Timestamp(adesso).floor("h")) / pd.Timedelta(hours=24)).astype(float), 0, 2)
    giorni = np.floor(np.nan_to_num(giorni, nan=0.0)).astype(int)
    utc = tempi.tz_localize(FUSO, ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
    ore_utc = np.where(utc.isna(), (tempi.hour - 1) % 24, utc.hour)
    return giorni, (ore_utc // 3).astype(int)


def correzione_oraria(vicine, modello, correzione, tempi, adesso):
    """Array orario della correzione (°C da sommare o fattore), o None se nessuna stazione la fornisce."""
    giorni, fasce = _scadenze_e_fasce(tempi, adesso)
    somma, pesi = np.zeros(len(giorni)), 0.0
    for stazione, peso, _, _ in vicine:
        if correzione not in stazione.get("misure", []):
            continue          # la stazione non misura questa variabile
        valori = (stazione.get(correzione) or {}).get(modello)
        if correzione == "temperatura":
            if valori:
                tabella = np.array([valori.get(str(g), [0.0] * 8) for g in range(3)], dtype=float)
                somma += peso * tabella[giorni, fasce]
        else:
            somma += peso * (valori if valori is not None else 1.0)
        pesi += peso
    if pesi == 0:
        return None
    return somma / pesi


def _corregge_serie(valori, correzione, tipo):
    valori = pd.to_numeric(pd.Series(valori), errors="coerce").to_numpy(dtype=float)
    return valori + correzione if tipo == "somma" else valori * correzione


def applica_taratura(dati_terrestri, modelli, latitudine, longitudine, adesso, correzioni=None):
    """Corregge ICON-2I (nei dati) e gli altri modelli (restituiti corretti). Restituisce (modelli, info)."""
    correzioni = leggi_correzioni() if correzioni is None else correzioni
    vicine = stazioni_vicine(correzioni, latitudine, longitudine, dati_terrestri.get("elevation"))
    if not vicine:
        return modelli, None

    applicate = set()
    orario = dati_terrestri["hourly"]
    tempi = pd.to_datetime(orario["time"])
    for variabile, (correzione, tipo) in VARIABILI.items():
        if variabile not in orario:
            continue
        valore = correzione_oraria(vicine, "ICON-2I", correzione, tempi, adesso)
        if valore is None:
            continue
        nuovi = _corregge_serie(orario[variabile], valore, tipo)
        orario[variabile] = [None if np.isnan(x) else round(float(x), 2) for x in nuovi]
        applicate.add(correzione)
        corrente = dati_terrestri.get("current") or {}
        if corrente.get(variabile) is not None and corrente.get("time"):
            indice = int(np.argmin(np.abs((tempi - pd.Timestamp(corrente["time"]).floor("h")) / pd.Timedelta(hours=1))))
            corrente[variabile] = round(float(_corregge_serie([corrente[variabile]], valore[indice], tipo)[0]), 1)

    corretti = {}
    for nome, tabella in modelli.items():
        tabella = tabella.copy()
        for variabile, (correzione, tipo) in VARIABILI.items():
            if variabile not in tabella:
                continue
            valore = correzione_oraria(vicine, nome, correzione, tabella.index, adesso)
            if valore is not None:
                tabella[variabile] = _corregge_serie(tabella[variabile].to_numpy(), valore, tipo)
                applicate.add(correzione)
        corretti[nome] = tabella

    info = {
        "stazioni": [{"nome": s["nome"], "distanza_km": round(d, 1), "dislivello_m": None if z is None else round(z)}
                     for s, _, d, z in vicine],
        "variabili": sorted(applicate),
        "aggiornata": correzioni.get("creato"),
    }
    return corretti, info


def pesi_appresi(correzioni=None):
    """Pesi dei modelli appresi dalle stazioni: {gruppo: {giorno: {modello: peso}}, con la fiducia (0-1)}."""
    correzioni = leggi_correzioni() if correzioni is None else correzioni
    if not correzioni or not correzioni.get("pesi"):
        return None
    risultato = {}
    for gruppo, per_giorno in correzioni["pesi"].items():
        risultato[gruppo] = {}
        for giorno, pesi in per_giorno.items():
            n = (correzioni.get("campioni_pesi") or {}).get(gruppo, {}).get(giorno, 0)
            risultato[gruppo][int(giorno)] = {"pesi": pesi, "fiducia": n / (n + CAMPIONI_PESI)}
    return risultato
