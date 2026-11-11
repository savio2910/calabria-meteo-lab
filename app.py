# =============================================================================
# Calabria Meteo Lab
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# Uso personale soltanto: vietate copia, modifica, redistribuzione
# o riutilizzo, anche parziale, senza autorizzazione scritta dell’autore.
# =============================================================================

import html
import json
import math
import unicodedata
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from home_viva import aggiungi_home_viva
from sfondo_meteo import aggiungi_sfondo_meteo

try:
    from meteostat import Stations, Hourly
    METEOSTAT_DISPONIBILE = True
except ImportError:
    METEOSTAT_DISPONIBILE = False
import streamlit as st
import streamlit.components.v1 as components
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim


# =============================================================================
# CONFIGURAZIONE STREAMLIT
# =============================================================================

st.set_page_config(
    page_title="Calabria Meteo Lab",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      #MainMenu {visibility: hidden;}
      header {visibility: hidden;}
      footer {visibility: hidden;}

      .block-container {
      max-width: none !important;
      width: 100% !important;
      padding: 0.5rem 1rem 2rem 1rem !important;
      }

      [data-testid="stAppViewContainer"] {
        background: #eef5f8;
      }

      [data-testid="stHeader"] {
        background: transparent;
      }

      iframe {
        background: #eef5f8 !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# COSTANTI
# =============================================================================

API_METEO_URL = "https://api.open-meteo.com/v1/forecast"
API_MARE_URL = "https://marine-api.open-meteo.com/v1/marine"

MODELLO_TERRESTRE = "italia_meteo_arpae_icon_2i"
FUSO_ORARIO = ZoneInfo("Europe/Rome")
GIORNI_PREVISIONE = 3

MODELLO_RISERVA = "icon_eu"

# Limiti per usare una stazione nella correzione osservativa
MAX_DISTANZA_STAZIONE_KM = 30
MAX_DISLIVELLO_STAZIONE_M = 200
MAX_CORREZIONE_TEMP_C = 4.0
API_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


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

CARTELLA_APP = Path(__file__).resolve().parent
FILE_COMUNI_COSTIERI = CARTELLA_APP / "comuni_costieri_calabria.csv"
CARTELLA_STATIC = CARTELLA_APP / "static"


@lru_cache(maxsize=None)
def leggi_static(nome):
    """Legge un file CSS/JS/HTML dalla cartella static/ (una volta sola)."""
    testo = (CARTELLA_STATIC / nome).read_text(encoding="utf-8")
    return testo[:-1] if testo.endswith("\n") else testo


STILE_CSS = leggi_static("stile.css")

COMUNI_RAPIDI = {
    "Amantea": (39.1331, 16.0746),
    "Catanzaro": (38.9098, 16.5877),
    "Cirò Marina": (39.3703, 17.1247),
    "Corigliano-Rossano": (39.5900, 16.5190),
    "Cosenza": (39.2983, 16.2537),
    "Crotone": (39.0808, 17.1271),
    "Isola di Capo Rizzuto": (38.9597, 17.0924),
    "Lamezia Terme": (38.9708, 16.3189),
    "Locri": (38.2415, 16.2624),
    "Palmi": (38.3594, 15.8510),
    "Praia a Mare": (39.8932, 15.7800),
    "Reggio Calabria": (38.1113, 15.6473),
    "Roccella Ionica": (38.3225, 16.4038),
    "Sibari": (39.7470, 16.4550),
    "Soverato": (38.6842, 16.5495),
    "Tropea": (38.6766, 15.8984),
    "Vibo Valentia": (38.6762, 16.1005),
}

ALIASES = {
    "reggio": "Reggio Calabria",
    "reggio di calabria": "Reggio Calabria",
    "rossano": "Corigliano-Rossano",
    "corigliano": "Corigliano-Rossano",
    "isola capo rizzuto": "Isola di Capo Rizzuto",
    "capo rizzuto": "Isola di Capo Rizzuto",
}

GIORNI_IT = [
    "lunedì",
    "martedì",
    "mercoledì",
    "giovedì",
    "venerdì",
    "sabato",
    "domenica",
]

MESI_IT = [
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
]

CODICI_METEO = {
    0: ("☀️", "Sereno"),
    1: ("🌤️", "Quasi sereno"),
    2: ("⛅", "Parzialmente nuvoloso"),
    3: ("☁️", "Coperto"),
    45: ("🌫️", "Nebbia"),
    48: ("🌫️", "Nebbia con brina"),
    51: ("🌦️", "Pioviggine debole"),
    53: ("🌦️", "Pioviggine moderata"),
    55: ("🌧️", "Pioviggine intensa"),
    56: ("🌧️", "Pioviggine gelata debole"),
    57: ("🌧️", "Pioviggine gelata intensa"),
    61: ("🌧️", "Pioggia debole"),
    63: ("🌧️", "Pioggia moderata"),
    65: ("🌧️", "Pioggia forte"),
    66: ("🌨️", "Pioggia gelata debole"),
    67: ("🌨️", "Pioggia gelata forte"),
    71: ("❄️", "Neve debole"),
    73: ("❄️", "Neve moderata"),
    75: ("❄️", "Neve forte"),
    77: ("❄️", "Granelli di neve"),
    80: ("🌦️", "Rovesci deboli"),
    81: ("🌧️", "Rovesci moderati"),
    82: ("🌧️", "Rovesci forti"),
    85: ("🌨️", "Rovesci nevosi deboli"),
    86: ("🌨️", "Rovesci nevosi forti"),
    95: ("⛈️", "Temporale"),
    96: ("⛈️", "Temporale con grandine"),
    99: ("⛈️", "Temporale con forte grandine"),
}

VARIABILI_CORRENTI = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "weather_code",
    "cloud_cover",
    "precipitation",
    "pressure_msl",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
]

VARIABILI_ORARIE = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "weather_code",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
]

VARIABILI_GIORNALIERE = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "sunrise",
    "sunset",
    "moonrise",
    "moonset",
    "moon_phase",
    "precipitation_sum",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
]

VARIABILI_MARINE_CORRENTI = [
    "wave_height",
    "wave_direction",
    "wave_period",
    "wave_peak_period",
    "wind_wave_height",
    "wind_wave_direction",
    "wind_wave_period",
    "swell_wave_height",
    "swell_wave_direction",
    "swell_wave_period",
    "sea_surface_temperature",
]

VARIABILI_MARINE_ORARIE = [
    "wave_height",
    "wave_direction",
    "wave_period",
    "wave_peak_period",
    "wind_wave_height",
    "wind_wave_direction",
    "wind_wave_period",
    "swell_wave_height",
    "swell_wave_direction",
    "swell_wave_period",
    "sea_surface_temperature",
]

VARIABILI_MARINE_GIORNALIERE = [
    "wave_height_max",
    "wave_direction_dominant",
    "wave_period_max",
    "wind_wave_height_max",
    "swell_wave_height_max",
    "swell_wave_direction_dominant",
]


# =============================================================================
# FORMATTAZIONE
# =============================================================================

def valore_finito(valore, default=0.0):
    """Converte uno scalare senza propagare NaN o infinito."""
    try:
        risultato = float(valore)
    except (TypeError, ValueError, OverflowError):
        return default
    return risultato if math.isfinite(risultato) else default


def numero(valore, decimali=1, unita=""):
    try:
        if valore is None or pd.isna(valore):
            return "—"

        return f"{float(valore):.{decimali}f}{unita}"

    except (TypeError, ValueError):
        return "—"


def direzione(gradi):
    try:
        if gradi is None or pd.isna(gradi):
            return "—"

        direzioni = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
        indice = int((float(gradi) + 22.5) // 45) % 8

        return direzioni[indice]

    except (TypeError, ValueError):
        return "—"


def meteo(codice):
    try:
        if codice is None or pd.isna(codice):
            return "", "Non disponibile"

        codice = int(float(codice))
    except (TypeError, ValueError):
        return "", "Non disponibile"

    return CODICI_METEO.get(
        codice,
        ("", "Non disponibile"),
    )


def data_it(valore):
    try:
        data = pd.Timestamp(valore)

        return (
            f"{GIORNI_IT[data.weekday()]} "
            f"{data.day} "
            f"{MESI_IT[data.month - 1]}"
        )

    except (TypeError, ValueError):
        return "Data non disponibile"


def ora_it(valore):
    try:
        if valore is None or pd.isna(valore):
            return "—"

        return pd.Timestamp(valore).strftime("%H:%M")

    except (TypeError, ValueError):
        return "—"


def fase_lunare(valore):
    try:
        if valore is None or pd.isna(valore):
            return "🌙 Luna"

        fase = float(valore)

        if fase < 0.03 or fase > 0.97:
            return "🌑 Luna nuova"
        if fase < 0.22:
            return "🌒 Falce crescente"
        if fase < 0.28:
            return "🌓 Primo quarto"
        if fase < 0.47:
            return "🌔 Gibbosa crescente"
        if fase < 0.53:
            return "🌕 Luna piena"
        if fase < 0.72:
            return "🌖 Gibbosa calante"
        if fase < 0.78:
            return "🌗 Ultimo quarto"

        return "🌘 Falce calante"

    except (TypeError, ValueError):
        return "🌙 Luna"


def e_notte(ora, alba, tramonto):
    try:
        if any(
            valore is None or pd.isna(valore)
            for valore in (ora, alba, tramonto)
        ):
            return False

        istante = pd.Timestamp(ora)

        return (
            istante < pd.Timestamp(alba)
            or istante >= pd.Timestamp(tramonto)
        )

    except (TypeError, ValueError):
        return False

def icona_meteo_html(codice, notte=False):
    """Rende le icone notturne con livelli SVG realmente sovrapposti."""
    icona_fallback, descrizione = meteo(codice)

    if not notte:
        return html.escape(icona_fallback)

    try:
        if codice is None or pd.isna(codice):
            return html.escape(icona_fallback)
        codice = int(codice)
    except (TypeError, ValueError):
        return html.escape(icona_fallback)

    luna = (
        '<path d="M43 10A22 22 0 1 0 55 48A22 22 0 0 1 43 10Z" '
        'fill="#f9d674" stroke="#d4a942" stroke-width="2"/>'
    )
    nube_piccola = (
        '<path d="M32 43c0-3 2.2-5.3 5-5.3 1 0 1.8.2 2.5.6 '
        '1.2-3.5 4.3-5.8 8.1-5.8 4.2 0 7.5 2.9 8.2 6.6 '
        '3.4.1 6.2 2.8 6.2 6.2 0 3.6-3 6.5-6.7 6.5H38 '
        'c-3.5 0-6-2.9-6-6.5z" fill="#eaf2f6" '
        'stroke="#8ba6b7" stroke-width="2" stroke-linejoin="round"/>'
    )
    nube_grande = (
        '<path d="M14 43c0-4 3-7 7-7 1.1 0 2.1.2 3 .6 '
        '1.7-5.6 6.8-9.6 12.8-9.6 6.3 0 11.5 4.1 13 9.8 '
        '1.3-.5 2.7-.8 4.2-.8 6 0 10.8 4.8 10.8 10.8 '
        'S60 57.5 54 57.5H22c-4.5 0-8-3.5-8-8 0-2.5 1-4.7 3-6.5z" '
        'fill="#d9e4eb" stroke="#8499a8" stroke-width="2" '
        'stroke-linejoin="round"/>'
    )
    gocce = (
        '<g stroke="#4ea8e6" stroke-width="3.8" stroke-linecap="round">'
        '<path d="M24 60l-3 6M39 60l-3 6M54 60l-3 6"/>'
        '</g>'
    )
    gocce_deboli = (
        '<g stroke="#4ea8e6" stroke-width="3.8" stroke-linecap="round">'
        '<path d="M31 59l-3 6M48 59l-3 6"/>'
        '</g>'
    )
    fiocchi_neve = (
        '<g fill="#f5fbff" stroke="#8bbdd8" stroke-width="1.4" '
        'stroke-linecap="round">'
        '<path d="M24 60v12M18 66h12M19.5 61.5l9 9M28.5 61.5l-9 9"/>'
        '<path d="M39 60v12M33 66h12M34.5 61.5l9 9M43.5 61.5l-9 9"/>'
        '<path d="M54 60v12M48 66h12M49.5 61.5l9 9M58.5 61.5l-9 9"/>'
        '</g>'
    )

    fiocchi_neve_deboli = (
        '<g fill="none" stroke="#b9d9ea" stroke-width="1.4" '
        'stroke-linecap="round">'
        '<path d="M31 60v10M26 65h10M27.5 61.5l7 7M34.5 61.5l-7 7"/>'
        '<path d="M48 60v10M43 65h10M44.5 61.5l7 7M51.5 61.5l-7 7"/>'
        '</g>'
    )

    if codice == 0:
        elementi = luna

    elif codice == 1:
        elementi = luna + nube_piccola

    elif codice == 2:
        elementi = luna + nube_grande

    elif codice == 3:
        elementi = nube_grande

    elif codice in (51, 53, 80):
        elementi = luna + nube_grande + gocce_deboli

    elif codice in (55, 56, 57, 61, 63, 65, 66, 67, 81, 82):
        elementi = luna + nube_grande + gocce

    elif codice in (71, 85):
        elementi = luna + nube_grande + fiocchi_neve_deboli

    elif codice in (73, 75, 77, 86):
        elementi = luna + nube_grande + fiocchi_neve

    else:
        return html.escape(icona_fallback)

    return (
        '<svg class="cml-weather-svg" viewBox="0 0 76 76" '
        'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{html.escape(descrizione, quote=True)} di notte">'
        f'{elementi}</svg>'
    )

def sintesi_oraria_html(ore):
    """
    Genera tre righe di sintesi a partire dal DataFrame 'ore':
      - Prossimo cambiamento significativo
      - Fascia più piovosa (2 ore consecutive)
      - Raffica massima e orario
    """
    if ore.empty:
        return ""

    # Assumiamo che 'ore' abbia già le colonne:
    # time, temperature_2m, precipitation, wind_gusts_10m, Scenario, Icona, Da, Notte

    # Filtriamo alle prossime 24 ore
    ora_rif = ore["time"].min()
    ore_24 = ore.loc[
        (ore["time"] >= ora_rif)
        & (ore["time"] < ora_rif + pd.Timedelta(hours=24))
    ].copy()

    if ore_24.empty:
        return ""

    # 1) Prossimo cambiamento significativo
    # Definiamo cambiamento quando:
    #   - scenario cambia (es. da sereno a nuvoloso/pioggia) OPPURE
    #   - |ΔT| >= 2 °C in un'ora OPPURE
    #   - |Δvento| >= 15 km/h in un'ora
    scenario_prev = None
    cambio_idx = None

    temp_ora = ore_24["temperature_2m"].values
    vento_ora = ore_24["wind_gusts_10m"].values
    scenario_ora = ore_24["Scenario"].values
    time_ora = ore_24["time"].values

    for i in range(1, len(ore_24)):
        dT = abs(float(temp_ora[i]) - float(temp_ora[i - 1]))
        dV = abs(float(vento_ora[i]) - float(vento_ora[i - 1]))
        s_curr = scenario_ora[i]
        s_prev = scenario_ora[i - 1]

        if scenario_prev is not None and s_curr != s_prev:
            cambio_idx = i
            break
        if dT >= 2.0 or dV >= 15.0:
            cambio_idx = i
            break

        scenario_prev = s_prev

    if cambio_idx is not None:
        ora_cambio = pd.Timestamp(time_ora[cambio_idx]).strftime("%H:%M")
        testo_cambio = (
            f"Condizioni in evoluzione dalle {ora_cambio}: "
            f"{scenario_ora[cambio_idx]}."
        )
    else:
        testo_cambio = (
            "Nessun cambiamento significativo previsto nelle prossime 24 ore."
        )

    # 2) Fascia più piovosa (due ore consecutive)
    precip = ore_24["precipitation"].fillna(0.0).values
    best_start = 0
    best_sum = -1.0

    for i in range(len(precip) - 1):
        s = float(precip[i]) + float(precip[i + 1])
        if s > best_sum:
            best_sum = s
            best_start = i

    if best_sum > 0:
        t_start = pd.Timestamp(time_ora[best_start]).strftime("%H:%M")
        t_end = pd.Timestamp(time_ora[best_start + 1]).strftime("%H:%M")
        testo_pioggia = (
            f"Fascia più piovosa: {t_start}–{t_end}, "
            f"cumulo previsto {best_sum:.1f} mm."
        )
    else:
        testo_pioggia = "Precipitazione oraria nulla o trascurabile nelle prossime 24 ore."

    # 3) Raffica massima e orario
    raffiche_valide = pd.to_numeric(
        ore_24["wind_gusts_10m"], errors="coerce"
    ).replace([float("inf"), float("-inf")], float("nan")).dropna()
    if raffiche_valide.empty:
        testo_vento = "Raffica massima non disponibile: dati del vento mancanti."
    else:
        idx_max_gust = raffiche_valide.idxmax()
        max_gust = float(raffiche_valide.loc[idx_max_gust])
        ora_max_gust = pd.Timestamp(
            ore_24.loc[idx_max_gust, "time"]
        ).strftime("%H:%M")
        testo_vento = (
            f"Raffica massima prevista: {max_gust:.0f} km/h intorno alle {ora_max_gust}."
        )

    return f"""
    <section class="cml-nowcast-box">
      <div class="cml-nowcast-head">
        <span class="cml-eyebrow">PROSSIME ORE</span>
        <h2>🗣️ Le prossime ore, in parole chiare</h2>
        <p>
          Sintesi automatica basata sulla previsione ICON-2I
          per le prossime 24 ore.
        </p>
      </div>

      <ul class="cml-nowcast-list">
        <li>
          <span class="cml-nowcast-bullet">🔹</span>
          <span>{html.escape(testo_cambio)}</span>
        </li>
        <li>
          <span class="cml-nowcast-bullet">🔹</span>
          <span>{html.escape(testo_pioggia)}</span>
        </li>
        <li>
          <span class="cml-nowcast-bullet">🔹</span>
          <span>{html.escape(testo_vento)}</span>
        </li>
      </ul>

      <div class="cml-nowcast-note">
        ℹ️ Questa sintesi è generata in modo automatico dai dati orari
        e non sostituisce avvisi ufficiali o bollettini di protezione civile.
      </div>
    </section>
    """

# =============================================================================
# NORMALIZZAZIONE E COMUNI COSTIERI
# =============================================================================

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


# =============================================================================
# GEOLOCALIZZAZIONE
# =============================================================================

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


# =============================================================================
# DOWNLOAD PREVISIONI
# =============================================================================

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


# =============================================================================
# PREPARAZIONE DATI
# =============================================================================

def calcola_dati_diurni(
    ore_giorno,
    alba,
    tramonto,
    ora_riferimento=None,
):
    if ore_giorno.empty:
        return 0, 0

    alba_ts = pd.to_datetime(alba, errors="coerce")
    tramonto_ts = pd.to_datetime(tramonto, errors="coerce")

    if pd.notna(alba_ts) and pd.notna(tramonto_ts):
        ore_diurne = ore_giorno.loc[
            (ore_giorno["time"] >= alba_ts)
            & (ore_giorno["time"] < tramonto_ts)
        ].copy()
    else:
        ore_diurne = ore_giorno.loc[
            (ore_giorno["time"].dt.hour >= 7)
            & (ore_giorno["time"].dt.hour <= 18)
        ].copy()

    if ore_diurne.empty:
        return 0, 0

    # Solo per oggi: conserva esclusivamente le ore diurne ancora future.
    if ora_riferimento is not None:
        ore_rimanenti = ore_diurne.loc[
            ore_diurne["time"] >= pd.Timestamp(ora_riferimento)
        ].copy()

        if not ore_rimanenti.empty:
            ore_diurne = ore_rimanenti

    nuvole = pd.to_numeric(
        ore_diurne["cloud_cover"],
        errors="coerce",
    ).fillna(0.0)

    nuvolosita_media = round(float(nuvole.mean()))

    if nuvolosita_media <= 25:
        return 0, nuvolosita_media

    if nuvolosita_media <= 40:
        return 1, nuvolosita_media

    if nuvolosita_media <= 70:
        return 2, nuvolosita_media

    return 3, nuvolosita_media

def calcola_codice_giornaliero(
    ore_giorno,
    codice_cielo,
    codice_daily=None,
    precipitazione_daily=None,
):
    """
    Sintesi delle 24 ore: i fenomeni significativi hanno priorità
    rispetto al cielo medio diurno. Gestisce anche valori NaN.
    """
    pioggia = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
    neve = {71, 73, 75, 77, 85, 86}
    temporali = {95, 96, 99}

    def numero_valido(valore):
        try:
            valore = float(valore)
        except (TypeError, ValueError):
            return None
        if pd.isna(valore) or not math.isfinite(valore):
            return None
        return valore

    def codice_valido(valore):
        valore = numero_valido(valore)
        return int(valore) if valore is not None else None

    daily = codice_valido(codice_daily)
    totale_daily = numero_valido(precipitazione_daily)
    totale_daily = totale_daily if totale_daily is not None else 0.0

    if ore_giorno is None or ore_giorno.empty:
        return daily if daily is not None else codice_cielo

    if "weather_code" in ore_giorno.columns:
        codici = pd.to_numeric(
            ore_giorno["weather_code"],
            errors="coerce",
        )
    else:
        codici = pd.Series(
            [pd.NA] * len(ore_giorno),
            index=ore_giorno.index,
        )

    if "precipitation" in ore_giorno.columns:
        precip = pd.to_numeric(
            ore_giorno["precipitation"],
            errors="coerce",
        ).clip(lower=0)
    else:
        precip = pd.Series(
            0.0,
            index=ore_giorno.index,
        )

    validi = codici.replace([float("inf"), float("-inf")], float("nan")).dropna().astype(int)
    totale_orario = float(precip.fillna(0.0).sum())
    totale = max(totale_orario, totale_daily)

    presenti_temporali = set(validi) & temporali
    if presenti_temporali:
        return max(presenti_temporali)

    if daily in temporali:
        return daily

    ore_bagnate = int((precip.fillna(0.0) >= 0.1).sum())
    ore_fenomeni = int(codici.isin(pioggia | neve).sum())
    significativo = (
        totale >= 0.5
        or ore_bagnate >= 2
        or ore_fenomeni >= 2
    )

    if significativo:
        fenomeni = validi[validi.isin(pioggia | neve)]

        if not fenomeni.empty:
            mask_neve = codici.isin(neve)
            mask_pioggia = codici.isin(pioggia)

            peso_neve = (
                int(mask_neve.sum()),
                float(precip[mask_neve].fillna(0.0).sum()),
            )
            peso_pioggia = (
                int(mask_pioggia.sum()),
                float(precip[mask_pioggia].fillna(0.0).sum()),
            )

            famiglia = neve if peso_neve > peso_pioggia else pioggia
            candidati = fenomeni[fenomeni.isin(famiglia)]

            if candidati.empty:
                candidati = fenomeni

            frequenze = candidati.value_counts()
            pari = frequenze[frequenze == frequenze.max()].index

            ordine = [
                51, 53, 55, 61, 63, 65, 80, 81, 82,
                56, 57, 66, 67, 77, 71, 73, 75, 85, 86,
            ]

            return int(
                max(
                    pari,
                    key=lambda c: ordine.index(c)
                    if c in ordine
                    else -1,
                )
            )

        if daily in pioggia | neve:
            return daily

        return 61

    if validi.empty and daily is not None:
        return daily

    return codice_cielo

def prepara_dati_terrestri(dati):
    ore_raw = pd.DataFrame(dati["hourly"])
    giorni = pd.DataFrame(dati["daily"])

    ore_raw["time"] = pd.to_datetime(
        ore_raw["time"]
    )

    giorni["time"] = pd.to_datetime(
        giorni["time"]
    )

    codici_prevalenti = []
    nuvolosita_giornaliera = []

    for _, riga_giorno in giorni.iterrows():
        data_giorno = riga_giorno["time"].date()

        ore_giorno = ore_raw.loc[
            ore_raw["time"].dt.date == data_giorno
        ]

        ora_locale = pd.Timestamp(
            datetime.now(FUSO_ORARIO).replace(tzinfo=None)
        ).floor("h")

        riferimento_giorno = (
            ora_locale
            if data_giorno == ora_locale.date()
            else None
        )

        codice, nubi = calcola_dati_diurni(
            ore_giorno,
            riga_giorno.get("sunrise"),
            riga_giorno.get("sunset"),
            riferimento_giorno,
        )

        codice = calcola_codice_giornaliero(
            ore_giorno,
            codice,
            riga_giorno.get("weather_code"),
            riga_giorno.get("precipitation_sum"),
        )
        codici_prevalenti.append(codice)
        nuvolosita_giornaliera.append(nubi)

    giorni["weather_code_prevalente"] = (
        codici_prevalenti
    )

    giorni["cloud_cover_diurno"] = (
        nuvolosita_giornaliera
    )

    giorni["Da"] = giorni[
        "wind_direction_10m_dominant"
    ].map(direzione)

    giorni["Fase lunare"] = giorni[
        "moon_phase"
    ].map(fase_lunare)

    ora_locale = datetime.now(
        FUSO_ORARIO
    ).replace(tzinfo=None)

    ore = ore_raw.loc[
        ore_raw["time"] >= pd.Timestamp(ora_locale).floor("h")
    ].copy()

    # Icone e scenari orari: codice weather_code orario di ICON-2I,
    # senza ricalcolare la classe del cielo dalla copertura nuvolosa.
    ore["Icona"] = ore["weather_code"].map(
        lambda codice: meteo(codice)[0]
    )

    ore["Scenario"] = ore["weather_code"].map(
        lambda codice: meteo(codice)[1]
    )

    ore["Da"] = ore["wind_direction_10m"].map(
        direzione
    )

    valori_notte = []

    for _, riga_ora in ore.iterrows():
        data_ora = riga_ora["time"].date()

        righe_giorno = giorni.loc[
            giorni["time"].dt.date == data_ora
        ]

        if righe_giorno.empty:
            valori_notte.append(False)
            continue

        giorno_corrente = righe_giorno.iloc[0]

        valori_notte.append(
            e_notte(
                riga_ora["time"],
                giorno_corrente.get("sunrise"),
                giorno_corrente.get("sunset"),
            )
        )

    ore["Notte"] = valori_notte

    return (
        ore.reset_index(drop=True),
        giorni.reset_index(drop=True),
    )


# =============================================================================
# STATO DEL MARE
# =============================================================================

def stato_mare_da_onda(altezza_onda):
    try:
        if altezza_onda is None or pd.isna(altezza_onda):
            return (
                "Non disponibile",
                "⚪",
                "cml-mare-nd",
            )

        altezza = float(altezza_onda)

        if altezza < 0.10:
            return "Calmo", "🟦", "cml-mare-calmo"

        if altezza < 0.50:
            return (
                "Quasi calmo",
                "🟦",
                "cml-mare-quasi-calmo",
            )

        if altezza < 1.25:
            return (
                "Poco mosso",
                "🟩",
                "cml-mare-poco-mosso",
            )

        if altezza < 2.50:
            return "Mosso", "🟨", "cml-mare-mosso"

        if altezza < 4.00:
            return (
                "Molto mosso",
                "🟧",
                "cml-mare-molto-mosso",
            )

        if altezza < 6.00:
            return (
                "Agitato",
                "🟥",
                "cml-mare-agitato",
            )

        return (
            "Molto agitato",
            "🟥",
            "cml-mare-molto-agitato",
        )

    except (TypeError, ValueError):
        return (
            "Non disponibile",
            "⚪",
            "cml-mare-nd",
        )


# =============================================================================
# INDICATORE METEOROLOGICO LOCALE
# =============================================================================

def valuta_rischio_locale(riga):
    precipitazione = float(
        riga.get("precipitation_sum", 0) or 0
    )

    raffica = float(
        riga.get("wind_gusts_10m_max", 0) or 0
    )

    # La nuvolosità media serve soltanto per l'icona della scheda giornaliera.
    # Per i rischi usa il codice giornaliero restituito da ICON-2I.
    codice_meteo = int(valore_finito(riga.get("weather_code"), -1))

    if (
        precipitazione >= 100
        or raffica >= 100
        or codice_meteo in [96, 99]
    ):
        if codice_meteo in [95, 96, 99]:
            return "rosso", "temporali"

        if raffica >= 100:
            return "rosso", "vento"

        return "rosso", "precipitazioni"

    if (
        precipitazione >= 50
        or raffica >= 70
        or codice_meteo in [95, 96, 99]
    ):
        if codice_meteo in [95, 96, 99]:
            return "arancione", "temporali"

        if raffica >= 70:
            return "arancione", "vento"

        return "arancione", "precipitazioni"

    if (
        precipitazione >= 20
        or raffica >= 50
        or codice_meteo in [80, 81, 82]
    ):
        if codice_meteo in [80, 81, 82]:
            return "giallo", "rovesci"

        if raffica >= 50:
            return "giallo", "vento"

        return "giallo", "precipitazioni"

    return "verde", "nessuna criticità"


def badge_rischio_html(livello, rischio):
    palette = {
        "verde": ("#4f6d7a", "○", "Indice meteo: nessun segnale"),
        "giallo": ("#2f6db3", "◔", "Indice meteo: attenzione"),
        "arancione": ("#6a3fb5", "◑", "Indice meteo: attenzione alta"),
        "rosso": ("#3b1f73", "●", "Indice meteo: attenzione molto alta"),
    }

    colore, icona, testo = palette.get(
        livello,
        palette["verde"],
    )

    return (
        f'<span class="cml-risk-badge" style="background:{colore};">'
        f"<span>{icona}</span>"
        f"<span>{html.escape(testo)} · {html.escape(rischio.title())}</span>"
        f"</span>"
    )



# =============================================================================
# OSSERVAZIONI REALI E CORREZIONE ADATTIVA
# =============================================================================

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


def riquadro_correzione_html(correzione):
    if not correzione:
        return ""

    distanza = (
        f"{correzione['distanza_km']:.1f} km"
        if correzione.get("distanza_km") is not None
        else "non disponibile"
    )

    bias_temp = correzione["bias_temp"]
    segno_temp = "+" if bias_temp >= 0 else ""

    bias_umidita = correzione["bias_umidita"]
    segno_umidita = "+" if bias_umidita >= 0 else ""

    rapporto = correzione["rapporto_vento"]
    variazione_vento = (rapporto - 1) * 100
    segno_vento = "+" if variazione_vento >= 0 else ""

    return f"""
    <section class="cml-nowcast-box">
      <div class="cml-nowcast-head">
        <span class="cml-eyebrow">CORREZIONE CON OSSERVAZIONI</span>
        <h2>🔎 Previsione adattata alle osservazioni</h2>
        <p>
          Le prossime 6 ore sono corrette usando le osservazioni recenti della stazione
          Meteostat più vicina e affidabile.
        </p>
      </div>

      <div class="cml-marine-grid">
        <div class="cml-marine-card">
          <span>📍 Stazione</span>
          <strong style="font-size:16px;">{html.escape(correzione['stazione'])}</strong>
          <small>Distanza: {html.escape(distanza)}</small>
        </div>

        <div class="cml-marine-card">
          <span>🕒 Ultima osservazione</span>
          <strong>{ora_it(correzione['ultima_osservazione'])}</strong>
          <small>{correzione['numero_osservazioni']} osservazioni nelle ultime 3 ore</small>
        </div>

        <div class="cml-marine-card">
          <span>🌡️ Correzione temperatura</span>
          <strong>{segno_temp}{bias_temp:.1f} °C</strong>
          <small>Bias medio osservato</small>
        </div>

        <div class="cml-marine-card">
          <span>💧 Correzione umidità</span>
          <strong>{segno_umidita}{bias_umidita:.0f} %</strong>
          <small>Bias medio osservato</small>
        </div>

        <div class="cml-marine-card">
          <span>💨 Correzione vento</span>
          <strong>{segno_vento}{variazione_vento:.0f} %</strong>
          <small>Rapporto osservazione/modello</small>
        </div>
      </div>

      <div class="cml-nowcast-note">
        ℹ️ La correzione è più forte nelle prossime ore e si attenua progressivamente entro 6 ore.
        È una stima automatica e non sostituisce avvisi ufficiali o valutazioni di sicurezza.
      </div>
    </section>
    """


# Pesi e soglie applicative: non sono criteri ufficiali di sicurezza.
CONFIG_ATTIVITA = {
    "escursionismo": {"pesi": {"pioggia":35,"raffiche":20,"temperatura":15,"vento":15,"neve":15}, "temp":(-5,8,26,34), "vento":(20,45), "raffiche":(35,70)},
    "ciclismo": {"pesi": {"pioggia":30,"vento":25,"raffiche":20,"temperatura":15,"nebbia":10}, "temp":(-2,10,27,34), "vento":(15,40), "raffiche":(30,60)},
    "spiaggia": {"pesi": {"temperatura":35,"pioggia":25,"nuvole":20,"vento":15,"raffiche":5}, "temp":(15,24,33,38), "nuvole":(45,90), "vento":(15,40), "raffiche":(30,55)},
    "fotografia": {"pesi": {"pioggia":30,"nuvole":30,"raffiche":20,"temperatura":10,"vento":10}, "temp":(-5,12,27,38), "nuvole":(70,95), "vento":(15,45), "raffiche":(25,55)},
    "corsa": {"pesi": {"percepita":35,"pioggia":25,"vento":20,"raffiche":20}, "temp":(-5,8,26,35), "vento":(15,40), "raffiche":(30,55)},
    "astronomia": {"pesi": {"nuvole":55,"pioggia":20,"vento":15,"raffiche":10}, "nuvole":(15,80), "vento":(10,35), "raffiche":(20,45)},
}


def valuta_attivita_pesata(dati, tipo):
    config = CONFIG_ATTIVITA[tipo]
    codice = valore_finito(dati.get("weather_code"), None)
    codice = int(codice) if codice is not None else None
    risultati = []
    limiti = []
    etichette = {"pioggia":"Precipitazione", "raffiche":"Raffiche", "vento":"Vento medio", "temperatura":"Temperatura", "percepita":"Temperatura percepita", "nuvole":"Nuvolosità", "neve":"Neve prevista", "nebbia":"Nebbia prevista"}
    campi = {"pioggia":"precipitation", "raffiche":"wind_gusts_10m", "vento":"wind_speed_10m", "temperatura":"temperature_2m", "percepita":"apparent_temperature", "nuvole":"cloud_cover"}
    unita = {"pioggia":"mm nel periodo del dato current", "raffiche":"km/h", "vento":"km/h", "temperatura":"°C", "percepita":"°C", "nuvole":"%"}

    def decrescente(x, ottimo, limite):
        return max(0.0, min(1.0, (limite-x)/(limite-ottimo)))

    for chiave, peso in config["pesi"].items():
        valore = codice if chiave in ("neve", "nebbia") else valore_finito(dati.get(campi[chiave]), None)
        indice = None
        soglia = ""
        testo = "Dato non disponibile"
        if chiave in ("neve", "nebbia"):
            soglia = "Codici nevosi 71, 73, 75, 77, 85, 86" if chiave == "neve" else "Codici nebbia 45, 48"
            if codice is not None:
                presente = codice in ({71,73,75,77,85,86} if chiave == "neve" else {45,48})
                indice = 0.0 if presente else 1.0
                testo = "Presente nel codice meteo" if presente else "Non indicata nel codice meteo"
        elif valore is not None:
            testo = f"{valore:.1f} {unita[chiave]}"
            if chiave == "pioggia":
                indice = decrescente(max(0.0,valore), 0.0, 2.0)
                soglia = "Indice 100 con 0 mm; indice 0 da 2 mm; variazione lineare"
                if codice in {51,53,55,56,57,61,63,65,66,67,80,81,82,71,73,75,77,85,86}:
                    indice = min(indice, 0.35)
                if codice in {95,96,99}: indice = 0.0
            elif chiave in ("vento", "raffiche", "nuvole"):
                ottimo, limite = config[chiave]
                indice = decrescente(valore, ottimo, limite)
                soglia = f"Indice 100 fino a {ottimo}; indice 0 da {limite}; variazione lineare"
            else:
                basso,ottimo_min,ottimo_max,alto = config["temp"]
                indice = 1.0 if ottimo_min <= valore <= ottimo_max else (max(0.0,(valore-basso)/(ottimo_min-basso)) if valore < ottimo_min else max(0.0,(alto-valore)/(alto-ottimo_max)))
                soglia = f"Ottimale {ottimo_min}–{ottimo_max} °C; indice 0 a {basso} / {alto} °C"
        risultati.append({"nome":etichette[chiave], "peso":peso, "indice":indice, "valore":testo, "soglia":soglia, "punti":None if indice is None else peso*indice, "persi":None if indice is None else peso*(1-indice)})

    # Vincoli cautelativi applicativi: il comfort non compensa eventi avversi.
    if codice in {95,96,99}: limiti.append((15,"Codice di temporale: punteggio massimo 15/100."))
    raffica = valore_finito(dati.get("wind_gusts_10m"), None)
    if raffica is not None and raffica >= config["raffiche"][1]:
        limiti.append((20,"Raffiche oltre il limite applicativo: punteggio massimo 20/100."))
    copertura = sum(r["peso"] for r in risultati if r["indice"] is not None)
    completo = copertura == 100 and codice is not None
    grezzo = sum(r["punti"] or 0.0 for r in risultati) if completo else None
    finale = None if grezzo is None else round(min([grezzo]+[l[0] for l in limiti]))
    return {"punteggio":finale,"grezzo":grezzo,"fattori":risultati,"limiti":limiti,"copertura":copertura,"codice_disponibile":codice is not None}


def punteggio_attivita_luogo(dati, tipo):
    return valuta_attivita_pesata(dati, tipo)["punteggio"]


def spiegazione_attivita_html(risultato):
    righe = []
    for r in risultato["fattori"]:
        indice = "N/D" if r["indice"] is None else f"{100*r['indice']:.0f}/100"
        punti = "N/D" if r["punti"] is None else f"{r['punti']:.1f} / {r['peso']}"
        persi = "N/D" if r["persi"] is None else f"{r['persi']:.1f}"
        righe.append(f"<tr><td>{html.escape(r['nome'])}</td><td>{html.escape(r['valore'])}</td><td>{r['peso']}%</td><td>{indice}</td><td>{punti}</td><td>{persi}</td></tr>")
    soglie = "".join(f"<li>{html.escape(r['nome'])}: {html.escape(r['soglia'] or 'Dato mancante: indice non calcolato')}</li>" for r in risultato["fattori"])
    if risultato["punteggio"] is None:
        motivo = "Dati incompleti: la percentuale non viene calcolata. I valori mancanti non sono interpretati come condizioni favorevoli."
    else:
        peggiori = sorted(risultato["fattori"], key=lambda r:r["persi"], reverse=True)
        peggiori = [r for r in peggiori if r["persi"]>0][:3]
        motivo = "Nessuna riduzione nei fattori considerati." if not peggiori else "I fattori che riducono maggiormente il punteggio sono: "+", ".join(f"{r['nome']} (−{r['persi']:.1f} punti)" for r in peggiori)+"."
        motivo += f" Media pesata prima dei vincoli: {risultato['grezzo']:.1f}/100."
    vincoli = " ".join(l[1] for l in risultato["limiti"])
    return f"<p>{html.escape(motivo)}</p><p>{html.escape(vincoli)}</p><div class='cml-table-wrap'><table class='cml-table'><thead><tr><th>Fattore</th><th>Dato</th><th>Peso</th><th>Indice</th><th>Punti ottenuti / massimi</th><th>Punti persi</th></tr></thead><tbody>{''.join(righe)}</tbody></table></div><details><summary>Soglie utilizzate</summary><ul>{soglie}</ul></details>"


def tabella_attivita_luogo_html(luogo, corrente, is_costiero=False):
    attivita = [
        ("escursionismo", "🥾 Escursionismo"),
        ("ciclismo", "🚴 Ciclismo"),
        ("fotografia", "📸 Fotografia"),
        ("corsa", "🏃 Corsa"),
        ("astronomia", "🔭 Astronomia"),
    ]

    if is_costiero:
        attivita.insert(2, ("spiaggia", "🏖️ Spiaggia"))

    righe = []
    spiegazioni = []
    for tipo, nome in attivita:
        risultato = valuta_attivita_pesata(corrente, tipo)
        punteggio = risultato["punteggio"]
        visualizzato = "N/D" if punteggio is None else f"{punteggio}%"
        spiegazioni.append(
            f"<details style='margin:12px 0;padding:12px;border:1px solid #d5e4e9;border-radius:12px'>"
            f"<summary>{html.escape(nome)} — Perché {visualizzato}?</summary>"
            + spiegazione_attivita_html(risultato) + "</details>"
        )
        colore = {
            4: "#16a34a", 3: "#84cc16", 2: "#eab308",
            1: "#f97316", 0: "#dc2626"
        }[min(4, (punteggio or 0) // 20)] if punteggio is not None else "#607987"
        righe.append(f"""
          <tr>
            <td>{html.escape(nome)}</td>
            <td>
              <div class="cml-activity-bar">
                <div class="cml-activity-bar-fill" style="width:{punteggio or 0}%;background:{colore};"></div>
              </div>
            </td>
            <td><b style="color:{colore};">{visualizzato}</b></td>
          </tr>
        """)

    nota_costa = (
        "La località risulta costiera: è inclusa anche la valutazione per la spiaggia."
        if is_costiero else
        "La località non risulta costiera: l’attività «Spiaggia» non è valutata."
    )

    return f"""
    <section class="cml-radar-box">
      <div class="cml-radar-head">
        <div>
          <h2>🏃 Attività per {html.escape(luogo)}</h2>
          <p>Indice di idoneità meteorologica sulle condizioni current del modello, non probabilità di riuscita. Pesi e soglie sono criteri applicativi non validati; non certificano la sicurezza.</p>
        </div>
      </div>
      <div class="cml-table-wrap">
        <table class="cml-table" style="min-width:620px;">
          <thead><tr><th>Attività</th><th>Idoneità meteorologica</th><th>Valore</th></tr></thead>
          <tbody>{''.join(righe)}</tbody>
        </table>
      </div>
      <h3>Perché questa percentuale?</h3>
      <p>Somma dei contributi: peso × indice / 100. Gli indici variano da 0 a 100. I vincoli cautelativi possono limitare il risultato. N/D indica dati insufficienti, non condizioni ottimali.</p>
      {''.join(spiegazioni)}
      <div class="cml-marine-note">
        ℹ️ {nota_costa} Valori stimati su dati ICON-2I della località selezionata.
        Per la spiaggia non è valutata la balneabilità; per l’astronomia non sono considerati
        buio e inquinamento luminoso.
      </div>
    </section>
    """

# =============================================================================
# GENERAZIONE HTML
# =============================================================================

def genera_app_completa(
    luogo,
    latitudine,
    longitudine,
    dati_terrestri,
    ore,
    giorni,
    dati_mare=None,
    distanza_mare_km=None,
    correzione_osservativa=None,
    is_costiero=False,
):
    corrente = dati_terrestri["current"]

    # Condizione attuale: icona coerente con la nuvolosità
    # quando non sono previsti fenomeni significativi.
    codice_corrente = corrente.get("weather_code")
    nuvolosita_corrente = corrente.get("cloud_cover")

    if (
        codice_corrente in (0, 1, 2, 3)
        and nuvolosita_corrente is not None
        and not pd.isna(nuvolosita_corrente)
    ):
        nuvolosita = float(nuvolosita_corrente)
        if nuvolosita <= 15: codice_corrente = 0
        elif nuvolosita <= 45: codice_corrente = 1
        elif nuvolosita <= 75: codice_corrente = 2
        else: codice_corrente = 3

    icona_corrente, descrizione_corrente = meteo(codice_corrente)
    sintesi_html = sintesi_oraria_html(ore)
    ora_corrente = corrente.get("time")
    alba_corrente = None
    tramonto_corrente = None

    if ora_corrente is not None and not giorni.empty:
        giorno_corrente = giorni.loc[
            giorni["time"].dt.date == pd.Timestamp(ora_corrente).date()
        ]
        if not giorno_corrente.empty:
            alba_corrente = giorno_corrente.iloc[0].get("sunrise")
            tramonto_corrente = giorno_corrente.iloc[0].get("sunset")

    icona_corrente_html = icona_meteo_html(
        corrente.get("weather_code"),
        e_notte(ora_corrente, alba_corrente, tramonto_corrente),
    )

    metriche = [
        (
            "🌡️",
            "Percepita",
            numero(
                corrente.get("apparent_temperature"),
                1,
                " °C",
            ),
        ),
        (
            "💧",
            "Umidità",
            numero(
                corrente.get("relative_humidity_2m"),
                0,
                " %",
            ),
        ),
        (
            "☁️",
            "Nuvolosità",
            numero(
                corrente.get("cloud_cover"),
                0,
                " %",
            ),
        ),
        (
            "💨",
            "Vento",
            numero(
                corrente.get("wind_speed_10m"),
                0,
                " km/h",
            ),
        ),
        (
            "🧭",
            "Provenienza",
            direzione(
                corrente.get("wind_direction_10m")
            ),
        ),
        (
            "🌬️",
            "Raffica",
            numero(
                corrente.get("wind_gusts_10m"),
                0,
                " km/h",
            ),
        ),
        (
            "🌀",
            "Pressione",
            numero(
                corrente.get("pressure_msl"),
                1,
                " hPa",
            ),
        ),
    ]

    metriche_html = "".join(
        f"""
        <div class="cml-metric-card">
          <div class="cml-metric-icon">{icona}</div>

          <div>
            <div class="cml-metric-label">
              {html.escape(etichetta)}
            </div>

            <div class="cml-metric-value">
              {html.escape(valore)}
            </div>
          </div>
        </div>
        """
        for icona, etichetta, valore in metriche
    )

    mare_html = ""

    if (
        dati_mare is not None
        and isinstance(dati_mare, dict)
        and dati_mare.get("current")
    ):
        corrente_mare = dati_mare["current"]
        orarie_mare = pd.DataFrame(dati_mare.get("hourly", {}))
        giornaliere_mare = pd.DataFrame(dati_mare.get("daily", {}))

        if not orarie_mare.empty and "time" in orarie_mare:
            orarie_mare["time"] = pd.to_datetime(orarie_mare["time"])

        altezza_onda = corrente_mare.get("wave_height")
        direzione_onda = corrente_mare.get("wave_direction")
        periodo_onda = corrente_mare.get("wave_period")
        altezza_mare_vento = corrente_mare.get("wind_wave_height")
        altezza_swell = corrente_mare.get("swell_wave_height")
        temperatura_mare = corrente_mare.get("sea_surface_temperature")

        stato_mare, icona_mare, classe_mare = stato_mare_da_onda(altezza_onda)

        previsioni_mare_html = ""
        if not orarie_mare.empty and "time" in orarie_mare:
            adesso_mare = pd.Timestamp(datetime.now(FUSO_ORARIO).replace(tzinfo=None))
            triorarie = orarie_mare.loc[
                (orarie_mare["time"].dt.hour % 3 == 0)
                & (orarie_mare["time"].dt.minute == 0)
                & (orarie_mare["time"] >= adesso_mare.floor("h"))
            ].sort_values("time").copy()
            sezioni_mare = []
            for data_mare, gruppo_mare in triorarie.groupby(triorarie["time"].dt.date):
                righe_mare = []
                for _, riga_mare in gruppo_mare.iterrows():
                    stato_prev, icona_prev, classe_prev = stato_mare_da_onda(riga_mare.get("wave_height"))
                    righe_mare.append(f"""
                      <tr>
                        <td>{ora_it(riga_mare.get("time"))}</td>
                        <td><span class="cml-marine-forecast-status {classe_prev}" style="margin:0;">
                          {icona_prev} {html.escape(stato_prev)}</span></td>
                        <td>{numero(riga_mare.get("wave_height"), 2)}</td>
                        <td>{direzione(riga_mare.get("wave_direction"))} · {numero(riga_mare.get("wave_direction"), 0, "°")}</td>
                        <td>{numero(riga_mare.get("sea_surface_temperature"), 1)}</td>
                      </tr>
                    """)
                sezioni_mare.append(f"""
                  <div class="cml-marine-forecast-date" style="margin-top:18px;">
                    {html.escape(data_it(data_mare).title())}
                  </div>
                  <div class="cml-table-wrap">
                    <table class="cml-table" style="min-width:680px;">
                      <thead><tr>
                        <th>Ora</th><th>Stazione del mare</th><th>Altezza onda m</th>
                        <th>Direzione onda</th><th>Temp. mare °C</th>
                      </tr></thead>
                      <tbody>{''.join(righe_mare)}</tbody>
                    </table>
                  </div>
                """)
            previsioni_mare_html = f"""
              <div class="cml-marine-forecast-title">🌊 Previsioni mare ogni 3 ore · prossimi {GIORNI_PREVISIONE} giorni</div>
              <p style="color:#607987;font-size:12px;">
                Orari locali Europe/Rome. Valori alle ore indicate, non medie su tre ore.
                Per oggi sono mostrate solo le scadenze dall’ora corrente in avanti.
              </p>
              {''.join(sezioni_mare) if sezioni_mare else '<p>Nessuna scadenza trioraria disponibile.</p>'}
            """
        else:
            previsioni_mare_html = '<p>Previsioni marine orarie non disponibili.</p>'

        mare_html = f"""
        <section class="cml-marine-box">
          <div class="cml-marine-head">
            <div>
              <span class="cml-eyebrow">BOLLETTINO COSTIERO</span>
              <h2>🌊 Vento e stato del mare</h2>
              <p>Stato attuale e previsione marina per il comune costiero di riferimento. La cella modellistica più vicina è a circa {numero(distanza_mare_km, 1, " km")} dal punto selezionato.</p>
            </div>
            <div class="cml-sea-status {classe_mare}">
              <span>{icona_mare}</span>
              <div><small>STATO DEL MARE</small><strong>{html.escape(stato_mare)}</strong></div>
            </div>
          </div>

          <div class="cml-marine-grid">
            <div class="cml-marine-card"><span>🌊 Altezza onda</span><strong>{numero(altezza_onda, 2, " m")}</strong><small>Onda significativa</small></div>
            <div class="cml-marine-card"><span>🧭 Provenienza onda</span><strong>{direzione(direzione_onda)}</strong><small>{numero(direzione_onda, 0, "°")}</small></div>
            <div class="cml-marine-card"><span>〰️ Periodo medio</span><strong>{numero(periodo_onda, 1, " s")}</strong><small>Intervallo medio d'onda</small></div>
            <div class="cml-marine-card"><span>💨 Mare del vento</span><strong>{numero(altezza_mare_vento, 2, " m")}</strong><small>Componente wind sea</small></div>
            <div class="cml-marine-card"><span>🌐 Mare di fondo</span><strong>{numero(altezza_swell, 2, " m")}</strong><small>Componente swell</small></div>
            <div class="cml-marine-card"><span>🌡️ Temperatura mare</span><strong>{numero(temperatura_mare, 1, " °C")}</strong><small>Temperatura superficiale</small></div>
          </div>

          {previsioni_mare_html}
          <div class="cml-marine-note">ℹ️ La direzione indica <b>da dove proviene</b> il moto ondoso. I valori sono stimati su griglia marina e possono essere meno rappresentativi presso baie, porti, promontori e costa molto frastagliata. Per navigazione e sicurezza consulta sempre fonti nautiche e avvisi ufficiali.</div>
        </section>
        """

    # ---------------------------------------------------------
    # SCHEDE GIORNALIERE
    # ---------------------------------------------------------

    etichette_giorni = ["OGGI", "DOMANI", "DOPODOMANI"]
    carte_html = []

    for indice, (_, riga) in enumerate(giorni.iterrows()):
        tag = (
            etichette_giorni[indice]
            if indice < len(etichette_giorni)
            else "PROSSIMAMENTE"
        )

        # La scheda sintetizza i fenomeni sulle 24 ore e il cielo medio diurno.
        codice_effettivo = riga.get(
            "weather_code_prevalente",
            riga.get("weather_code"),
        )

        try:
            if codice_effettivo is None or pd.isna(codice_effettivo):
                codice_effettivo = 3
            else:
                codice_effettivo = int(float(codice_effettivo))
        except (TypeError, ValueError):
            codice_effettivo = 3

        icona, descrizione = meteo(codice_effettivo)
        fase = html.escape(str(riga.get("Fase lunare", "🌙 Luna")))
        livello, rischio = valuta_rischio_locale(riga)
        badge_rischio = badge_rischio_html(livello, rischio)

        if codice_effettivo in [95, 96, 99]:
            classe_icona = "cml-icon-thunder"
        elif codice_effettivo in [71, 73, 75, 77, 85, 86]:
            classe_icona = "cml-icon-snow"
        elif (
            codice_effettivo in range(51, 68)
            or codice_effettivo in range(80, 83)
        ):
            classe_icona = "cml-icon-rain"
        elif codice_effettivo in [2, 3, 45, 48]:
            classe_icona = "cml-icon-cloud"
        else:
            classe_icona = "cml-icon-sun"

        carte_html.append(
            f"""
            <article class="cml-day-card" id="scheda-{riga['time'].date()}"
              role="button" tabindex="0" aria-expanded="false"
              aria-controls="dettaglio-{riga['time'].date()}"
              aria-label="Mostra la previsione oraria per {html.escape(data_it(riga['time']), quote=True)}"
              onclick="mostraGiorno('{riga['time'].date()}', this, event)"
              onkeydown="if (event.target === this && (event.key === 'Enter' || event.key === ' ')) {{ event.preventDefault(); mostraGiorno('{riga['time'].date()}', this, event); }}">
              <div class="cml-day-head">
                <span class="cml-day-tag">{tag}</span>

                <span class="cml-day-date">
                  {html.escape(data_it(riga["time"]))}
                </span>
              </div>

              <div class="cml-risk-row">
                {badge_rischio}
              </div>

              <div class="cml-day-weather">
                <div class="cml-day-icon {classe_icona}">
                  {icona}
                </div>

                <div>
                  <div class="cml-day-description">
                    {html.escape(descrizione)}
                  </div>

                  <div class="cml-day-moon">
                    {fase}
                  </div>
                </div>
              </div>

              <div class="cml-temperature-grid">
                <div class="cml-temp-box">
                  <span>MINIMA</span>

                  <strong class="cml-temp-min">
                    ↓ {numero(riga["temperature_2m_min"], 1, "°")}
                  </strong>
                </div>

                <div class="cml-temp-box">
                  <span>MASSIMA</span>

                  <strong class="cml-temp-max">
                    ↑ {numero(riga["temperature_2m_max"], 1, "°")}
                  </strong>
                </div>
              </div>

              <div class="cml-day-details">
                <div>
                  <span>☁️ Nuvolosità diurna</span>
                  <b>{numero(riga.get("cloud_cover_diurno"), 0, " %")}</b>
                </div>

                <div>
                  <span>🌧️ Precipitazione</span>
                  <b>{numero(riga.get("precipitation_sum"), 1, " mm")}</b>
                </div>

                <div>
                  <span>💨 Vento massimo</span>
                  <b>{numero(riga.get("wind_speed_10m_max"), 0, " km/h")}</b>
                </div>

                <div>
                  <span>🌬️ Raffica massima</span>
                  <b>{numero(riga.get("wind_gusts_10m_max"), 0, " km/h")}</b>
                </div>

                <div>
                  <span>🧭 Direzione dominante</span>
                  <b>{html.escape(str(riga.get("Da", "—")))}</b>
                </div>
              </div>

              <div class="cml-astro-grid">
                <div>
                  <span>☀️ Alba</span>
                  <b>{ora_it(riga.get("sunrise"))}</b>
                </div>

                <div>
                  <span>🌇 Tramonto</span>
                  <b>{ora_it(riga.get("sunset"))}</b>
                </div>

                <div>
                  <span>🌙 Sorge</span>
                  <b>{ora_it(riga.get("moonrise"))}</b>
                </div>

                <div>
                  <span>🌘 Tramonta</span>
                  <b>{ora_it(riga.get("moonset"))}</b>
                </div>
              </div>
              <!--DETTAGLIO-{riga['time'].date()}-->
            </article>
            """
        )

    # ---------------------------------------------------------
    # DETTAGLI ORARI (TABELLA PRIMA, GRAFICO DOPO)
    # ---------------------------------------------------------

    date_disponibili = sorted(ore["time"].dt.date.unique())

    if not date_disponibili:
        raise RuntimeError(
            "Non sono disponibili dati orari futuri per la località selezionata."
        )

    dati_grafici = {}
    tabelle_html = []

    for indice, data_giorno in enumerate(date_disponibili):
        chiave = str(data_giorno)

        ore_giorno = ore.loc[
            ore["time"].dt.date == data_giorno
        ].copy()

        dati_grafici[chiave] = {
            "ore": ore_giorno["time"].dt.strftime("%H:%M").tolist(),

            "temperatura": [
                round(float(valore), 1)
                if pd.notna(valore)
                else None
                for valore in ore_giorno["temperature_2m"].tolist()
            ],

            "nuvolosita": [
                round(float(valore), 0)
                if pd.notna(valore)
                else None
                for valore in ore_giorno["cloud_cover"].tolist()
            ],

            "precipitazione": [
                round(float(valore), 1)
                if pd.notna(valore)
                else None
                for valore in ore_giorno["precipitation"].tolist()
            ],

            "vento": [
                round(float(valore), 1)
                if pd.notna(valore)
                else None
                for valore in ore_giorno["wind_speed_10m"].tolist()
            ],

            "raffiche": [
                round(float(valore), 1)
                if pd.notna(valore)
                else None
                for valore in ore_giorno["wind_gusts_10m"].tolist()
            ],
        }

        righe_tabella = []

        for _, riga in ore_giorno.iterrows():
            classe_notte = (
                "cml-night-row"
                if bool(riga.get("Notte", False))
                else ""
            )
            icona_ora_html = icona_meteo_html(
                riga.get("weather_code"),
                bool(riga.get("Notte", False)),
            )

            righe_tabella.append(
                f"""
                <tr class="{classe_notte}">
                  <td>{riga["time"].strftime("%H:%M")}</td>

                  <td class="cml-scenario-cell">
                    <span class="cml-table-icon">
                      {icona_ora_html}
                    </span>

                    <span>
                      {html.escape(str(riga["Scenario"]))}
                    </span>
                  </td>

                  <td>{numero(riga["temperature_2m"], 1)}</td>
                  <td>{numero(riga["apparent_temperature"], 1)}</td>
                  <td>{numero(riga["precipitation"], 1)}</td>
                  <td>{numero(riga["wind_speed_10m"], 0)}</td>
                  <td>{html.escape(str(riga["Da"]))}</td>
                  <td>{numero(riga["wind_gusts_10m"], 0)}</td>
                  <td>{numero(riga["cloud_cover"], 0)}</td>
                  <td>{numero(riga["relative_humidity_2m"], 0)}</td>
                </tr>
                """
            )

        tabelle_html.append(
            f"""
            <div id="dettaglio-{chiave}" class="cml-day-inline-detail" hidden
                 onclick="event.stopPropagation()">

              <h3>
                🕒 Previsione oraria ·
                {html.escape(data_it(data_giorno).title())}
              </h3>

              <div class="cml-table-wrap">
                <table class="cml-table">
                  <thead>
                    <tr>
                      <th>Ora</th>
                      <th>Scenario</th>
                      <th>Temp. °C</th>
                      <th>Percepita °C</th>
                      <th>Pioggia mm</th>
                      <th>Vento km/h</th>
                      <th>Da</th>
                      <th>Raffica km/h</th>
                      <th>Nubi %</th>
                      <th>Umidità %</th>
                    </tr>
                  </thead>

                  <tbody>
                    {''.join(righe_tabella)}
                  </tbody>
                </table>
              </div>

              <div class="cml-chart-box">
              <div class="cml-chart-title">
                🌡️ Andamento della temperatura
              </div>

              <div class="cml-chart-subtitle">
                Temperatura prevista nelle diverse ore della giornata.
              </div>

              <div class="cml-chart-canvas-wrap">
                <canvas id="temperaturaChart-{chiave}"></canvas>
              </div>
            </div>

            <div class="cml-chart-box">
              <div class="cml-chart-title">
                ☁️ Nuvolosità e precipitazioni
              </div>

              <div class="cml-chart-subtitle">
                Nuvolosità prevista e precipitazione oraria.
              </div>

              <div class="cml-chart-canvas-wrap">
                <canvas id="nuvolositaPrecipitazioniChart-{chiave}"></canvas>
              </div>
            </div>

            <div class="cml-chart-box">
              <div class="cml-chart-title">
                💨 Andamento del vento
              </div>

              <div class="cml-chart-subtitle">
                Vento medio e raffiche previste.
              </div>

              <div class="cml-chart-canvas-wrap">
                <canvas id="ventoChart-{chiave}"></canvas>
              </div>
            </div>

            </div>
            """
        )

    dettagli_per_data = {
        str(data): dettaglio
        for data, dettaglio in zip(date_disponibili, tabelle_html)
    }

    carte_html = [
        carta.replace(
            f"<!--DETTAGLIO-{riga['time'].date()}-->",
            dettagli_per_data.get(
                str(riga['time'].date()),
                '<div class="cml-day-inline-empty">Nessuna ora futura disponibile per questo giorno.</div>',
            ),
        )
        for carta, (_, riga) in zip(carte_html, giorni.iterrows())
    ]

    dati_grafici_json = json.dumps(dati_grafici, ensure_ascii=False)

    # ---------------------------------------------------------
    # HTML COMPLETO CON HOME / PREVISIONI / RADAR
    # ---------------------------------------------------------

    riquadro_correzione = riquadro_correzione_html(
        correzione_osservativa
    )

    if "precipitation" not in corrente or corrente.get("precipitation") is None:
        try:
            ora_corrente = pd.Timestamp(
                corrente.get("time")
            ).floor("h")
    
            pioggia_ora = ore.loc[
                ore["time"] == ora_corrente,
                "precipitation",
            ]
    
            corrente["precipitation"] = (
                float(pioggia_ora.iloc[0])
                if not pioggia_ora.empty
                and pd.notna(pioggia_ora.iloc[0])
                else 0.0
            )
        except Exception:
            corrente["precipitation"] = 0.0
    
    tabella_attivita_luogo = tabella_attivita_luogo_html(
        luogo,
        corrente,
        is_costiero,
    )

    codice_sfondo = int(
        valore_finito(
            corrente.get("weather_code"),
            -1,
        )
    )

    ora_sfondo = pd.to_datetime(
        corrente.get("time"),
        errors="coerce",
    )

    notte_sfondo = False

    if pd.notna(ora_sfondo) and not giorni.empty:
        giorno_sfondo = giorni.loc[
            giorni["time"].dt.date == ora_sfondo.date()
        ]

        if not giorno_sfondo.empty:
            notte_sfondo = e_notte(
                ora_sfondo,
                giorno_sfondo.iloc[0].get("sunrise"),
                giorno_sfondo.iloc[0].get("sunset"),
            )

    if codice_sfondo in (95, 96, 99):
        classe_sfondo_meteo = "cml-bg-thunder"

    elif codice_sfondo in (71, 73, 75, 77, 85, 86):
        classe_sfondo_meteo = "cml-bg-snow"

    elif codice_sfondo in (
        51, 53, 55, 56, 57,
        61, 63, 65, 66, 67,
        80, 81, 82,
    ):
        classe_sfondo_meteo = "cml-bg-rain"

    elif codice_sfondo in (45, 48):
        classe_sfondo_meteo = "cml-bg-fog"

    elif codice_sfondo in (2, 3):
        classe_sfondo_meteo = "cml-bg-cloud"

    elif notte_sfondo:
        classe_sfondo_meteo = "cml-bg-night"

    else:
        classe_sfondo_meteo = "cml-bg-clear"
        
    script_app = (
        leggi_static("app.js")
        .replace("__CML_DATI_GRAFICI__", dati_grafici_json)
        .replace("__CML_LAT__", str(latitudine))
        .replace("__CML_LON__", str(longitudine))
        .replace("__CML_LUOGO_HTML__", html.escape(luogo))
    )

    documento_html = f"""
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
{STILE_CSS}
</style>
</head>

<body>

<!-- ===================== HOME ===================== -->
<section id="cml-home" class="cml-view">

  <section class="cml-home-hero">
    <div class="cml-hero-backdrop" aria-hidden="true">
      <div class="cml-hero-glow"></div>
      <div class="cml-hero-grid"></div>
    </div>

    <div class="cml-hero-content">
      <div class="cml-brand">
        <span class="cml-brand-mark"></span>
        CALABRIA · METEOROLOGIA LOCALE
      </div>

      <h1>
        <span class="cml-hero-title-line">Calabria</span>
        <span class="cml-hero-title-accent">Meteo Lab</span>
      </h1>

      <p class="cml-hero-lead">
        Previsioni locali, radar delle precipitazioni, satellite e fulminazioni
        per scegliere la località e leggere il tempo in Calabria.
      </p>

      <div class="cml-hero-badges">
        <span class="cml-hero-badge">🌦️ ICON-2I</span>
        <span class="cml-hero-badge">📡 Radar live</span>
        <span class="cml-hero-badge">🛰️ Satellite</span>
        <span class="cml-hero-badge">⚡ Fulmini</span>
      </div>
    </div>

    <div class="cml-hero-visual" aria-hidden="true">
      <svg class="cml-hero-scene" viewBox="0 0 420 260" role="img" aria-label="Illustrazione meteorologica della Calabria">
        <defs>
          <linearGradient id="cmlSky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#0b3f5c"/>
            <stop offset="55%" stop-color="#12708c"/>
            <stop offset="100%" stop-color="#22a3ad"/>
          </linearGradient>
          <linearGradient id="cmlSea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#0d6d86"/>
            <stop offset="100%" stop-color="#063a4d"/>
          </linearGradient>
          <linearGradient id="cmlLand" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#2f7a5b"/>
            <stop offset="100%" stop-color="#14453a"/>
          </linearGradient>
          <radialGradient id="cmlSun" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#ffe89a"/>
            <stop offset="70%" stop-color="#ffc247"/>
            <stop offset="100%" stop-color="#ff9d2e"/>
          </radialGradient>
        </defs>

        <rect width="420" height="260" fill="url(#cmlSky)"/>
        <!-- Radar meteorologico in lontananza -->
        <g class="cml-radar-sweep" opacity=".30">
          <circle cx="345" cy="155" r="72" fill="none"
                  stroke="#9ee8ed" stroke-width="1.4"/>
          <circle cx="345" cy="155" r="48" fill="none"
                  stroke="#9ee8ed" stroke-width="1.1"/>
          <circle cx="345" cy="155" r="24" fill="none"
                  stroke="#9ee8ed" stroke-width="1"/>
          <line x1="345" y1="155" x2="409" y2="155"
                stroke="#d7ffff" stroke-width="1.5"/>
        </g>
        
        <!-- Particelle atmosferiche -->
        <g class="cml-hero-particles" fill="#d8fbff">
          <circle cx="44" cy="52" r="2"/>
          <circle cx="68" cy="178" r="1.6"/>
          <circle cx="244" cy="31" r="1.5"/>
          <circle cx="386" cy="126" r="2"/>
          <circle cx="256" cy="175" r="1.4"/>
          <circle cx="29" cy="213" r="1.3"/>
        </g>
        
        <!-- Fulmine discreto -->
        <path
          class="cml-hero-lightning"
          d="M252 104 L234 142 L251 142 L239 172 L274 126 L256 126 Z"
          fill="#fff1a3"
          opacity="0"
        />
        <g class="cml-hero-sun">
          <circle cx="318" cy="72" r="34" fill="url(#cmlSun)"/>
          <g class="cml-hero-rays" stroke="#ffd166" stroke-width="4" stroke-linecap="round">
            <line x1="318" y1="16" x2="318" y2="28"/>
            <line x1="318" y1="116" x2="318" y2="128"/>
            <line x1="262" y1="72" x2="274" y2="72"/>
            <line x1="362" y1="72" x2="374" y2="72"/>
            <line x1="279" y1="33" x2="288" y2="42"/>
            <line x1="348" y1="102" x2="357" y2="111"/>
            <line x1="357" y1="33" x2="348" y2="42"/>
            <line x1="288" y1="102" x2="279" y2="111"/>
          </g>
        </g>

        <g class="cml-hero-cloud">
          <path d="M116 96c0-16 13-29 29-29 8 0 15 3 20 9 5-12 17-20 31-20 19 0 34 15 34 34 0 2 0 4-1 6h-113z" fill="#eaf4f8" opacity=".94"/>
          <path d="M70 122c0-12 10-22 22-22 6 0 11 2 15 7 4-9 13-15 24-15 14 0 26 12 26 26 0 2 0 3-1 4H70z" fill="#dcebf1" opacity=".82"/>
        </g>

        <g class="cml-hero-rain" stroke="#8ed8f2" stroke-width="4" stroke-linecap="round">
          <line x1="112" y1="140" x2="104" y2="162"/>
          <line x1="140" y1="140" x2="132" y2="162"/>
          <line x1="168" y1="140" x2="160" y2="162"/>
          <line x1="196" y1="140" x2="188" y2="162"/>
        </g>

        <path d="M0 197c48-38 92-58 141-52 40 5 69 24 110 18 49-7 89-33 169-24v121H0z" fill="url(#cmlLand)"/>
        <path d="M0 226c58-25 111-34 168-22 55 12 96 7 138-11 43-18 78-20 114-10v87H0z" fill="url(#cmlSea)"/>
        <g class="cml-hero-waves" stroke="#9be3ef" stroke-width="3" stroke-linecap="round" opacity=".7">
          <path d="M35 236c14-7 28-7 42 0"/>
          <path d="M112 247c14-7 28-7 42 0"/>
          <path d="M208 238c14-7 28-7 42 0"/>
          <path d="M292 250c14-7 28-7 42 0"/>
        </g>
      </svg>
    </div>
  </section>

  <section class="cml-radar-box">
    <div class="cml-radar-head">
      <div>
        <h2>📡 Radar precipitazioni live</h2>

        <p>
          Sequenza radar RainViewer centrata sulla località selezionata:
          {html.escape(luogo)}.
        </p>
      </div>

      <button
        class="cml-radar-btn"
        id="btn-play"
        type="button"
        onclick="togglePlayRadar()"
      >
        ⏸ Pausa
      </button>
    </div>

    <div id="radar-map"></div>

    <div class="cml-radar-footer">
      <span>
        🛰️ Base cartografica OpenStreetMap · Overlay radar RainViewer
      </span>

      <span>
        Frame:
        <span id="radar-timestamp" class="cml-radar-time">
          caricamento...
        </span>
      </span>
    </div>
  </section>

  <div class="cml-note">
    ℹ️ Il radar mostra le precipitazioni osservate dai frame disponibili.
    Non costituisce un bollettino di allerta né una previsione ufficiale.
  </div>

  <!-- ===================== SATELLITE NUVOLOSITÀ ===================== -->
  <section class="cml-radar-box">
    <div class="cml-radar-head">
      <div>
        <h2>🛰️ Satellite · Nuvolosità</h2>
        <p>
          Immagini satellitari delle nubi, centrate sulla località
          selezionata: {html.escape(luogo)}.
          Controlla l’orario dell’immagine nella mappa.
        </p>
      </div>
    </div>

    <iframe
      title="Satellite della nuvolosità"
      loading="lazy"
      src="https://embed.windy.com/embed2.html?lat={latitudine}&amp;lon={longitudine}&amp;zoom=7&amp;level=surface&amp;overlay=satellite&amp;product=satellite&amp;menu=&amp;message=&amp;marker=true&amp;calendar=now&amp;pressure=&amp;type=map&amp;location=coordinates&amp;detail=&amp;metricWind=km%2Fh&amp;metricTemp=%C2%B0C"
      style="display:block;width:100%;height:520px;border:1px solid #d8e7eb;border-radius:16px;"
      allowfullscreen
    ></iframe>

    <div class="cml-radar-footer">
      <span>🛰️ Visualizzazione satellitare · Windy</span>
      <a
        href="https://www.windy.com/-Satellite-satellite?satellite,{latitudine},{longitudine},7"
        target="_blank"
        rel="noopener noreferrer"
      >
        Apri il satellite su Windy ↗
      </a>
    </div>

    <div class="cml-marine-note">
      ℹ️ Le immagini satellitari mostrano le nubi:
      non sono una misura diretta della pioggia al suolo.
      Se il widget non mostra il satellite, usa il collegamento
      oppure configura il riquadro dal generatore ufficiale Windy.
    </div>
  </section>

  <!-- ===================== FULMINAZIONI ===================== -->
  <section class="cml-radar-box">
    <div class="cml-radar-head">
      <div>
        <h2>⚡ Fulminazioni osservate</h2>
        <p>
          Scariche rilevate dalla rete Blitzortung,
          con mappa centrata su {html.escape(luogo)}.
        </p>
      </div>
    </div>

    <iframe
      title="Mappa delle fulminazioni Blitzortung"
      loading="lazy"
      src="https://map.blitzortung.org/index.php?interactive=1&amp;NavigationControl=1&amp;FullScreenControl=1&amp;Cookies=0&amp;InfoDiv=1&amp;MenuButtonDiv=1&amp;ScaleControl=1#7/{latitudine}/{longitudine}"
      style="display:block;width:100%;height:520px;border:1px solid #d8e7eb;border-radius:16px;"
      allowfullscreen
    ></iframe>

    <div class="cml-radar-footer">
      <span>⚡ Dati: Blitzortung.org e collaboratori</span>
      <a
        href="https://map.blitzortung.org/#7/{latitudine}/{longitudine}"
        target="_blank"
        rel="noopener noreferrer"
      >
        Apri la mappa dei fulmini ↗
      </a>
    </div>

    <div class="cml-marine-note">
      ℹ️ La mappa mostra le scariche rilevate dalla rete,
      non una previsione dei fulmini.
      L’assenza di scariche visualizzate non garantisce
      l’assenza di rischio temporalesco.
      Consulta gli avvisi ufficiali.
    </div>
  </section>

</section>



  <section class="cml-home-actions">

    <button
      class="cml-home-choice"
      type="button"
      onclick="mostraVista('previsioni')"
    >
      <div class="cml-home-choice-icon">📅</div>

      <h2>Previsioni orarie</h2>

      <p>
        Consulta condizioni attuali, temperatura, vento, precipitazioni,
        tabelle ora per ora e grafici per i prossimi tre giorni.
      </p>

      <span>Apri previsioni →</span>
    </button>

    <button
      class="cml-home-choice activities"
      type="button"
      onclick="apriVistaAttivita()"
    >
      <div class="cml-home-choice-icon">🏃</div>

      <h2>Attività</h2>

      <p>
        Scopri quali attività sono più adatte alle condizioni meteorologiche
        previste nelle diverse zone della Calabria.
      </p>

      <span>Apri attività →</span>
    </button>

  </section>

</section>


<!-- ===================== PREVISIONI ===================== -->
<section
  id="cml-previsioni"
  class="cml-view {classe_sfondo_meteo}"
  hidden
>

  <div class="cml-nav-bar">
    <button
      class="cml-back-btn"
      type="button"
      onclick="mostraVista('home')"
    >
      ← Torna alla home
    </button>

    <span class="cml-nav-title">
      📅 Previsioni orarie · {html.escape(luogo)}
    </span>
  </div>

  <section class="cml-hero">
    <div class="cml-brand">
      <span class="cml-brand-mark"></span>
      CALABRIA · METEOROLOGIA LOCALE
    </div>

    <h1>Previsioni per {html.escape(luogo)}</h1>

    <p>
      Previsioni ad alta risoluzione per la località selezionata:
      temperatura, cielo, vento, precipitazioni e sviluppo delle
      prossime 72 ore.
    </p>
  </section>

  <section class="cml-current">
    <div class="cml-current-main">
      <div class="cml-place-block">

        <div class="cml-kicker">
          <span class="cml-live-dot"></span>
          ICON-2I · PREVISIONE LOCALE
        </div>

        <h2>📍 {html.escape(luogo)}</h2>

        <div class="cml-condition">
          <span class="cml-current-weather-icon">
            {icona_corrente_html}
          </span>

          {html.escape(descrizione_corrente)}
        </div>

      </div>

      <div class="cml-temperature">
        <span>{numero(corrente.get("temperature_2m"), 1, "")}</span>
        <small>°C</small>
      </div>
    </div>

    <div class="cml-metrics">
      {metriche_html}
    </div>

    <div class="cml-current-footer">
      <span>
        ◷ Valido alle
        <b>{html.escape(str(corrente.get("time", "—")))}</b>
      </span>

      <span>
        ◉ Fuso
        <b>Europe/Rome</b>
      </span>

      <span>
        ◌ Fonte
        <b>ItaliaMeteo–ARPAE</b>
      </span>
    </div>
  </section>

  {mare_html}
  {riquadro_correzione}
  {sintesi_html}

  <section class="cml-three-days">
    <div class="cml-section-title">
      <div>
        <span>ORIZZONTE PREVISIONALE</span>

        <h2>📅 I prossimi tre giorni</h2>

        <p>
          Premi sul giorno che ti interessa per visualizzare prima
          la previsione oraria e poi il grafico.
        </p>
      </div>

      <div class="cml-pill">72 ore</div>
    </div>

    <div class="cml-days-grid">
      {''.join(carte_html)}
    </div>
    <div class="cml-note">
      ℹ️ L'«indice meteo» è una stima automatica di questa app, <b>non un'allerta ufficiale</b>.
      Per le allerte consulta il
      <a href="https://www.cfd.calabria.it/" target="_blank" rel="noopener">Centro Funzionale Multirischi – ARPACAL</a>.
    </div>

    <div class="cml-note">
      ℹ️ Le icone sintetizzano i fenomeni significativi sulle 24 ore;
      in assenza di fenomeni mostrano il cielo medio diurno.
      La nuvolosità riportata è la media diurna. Temperature, precipitazioni e vento
      rappresentano estremi o cumulati sulle 24 ore.
    </div>
  </section>

  <div class="cml-note">
    ℹ️ <b>ICON-2I:</b> modello deterministico ad alta risoluzione
    di ItaliaMeteo–ARPAE. I dati terrestri sono forniti attraverso
    Open-Meteo.
  </div>

</section>


<!-- ===================== RADAR ===================== -->



<!-- ===================== ATTIVITÀ ===================== -->
<section id="cml-attivita" class="cml-view" hidden>

  <div class="cml-nav-bar">
    <button
      class="cml-back-btn"
      type="button"
      onclick="mostraVista('home')"
    >
      ← Torna alla home
    </button>

    <span class="cml-nav-title">
      🏃 Attività consigliate · {html.escape(luogo)}
    </span>
  </div>

  {tabella_attivita_luogo}

</section>

<!-- ===================== SCRIPT ===================== -->
<script>
{script_app}
</script>

<!-- ===================== COPYRIGHT ===================== -->
<footer class="cml-copyright">
  <div><strong>Calabria Meteo Lab</strong> · © 2026 Saverio Campanella · Tutti i diritti riservati</div>
  <div>Codice, interfaccia e contenuti dell’applicazione sono protetti da copyright.</div>
</footer>

</body>
</html>
"""

    return aggiungi_dashboard_interattiva(documento_html, ore, luogo)



def aggiungi_dashboard_interattiva(documento_html, ore, luogo):
    campi = ["time", "temperature_2m", "apparent_temperature", "precipitation",
             "wind_speed_10m", "wind_gusts_10m", "cloud_cover", "relative_humidity_2m", "Scenario", "Notte"]
    tabella = ore.reindex(columns=campi).copy()
    tabella["time"] = pd.to_datetime(tabella["time"]).dt.strftime("%Y-%m-%dT%H:%M")
    dati_json = tabella.to_json(orient="records", force_ascii=False).replace("<", "\\u003c")
    interfaccia = leggi_static("esploratore.html")
    interfaccia = interfaccia.replace("__EX_DATA__", dati_json).replace(
        "__EX_PLACE__", json.dumps(str(luogo), ensure_ascii=False).replace("<", "\\u003c")
    )
    return documento_html.replace("</body>", interfaccia + "\n</body>")


# =============================================================================
# INTERFACCIA STREAMLIT
# =============================================================================

try:
    COMUNI_COSTIERI = carica_comuni_costieri()

except (FileNotFoundError, ValueError) as errore_costieri:
    st.error(str(errore_costieri))
    st.stop()

st.markdown("## 🔎 Seleziona località calabrese")

with st.form("search_form", clear_on_submit=False):
    colonna_input, colonna_bottone = st.columns([4, 1])

    with colonna_input:
        testo_localita = st.text_input(
            "Località",
            value="",
            placeholder="",
            label_visibility="collapsed",
        )

    with colonna_bottone:
        cerca_localita = st.form_submit_button(
            "Aggiorna previsione",
            use_container_width=True,
            type="primary",
        )


# =============================================================================
# CONTROLLO INPUT
# =============================================================================

if not testo_localita.strip():
    st.info(
        "Inserisci una località calabrese e premi «Aggiorna previsione» "
        "per visualizzare le previsioni."
    )
    st.stop()


if not cerca_localita and "previsione_caricata" not in st.session_state:
    st.stop()


# =============================================================================
# ESECUZIONE
# =============================================================================

try:
    (
        luogo,
        latitudine,
        longitudine,
        comune_amministrativo,
    ) = risolvi_localita(testo_localita)

    with st.spinner(
        f"Elaborazione previsione ICON-2I e radar per {luogo}..."
    ):
        dati_terrestri = scarica_previsione_terrestre(
            latitudine,
            longitudine,
        )

        dati_orari, dati_giornalieri = (
            prepara_dati_terrestri(
                dati_terrestri
            )
        )

        osservazioni, stazione_oss, ultima_osservazione = (
            scarica_osservazioni_meteostat(
                latitudine,
                longitudine,
                dati_terrestri.get("elevation"),
            )
        )

        correzione_osservativa = calcola_correzione_osservativa(
            dati_terrestri,
            osservazioni,
            stazione_oss,
            ultima_osservazione,
        )

        # Ricalcola le serie dopo la correzione osservativa
        dati_orari, dati_giornalieri = (
            prepara_dati_terrestri(
                dati_terrestri
            )
        )

        dati_mare = None
        distanza_mare_km = None

        is_costiero = comune_e_costiero(
            comune_amministrativo,
            COMUNI_COSTIERI,
        )

        if is_costiero:
            try:
                (
                    dati_mare,
                    distanza_mare_km,
                ) = scarica_previsione_mare(
                    latitudine,
                    longitudine,
                )

            except RuntimeError:
                dati_mare = None
                distanza_mare_km = None

    st.session_state.previsione_caricata = True
    ore_riserva = dati_terrestri.get("_ore_riserva") or []
    if dati_terrestri.get("_fonte", "ICON-2I") != "ICON-2I":
        st.warning(f"⚠️ Fonte dei dati: {dati_terrestri['_fonte']}.")
    elif ore_riserva:
        st.info(
            f"ℹ️ {len(ore_riserva)} ore non coperte da ICON-2I sono state completate "
            f"con ICON-EU (a partire dalle {pd.Timestamp(ore_riserva[0]).strftime('%d/%m %H:%M')})."
        )
    documento = genera_app_completa(
        luogo,
        latitudine,
        longitudine,
        dati_terrestri,
        dati_orari,
        dati_giornalieri,
        dati_mare,
        distanza_mare_km,
        correzione_osservativa,
        is_costiero,
    )
    documento = aggiungi_home_viva(documento)

    documento = aggiungi_sfondo_meteo(
        documento,
        luogo,
        dati_terrestri,
        dati_orari,
        dati_giornalieri,
        is_costiero=is_costiero,
    )
    
    components.html(
        documento,
        height=4300,
        scrolling=True,
    )
    

except Exception as errore:
    st.error(str(errore))
