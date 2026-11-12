# =============================================================================
# Calabria Meteo Lab - Modello combinato di 8 modelli
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Media pesata ora per ora con pesi che cambiano con la scadenza:
# - ad alta risoluzione: ICON-2I (2,2 km), MOLOCH (1,2 km), WRF ItaliaMeteo e
#   WRF CIMA (1,5 km), BOLAM (8 km): dettaglio su rilievi, coste e temporali,
#   pesano di più nelle prime ore;
# - globali ed europei: ECMWF IFS (il miglior modello globale), ICON-EU, AIFS:
#   pesano di più dal secondo giorno.
# Se un modello manca (o la sua corsa finisce prima, come MOLOCH dopo 45 ore)
# gli altri vengono riproporzionati. AIFS non entra in pioggia e nuvolosità
# (dati ogni 6 ore, troppo grossolani). I pesi andranno tarati con i dati storici.

import math

import numpy as np
import pandas as pd
import requests
import streamlit as st

from meteo.api import HTTP_FACOLTATIVO as HTTP
from meteo.config import API_METEO_URL, VARIABILI_ORARIE

# Nomi da provare per ogni modello su Open-Meteo (in ordine)
MODELLI_AGGIUNTIVI = {
    "ECMWF IFS": ["ecmwf_ifs", "ecmwf_ifs025"],
    "ICON-EU": ["icon_eu"],
    "AIFS": ["ecmwf_aifs025_single", "ecmwf_aifs025"],
}
PRINCIPALE = "ICON-2I"
ORDINE = [PRINCIPALE, "MOLOCH", "WRF ItaliaMeteo", "WRF CIMA", "BOLAM", "ECMWF IFS", "ICON-EU", "AIFS"]

# Pesi per ora di scadenza; tra un punto e l'altro variano in modo graduale
PESI = {
    0: {"ICON-2I": 0.25, "MOLOCH": 0.20, "WRF ItaliaMeteo": 0.075, "WRF CIMA": 0.075, "BOLAM": 0.05,
        "ECMWF IFS": 0.20, "ICON-EU": 0.10, "AIFS": 0.05},
    24: {"ICON-2I": 0.22, "MOLOCH": 0.15, "WRF ItaliaMeteo": 0.06, "WRF CIMA": 0.06, "BOLAM": 0.05,
         "ECMWF IFS": 0.28, "ICON-EU": 0.10, "AIFS": 0.08},
    48: {"ICON-2I": 0.20, "MOLOCH": 0.10, "WRF ItaliaMeteo": 0.05, "WRF CIMA": 0.05, "BOLAM": 0.05,
         "ECMWF IFS": 0.35, "ICON-EU": 0.08, "AIFS": 0.12},
    72: {"ICON-2I": 0.20, "MOLOCH": 0.05, "WRF ItaliaMeteo": 0.05, "WRF CIMA": 0.05, "BOLAM": 0.05,
         "ECMWF IFS": 0.37, "ICON-EU": 0.08, "AIFS": 0.15},
}
MODELLI_METEOHUB = {"MOLOCH", "WRF ItaliaMeteo", "WRF CIMA", "BOLAM"}

VARIABILI_MEDIA = [
    "temperature_2m", "apparent_temperature", "relative_humidity_2m", "cloud_cover",
    "wind_speed_10m", "wind_gusts_10m", "precipitation", "pressure_msl",
]
ESCLUSI = {"precipitation": {"AIFS"}, "cloud_cover": {"AIFS"}}
TEMPORALE = {95, 96, 99}

# Raffiche per i modelli che non le forniscono (MeteoHub): vento medio x fattore di raffica
# di ICON-2I nella stessa ora e nello stesso punto (rilievo, turbolenza), entro questi limiti.
FATTORE_RAFFICA = {"minimo": 1.3, "massimo": 2.5, "predefinito": 1.6, "vento_minimo_kmh": 5.0}
RAFFICA_MINIMA_SU_VENTO = 1.3     # le raffiche combinate non scendono mai sotto vento medio x 1,3
NEVE_TEMPERATURA = 1.5


def fattore_raffica(tabella):
    """Rapporto raffica / vento medio ora per ora (da ICON-2I), con limiti ragionevoli."""
    f = FATTORE_RAFFICA
    if "wind_gusts_10m" not in tabella or "wind_speed_10m" not in tabella:
        return np.full(len(tabella), f["predefinito"])
    vento = tabella["wind_speed_10m"].to_numpy(dtype=float)
    raffiche = tabella["wind_gusts_10m"].to_numpy(dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        rapporto = np.clip(raffiche / vento, f["minimo"], f["massimo"])
    return np.where(np.isnan(rapporto) | (vento < f["vento_minimo_kmh"]), f["predefinito"], rapporto)


def pesi_alla_scadenza(ore):
    """Pesi (non ancora riproporzionati) dopo 'ore' ore di scadenza."""
    punti = sorted(PESI)
    ore = min(max(ore, punti[0]), punti[-1])
    for a, b in zip(punti, punti[1:]):
        if a <= ore <= b:
            f = (ore - a) / (b - a) if b > a else 0.0
            return {m: PESI[a][m] + (PESI[b][m] - PESI[a][m]) * f for m in ORDINE}
    return dict(PESI[punti[-1]])


# -----------------------------------------------------------------------------
# Download dei modelli aggiuntivi
# -----------------------------------------------------------------------------

def _tabella(dati):
    orario = (dati or {}).get("hourly") or {}
    if not orario.get("time"):
        return None
    tabella = pd.DataFrame({k: v for k, v in orario.items() if k != "time"}, index=pd.to_datetime(orario["time"]))
    tabella = tabella.apply(pd.to_numeric, errors="coerce")
    # modelli con dati ogni 3-6 ore: interpolazione per le ore intermedie (non per la pioggia)
    continue_ = [c for c in tabella.columns if c not in ("precipitation", "weather_code")]
    tabella[continue_] = tabella[continue_].interpolate(method="time", limit=5, limit_area="inside")
    return tabella if tabella.notna().any().any() else None


@st.cache_data(ttl=1800, show_spinner=False)
def scarica_modelli_aggiuntivi(latitudine, longitudine):
    """{nome modello: DataFrame orario} per i modelli che rispondono."""
    variabili = sorted(set(VARIABILI_ORARIE) | {"pressure_msl"})
    risultati = {}
    for nome, candidati in MODELLI_AGGIUNTIVI.items():
        for candidato in candidati:
            try:
                risposta = HTTP.get(API_METEO_URL, params={
                    "latitude": latitudine, "longitude": longitudine, "models": candidato,
                    "timezone": "Europe/Rome", "forecast_days": 3, "wind_speed_unit": "kmh",
                    "hourly": ",".join(variabili),
                }, timeout=10)
                risposta.raise_for_status()
                tabella = _tabella(risposta.json())
            except (requests.RequestException, ValueError):
                continue
            if tabella is not None:
                risultati[nome] = tabella
                break
    return risultati


# -----------------------------------------------------------------------------
# Combinazione
# -----------------------------------------------------------------------------

def _codice_combinato(pioggia, temperatura, nuvole, codici, pesi):
    """Codice meteo ricavato dai valori combinati."""
    principali = [codici.get(m) for m in (PRINCIPALE, "ECMWF IFS") if pesi.get(m, 0) > 0]
    if pioggia >= 0.1 and any(c in TEMPORALE for c in principali if c is not None):
        return 95
    if pioggia >= 0.2:
        neve = temperatura is not None and temperatura <= NEVE_TEMPERATURA
        if pioggia < 1:
            return 71 if neve else 61
        if pioggia < 4:
            return 73 if neve else 63
        return 75 if neve else 65
    if pioggia >= 0.1:
        return 71 if temperatura is not None and temperatura <= NEVE_TEMPERATURA else 51
    if codici.get(PRINCIPALE) in (45, 48) and (nuvole is None or nuvole >= 60):
        return 45
    if nuvole is None:
        return codici.get(PRINCIPALE, 3)
    if nuvole <= 15:
        return 0
    if nuvole <= 45:
        return 1
    if nuvole <= 75:
        return 2
    return 3


GRAVITA = {95: 6, 96: 6, 99: 6, 75: 5, 73: 5, 71: 5, 65: 4, 63: 4, 61: 4, 51: 3, 45: 2, 3: 1, 2: 1, 1: 0, 0: 0}


def combina(dati_terrestri, modelli, adesso):
    """Sostituisce nei dati ICON-2I le serie orarie, i valori giornalieri e quelli attuali con la media pesata.

    Restituisce i pesi effettivi della prima ora (per mostrarli), o None se non c'è nulla da combinare.
    """
    if not modelli:
        return None
    orario = dati_terrestri["hourly"]
    tempi = pd.to_datetime(orario["time"])
    base = pd.DataFrame({k: v for k, v in orario.items() if k != "time"}, index=tempi).apply(pd.to_numeric, errors="coerce")
    tabelle = {PRINCIPALE: base, **{m: t.reindex(tempi) for m, t in modelli.items()}}
    disponibili = [m for m in ORDINE if m in tabelle]
    fattore = fattore_raffica(base)
    for m in disponibili:
        t = tabelle[m]
        if "wind_gusts_10m" not in t and "wind_speed_10m" in t:
            tabelle[m] = t.assign(wind_gusts_10m=t["wind_speed_10m"].to_numpy(dtype=float) * fattore)
    scadenze = ((tempi - pd.Timestamp(adesso).floor("h")) / pd.Timedelta(hours=1)).to_numpy()
    pesi_ora = [pesi_alla_scadenza(max(0.0, s)) for s in scadenze]

    def media(variabile):
        valori = np.full((len(tempi), len(disponibili)), np.nan)
        pesi = np.zeros_like(valori)
        for j, m in enumerate(disponibili):
            if variabile in tabelle[m] and m not in ESCLUSI.get(variabile, set()):
                valori[:, j] = tabelle[m][variabile].to_numpy(dtype=float)
                pesi[:, j] = [p[m] for p in pesi_ora]
        pesi = np.where(np.isnan(valori), 0.0, pesi)
        somma = pesi.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(somma > 0, np.nansum(np.nan_to_num(valori) * pesi, axis=1) / somma, np.nan)

    combinati = {v: media(v) for v in VARIABILI_MEDIA}
    with np.errstate(invalid="ignore"):
        combinati["wind_gusts_10m"] = np.fmax(combinati["wind_gusts_10m"],
                                              combinati["wind_speed_10m"] * RAFFICA_MINIMA_SU_VENTO)

    # Direzione del vento: media dei vettori (nord e sud non fanno est)
    u = np.zeros(len(tempi)); v = np.zeros(len(tempi)); w = np.zeros(len(tempi))
    for m in disponibili:
        t = tabelle[m]
        if "wind_direction_10m" in t and "wind_speed_10m" in t:
            gradi = np.radians(t["wind_direction_10m"].to_numpy(dtype=float))
            forza = t["wind_speed_10m"].to_numpy(dtype=float)
            peso = np.array([p[m] for p in pesi_ora])
            valido = ~(np.isnan(gradi) | np.isnan(forza))
            u += np.where(valido, -forza * np.sin(gradi) * peso, 0)
            v += np.where(valido, -forza * np.cos(gradi) * peso, 0)
            w += np.where(valido, peso, 0)
    direzione = np.where(w > 0, (np.degrees(np.arctan2(-u, -v)) + 360) % 360, base.get("wind_direction_10m"))

    # Codice meteo dai valori combinati
    codici = []
    for i in range(len(tempi)):
        per_modello = {m: (None if pd.isna(tabelle[m].get("weather_code", pd.Series(dtype=float)).iloc[i])
                           else int(tabelle[m]["weather_code"].iloc[i]))
                       for m in disponibili if "weather_code" in tabelle[m]}
        pioggia = 0.0 if np.isnan(combinati["precipitation"][i]) else combinati["precipitation"][i]
        temperatura = None if np.isnan(combinati["temperature_2m"][i]) else combinati["temperature_2m"][i]
        nuvole = None if np.isnan(combinati["cloud_cover"][i]) else combinati["cloud_cover"][i]
        codici.append(_codice_combinato(pioggia, temperatura, nuvole, per_modello, pesi_ora[i]))

    # Valori dei singoli modelli, per mostrarli nel dettaglio dell'ora
    for m in disponibili:
        for variabile, prefisso in (("temperature_2m", "modello_temp_"), ("precipitation", "modello_pioggia_")):
            if variabile in tabelle[m]:
                orario[prefisso + m] = [None if pd.isna(x) else round(float(x), 1) for x in tabelle[m][variabile]]

    icon_prima = {v: base[v].copy() for v in VARIABILI_MEDIA if v in base}
    for variabile, serie in combinati.items():
        orario[variabile] = [None if np.isnan(x) else round(float(x), 2) for x in serie]
    orario["wind_direction_10m"] = [None if pd.isna(x) else round(float(x)) for x in direzione]
    orario["weather_code"] = codici

    _aggiorna_giornaliero(dati_terrestri, tempi, combinati, direzione, codici)
    _aggiorna_corrente(dati_terrestri, tempi, combinati, icon_prima, direzione, codici)

    totale = sum(pesi_ora[0][m] for m in disponibili) if len(tempi) else 1
    indice_adesso = int(np.argmin(np.abs(scadenze))) if len(scadenze) else 0
    pesi_adesso = {m: pesi_ora[indice_adesso][m] / totale for m in disponibili}
    dati_terrestri["_fonte"] = "Combinato (" + ", ".join(disponibili) + ")"
    dati_terrestri["_pesi"] = pesi_adesso
    return pesi_adesso


def _aggiorna_giornaliero(dati, tempi, combinati, direzione, codici):
    giornaliero = dati.get("daily") or {}
    if not giornaliero.get("time"):
        return
    date = pd.to_datetime(giornaliero["time"]).date
    giorno_ora = tempi.date
    for i, data in enumerate(date):
        maschera = giorno_ora == data
        if maschera.sum() < 20:   # giorno incompleto: restano i valori ICON-2I
            continue

        def massimo(chiave):
            serie = combinati[chiave][maschera]
            return None if np.all(np.isnan(serie)) else round(float(np.nanmax(serie)), 1)

        for chiave, valore in (
            ("temperature_2m_max", massimo("temperature_2m")),
            ("temperature_2m_min", None if np.all(np.isnan(combinati["temperature_2m"][maschera]))
             else round(float(np.nanmin(combinati["temperature_2m"][maschera])), 1)),
            ("precipitation_sum", round(float(np.nansum(combinati["precipitation"][maschera])), 1)),
            ("wind_speed_10m_max", massimo("wind_speed_10m")),
            ("wind_gusts_10m_max", massimo("wind_gusts_10m")),
        ):
            if chiave in giornaliero and valore is not None:
                giornaliero[chiave][i] = valore
        if "wind_direction_10m_dominant" in giornaliero:
            angoli = np.radians(np.asarray(direzione, dtype=float)[maschera])
            angoli = angoli[~np.isnan(angoli)]
            if len(angoli):
                giornaliero["wind_direction_10m_dominant"][i] = round(
                    float((math.degrees(math.atan2(np.sin(angoli).mean(), np.cos(angoli).mean())) + 360) % 360))
        if "weather_code" in giornaliero:
            codici_giorno = [c for c, m in zip(codici, maschera) if m]
            giornaliero["weather_code"][i] = max(codici_giorno, key=lambda c: GRAVITA.get(c, 1))


def _aggiorna_corrente(dati, tempi, combinati, icon_prima, direzione, codici):
    corrente = dati.get("current") or {}
    if not corrente.get("time") or not len(tempi):
        return
    ora = pd.Timestamp(corrente["time"]).floor("h")
    posizioni = np.where(tempi == ora)[0]
    if not len(posizioni):
        return
    i = int(posizioni[0])
    # stesso scostamento della media rispetto a ICON-2I in quell'ora
    for variabile in ("temperature_2m", "apparent_temperature", "relative_humidity_2m", "cloud_cover",
                      "wind_speed_10m", "wind_gusts_10m", "pressure_msl"):
        if corrente.get(variabile) is None or variabile not in icon_prima:
            continue
        differenza = combinati[variabile][i] - icon_prima[variabile].iloc[i]
        if not np.isnan(differenza):
            valore = corrente[variabile] + differenza
            if variabile in ("relative_humidity_2m", "cloud_cover"):
                valore = min(100.0, max(0.0, valore))
            corrente[variabile] = round(float(valore), 1)
    if not pd.isna(direzione[i]):
        corrente["wind_direction_10m"] = round(float(direzione[i]))
    corrente["weather_code"] = codici[i]
