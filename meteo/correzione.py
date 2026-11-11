# =============================================================================
# Calabria Meteo Lab - Osservazioni Meteostat e correzione della previsione.
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

from datetime import datetime

import pandas as pd
import streamlit as st

from meteo.config import FUSO_ORARIO, MAX_CORREZIONE_TEMP_C, MAX_DISLIVELLO_STAZIONE_M, MAX_DISTANZA_STAZIONE_KM

try:
    from meteostat import Stations, Hourly
    METEOSTAT_DISPONIBILE = True
except ImportError:
    METEOSTAT_DISPONIBILE = False


@st.cache_data(ttl=900, show_spinner=False)
def scarica_osservazioni_meteostat(latitudine, longitudine, quota_localita=None):
    """Scarica le osservazioni delle ultime 6 ore dalla stazione Meteostat più vicina."""
    if not METEOSTAT_DISPONIBILE:
        return None, None, None

    try:
        stazioni = Stations().nearby(latitudine, longitudine)
        elenco = stazioni.fetch(10)

        if elenco.empty:
            return None, None, None

        fine = pd.Timestamp.utcnow().tz_localize(None).floor("h")
        inizio = fine - pd.Timedelta(hours=6)

        for _, stazione in elenco.iterrows():
            # Scarta stazioni lontane o a quota molto diversa (es. Monte Scuro
            # a 1700 m per una località di valle): microclima non rappresentativo.
            distanza_km = float(stazione.get("distance", 0) or 0) / 1000
            if distanza_km > MAX_DISTANZA_STAZIONE_KM:
                continue

            quota_stazione = stazione.get("elevation")
            if (
                quota_localita is not None
                and quota_stazione is not None
                and pd.notna(quota_stazione)
                and abs(float(quota_stazione) - float(quota_localita)) > MAX_DISLIVELLO_STAZIONE_M
            ):
                continue

            try:
                dati = Hourly(
                    stazione.name,
                    start=inizio.to_pydatetime(),
                    end=fine.to_pydatetime(),
                    model=False,  # solo misure reali, niente dati di modello
                ).fetch()

                if dati.empty:
                    continue

                dati = dati.dropna(subset=["temp"], how="all")

                if dati.empty:
                    continue

                # Meteostat usa l'ora UTC, ICON-2I l'ora locale (Europe/Rome)
                dati.index = (
                    pd.to_datetime(dati.index)
                    .tz_localize("UTC")
                    .tz_convert(FUSO_ORARIO)
                    .tz_localize(None)
                )

                ultima = dati.index.max()
                adesso_locale = pd.Timestamp(datetime.now(FUSO_ORARIO).replace(tzinfo=None))
                if adesso_locale - ultima > pd.Timedelta(hours=3):
                    continue

                return dati, stazione, ultima

            except Exception:
                continue

        return None, None, None

    except Exception:
        return None, None, None


def calcola_correzione_osservativa(dati_terrestri, osservazioni, stazione, ultima_osservazione):
    """Calcola il bias locale osservato nelle ultime 3 ore e lo applica alle prossime 6 ore."""
    if osservazioni is None or osservazioni.empty or stazione is None:
        return None

    try:
        ore_modello = pd.DataFrame(dati_terrestri["hourly"])
        ore_modello["time"] = pd.to_datetime(ore_modello["time"])
        ore_modello = ore_modello.set_index("time")

        limite = osservazioni.index.max() - pd.Timedelta(hours=3)
        ultime_3 = osservazioni.loc[osservazioni.index > limite]
        if ultime_3.empty:
            return None

        bias_temp = []
        bias_umidita = []
        rapporto_vento = []

        for istante, riga_oss in ultime_3.iterrows():
            ora_modello = istante.floor("h")
            if ora_modello not in ore_modello.index:
                continue

            riga_modello = ore_modello.loc[ora_modello]

            if pd.notna(riga_oss.get("temp")) and pd.notna(riga_modello.get("temperature_2m")):
                bias_temp.append(float(riga_oss["temp"]) - float(riga_modello["temperature_2m"]))

            if pd.notna(riga_oss.get("rhum")) and pd.notna(riga_modello.get("relative_humidity_2m")):
                bias_umidita.append(float(riga_oss["rhum"]) - float(riga_modello["relative_humidity_2m"]))

            if (
                pd.notna(riga_oss.get("wspd"))
                and pd.notna(riga_modello.get("wind_speed_10m"))
                and float(riga_modello["wind_speed_10m"]) > 1
            ):
                rapporto_vento.append(float(riga_oss["wspd"]) / float(riga_modello["wind_speed_10m"]))

        if not bias_temp and not bias_umidita and not rapporto_vento:
            return None

        bias_temp = float(pd.Series(bias_temp).mean()) if bias_temp else 0.0
        bias_umidita = float(pd.Series(bias_umidita).mean()) if bias_umidita else 0.0
        rapporto_vento = float(pd.Series(rapporto_vento).mean()) if rapporto_vento else 1.0
        rapporto_vento = max(0.5, min(2.0, rapporto_vento))

        # Una differenza così grande indica una stazione non rappresentativa
        if abs(bias_temp) > MAX_CORREZIONE_TEMP_C:
            return None

        ore = pd.DataFrame(dati_terrestri["hourly"])
        ore["time"] = pd.to_datetime(ore["time"])

        adesso = pd.Timestamp(datetime.now(FUSO_ORARIO).replace(tzinfo=None)).floor("h")
        prossime = ore.loc[
            (ore["time"] >= adesso)
            & (ore["time"] < adesso + pd.Timedelta(hours=6))
        ].copy()

        for indice, riga in prossime.iterrows():
            ore_trascorse = int((riga["time"] - adesso).total_seconds() // 3600)
            peso = max(0.0, 1.0 - ore_trascorse / 6.0)

            if pd.notna(ore.at[indice, "temperature_2m"]):
                ore.at[indice, "temperature_2m"] += bias_temp * peso

            if pd.notna(ore.at[indice, "relative_humidity_2m"]):
                valore = ore.at[indice, "relative_humidity_2m"] + bias_umidita * peso
                ore.at[indice, "relative_humidity_2m"] = max(0.0, min(100.0, valore))

            if pd.notna(ore.at[indice, "wind_speed_10m"]):
                ore.at[indice, "wind_speed_10m"] *= (1 + (rapporto_vento - 1) * peso)

            if pd.notna(ore.at[indice, "wind_gusts_10m"]):
                ore.at[indice, "wind_gusts_10m"] *= (1 + (rapporto_vento - 1) * peso)

        dati_terrestri["hourly"] = ore.to_dict("list")

        corrente = dati_terrestri.get("current") or {}
        if corrente.get("temperature_2m") is not None:
            corrente["temperature_2m"] += bias_temp
        if corrente.get("relative_humidity_2m") is not None:
            corrente["relative_humidity_2m"] = max(
                0.0, min(100.0, corrente["relative_humidity_2m"] + bias_umidita)
            )
        for chiave in ("wind_speed_10m", "wind_gusts_10m"):
            if corrente.get(chiave) is not None:
                corrente[chiave] *= rapporto_vento

        giornaliero = dati_terrestri.get("daily") or {}
        oggi = adesso.strftime("%Y-%m-%d")
        if oggi in giornaliero.get("time", []):
            i_oggi = giornaliero["time"].index(oggi)
            temp_oggi = ore.loc[
                ore["time"].dt.strftime("%Y-%m-%d") == oggi, "temperature_2m"
            ].dropna()
            if not temp_oggi.empty:
                giornaliero["temperature_2m_max"][i_oggi] = float(temp_oggi.max())
                giornaliero["temperature_2m_min"][i_oggi] = float(temp_oggi.min())
        return {
            "stazione": str(stazione.get("name", "Stazione senza nome")),
            "distanza_km": float(stazione.get("distance", 0)) / 1000
                if stazione.get("distance") is not None else None,
            "ultima_osservazione": ultima_osservazione,
            "bias_temp": bias_temp,
            "bias_umidita": bias_umidita,
            "rapporto_vento": rapporto_vento,
            "numero_osservazioni": len(ultime_3),
        }

    except Exception:
        return None
