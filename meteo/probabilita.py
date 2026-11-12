# =============================================================================
# Calabria Meteo Lab - Probabilità dagli ensemble e affidabilità della previsione
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# - Probabilità di pioggia: quota di scenari con pioggia, media tra
#   ICON-EU-EPS (40 scenari) ed ECMWF ENS (51 scenari), con peso uguale.
# - Forchetta delle temperature: 10° e 90° percentile degli scenari.
# - Vento: probabilità di raffiche forti (≥ 50 km/h) e di burrasca (≥ 75 km/h),
#   forchette del vento medio massimo e della raffica massima del giorno.
# - Temporali nell'intorno: quota di 9 punti ICON-2I (circa 10 km) con
#   temporale nell'ora o in quella prima/dopo.
# - Affidabilità: Alta / Media / Bassa in base a quante condizioni di
#   accordo tra gli scenari non sono rispettate.

import numpy as np
import pandas as pd
import requests
import streamlit as st

from meteo.api import HTTP_FACOLTATIVO as HTTP
from meteo.config import API_METEO_URL, MODELLO_TERRESTRE

API_ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

# Per ogni ensemble: nomi da provare in ordine (Open-Meteo li ha rinominati nel 2026)
MODELLI_ENSEMBLE = {
    "ICON-EU-EPS": ["icon_eu_eps", "icon_eu"],
    "ECMWF ENS": ["ecmwf_ifs025_ensemble", "ecmwf_ifs025"],
}

SOGLIA_PIOGGIA_ORA_MM = 0.2
SOGLIA_PIOGGIA_GIORNO_MM = 1.0
PERCENTILI = (10, 90)
CODICI_TEMPORALE = {95, 96, 99}
PASSO_INTORNO_GRADI = 0.09        # circa 10 km in latitudine

# Raffiche: soglie mostrate (forti, burrasca) e soglie usate da attività e viaggio
SOGLIE_RAFFICHE = {"forti": 50, "burrasca": 75}
SOGLIE_RAFFICHE_ORARIE = (40, 45, 50, 60, 70, 75, 90)
PROBABILITA_MINIMA_MOSTRATA = 0.10
PROBABILITA_AVVISO_RAFFICHE = 0.30   # attività e viaggio: "possibili raffiche forti"

AFFIDABILITA = {
    "probabilita_incerta": (0.20, 0.80),   # tra 20% e 80% gli scenari non concordano
    "forchetta_massima_c": 3.0,            # forchetta 10°–90° della temperatura oltre 3 °C
    "margine_icon_c": 1.0,                 # massima ICON-2I fuori dalla forchetta di oltre 1 °C
    "raffiche_incerte": (0.30, 0.70),      # tra 30% e 70% degli scenari con raffiche ≥ 50 km/h
}
LIVELLI_AFFIDABILITA = {0: ("🟢", "Alta"), 1: ("🟡", "Media"), 2: ("🟠", "Bassa")}


# -----------------------------------------------------------------------------
# Download
# -----------------------------------------------------------------------------

def _colonne_membri(orario, variabile):
    """Valori di tutti gli scenari di una variabile (controllo incluso) come DataFrame."""
    colonne = {
        chiave: valori for chiave, valori in orario.items()
        if chiave == variabile or chiave.startswith(variabile + "_member")
    }
    return pd.DataFrame(colonne, dtype="float64")


VARIABILI_ENSEMBLE = {"pioggia": "precipitation", "temperatura": "temperature_2m",
                      "vento": "wind_speed_10m", "raffiche": "wind_gusts_10m"}


def _tabelle_membri(orario):
    """{"pioggia": DataFrame, ...} con una colonna per scenario; il vento è facoltativo."""
    tempi = pd.to_datetime(orario.get("time", []))
    tabelle = {}
    for nome, variabile in VARIABILI_ENSEMBLE.items():
        tabella = _colonne_membri(orario, variabile)
        tabella.index = tempi
        tabelle[nome] = tabella if tabella.shape[1] >= 2 and tabella.notna().any().any() else None
    if tabelle["pioggia"] is None or tabelle["temperatura"] is None or len(tempi) == 0:
        raise ValueError("risposta senza scenari")
    return tabelle


def _richiesta_ensemble(latitudini, longitudini, nome, con_vento=True):
    variabili = ["precipitation", "temperature_2m"] + (["wind_speed_10m", "wind_gusts_10m"] if con_vento else [])
    risposta = HTTP.get(
        API_ENSEMBLE_URL,
        params={
            "latitude": latitudini,
            "longitude": longitudini,
            "models": nome,
            "hourly": ",".join(variabili),
            "timezone": "Europe/Rome",
            "forecast_days": 3,
            "wind_speed_unit": "kmh",
        },
        timeout=12,
    )
    if getattr(risposta, "status_code", 200) == 400 and con_vento:   # variabili del vento non disponibili: senza vento
        return _richiesta_ensemble(latitudini, longitudini, nome, con_vento=False)
    risposta.raise_for_status()
    dati = risposta.json()
    return dati if isinstance(dati, list) else [dati]


def _scarica_modello(latitudine, longitudine, nomi):
    ultimo_errore = None
    for nome in nomi:
        try:
            punto = _richiesta_ensemble(latitudine, longitudine, nome)[0]
            return {**_tabelle_membri(punto.get("hourly") or {}), "nome_api": nome}
        except (requests.RequestException, ValueError, KeyError, IndexError) as errore:
            ultimo_errore = errore
    raise RuntimeError(f"ensemble non disponibile: {ultimo_errore}")


@st.cache_data(ttl=3600, show_spinner=False)
def scarica_ensemble(latitudine, longitudine):
    """{nome modello: {"pioggia": DataFrame, "temperatura": DataFrame}} per gli ensemble disponibili."""
    risultati = {}
    for modello, nomi in MODELLI_ENSEMBLE.items():
        try:
            risultati[modello] = _scarica_modello(latitudine, longitudine, nomi)
        except RuntimeError:
            continue
    return risultati


@st.cache_data(ttl=1800, show_spinner=False)
def temporali_nell_intorno(latitudine, longitudine):
    """Quota oraria di 9 punti ICON-2I (circa 10 km) con temporale nell'ora o in quella prima/dopo."""
    passo_lat = PASSO_INTORNO_GRADI
    passo_lon = PASSO_INTORNO_GRADI / max(np.cos(np.radians(latitudine)), 0.3)
    punti = [(latitudine + i * passo_lat, longitudine + j * passo_lon) for i in (-1, 0, 1) for j in (-1, 0, 1)]
    try:
        risposta = HTTP.get(
            API_METEO_URL,
            params={
                "latitude": ",".join(f"{la:.3f}" for la, _ in punti),
                "longitude": ",".join(f"{lo:.3f}" for _, lo in punti),
                "models": MODELLO_TERRESTRE,
                "hourly": "weather_code",
                "timezone": "Europe/Rome",
                "forecast_days": 3,
            },
            timeout=10,
        )
        risposta.raise_for_status()
        dati = risposta.json()
    except (requests.RequestException, ValueError):
        return None

    dati = dati if isinstance(dati, list) else [dati]
    colonne = {}
    for indice, punto in enumerate(dati):
        orario = punto.get("hourly") or {}
        codici = pd.Series(orario.get("weather_code", []), index=pd.to_datetime(orario.get("time", [])), dtype="float64")
        temporale = codici.isin(CODICI_TEMPORALE).astype(float)
        colonne[indice] = temporale.rolling(3, center=True, min_periods=1).max()  # ora prima e dopo
    if not colonne:
        return None
    return pd.DataFrame(colonne).mean(axis=1)


@st.cache_data(ttl=3600, show_spinner=False)
def raffiche_nei_punti(coordinate):
    """Per ogni punto (tuple di (lat, lon)): elenco di DataFrame delle raffiche degli scenari.

    Una sola richiesta per ensemble per tutti i punti (usata dal viaggio).
    """
    risultati = [[] for _ in coordinate]
    if not coordinate:
        return risultati
    latitudini = ",".join(f"{la:.3f}" for la, _ in coordinate)
    longitudini = ",".join(f"{lo:.3f}" for _, lo in coordinate)
    for nomi in MODELLI_ENSEMBLE.values():
        for nome in nomi:
            try:
                punti = _richiesta_ensemble(latitudini, longitudini, nome)
            except (requests.RequestException, ValueError):
                continue
            for i, punto in enumerate(punti[:len(coordinate)]):
                try:
                    raffiche = _tabelle_membri(punto.get("hourly") or {})["raffiche"]
                except ValueError:
                    raffiche = None
                if raffiche is not None:
                    risultati[i].append(raffiche)
            break
    return risultati


# -----------------------------------------------------------------------------
# Calcoli
# -----------------------------------------------------------------------------

def quota_scenari_oltre(tabelle, istante, soglia):
    """Quota di scenari (media tra gli ensemble) con valore ≥ soglia nell'ora indicata."""
    quote = []
    for tabella in tabelle:
        if tabella is None:
            continue
        ora = pd.Timestamp(istante).floor("h")
        if ora in tabella.index:
            riga = tabella.loc[ora].dropna()
            if len(riga):
                quote.append(float((riga >= soglia).mean()))
    return float(np.mean(quote)) if quote else None


def _raffiche_orarie(ensemble):
    """{istante: {soglia: probabilità}} per le soglie di SOGLIE_RAFFICHE_ORARIE."""
    tabelle = [d.get("raffiche") for d in ensemble.values() if d.get("raffiche") is not None]
    if not tabelle:
        return {}
    risultato = {}
    for soglia in SOGLIE_RAFFICHE_ORARIE:
        quote = pd.concat([(t >= soglia).where(t.notna()).mean(axis=1) for t in tabelle], axis=1).mean(axis=1)
        for istante, valore in quote.items():
            if pd.notna(valore):
                risultato.setdefault(istante, {})[soglia] = float(valore)
    return risultato

def probabilita_pioggia_oraria(ensemble):
    """Probabilità oraria di pioggia (≥ 0,2 mm/h), media tra gli ensemble."""
    quote = [(dati["pioggia"] >= SOGLIA_PIOGGIA_ORA_MM).mean(axis=1) for dati in ensemble.values()]
    return pd.concat(quote, axis=1).mean(axis=1) if quote else pd.Series(dtype=float)


def probabilita_pioggia_finestra(ensemble, inizio, fine, soglia=SOGLIA_PIOGGIA_ORA_MM):
    """Probabilità che piova almeno in un'ora tra 'inizio' (incluso) e 'fine' (escluso)."""
    quote = []
    for dati in ensemble.values():
        tratto = dati["pioggia"].loc[(dati["pioggia"].index >= inizio) & (dati["pioggia"].index < fine)]
        if not tratto.empty:
            quote.append(float((tratto >= soglia).any(axis=0).mean()))
    return float(np.mean(quote)) if quote else None


def statistiche_vento_giorno(ensemble, data):
    """Forchette del vento medio massimo e della raffica massima del giorno, probabilità di raffiche forti."""
    venti, raffiche, forti, burrasca = [], [], [], []
    for dati in ensemble.values():
        if dati.get("raffiche") is None:
            continue
        giorno = dati["raffiche"].index.date == data
        if giorno.sum() < 18:
            continue
        massime = dati["raffiche"].loc[giorno].max(axis=0).dropna()
        if massime.empty:
            continue
        raffiche.append(massime)
        forti.append(float((massime >= SOGLIE_RAFFICHE["forti"]).mean()))
        burrasca.append(float((massime >= SOGLIE_RAFFICHE["burrasca"]).mean()))
        if dati.get("vento") is not None:
            venti.append(dati["vento"].loc[dati["vento"].index.date == data].max(axis=0).dropna())
    if not raffiche:
        return {}
    raffiche = pd.concat(raffiche)
    risultato = {
        "raffica": tuple(float(np.percentile(raffiche, p)) for p in PERCENTILI),
        "raffiche_forti": float(np.mean(forti)),
        "burrasca": float(np.mean(burrasca)),
    }
    if venti:
        venti = pd.concat(venti)
        risultato["vento"] = tuple(float(np.percentile(venti, p)) for p in PERCENTILI)
    return risultato


def statistiche_giorno(ensemble, data):
    """Probabilità di pioggia (≥ 1 mm nel giorno) e forchette di massima e minima."""
    quote, massime, minime = [], [], []
    for dati in ensemble.values():
        giorno = dati["pioggia"].index.date == data
        if giorno.sum() < 18:   # giorno coperto solo in parte dalla previsione
            continue
        quote.append(float((dati["pioggia"].loc[giorno].sum(axis=0) >= SOGLIA_PIOGGIA_GIORNO_MM).mean()))
        temperature = dati["temperatura"].loc[giorno]
        massime.append(temperature.max(axis=0))
        minime.append(temperature.min(axis=0))
    if not quote:
        return None
    massime = pd.concat(massime)
    minime = pd.concat(minime)
    return {
        "pioggia": float(np.mean(quote)),
        "massima": tuple(float(np.percentile(massime, p)) for p in PERCENTILI),
        "minima": tuple(float(np.percentile(minime, p)) for p in PERCENTILI),
        **statistiche_vento_giorno(ensemble, data),
    }


def affidabilita(probabilita, forchetta_c, icon_piove, icon_fuori_forchetta=False, raffiche_forti=None):
    """(livello 0/1/2, motivi) contando le condizioni di accordo non rispettate.

    Condizioni: scenari concordi sulla pioggia; forchetta della temperatura
    stretta; ICON-2I in linea con gli ensemble (pioggia e temperatura massima);
    scenari concordi sulle raffiche forti.
    """
    if probabilita is None:
        return None, []
    motivi = []
    basso, alto = AFFIDABILITA["probabilita_incerta"]
    if basso <= probabilita <= alto:
        motivi.append("scenari divisi sulla pioggia")
    if forchetta_c is not None and forchetta_c > AFFIDABILITA["forchetta_massima_c"]:
        motivi.append("temperature molto variabili tra gli scenari")
    pioggia_discorde = icon_piove is not None and (
        (icon_piove and probabilita < basso) or (not icon_piove and probabilita > alto)
    )
    if pioggia_discorde or icon_fuori_forchetta:
        motivi.append("la previsione e gli ensemble non concordano")
    if raffiche_forti is not None and (AFFIDABILITA["raffiche_incerte"][0] <= raffiche_forti
                                       <= AFFIDABILITA["raffiche_incerte"][1]):
        motivi.append("scenari divisi sul vento")
    return min(len(motivi), 2), motivi


def calcola_probabilita(ensemble, intorno, ore, giorni):
    """Tutte le informazioni probabilistiche usate dalla pagina (None se gli ensemble mancano)."""
    if not ensemble:
        return None

    pioggia_oraria = probabilita_pioggia_oraria(ensemble)
    raffiche_orarie = _raffiche_orarie(ensemble)
    orarie = {}
    for istante in ore["time"]:
        istante = pd.Timestamp(istante)
        orarie[istante] = {
            "pioggia": float(pioggia_oraria.get(istante)) if istante in pioggia_oraria.index else None,
            "temporali": float(intorno.get(istante)) if intorno is not None and istante in intorno.index else None,
            "raffiche": raffiche_orarie.get(istante, {}),
        }

    giornaliere = {}
    for _, riga in giorni.iterrows():
        data = pd.Timestamp(riga["time"]).date()
        statistiche = statistiche_giorno(ensemble, data)
        if statistiche is None:
            continue
        icon_piove = float(riga.get("precipitation_sum") or 0) >= SOGLIA_PIOGGIA_GIORNO_MM
        forchetta = statistiche["massima"][1] - statistiche["massima"][0]
        massima_icon = pd.to_numeric(riga.get("temperature_2m_max"), errors="coerce")
        margine = AFFIDABILITA["margine_icon_c"]
        fuori = bool(pd.notna(massima_icon) and not (
            statistiche["massima"][0] - margine <= massima_icon <= statistiche["massima"][1] + margine
        ))
        livello, motivi = affidabilita(statistiche["pioggia"], forchetta, icon_piove, fuori,
                                       statistiche.get("raffiche_forti"))
        giornaliere[data] = {**statistiche, "affidabilita": livello, "motivi": motivi}

    # Prossime 12 ore
    prossime = None
    if not ore.empty:
        inizio = pd.Timestamp(ore.iloc[0]["time"])
        fine = inizio + pd.Timedelta(hours=12)
        probabilita = probabilita_pioggia_finestra(ensemble, inizio, fine)
        tratto = ore.loc[(ore["time"] >= inizio) & (ore["time"] < fine)]
        icon_piove = bool((pd.to_numeric(tratto["precipitation"], errors="coerce").fillna(0) >= SOGLIA_PIOGGIA_ORA_MM).any())
        forchette = []
        for dati in ensemble.values():
            temperature = dati["temperatura"].loc[(dati["temperatura"].index >= inizio) & (dati["temperatura"].index < fine)]
            if not temperature.empty:
                forchette.append(temperature.quantile(PERCENTILI[1] / 100, axis=1) - temperature.quantile(PERCENTILI[0] / 100, axis=1))
        forchetta = float(pd.concat(forchette).max()) if forchette else None
        raffiche = [d["raffiche"] for d in ensemble.values() if d.get("raffiche") is not None]
        raffiche_forti = None
        if raffiche:
            raffiche_forti = probabilita_pioggia_finestra(
                {i: {"pioggia": t} for i, t in enumerate(raffiche)}, inizio, fine, SOGLIE_RAFFICHE["forti"])
        livello, motivi = affidabilita(probabilita, forchetta, icon_piove, raffiche_forti=raffiche_forti)
        prossime = {"pioggia": probabilita, "raffiche_forti": raffiche_forti, "affidabilita": livello, "motivi": motivi}

    scenari = sum(dati["pioggia"].shape[1] for dati in ensemble.values())
    return {
        "orarie": orarie,
        "giornaliere": giornaliere,
        "prossime_12": prossime,
        "modelli": list(ensemble),
        "scenari": scenari,
        "intorno_disponibile": intorno is not None,
    }


def testo_affidabilita(livello):
    if livello is None:
        return ""
    simbolo, nome = LIVELLI_AFFIDABILITA[livello]
    return f"{simbolo} Affidabilità {nome.lower()}"
