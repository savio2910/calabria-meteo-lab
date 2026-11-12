# =============================================================================
# Calabria Meteo Lab - Quota neve, potenziale temporalesco, polveri e UV
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# - Quota neve: quota dello zero termico meno 300 m (regola pratica dei
#   bollettini italiani), mostrata solo con precipitazioni e sotto i 2000 m.
# - Potenziale temporalesco: CAPE (energia disponibile per i temporali).
# - Polveri sahariane e indice UV: modello europeo CAMS (Air Quality API).
# Dati facoltativi: se non disponibili la pagina funziona come prima.

import pandas as pd
import requests
import streamlit as st

from meteo.api import HTTP_FACOLTATIVO as HTTP
from meteo.config import API_METEO_URL

API_QUALITA_ARIA_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

SOGLIE_INDICATORI = {
    "neve_sotto_zero_termico_m": 300,
    "neve_quota_massima_m": 2000,       # sopra questa quota la neve non viene segnalata
    "pioggia_mm": 0.2,                  # ora con precipitazione
    "cape": (300, 1000, 2500),          # J/kg: moderato, alto, molto alto
    "polveri": (50, 150),               # µg/m³ al suolo: presenti, intense
    "uv": (3, 6, 8, 11),                # scala OMS: moderato, alto, molto alto, estremo
}

LIVELLI_CAPE = ["basso", "moderato", "alto", "molto alto"]
LIVELLI_UV = ["basso", "moderato", "alto", "molto alto", "estremo"]


def livello(valore, soglie):
    """Indice della fascia: 0 sotto la prima soglia, 1 sopra la prima, ecc."""
    if valore is None or pd.isna(valore):
        return None
    return sum(valore >= s for s in soglie)


def quota_neve(zero_termico_m):
    if zero_termico_m is None or pd.isna(zero_termico_m):
        return None
    return max(0, int(round((zero_termico_m - SOGLIE_INDICATORI["neve_sotto_zero_termico_m"]) / 100.0)) * 100)


def _orario(dati, variabili):
    orario = (dati or {}).get("hourly") or {}
    if not orario.get("time"):
        return pd.DataFrame()
    tabella = pd.DataFrame({v: orario.get(v) for v in variabili if v in orario}, index=pd.to_datetime(orario["time"]))
    return tabella.apply(pd.to_numeric, errors="coerce")


@st.cache_data(ttl=1800, show_spinner=False)
def scarica_indicatori(latitudine, longitudine):
    """DataFrame orario con le colonne disponibili tra zero_termico, cape, polveri, uv."""
    parti = []
    try:
        # senza "models": Open-Meteo sceglie per ogni variabile il modello che la fornisce
        risposta = HTTP.get(API_METEO_URL, params={
            "latitude": latitudine, "longitude": longitudine, "timezone": "Europe/Rome",
            "forecast_days": 3, "hourly": "freezing_level_height,cape",
        }, timeout=10)
        risposta.raise_for_status()
        parti.append(_orario(risposta.json(), ["freezing_level_height", "cape"]))
    except (requests.RequestException, ValueError):
        pass
    try:
        risposta = HTTP.get(API_QUALITA_ARIA_URL, params={
            "latitude": latitudine, "longitude": longitudine,
            "timezone": "Europe/Rome", "forecast_days": 3, "hourly": "dust,uv_index",
        }, timeout=10)
        risposta.raise_for_status()
        parti.append(_orario(risposta.json(), ["dust", "uv_index"]))
    except (requests.RequestException, ValueError):
        pass
    parti = [p for p in parti if not p.empty]
    if not parti:
        return None
    tabella = pd.concat(parti, axis=1)
    return tabella.rename(columns={"freezing_level_height": "zero_termico", "dust": "polveri", "uv_index": "uv"})


def valore_ora(indicatori, istante, colonna):
    if indicatori is None or colonna not in indicatori.columns:
        return None
    istante = pd.Timestamp(istante)
    if istante not in indicatori.index:
        return None
    valore = indicatori.at[istante, colonna]
    return None if pd.isna(valore) else float(valore)


def neve_nelle_ore(indicatori, ore):
    """Quota neve più bassa tra le ore con precipitazione (None se oltre 2000 m o senza pioggia)."""
    quote = []
    for _, riga in ore.iterrows():
        pioggia = pd.to_numeric(riga.get("precipitation"), errors="coerce")
        if pd.isna(pioggia) or pioggia < SOGLIE_INDICATORI["pioggia_mm"]:
            continue
        quota = quota_neve(valore_ora(indicatori, riga["time"], "zero_termico"))
        if quota is not None:
            quote.append(quota)
    if not quote or min(quote) > SOGLIE_INDICATORI["neve_quota_massima_m"]:
        return None
    return min(quote)


def riassunto_giorno(indicatori, ore_giorno):
    """Valori di un giorno: quota neve, livello del potenziale temporalesco, UV massimo, polveri massime."""
    if indicatori is None or ore_giorno.empty:
        return {}
    tratto = indicatori.loc[indicatori.index.isin(pd.to_datetime(ore_giorno["time"]))]
    risultato = {"neve": neve_nelle_ore(indicatori, ore_giorno)}
    if "cape" in tratto and tratto["cape"].notna().any():
        risultato["cape"] = livello(tratto["cape"].max(), SOGLIE_INDICATORI["cape"])
    if "uv" in tratto and tratto["uv"].notna().any():
        risultato["uv"] = float(tratto["uv"].max())
    if "polveri" in tratto and tratto["polveri"].notna().any():
        risultato["polveri"] = float(tratto["polveri"].max())
    return risultato


def testi_indicatori(riassunto):
    """Brevi testi da mostrare (solo quelli che contano)."""
    testi = []
    if riassunto.get("neve") is not None:
        testi.append(f"❄️ Neve oltre i {riassunto['neve']:,} m".replace(",", "."))
    if riassunto.get("cape"):
        testi.append(f"⛈️ Potenziale temporalesco {LIVELLI_CAPE[riassunto['cape']]}")
    if riassunto.get("uv") is not None and livello(riassunto["uv"], SOGLIE_INDICATORI["uv"]):
        uv = riassunto["uv"]   # mostrato da "moderato" in su
        testi.append(f"☀️ UV fino a {uv:.0f} ({LIVELLI_UV[livello(uv, SOGLIE_INDICATORI['uv'])]})")
    polveri = livello(riassunto.get("polveri"), SOGLIE_INDICATORI["polveri"])
    if polveri:
        testi.append("🏜️ Polveri sahariane " + ("intense" if polveri == 2 else "presenti"))
    return testi
