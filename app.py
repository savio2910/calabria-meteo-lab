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
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

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

      .block-container {{
      max-width: none !important;
      width: 100% !important;
      padding: 0.5rem 1rem 2rem 1rem !important;
      }}

      [data-testid="stAppViewContainer"] {{
        background: #eef5f8;
      }}

      [data-testid="stHeader"] {{
        background: transparent;
      }}

      iframe {{
        background: #eef5f8 !important;
      }}
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

FILE_COMUNI_COSTIERI = Path("comuni_costieri_calabria.csv")

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
# COSTANTI PER IL PERCORSO METEO‑ASSISTITO
# =============================================================================

API_GEOCODIFICA_URL = "https://nominatim.openstreetmap.org/search"
API_ROUTING_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
ORARI_DA_CONFRONTARE = [-120, -90, -60, -30, 0, 30, 60]


# =============================================================================
# FORMATTAZIONE
# =============================================================================

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
            return "❔", "Non disponibile"

        return CODICI_METEO.get(
            int(codice),
            ("❔", "Non disponibile"),
        )

    except (TypeError, ValueError):
        return "❔", "Non disponibile"


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
    idx_max_gust = int(ore_24["wind_gusts_10m"].idxmax())
    max_gust = float(ore_24.loc[idx_max_gust, "wind_gusts_10m"])
    ora_max_gust = pd.Timestamp(ore_24.loc[idx_max_gust, "time"]).strftime("%H:%M")

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

@st.cache_data(ttl=600, show_spinner=False)
def scarica_previsione_terrestre(latitudine, longitudine):
    parametri = {
        "latitude": latitudine,
        "longitude": longitudine,
        "models": MODELLO_TERRESTRE,
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
        risposta = requests.get(
            API_METEO_URL,
            params=parametri,
            timeout=25,
        )

        risposta.raise_for_status()

        return risposta.json()

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Errore nella ricezione dei dati ICON-2I: {exc}"
        ) from exc


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
        risposta = requests.get(
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
    codice_meteo = int(riga.get("weather_code") or 0)

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
        "verde": (
            "#12855c",
            "✅",
            "Nessuna criticità stimata",
        ),
        "giallo": (
            "#b77906",
            "⚠️",
            "Attenzione meteorologica",
        ),
        "arancione": (
            "#d85d05",
            "🟠",
            "Rischio meteorologico elevato",
        ),
        "rosso": (
            "#be2635",
            "🔴",
            "Rischio meteorologico molto elevato",
        ),
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
def scarica_osservazioni_meteostat(latitudine, longitudine):
    """Scarica le osservazioni delle ultime 6 ore dalla stazione Meteostat più vicina."""
    if not METEOSTAT_DISPONIBILE:
        return None, None, None

    try:
        stazioni = Stations().nearby(latitudine, longitudine)
        elenco = stazioni.fetch(5)

        if elenco.empty:
            return None, None, None

        fine = pd.Timestamp.utcnow().tz_localize(None).floor("h")
        inizio = fine - pd.Timedelta(hours=6)

        for _, stazione in elenco.iterrows():
            try:
                dati = Hourly(
                    stazione.name,
                    start=inizio.to_pydatetime(),
                    end=fine.to_pydatetime(),
                ).fetch()

                if dati.empty:
                    continue

                dati = dati.dropna(subset=["temp"], how="all")

                if dati.empty:
                    continue

                ultima = dati.index.max()
                if pd.Timestamp.utcnow().tz_localize(None) - ultima > pd.Timedelta(hours=3):
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

        ultime_3 = osservazioni.last("3h")
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

        ore = pd.DataFrame(dati_terrestri["hourly"])
        ore["time"] = pd.to_datetime(ore["time"])

        adesso = pd.Timestamp.utcnow().tz_localize(None).floor("h")
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


def punteggio_attivita_luogo(dati, tipo):
    temperatura = float(dati.get("temperature_2m") or 0)
    percepita = float(dati.get("apparent_temperature") or temperatura)
    pioggia = float(dati.get("precipitation") or 0)
    vento = float(dati.get("wind_speed_10m") or 0)
    raffica = float(dati.get("wind_gusts_10m") or 0)
    nuvole = float(dati.get("cloud_cover") or 0)
    codice = int(dati.get("weather_code") or 0)
    temporale = codice in (95, 96, 99)
    rovesci = codice in (80, 81, 82)
    pioggia_meteo = codice in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67)
    punteggio = 100

    if temporale: punteggio -= 85
    if pioggia >= 2: punteggio -= min(55, 20 + pioggia * 14)
    elif pioggia > 0: punteggio -= min(30, pioggia * 18)
    elif rovesci or pioggia_meteo: punteggio -= 25
    if raffica >= 70: punteggio -= 55
    elif raffica >= 50: punteggio -= 32
    elif raffica >= 35: punteggio -= 15

    if tipo == "escursionismo":
        if temperatura < 4 or temperatura > 31: punteggio -= 20
        if vento >= 30: punteggio -= min(25, (vento - 25) * 2)
        if 71 <= codice <= 77: punteggio -= 40
    elif tipo == "ciclismo":
        if temperatura < 6 or temperatura > 30: punteggio -= 22
        if vento >= 20: punteggio -= min(40, (vento - 18) * 2.5)
        if raffica >= 40: punteggio -= 18
    elif tipo == "spiaggia":
        if temperatura < 22: punteggio -= min(55, (22 - temperatura) * 6)
        if temperatura > 35: punteggio -= 18
        if nuvole > 75: punteggio -= 30
        elif nuvole > 50: punteggio -= 12
        if vento >= 30: punteggio -= 25
    elif tipo == "fotografia":
        if temporale or pioggia >= 3: punteggio -= 35
        if nuvole >= 95: punteggio -= 25
        elif 30 <= nuvole <= 75: punteggio += 5
        if raffica >= 55: punteggio -= 20
    elif tipo == "corsa":
        if percepita < 4 or percepita > 29: punteggio -= 28
        if vento >= 28: punteggio -= min(35, (vento - 22) * 2.5)
        if raffica >= 45: punteggio -= 18
    elif tipo == "astronomia":
        if nuvole > 85: punteggio -= 75
        elif nuvole > 65: punteggio -= 50
        elif nuvole > 40: punteggio -= 28
        elif nuvole > 20: punteggio -= 10
        if pioggia > 0 or pioggia_meteo or rovesci: punteggio -= 35
        if temporale: punteggio -= 30
        if raffica >= 45: punteggio -= 18

    return max(0, min(100, round(punteggio)))


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
    for tipo, nome in attivita:
        punteggio = punteggio_attivita_luogo(corrente, tipo)
        colore = {
            4: "#16a34a", 3: "#84cc16", 2: "#eab308",
            1: "#f97316", 0: "#dc2626"
        }[min(4, punteggio // 20)]
        righe.append(f"""
          <tr>
            <td>{html.escape(nome)}</td>
            <td>
              <div class="cml-activity-bar">
                <div class="cml-activity-bar-fill" style="width:{punteggio}%;background:{colore};"></div>
              </div>
            </td>
            <td><b style="color:{colore};">{punteggio}%</b></td>
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
          <p>Percentuale di svolgimento stimata dalle condizioni meteorologiche previste per la località cercata.</p>
        </div>
      </div>
      <div class="cml-table-wrap">
        <table class="cml-table" style="min-width:620px;">
          <thead><tr><th>Attività</th><th>Percentuale di svolgimento</th><th>Valore</th></tr></thead>
          <tbody>{''.join(righe)}</tbody>
        </table>
      </div>
      <div class="cml-marine-note">
        ℹ️ {nota_costa} Valori stimati su dati ICON-2I della località selezionata.
        Per la spiaggia non è valutata la balneabilità; per l’astronomia non sono considerati
        buio e inquinamento luminoso.
      </div>
    </section>
    """



# =============================================================================
# FUNZIONI PER IL PERCORSO METEO‑ASSISTITO
# =============================================================================

def geocodifica_generale(nome, nazione="Italia"):
    try:
        geocoder = Nominatim(user_agent="calabria_meteo_lab_percorso_v1", timeout=30)
        risposta = geocoder.geocode(f"{nome}, {nazione}", exactly_one=True, addressdetails=True, timeout=15)
    except (GeocoderServiceError, GeocoderTimedOut) as exc:
        raise RuntimeError("Servizio di geolocalizzazione temporaneamente non disponibile.") from exc
    if risposta is None:
        raise ValueError(f"Località «{nome}» non trovata.")
    latitudine = float(risposta.latitude)
    longitudine = float(risposta.longitude)
    indirizzo = risposta.raw.get("address", {})
    nome_risolto = indirizzo.get("city") or indirizzo.get("town") or indirizzo.get("village") or indirizzo.get("municipality") or nome.title()
    return nome_risolto, latitudine, longitudine


def scarica_percorso_ors(lat_partenza, lon_partenza, lat_arrivo, lon_arrivo, profilo="driving-car", api_key=None):
    import base64
    url = f"https://api.openrouteservice.org/v2/directions/{profilo}/geojson"
    headers = {"Accept": "application/json, application/geo+json", "Content-Type": "application/json; charset=UTF-8"}
    if api_key:
        headers["Authorization"] = api_key
    body = {"coordinates": [[lon_partenza, lat_partenza], [lon_arrivo, lat_arrivo]], "elevation": False, "format": "geojson"}
    try:
        risposta = requests.post(url, json=body, headers=headers, timeout=30)
        risposta.raise_for_status()
        dati = risposta.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Errore nel calcolo del percorso: {exc}") from exc
    features = dati.get("features", [])
    if not features:
        raise ValueError("Nessun percorso trovato.")
    feature = features[0]
    geometria = feature.get("geometry", {}).get("coordinates", [])
    properties = feature.get("properties", {})
    segments = properties.get("segments", [{}])
    segmento = segments[0] if segments else {}
    distanza_m = segmento.get("distance", 0)
    durata_s = segmento.get("duration", 0)
    return {"geometria": geometria, "distanza_km": distanza_m / 1000.0 if distanza_m else 0, "durata_secondi": durata_s, "istruzioni": segmento.get("steps", [])}


def estrai_punti_percorso(geometria, numero_punti=12):
    if not geometria:
        return []
    n = len(geometria)
    if n <= numero_punti:
        return [(lat, lon) for lon, lat in geometria]
    passo = max(1, n // numero_punti)
    punti = []
    for i in range(0, n, passo):
        if len(punti) >= numero_punti:
            break
        lon, lat = geometria[i]
        punti.append((lat, lon))
    if punti and punti[-1] != (geometria[-1][1], geometria[-1][0]):
        punti.append((geometria[-1][1], geometria[-1][0]))
    return punti


def scarica_meteo_punti_percorso(punti, data_partenza, ora_partenza, durata_stimata_minuti):
    risultati = []
    inizio = datetime.combine(data_partenza, ora_partenza)
    fine = inizio + timedelta(minutes=durata_stimata_minuti + 60)
    for lat, lon in punti:
        parametri = {"latitude": lat, "longitude": lon, "models": MODELLO_TERRESTRE, "timezone": "Europe/Rome", "forecast_days": 3, "temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm", "hourly": ",".join(["temperature_2m", "precipitation", "rain", "showers", "snowfall", "weather_code", "wind_speed_10m", "wind_gusts_10m", "cloud_cover", "visibility"])}
        try:
            risposta = requests.get(API_METEO_URL, params=parametri, timeout=25)
            risposta.raise_for_status()
            dati = risposta.json()
        except requests.RequestException:
            continue
        ore_raw = pd.DataFrame(dati.get("hourly", {}))
        if ore_raw.empty:
            continue
        ore_raw["time"] = pd.to_datetime(ore_raw["time"])
        ore_filtrate = ore_raw.loc[(ore_raw["time"] >= pd.Timestamp(inizio)) & (ore_raw["time"] <= pd.Timestamp(fine))].copy()
        if ore_filtrate.empty:
            continue
        meteo_orario = []
        for _, riga in ore_filtrate.iterrows():
            meteo_orario.append({"time": riga["time"], "temperature_2m": riga.get("temperature_2m"), "precipitation": riga.get("precipitation"), "rain": riga.get("rain"), "snowfall": riga.get("snowfall"), "weather_code": riga.get("weather_code"), "wind_speed_10m": riga.get("wind_speed_10m"), "wind_gusts_10m": riga.get("wind_gusts_10m"), "cloud_cover": riga.get("cloud_cover"), "visibility": riga.get("visibility")})
        risultati.append({"lat": lat, "lon": lon, "meteo_orario": meteo_orario})
    return risultati


def valuta_condizioni_punto(meteo_orario):
    if not meteo_orario:
        return {"precipitazione_max_mm": 0, "pioggia_max_mm": 0, "neve_max_mm": 0, "codice_meteo_max": 0, "vento_max_kmh": 0, "raffica_max_kmh": 0, "visibilita_min_m": 10000, "indice_rischio": 0, "criticita": []}
    precip_max = pioggia_max = neve_max = codice_max = vento_max = raffica_max = 0
    visibilita_min = 10000
    for riga in meteo_orario:
        precip = float(riga.get("precipitation") or 0)
        pioggia = float(riga.get("rain") or 0)
        neve = float(riga.get("snowfall") or 0)
        codice = int(riga.get("weather_code") or 0)
        vento = float(riga.get("wind_speed_10m") or 0)
        raffica = float(riga.get("wind_gusts_10m") or 0)
        vis = float(riga.get("visibility") or 10000)
        precip_max = max(precip_max, precip)
        pioggia_max = max(pioggia_max, pioggia)
        neve_max = max(neve_max, neve)
        codice_max = max(codice_max, codice)
        vento_max = max(vento_max, vento)
        raffica_max = max(raffica_max, raffica)
        visibilita_min = min(visibilita_min, vis)
    rischio = 0
    if precip_max >= 2: rischio += 25
    elif precip_max > 0: rischio += 10
    if pioggia_max >= 2: rischio += 15
    if neve_max > 0: rischio += 35
    if codice_max in (95, 96, 99): rischio += 45
    if raffica_max >= 70: rischio += 30
    elif raffica_max >= 50: rischio += 15
    if visibilita_min < 1000: rischio += 25
    elif visibilita_min < 3000: rischio += 10
    rischio = min(rischio, 100)
    criticita = []
    if precip_max >= 2: criticita.append(f"Precipitazione fino a {precip_max:.1f} mm/h")
    elif precip_max > 0: criticita.append(f"Precipitazione debole ({precip_max:.1f} mm/h)")
    if neve_max > 0: criticita.append(f"Neve prevista ({neve_max:.1f} mm/h)")
    if codice_max in (95, 96, 99): criticita.append("Temporale previsto")
    if raffica_max >= 70: criticita.append(f"Raffiche forti ({raffica_max:.0f} km/h)")
    elif raffica_max >= 50: criticita.append(f"Raffiche moderate ({raffica_max:.0f} km/h)")
    if visibilita_min < 1000: criticita.append(f"Visibilità molto ridotta ({visibilita_min:.0f} m)")
    elif visibilita_min < 3000: criticita.append(f"Visibilità ridotta ({visibilita_min:.0f} m)")
    return {"precipitazione_max_mm": precip_max, "pioggia_max_mm": pioggia_max, "neve_max_mm": neve_max, "codice_meteo_max": codice_max, "vento_max_kmh": vento_max, "raffica_max_kmh": raffica_max, "visibilita_min_m": visibilita_min, "indice_rischio": rischio, "criticita": criticita}


def valuta_percorso_completo(dati_punti):
    if not dati_punti:
        return {"indice_rischio_medio": 0, "indice_rischio_max": 0, "punto_peggiore": {"lat": 0, "lon": 0, "indice": 0}, "criticita_totali": [], "dettaglio_punti": []}
    valutazioni = []
    criticita_totali = []
    rischio_max = 0
    punto_peggiore = {"lat": 0, "lon": 0, "indice": 0}
    for punto in dati_punti:
        valutazione = valuta_condizioni_punto(punto.get("meteo_orario", []))
        valutazione["lat"] = punto["lat"]
        valutazione["lon"] = punto["lon"]
        valutazioni.append(valutazione)
        criticita_totali.extend(valutazione["criticita"])
        if valutazione["indice_rischio"] > rischio_max:
            rischio_max = valutazione["indice_rischio"]
            punto_peggiore = {"lat": punto["lat"], "lon": punto["lon"], "indice": rischio_max}
    indici = [v["indice_rischio"] for v in valutazioni]
    rischio_medio = sum(indici) / len(indici) if indici else 0
    criticita_univoche = list(dict.fromkeys(criticita_totali))
    return {"indice_rischio_medio": round(rischio_medio), "indice_rischio_max": rischio_max, "punto_peggiore": punto_peggiore, "criticita_totali": criticita_univoche, "dettaglio_punti": valutazioni}


def confronta_orari_partenza(percorso, data_partenza, ora_desiderata, punti, scarti_minuti=ORARI_DA_CONFRONTARE):
    risultati = []
    durata_minuti = percorso.get("durata_secondi", 0) / 60.0
    for scarto in scarti_minuti:
        ora_test = datetime.combine(data_partenza, ora_desiderata) + timedelta(minutes=scarto)
        if ora_test < datetime.now():
            continue
        dati_meteo = scarica_meteo_punti_percorso(punti, ora_test.date(), ora_test.time(), durata_minuti)
        valutazione = valuta_percorso_completo(dati_meteo)
        risultati.append({"orario_partenza": ora_test, "indice_rischio_medio": valutazione["indice_rischio_medio"], "indice_rischio_max": valutazione["indice_rischio_max"], "criticita_totali": valutazione["criticita_totali"]})
    risultati.sort(key=lambda x: x["indice_rischio_medio"])
    return risultati


def genera_consiglio_orario(risultati_confronto, ora_desiderata):
    if not risultati_confronto:
        return {"orario_consigliato": None, "testo_consiglio": "Nessun orario disponibile per il confronto.", "testo_avviso": ""}
    migliore = risultati_confronto[0]
    ora_migliore = migliore["orario_partenza"]
    differenza_minuti = (ora_migliore - datetime.combine(ora_migliore.date(), ora_desiderata)).total_seconds() / 60.0
    if abs(differenza_minuti) <= 15:
        testo = f"✅ L'orario da te scelto ({ora_desiderata.strftime('%H:%M')}) è già ottimale. Indice meteo stimato: {migliore['indice_rischio_medio']}/100."
    elif differenza_minuti < 0:
        testo = f"⏰ Ti consigliamo di partire alle {ora_migliore.strftime('%H:%M')} ({int(-differenza_minuti)} minuti prima). Indice meteo stimato: {migliore['indice_rischio_medio']}/100."
    else:
        testo = f"⏰ Ti consigliamo di partire alle {ora_migliore.strftime('%H:%M')} ({int(differenza_minuti)} minuti dopo). Indice meteo stimato: {migliore['indice_rischio_medio']}/100."
    avviso = ""
    if migliore["indice_rischio_max"] >= 60:
        avviso = f"<br><br>⚠️ Attenzione: lungo il percorso è prevista una sezione con condizioni meteorologiche difficili (indice di rischio fino a {migliore['indice_rischio_max']}/100). Valuta se posticipare o anticipare ulteriormente la partenza."
    return {"orario_consigliato": ora_migliore, "testo_consiglio": testo, "testo_avviso": avviso}


def genera_riepilogo_percorso_html(percorso, valutazione, consiglio, nome_partenza, nome_arrivo):
    distanza_km = percorso.get("distanza_km", 0)
    durata_minuti = percorso.get("durata_secondi", 0) / 60.0
    ore = int(durata_minuti // 60)
    minuti = int(durata_minuti % 60)
    durata_testo = f"{ore} h {minuti} min" if ore > 0 else f"{minuti} min"
    indice_medio = valutazione.get("indice_rischio_medio", 0)
    indice_max = valutazione.get("indice_rischio_max", 0)
    if indice_medio <= 20:
        colore = "#16a34a"
        testo_condizioni = "Condizioni favorevoli"
    elif indice_medio <= 40:
        colore = "#eab308"
        testo_condizioni = "Attenzione moderata"
    elif indice_medio <= 60:
        colore = "#f97316"
        testo_condizioni = "Condizioni difficili"
    else:
        colore = "#dc2626"
        testo_condizioni = "Condizioni molto difficili"
    criticita_html = ""
    if valutazione.get("criticita_totali"):
        criticita_html = "<br><br><strong>Criticità previste:</strong><ul>"
        for c in valutazione["criticita_totali"][:5]:
            criticita_html += f"<li>{html.escape(c)}</li>"
        criticita_html += "</ul>"
    return f"""
    <section class="cml-nowcast-box">
      <div class="cml-nowcast-head">
        <span class="cml-eyebrow">PERCORSO METEO‑ASSISTITO</span>
        <h2>🚗 Riepilogo del viaggio</h2>
      </div>
      <p style="font-size:16px; margin-bottom:18px;"><strong>{html.escape(nome_partenza)}</strong> → <strong>{html.escape(nome_arrivo)}</strong></p>
      <div class="cml-marine-grid" style="margin-bottom:20px;">
        <div class="cml-marine-card"><span>📏 Distanza</span><strong>{distanza_km:.1f} km</strong></div>
        <div class="cml-marine-card"><span>⏱️ Durata stimata</span><strong>{durata_testo}</strong></div>
        <div class="cml-marine-card"><span>🌡️ Condizioni meteo</span><strong style="color:{colore};">{testo_condizioni}</strong><small>Indice: {indice_medio}/100 (max {indice_max})</small></div>
      </div>
      <div style="background:#f0f9ff; border:1px solid #bae6fd; border-radius:12px; padding:16px; margin-bottom:18px;">
        <strong style="color:#0369a1; font-size:16px;">💡 Consiglio sull'orario</strong><br><br>
        <span style="color:#0c4a6e; font-size:14px;">{consiglio["testo_consiglio"]}</span>
        {consiglio["testo_avviso"]}
      </div>
      {criticita_html}
      <div class="cml-nowcast-note">ℹ️ L'indice meteo è una stima basata su precipitazioni, vento, temporali, neve e visibilità. Non tiene conto di traffico, incidenti o lavori stradali. Consulta sempre fonti ufficiali e guidare con prudenza.</div>
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

        # Solo la scheda «I prossimi tre giorni» usa il cielo medio diurno.
        codice_effettivo = riga.get(
            "weather_code_prevalente",
            riga.get("weather_code"),
        )

        icona, descrizione = meteo(codice_effettivo)
        fase = html.escape(str(riga.get("Fase lunare", "🌙 Luna")))
        livello, rischio = valuta_rischio_locale(riga)
        badge_rischio = badge_rischio_html(livello, rischio)

        if codice_effettivo in [95, 96, 99]:
            classe_icona = "cml-icon-thunder"
        elif codice_effettivo in range(71, 87):
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

    tabella_attivita_luogo = tabella_attivita_luogo_html(
        luogo,
        corrente,
        is_costiero,
    )

    documento_html = f"""
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
:root {{
  --ink: #102b3b;
  --muted: #607987;
  --orange: #f26e17;
  --page: #eef5f8;
}}

* {{
  box-sizing: border-box;
}}

body {{
  margin: 0;
  padding: 8px;
  min-height: 100vh;
  color: var(--ink);
  background: var(--page);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
  line-height: 1.45;
}}

.cml-view[hidden] {{
  display: none !important;
}}

/* ===================== HOME ===================== */

.cml-home-hero {{
  position: relative;
  overflow: hidden;
  width: 100%;
  min-height: 380px;
  margin: 0 0 32px;
  padding: 90px 7vw;
  border: 1px solid #07516c;
  border-radius: 28px;
  color: #ffffff;
  background:
    radial-gradient(circle at 85% 15%, rgba(255, 210, 92, 0.20), transparent 28%),
    linear-gradient(135deg, #06324d 0%, #075b78 52%, #087f91 100%);
  box-shadow: 0 14px 32px rgba(9, 61, 83, 0.22);
}}

.cml-home-hero::before {{
  content: "";
  position: absolute;
  right: -85px;
  bottom: -105px;
  width: 310px;
  height: 310px;
  border: 36px solid rgba(255, 255, 255, 0.08);
  border-radius: 50%;
}}

.cml-home-hero > * {{
  position: relative;
  z-index: 1;
}}

.cml-home-hero h1 {{
  max-width: 1100px;
  margin: 28px 0 20px;
  color: #ffffff;
  font-size: clamp(48px, 6vw, 92px);
  font-weight: 850;
  letter-spacing: -1.5px;
  line-height: 1.08;
}}

.cml-home-hero p {{
  max-width: 1050px;
  margin: 0;
  color: #e2f5f8;
  font-size: clamp(18px, 2vw, 27px);
  line-height: 1.7;
}}

.cml-home-actions {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
  width: 100%;
  max-width: none;
  margin: 0 0 32px;
}}

.cml-home-choice {{
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-height: 430px;
  width: 100%;
  padding: 46px;
  border: 1px solid #d2e4e9;
  border-radius: 24px;
  background: #ffffff;
  color: #102b3b;
  cursor: pointer;
  text-align: left;
  box-shadow: 0 10px 28px rgba(23, 67, 84, 0.12);
  transition: transform 0.18s ease, box-shadow 0.18s ease,
              border-color 0.18s ease;
}}

.cml-home-choice:hover,
.cml-home-choice:focus-visible {{
  transform: translateY(-4px);
  border-color: #087087;
  outline: none;
  box-shadow: 0 15px 32px rgba(8, 112, 135, 0.22);
}}

.cml-home-choice-icon {{
  display: flex;
  align-items: center;
  justify-content: center;
  width: 62px;
  height: 62px;
  margin-bottom: 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, #d9f4f7, #a8e1e7);
  font-size: 31px;
}}

.cml-home-choice.radar .cml-home-choice-icon {{
  background: linear-gradient(135deg, #dce7ff, #adc5ec);
}}

.cml-home-choice.activities .cml-home-choice-icon {{
  background: linear-gradient(135deg, #dce7ff, #adc5ec);
}}

.cml-home-choice h2 {{
  margin: 0 0 8px;
  color: #102b3b;
  font-size: 24px;
}}

.cml-home-choice p {{
  margin: 0;
  color: #607987;
  font-size: 14px;
  line-height: 1.6;
}}

.cml-home-choice span {{
  margin-top: auto;
  padding-top: 20px;
  color: #087087;
  font-size: 13px;
  font-weight: 850;
}}

/* ===================== NAV BAR ===================== */

.cml-nav-bar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin: 8px 0 20px;
  padding: 12px 15px;
  border: 1px solid #d5e4e9;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 6px 18px rgba(23, 67, 84, 0.08);
}}

.cml-back-btn {{
  border: 0;
  border-radius: 10px;
  padding: 10px 14px;
  background: #e7f6f8;
  color: #087087;
  cursor: pointer;
  font-size: 13px;
  font-weight: 850;
  transition: background 0.16s ease, transform 0.16s ease;
}}

.cml-back-btn:hover {{
  background: #cdeef2;
  transform: translateX(-2px);
}}

.cml-nav-title {{
  color: #102b3b;
  font-size: 14px;
  font-weight: 850;
}}

/* ===================== HERO E CONDIZIONI ===================== */

.cml-hero {{
  position: relative;
  overflow: hidden;
  margin: 8px 0 22px;
  padding: 42px 46px 38px;
  border: 1px solid #07516c;
  border-radius: 28px;
  color: #ffffff;
  background: linear-gradient(135deg, #06324d 0%, #075b78 52%, #087f91 100%);
  box-shadow: 0 14px 32px rgba(9, 61, 83, 0.22);
}}

.cml-hero::before {{
  content: "";
  position: absolute;
  top: -170px;
  right: -120px;
  width: 360px;
  height: 360px;
  border: 42px solid rgba(255, 255, 255, 0.09);
  border-radius: 50%;
}}

.cml-hero::after {{
  content: "";
  position: absolute;
  right: 80px;
  bottom: -220px;
  width: 260px;
  height: 260px;
  border: 32px solid rgba(255, 255, 255, 0.06);
  border-radius: 50%;
}}

.cml-hero > * {{
  position: relative;
  z-index: 1;
}}

.cml-brand {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 15px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 999px;
  background: rgba(0, 35, 55, 0.35);
  color: #d7f7fa;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 2px;
}}

.cml-brand-mark {{
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: #ffd45c;
  box-shadow: 0 0 0 5px rgba(255, 212, 92, 0.18);
}}

.cml-hero h1 {{
  margin: 19px 0 10px;
  color: #ffffff;
  font-size: 44px;
  font-weight: 800;
  letter-spacing: -1.5px;
  line-height: 1.1;
}}

.cml-hero p {{
  max-width: 760px;
  margin: 0;
  color: #e2f5f8;
  font-size: 15px;
  line-height: 1.7;
}}

.cml-current {{
  overflow: hidden;
  margin: 22px 0 25px;
  border: 1px solid #d5e4e9;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 10px 30px rgba(23, 67, 84, 0.12);
}}

.cml-current-main {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 34px 38px;
  border-bottom: 1px solid #e2edf0;
  background: #ffffff;
}}

.cml-kicker {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 13px;
  border-radius: 999px;
  background: #e3f5f8;
  color: #087087;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.2px;
}}

.cml-live-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #18a579;
  box-shadow: 0 0 0 4px rgba(24, 165, 121, 0.16);
}}

.cml-place-block h2 {{
  margin: 13px 0 10px;
  color: var(--ink);
  font-size: 35px;
  letter-spacing: -0.7px;
}}

.cml-condition {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 13px;
  border: 1px solid #e1edf0;
  border-radius: 11px;
  color: #4d6570;
  background: #f8fbfc;
  font-size: 16px;
  font-weight: 650;
}}

.cml-temperature {{
  display: flex;
  align-items: flex-start;
  color: var(--orange);
  font-weight: 900;
  line-height: 0.9;
  white-space: nowrap;
}}

.cml-temperature span {{
  font-size: 84px;
  letter-spacing: -7px;
}}

.cml-temperature small {{
  margin: 10px 0 0 8px;
  font-size: 28px;
}}

.cml-metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  padding: 22px 28px;
}}

.cml-metric-card {{
  display: flex;
  align-items: center;
  gap: 13px;
  min-height: 70px;
  padding: 14px 16px;
  border: 1px solid #dce9ed;
  border-radius: 15px;
  background-color: #f7fbfc;
}}

.cml-metric-icon {{
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border: 1px solid #e2edef;
  border-radius: 12px;
  background: #ffffff;
  font-size: 23px;
}}

.cml-metric-label {{
  color: var(--muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.7px;
  text-transform: uppercase;
}}

.cml-metric-value {{
  margin-top: 4px;
  color: var(--ink);
  font-size: 17px;
  font-weight: 850;
}}

.cml-current-footer {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px 25px;
  padding: 14px 28px;
  border-top: 1px solid #e3edf0;
  background: #f8fbfc;
  color: var(--muted);
  font-size: 12px;
}}

.cml-current-footer b {{
  color: #294e5c;
}}

/* ===================== MARE ===================== */

.cml-marine-box {{
  margin: 0 0 30px;
  padding: 26px;
  border: 1px solid #cbdfe8;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 8px 28px rgba(23, 67, 84, 0.10);
}}

.cml-marine-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}}

.cml-eyebrow {{
  color: #087087;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 1.8px;
}}

.cml-marine-head h2 {{
  margin: 6px 0 4px;
  color: var(--ink);
  font-size: 25px;
}}

.cml-marine-head p {{
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}}

.cml-sea-status {{
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 190px;
  padding: 13px 16px;
  border-radius: 14px;
  color: #ffffff;
}}

.cml-sea-status > span {{
  font-size: 28px;
}}

.cml-sea-status small {{
  display: block;
  margin-bottom: 3px;
  color: rgba(255, 255, 255, 0.84);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.9px;
}}

.cml-sea-status strong {{
  display: block;
  font-size: 17px;
}}

.cml-mare-calmo {{ background: #0d77a7; }}
.cml-mare-quasi-calmo {{ background: #168db7; }}
.cml-mare-poco-mosso {{ background: #278b5e; }}
.cml-mare-mosso {{ background: #c18a1c; }}
.cml-mare-molto-mosso {{ background: #d16418; }}
.cml-mare-agitato {{ background: #c3313d; }}
.cml-mare-molto-agitato {{ background: #8b1e29; }}
.cml-mare-nd {{ background: #6d7d86; }}

.cml-marine-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
  gap: 12px;
}}

.cml-marine-card {{
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-height: 105px;
  padding: 15px;
  border: 1px solid #dbe8ec;
  border-radius: 15px;
  background: #f7fbfc;
}}

.cml-marine-card span {{
  color: #54707c;
  font-size: 12px;
  font-weight: 700;
}}

.cml-marine-card strong {{
  color: #143b4b;
  font-size: 22px;
}}

.cml-marine-card small {{
  color: #768c95;
  font-size: 11px;
}}

.cml-marine-note {{
  margin-top: 16px;
  padding: 12px 15px;
  border: 1px solid #bfe1ea;
  border-left: 4px solid #168db7;
  border-radius: 11px;
  background: #ecf9fc;
  color: #3d6270;
  font-size: 12px;
  line-height: 1.6;
}}

/* ===================== PREVISIONI MARE ===================== */

.cml-marine-forecast-title {{
  margin: 24px 0 12px;
  color: var(--ink);
  font-size: 19px;
  font-weight: 850;
}}

.cml-marine-forecast-grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}}

.cml-marine-forecast-card {{
  padding: 15px;
  border: 1px solid #dbe8ec;
  border-radius: 15px;
  background: #f7fbfc;
}}

.cml-marine-forecast-date {{
  margin-bottom: 8px;
  color: #143b4b;
  font-size: 14px;
  font-weight: 850;
  text-transform: capitalize;
}}

.cml-marine-forecast-status {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  padding: 5px 8px;
  border-radius: 8px;
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
}}

.cml-marine-forecast-values {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 9px;
}}

.cml-marine-forecast-values span {{
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: #54707c;
  font-size: 12px;
}}

.cml-marine-forecast-values b {{
  color: #143b4b;
  font-size: 16px;
}}

.cml-marine-forecast-values small {{
  color: #768c95;
  font-size: 10px;
}}

/* ===================== RADAR ===================== */

.cml-radar-box {{
  margin-bottom: 32px;
  padding: 26px;
  border: 1px solid #d5e4e9;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 8px 28px rgba(23, 67, 84, 0.10);
}}

.cml-radar-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}}

.cml-radar-head h2 {{
  margin: 0;
  color: var(--ink);
  font-size: 23px;
}}

.cml-radar-head p {{
  margin: 3px 0 0;
  color: var(--muted);
  font-size: 12px;
}}

.cml-radar-btn {{
  border: 0;
  border-radius: 11px;
  padding: 10px 16px;
  background: linear-gradient(135deg, #0c7f96, #075d74);
  color: #ffffff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}}

#radar-map {{
  width: 100%;
  height: 480px;
  border: 1px solid #d8e7eb;
  border-radius: 16px;
}}

.cml-radar-footer {{
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px 20px;
  margin-top: 14px;
  padding: 12px 15px;
  border: 1px solid #dcebef;
  border-radius: 12px;
  background: #f5fafb;
  color: var(--muted);
  font-size: 12px;
}}

.cml-radar-time {{
  color: #087087;
  font-weight: 850;
}}

/* ===================== NOWCAST ===================== */

.cml-nowcast-box {{
  margin: 0 0 30px;
  padding: 26px;
  border: 1px solid #d5e4e9;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 8px 28px rgba(23, 67, 84, 0.10);
}}

.cml-nowcast-head {{
  margin-bottom: 16px;
}}

.cml-nowcast-head h2 {{
  margin: 6px 0 4px;
  color: #102b3b;
  font-size: 23px;
}}

.cml-nowcast-head p {{
  margin: 0;
  color: #607987;
  font-size: 12px;
}}

.cml-nowcast-list {{
  list-style: none;
  margin: 0;
  padding: 0;
}}

.cml-nowcast-list li {{
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
  color: #2a4b58;
  font-size: 14px;
  line-height: 1.5;
}}

.cml-nowcast-bullet {{
  flex: 0 0 20px;
  font-size: 16px;
}}

.cml-nowcast-note {{
  margin-top: 14px;
  padding: 11px 14px;
  border: 1px solid #f0dca8;
  border-left: 4px solid #dc9c2d;
  border-radius: 11px;
  background: #fff8e7;
  color: #67552d;
  font-size: 12px;
  line-height: 1.5;
}}

/* ===================== SECTION TITLE ===================== */

.cml-section-title {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin: 38px 0 18px;
}}

.cml-section-title span {{
  color: #0b7f98;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 1.8px;
}}

.cml-section-title h2 {{
  margin: 7px 0 5px;
  color: var(--ink);
  font-size: 28px;
  letter-spacing: -0.6px;
}}

.cml-section-title p {{
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}}

.cml-pill {{
  padding: 8px 14px;
  border: 1px solid #bfe2e8;
  border-radius: 999px;
  background: #e7f6f8;
  color: #087087;
  font-size: 12px;
  font-weight: 850;
  white-space: nowrap;
}}

/* ===================== CARDS GIORNI ===================== */

.cml-days-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 18px;
}}

.cml-day-card {{
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  padding: 23px;
  border: 1px solid #d5e4e9;
  border-radius: 22px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(23, 67, 84, 0.10);
}}

.cml-day-card:hover, .cml-day-card:focus-visible {{
  border-color: #087087;
  outline: 2px solid transparent;
  box-shadow: 0 10px 28px rgba(8, 112, 135, 0.23);
}}

.cml-day-card.active {{
  grid-column: 1 / -1;
  border-color: #087087;
}}

.cml-day-inline-detail[hidden] {{ display: none !important; }}

.cml-day-inline-detail {{
  margin-top: 22px;
  padding-top: 18px;
  border-top: 2px solid #d5e4e9;
  cursor: default;
}}

.cml-day-inline-detail h3 {{
  margin: 0 0 10px;
  color: #102b3b;
  font-size: 21px;
}}

.cml-day-inline-empty {{
  margin-top: 16px;
  color: #607987;
  font-size: 13px;
}}

.cml-day-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}}

.cml-day-tag {{
  padding: 6px 12px;
  border-radius: 999px;
  background: linear-gradient(135deg, #0e95ab, #087087);
  color: #ffffff;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 1px;
}}

.cml-day-date {{
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  text-transform: capitalize;
}}

.cml-risk-row {{
  margin: 14px 0;
}}

.cml-risk-badge {{
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 10px;
  border-radius: 10px;
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
}}

.cml-day-weather {{
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}}

.cml-day-icon {{
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 68px;
  height: 68px;
  border-radius: 19px;
  font-size: 35px;
  box-shadow: 0 6px 14px rgba(23, 67, 84, 0.15);
}}

.cml-icon-sun {{ background: linear-gradient(135deg, #ffe99a, #f9b843); }}
.cml-icon-cloud {{ background: linear-gradient(135deg, #dbe6ea, #93aab5); }}
.cml-icon-rain {{ background: linear-gradient(135deg, #9ed4ef, #327eae); }}
.cml-icon-snow {{ background: linear-gradient(135deg, #eff9ff, #b8d5e3); }}
.cml-icon-thunder {{ background: linear-gradient(135deg, #cbb3e6, #67458b); }}

.cml-day-description {{
  color: var(--ink);
  font-size: 18px;
  font-weight: 850;
}}

.cml-day-moon {{
  display: inline-flex;
  margin-top: 6px;
  padding: 5px 9px;
  border-radius: 999px;
  background: #eef2ff;
  color: #48538f;
  font-size: 11px;
  font-weight: 750;
}}

.cml-temperature-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 17px;
  padding: 13px;
  border: 1px solid #e1ebee;
  border-radius: 15px;
  background: #f8fbfc;
}}

.cml-temp-box {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}}

.cml-temp-box span {{
  color: var(--muted);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 1px;
}}

.cml-temp-box strong {{
  font-size: 24px;
}}

.cml-temp-min {{
  color: #167aa9;
}}

.cml-temp-max {{
  color: var(--orange);
}}

.cml-day-details {{
  display: grid;
  gap: 9px;
  margin-bottom: 18px;
  padding-bottom: 17px;
  border-bottom: 1px solid #e4edef;
}}

.cml-day-details div {{
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: #536d78;
  font-size: 13px;
}}

.cml-day-details b {{
  color: #234b59;
  white-space: nowrap;
}}

.cml-astro-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 9px;
}}

.cml-astro-grid div {{
  display: flex;
  justify-content: space-between;
  gap: 6px;
  padding: 9px;
  border: 1px solid #e3edef;
  border-radius: 10px;
  background: #fafcfd;
  color: #637b85;
  font-size: 11px;
}}

.cml-astro-grid b {{
  color: #254c5a;
}}

.cml-note {{
  margin: 18px 0 25px;
  padding: 15px 18px;
  border: 1px solid #f0dca8;
  border-left: 5px solid #dc9c2d;
  border-radius: 14px;
  background: #fff8e7;
  color: #67552d;
  font-size: 13px;
  line-height: 1.6;
}}

/* ===================== CHART ===================== */

.cml-chart-box {{
  margin: 20px 0 14px;
  padding: 20px;
  border: 1px solid #d5e4e9;
  border-radius: 20px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(23, 67, 84, 0.10);
}}

.cml-chart-title {{
  margin-bottom: 4px;
  color: var(--ink);
  font-size: 18px;
  font-weight: 850;
}}

.cml-chart-subtitle {{
  margin-bottom: 15px;
  color: var(--muted);
  font-size: 12px;
}}

.cml-chart-canvas-wrap {{
  position: relative;
  height: 330px;
}}

/* ===================== TABELLA ===================== */

.cml-table-wrap {{
  width: 100%;
  overflow-x: auto;
  border: 1px solid #d5e4e9;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 8px 28px rgba(23, 67, 84, 0.10);
}}

.cml-table {{
  width: 100%;
  min-width: 1080px;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;
  white-space: nowrap;
}}

.cml-table th {{
  padding: 15px 10px;
  background: linear-gradient(135deg, #0b7f98, #075d74);
  color: #ffffff;
  font-size: 11px;
  font-weight: 850;
  letter-spacing: 0.3px;
  text-align: center;
  text-transform: uppercase;
}}

.cml-table th:first-child {{
  border-top-left-radius: 17px;
}}

.cml-table th:last-child {{
  border-top-right-radius: 17px;
}}

.cml-table td {{
  padding: 11px 10px;
  border-bottom: 1px solid #e7eff1;
  color: #284d5a;
  text-align: right;
  font-variant-numeric: tabular-nums;
}}

.cml-table td:first-child {{
  color: #087087;
  font-weight: 850;
  text-align: center;
}}

.cml-table td:nth-child(2) {{
  text-align: left;
}}

.cml-table td:nth-child(7) {{
  text-align: center;
  font-weight: 800;
}}

.cml-table tbody tr:nth-child(even) {{
  background: #f8fbfc;
}}

.cml-table tbody tr:hover {{
  background: #eaf7fa;
}}

.cml-scenario-cell {{
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 180px;
  font-weight: 650;
}}

.cml-table-icon {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 31px;
  width: 31px;
  height: 31px;
  border: 1px solid #e2edef;
  border-radius: 9px;
  background: #ffffff;
  font-size: 18px;
}}

.cml-night-row {{
  background: linear-gradient(90deg, #142549, #203b68) !important;
}}

.cml-weather-svg {{
  display: block;
  width: 100%;
  height: 100%;
}}

.cml-table-icon .cml-weather-svg {{
  width: 29px;
  height: 29px;
}}

.cml-current-weather-icon {{
  display: inline-flex;
  width: 30px;
  height: 30px;
  align-items: center;
  justify-content: center;
  flex: 0 0 30px;
  font-size: 22px;
}}

.cml-night-row td {{
  border-bottom-color: rgba(255, 255, 255, 0.10);
  color: #e5f0ff;
}}

.cml-night-row td:first-child {{
  color: #a8eaf5;
}}

.cml-night-row .cml-scenario-cell {{
  color: #ffedb2;
}}

.cml-night-row .cml-table-icon {{
  border-color: rgba(255, 255, 255, 0.16);
  background: #142549;
}}


/* ===================== COPYRIGHT ===================== */

.cml-copyright {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 20px;
  margin: 28px 0 12px;
  padding: 14px 18px;
  border: 1px solid #d5e4e9;
  border-radius: 14px;
  background: #ffffff;
  color: #607987;
  font-size: 12px;
  line-height: 1.5;
}}

.cml-copyright strong {{
  color: #102b3b;
}}

/* ===================== ATTIVITÀ ===================== */

.cml-activity-bar {{
  width: 100%;
  min-width: 180px;
  height: 10px;
  border-radius: 999px;
  background: #e5eef1;
  overflow: hidden;
}}

.cml-activity-bar-fill {{
  height: 100%;
  border-radius: 999px;
}}

@media (max-width: 760px) {{
  .cml-copyright {{
    flex-direction: column;
    align-items: flex-start;
  }}
}}

/* ===================== MEDIA ===================== */

@media (max-width: 760px) {{
  body {{
    padding: 4px;
  }}

  .cml-hero {{
    padding: 31px 25px;
  }}

  .cml-hero h1 {{
    font-size: 34px;
  }}

  .cml-current-main {{
    align-items: flex-start;
    flex-direction: column;
    padding: 26px 24px;
  }}

  .cml-temperature span {{
    font-size: 69px;
  }}

  .cml-metrics {{
    padding: 18px;
  }}

  .cml-marine-box {{
    padding: 18px;
  }}

  .cml-radar-box {{
    padding: 17px;
  }}

  #radar-map {{
    height: 390px;
  }}

  .cml-section-title {{
    align-items: flex-start;
    flex-direction: column;
  }}

  .cml-hour-header {{
    padding: 24px;
  }}

  .cml-chart-canvas-wrap {{
    height: 280px;
  }}

  .cml-home-hero {{
    padding: 38px 25px;
  }}

  .cml-home-hero h1 {{
    font-size: 36px;
  }}

  .cml-home-actions {{
    grid-template-columns: 1fr;
  }}

  .cml-nav-bar {{
    align-items: flex-start;
    flex-direction: column;
  }}
}}
</style>
</head>

<body>

<!-- ===================== HOME ===================== -->
<section id="cml-home" class="cml-view">

  <section class="cml-home-hero">
    <div class="cml-brand">
      <span class="cml-brand-mark"></span>
      CALABRIA · METEOROLOGIA LOCALE
    </div>

    <h1>Calabria Meteo Lab</h1>

    <p>
      Previsioni meteorologiche locali e radar delle precipitazioni
      per la Calabria. Scegli la sezione che vuoi consultare.
    </p>
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
      class="cml-home-choice radar"
      type="button"
      onclick="mostraVista('radar')"
    >
      <div class="cml-home-choice-icon">📡</div>

      <h2>Radar precipitazioni, nuvolosità e fulminazioni</h2>

      <p>
        Visualizza la sequenza radar delle precipitazioni in tempo quasi
        reale, centrata sulla località selezionata.
      </p>

      <span>Apri radar →</span>
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
<section id="cml-previsioni" class="cml-view" hidden>

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
      ℹ️ Le schede mostrano la condizione prevalente e la nuvolosità
      media nelle ore diurne. Temperature, precipitazioni e vento
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
<section id="cml-radar" class="cml-view" hidden>

  <div class="cml-nav-bar">
    <button
      class="cml-back-btn"
      type="button"
      onclick="mostraVista('home')"
    >
      ← Torna alla home
    </button>

    <span class="cml-nav-title">
      📡 Radar precipitazioni, nuvolosità e fulminazioni · {html.escape(luogo)}
    </span>
  </div>

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
const datiGraficiPerGiorno = {dati_grafici_json};

let meteoChartInstance = null;
let radarMap = null;
let attivitaMap = null;
let attivitaLayer = null;
let datiCelleCache = null;
let cacheTimestamp = null;

// Griglia Calabria per attività
const CALABRIA_BOUNDS = {{
  latMin: 37.75,
  latMax: 40.15,
  lonMin: 15.60,
  lonMax: 17.25,
}};

const PASSO_GRIGLIA_KM = 15.0;
const PASSO_LAT = PASSO_GRIGLIA_KM / 111.0;
const PASSO_LON = PASSO_GRIGLIA_KM / 86.0;

let celleAttivita = [];
const CACHE_DURATION_MS = 15 * 60 * 1000;

/* ---------- NAVIGAZIONE HOME / PREVISIONI / RADAR ---------- */

function mostraVista(nome) {{
  document.querySelectorAll(".cml-view").forEach(function(vista) {{
    vista.setAttribute("hidden", "");
  }});

  const vistaDaMostrare = document.getElementById("cml-" + nome);

  if (vistaDaMostrare) {{
    vistaDaMostrare.removeAttribute("hidden");
  }}

  if (
    nome === "radar"
    && typeof radarMap !== "undefined"
    && radarMap
  ) {{
    setTimeout(function() {{
      radarMap.invalidateSize();
    }}, 200);
  }}

  if (
    nome === "attivita"
    && typeof attivitaMap !== "undefined"
    && attivitaMap
  ) {{
    setTimeout(function() {{
      attivitaMap.invalidateSize();
    }}, 200);
  }}

  window.scrollTo({{
    top: 0,
    behavior: "smooth"
  }});
}}

/* ---------- GRAFICO METEO ---------- */

function creaGrafici(chiave) {{
  const dati = datiGraficiPerGiorno[chiave];

  if (!dati) {{
    return;
  }}

  const canvasTemperatura = document.getElementById(
    "temperaturaChart-" + chiave
  );

  const canvasNuvolositaPrecipitazioni =
    document.getElementById(
      "nuvolositaPrecipitazioniChart-" + chiave
    );

  const canvasVento = document.getElementById(
    "ventoChart-" + chiave
  );

  if (
    !canvasTemperatura
    || !canvasNuvolositaPrecipitazioni
    || !canvasVento
  ) {{
    return;
  }}

  const opzioniComuni = {{
    responsive: true,
    maintainAspectRatio: false,

    interaction: {{
      mode: "index",
      intersect: false
    }},

    plugins: {{
      legend: {{
        position: "top",

        labels: {{
          usePointStyle: true,
          padding: 18,

          font: {{
            size: 12,
            weight: "600"
          }}
        }}
      }},

      tooltip: {{
        backgroundColor: "rgba(15, 43, 59, 0.95)",
        padding: 11,
        cornerRadius: 9
      }}
    }},

    scales: {{
      x: {{
        grid: {{
          color: "rgba(16, 43, 59, 0.06)"
        }},

        ticks: {{
          maxRotation: 0,
          autoSkip: true
        }}
      }}
    }}
  }};

  /*
   * 1. GRAFICO TEMPERATURA
   */

    const graficoTemperatura = new Chart(
    canvasTemperatura.getContext("2d"),
    {{
      type: "line",

      data: {{
        labels: dati.ore,

        datasets: [
          {{
            label: "Temperatura °C",
            data: dati.temperatura,
            borderColor: "#ef6c16",
            backgroundColor: "rgba(239, 108, 22, 0.16)",
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 3,
            tension: 0.35,
            fill: true
          }}
        ]
      }},

      options: {{
        responsive: true,
        maintainAspectRatio: false,

        interaction: {{
          mode: "index",
          intersect: false
        }},

        plugins: {{
          legend: {{
            position: "top",
            labels: {{
              usePointStyle: true,
              padding: 18,
              font: {{
                size: 12,
                weight: "600"
              }}
            }}
          }},
          tooltip: {{
            backgroundColor: "rgba(15, 43, 59, 0.95)",
            padding: 11,
            cornerRadius: 9
          }}
        }},

        scales: {{
          x: {{
            grid: {{
              color: "rgba(16, 43, 59, 0.06)"
            }},
            ticks: {{
              maxRotation: 0,
              autoSkip: true
            }}
          }},
          y: {{
            title: {{
              display: true,
              text: "Temperatura °C"
            }},
            grid: {{
              color: "rgba(16, 43, 59, 0.08)"
            }}
          }}
        }}
      }}
    }}
  );
  /*
   * 2. GRAFICO NUVOLOSITÀ E PRECIPITAZIONI
   */

  const graficoNuvolositaPrecipitazioni = new Chart(
    canvasNuvolositaPrecipitazioni.getContext("2d"),
    {{
      data: {{
        labels: dati.ore,

        datasets: [
          {{
            type: "line",
            label: "Nuvolosità %",
            data: dati.nuvolosita,

            yAxisID: "nuvolosita",

            borderColor: "#687b88",
            backgroundColor: "rgba(104, 123, 136, 0.16)",

            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 3,
            tension: 0.35,
            fill: true
          }},

          {{
            type: "bar",
            label: "Precipitazione mm",
            data: dati.precipitazione,

            yAxisID: "precipitazione",

            backgroundColor: "rgba(47, 137, 202, 0.68)",
            borderColor: "#1679ba",
            borderWidth: 1,
            borderRadius: 4
          }}
        ]
      }},

      options: {{
        ...opzioniComuni,

        scales: {{
          ...opzioniComuni.scales,

          nuvolosita: {{
            type: "linear",
            position: "left",
            min: 0,
            max: 100,

            title: {{
              display: true,
              text: "Nuvolosità %"
            }},

            grid: {{
              color: "rgba(16, 43, 59, 0.08)"
            }}
          }},

          precipitazione: {{
            type: "linear",
            position: "right",
            min: 0,

            title: {{
              display: true,
              text: "Precipitazione mm"
            }},

            grid: {{
              drawOnChartArea: false
            }}
          }}
        }}
      }}
    }}
  );

  /*
   * 3. GRAFICO VENTO
   */

    const graficoVento = new Chart(
    canvasVento.getContext("2d"),
    {{
      type: "line",

      data: {{
        labels: dati.ore,

        datasets: [
          {{
            label: "Vento medio km/h",
            data: dati.vento,
            borderColor: "#0a8b72",
            backgroundColor: "rgba(10, 139, 114, 0.12)",
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 3,
            tension: 0.3,
            fill: true
          }},
          {{
            label: "Raffiche km/h",
            data: dati.raffiche,
            borderColor: "#9c3f84",
            backgroundColor: "rgba(156, 63, 132, 0.08)",
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 2.5,
            borderDash: [7, 4],
            tension: 0.3,
            fill: false
          }}
        ]
      }},

      options: {{
        responsive: true,
        maintainAspectRatio: false,

        interaction: {{
          mode: "index",
          intersect: false
        }},

        plugins: {{
          legend: {{
            position: "top",
            labels: {{
              usePointStyle: true,
              padding: 18,
              font: {{
                size: 12,
                weight: "600"
              }}
            }}
          }},
          tooltip: {{
            backgroundColor: "rgba(15, 43, 59, 0.95)",
            padding: 11,
            cornerRadius: 9
          }}
        }},

        scales: {{
          x: {{
            grid: {{
              color: "rgba(16, 43, 59, 0.06)"
            }},
            ticks: {{
              maxRotation: 0,
              autoSkip: true
            }}
          }},
          y: {{
            beginAtZero: true,
            title: {{
              display: true,
              text: "Velocità km/h"
            }},
            grid: {{
              color: "rgba(16, 43, 59, 0.08)"
            }}
          }}
        }}
      }}
    }}
  );

  meteoChartInstance = {{
    temperatura: graficoTemperatura,
    nuvolositaPrecipitazioni:
      graficoNuvolositaPrecipitazioni,
    vento: graficoVento,

    destroy: function() {{
      this.temperatura.destroy();
      this.nuvolositaPrecipitazioni.destroy();
      this.vento.destroy();
    }}
  }};
}}
/* ---------- APERTURA SCHEDA GIORNO ---------- */

function mostraGiorno(chiave, scheda, event) {{
  if (event && event.target.closest(".cml-day-inline-detail")) return;

  const dettaglio = document.getElementById("dettaglio-" + chiave);

  if (!dettaglio) return;

  const eraAperta = !dettaglio.hidden;

  document.querySelectorAll(".cml-day-card").forEach(function(card) {{
    card.classList.remove("active");
    card.setAttribute("aria-expanded", "false");
  }});

  document.querySelectorAll(".cml-day-inline-detail").forEach(function(panel) {{
    panel.hidden = true;
  }});

  if (meteoChartInstance) {{
    meteoChartInstance.destroy();
    meteoChartInstance = null;
  }}

  if (eraAperta) return;

  dettaglio.hidden = false;
  scheda.classList.add("active");
  scheda.setAttribute("aria-expanded", "true");

  if (typeof Chart !== "undefined") {{
    requestAnimationFrame(function() {{
      creaGrafici(chiave);
    }});
  }}
}}

/* ---------- MAPPA RADAR ---------- */

radarMap = L.map("radar-map", {{
  center: [{latitudine}, {longitudine}],
  zoom: 8,
  minZoom: 5,
  maxZoom: 18,
  zoomControl: true
}});

L.tileLayer(
  "https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",
  {{
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 18
  }}
).addTo(radarMap);

const pinIcon = L.divIcon({{
  className: "cml-radar-pin-wrapper",

  html:
    '<div style="width:20px;height:20px;background:#e63b45;border:3px solid #ffffff;border-radius:50%;box-shadow:0 0 0 3px rgba(230,59,69,0.40),0 4px 10px rgba(0,0,0,0.25);"></div>',

  iconSize: [20, 20],
  iconAnchor: [10, 10]
}});

L.marker([{latitudine}, {longitudine}], {{
  icon: pinIcon,
  title: "{html.escape(luogo)}"
}}).addTo(radarMap);

let radarTimes = [];
let radarLayers = {{}};
let radarFrameIndex = 0;
let radarPlaying = true;
let radarTimer = null;

function visualizzaFrameRadar(indice) {{
  if (radarTimes.length === 0) {{
    return;
  }}

  const tempoPrecedente = radarTimes[radarFrameIndex];

  if (radarLayers[tempoPrecedente]) {{
    radarLayers[tempoPrecedente].setOpacity(0);
  }}

  radarFrameIndex = indice;

  const tempo = radarTimes[radarFrameIndex];

  if (radarLayers[tempo]) {{
    radarLayers[tempo].setOpacity(0.72);
  }}

  const data = new Date(tempo * 1000);

  const ore = String(data.getHours()).padStart(2, "0");
  const minuti = String(data.getMinutes()).padStart(2, "0");

  const timestamp = document.getElementById("radar-timestamp");

  if (timestamp) {{
    timestamp.textContent = ore + ":" + minuti + " (ora locale)";
  }}
}}

function avviaRadar() {{
  if (radarTimer) {{
    clearInterval(radarTimer);
  }}

  radarTimer = setInterval(function() {{
    if (radarTimes.length === 0) {{
      return;
    }}

    const prossimo = (radarFrameIndex + 1) % radarTimes.length;
    visualizzaFrameRadar(prossimo);
  }}, 800);
}}

function togglePlayRadar() {{
  const bottone = document.getElementById("btn-play");

  if (radarPlaying) {{
    clearInterval(radarTimer);
    radarPlaying = false;
    bottone.textContent = "▶ Play";
  }} else {{
    avviaRadar();
    radarPlaying = true;
    bottone.textContent = "⏸ Pausa";
  }}
}}

// ---------- MAPPA ATTIVITÀ: DATI REALI ICON-2I ----------

function generaCelleCalabria() {{
  const celle = [];
  let lat = CALABRIA_BOUNDS.latMin;

  while (lat <= CALABRIA_BOUNDS.latMax) {{
    let lon = CALABRIA_BOUNDS.lonMin;
    while (lon <= CALABRIA_BOUNDS.lonMax) {{
      celle.push({{
        latitudine: Number(lat.toFixed(4)),
        longitudine: Number(lon.toFixed(4)),
        id: celle.length + 1
      }});
      lon += PASSO_LON;
    }}
    lat += PASSO_LAT;
  }}
  return celle;
}}

function etichettaMeteo(codice) {{
  const etichette = {{
    0: 'Sereno', 1: 'Quasi sereno', 2: 'Parzialmente nuvoloso', 3: 'Coperto',
    45: 'Nebbia', 48: 'Nebbia con brina', 51: 'Pioviggine debole',
    53: 'Pioviggine moderata', 55: 'Pioviggine intensa', 61: 'Pioggia debole',
    63: 'Pioggia moderata', 65: 'Pioggia forte', 71: 'Neve debole',
    73: 'Neve moderata', 75: 'Neve forte', 80: 'Rovesci deboli',
    81: 'Rovesci moderati', 82: 'Rovesci forti', 95: 'Temporale',
    96: 'Temporale con grandine', 99: 'Temporale con forte grandine'
  }};
  return etichette[codice] || 'Non disponibile';
}}

function nomeAttivita(tipo) {{
  const nomi = {{
    escursionismo: '🥾 Escursionismo',
    ciclismo: '🚴 Ciclismo',
    spiaggia: '🏖️ Spiaggia',
    fotografia: '📸 Fotografia',
    corsa: '🏃 Corsa',
    astronomia: '🔭 Astronomia'
  }};
  return nomi[tipo] || tipo;
}}

function punteggioAttivitaReale(dati, tipo) {{
  const temperatura = Number(dati.temperature_2m || 0);
  const percepita = Number(dati.apparent_temperature || temperatura);
  const pioggia = Number(dati.precipitation || 0);
  const vento = Number(dati.wind_speed_10m || 0);
  const raffica = Number(dati.wind_gusts_10m || 0);
  const nuvole = Number(dati.cloud_cover || 0);
  const codice = Number(dati.weather_code || 0);
  const temporale = [95, 96, 99].includes(codice);
  const rovesci = [80, 81, 82].includes(codice);
  const pioggiaMeteo = [51, 53, 55, 56, 57, 61, 63, 65, 66, 67].includes(codice);
  let punteggio = 100;

  if (temporale) punteggio -= 85;
  if (pioggia >= 2) punteggio -= Math.min(55, 20 + pioggia * 14);
  else if (pioggia > 0) punteggio -= Math.min(30, pioggia * 18);
  else if (rovesci || pioggiaMeteo) punteggio -= 25;
  if (raffica >= 70) punteggio -= 55;
  else if (raffica >= 50) punteggio -= 32;
  else if (raffica >= 35) punteggio -= 15;

  if (tipo === 'escursionismo') {{
    if (temperatura < 4 || temperatura > 31) punteggio -= 20;
    if (vento >= 30) punteggio -= Math.min(25, (vento - 25) * 2);
    if (codice >= 71 && codice <= 77) punteggio -= 40;
  }} else if (tipo === 'ciclismo') {{
    if (temperatura < 6 || temperatura > 30) punteggio -= 22;
    if (vento >= 20) punteggio -= Math.min(40, (vento - 18) * 2.5);
    if (raffica >= 40) punteggio -= 18;
  }} else if (tipo === 'spiaggia') {{
    if (temperatura < 22) punteggio -= Math.min(55, (22 - temperatura) * 6);
    if (temperatura > 35) punteggio -= 18;
    if (nuvole > 75) punteggio -= 30;
    else if (nuvole > 50) punteggio -= 12;
    if (vento >= 30) punteggio -= 25;
  }} else if (tipo === 'fotografia') {{
    if (temporale || pioggia >= 3) punteggio -= 35;
    if (nuvole >= 95) punteggio -= 25;
    else if (nuvole >= 30 && nuvole <= 75) punteggio += 5;
    if (raffica >= 55) punteggio -= 20;
  }} else if (tipo === 'corsa') {{
    if (percepita < 4 || percepita > 29) punteggio -= 28;
    if (vento >= 28) punteggio -= Math.min(35, (vento - 22) * 2.5);
    if (raffica >= 45) punteggio -= 18;
  }} else if (tipo === 'astronomia') {{
    if (nuvole > 85) punteggio -= 75;
    else if (nuvole > 65) punteggio -= 50;
    else if (nuvole > 40) punteggio -= 28;
    else if (nuvole > 20) punteggio -= 10;
    if (pioggia > 0 || pioggiaMeteo || rovesci) punteggio -= 35;
    if (temporale) punteggio -= 30;
    if (raffica >= 45) punteggio -= 18;
  }}

  return Math.max(0, Math.min(100, Math.round(punteggio)));
}}

function coloreDaPunteggio(punteggio) {{
  if (punteggio >= 80) return '#16a34a';
  if (punteggio >= 60) return '#84cc16';
  if (punteggio >= 40) return '#eab308';
  if (punteggio >= 20) return '#f97316';
  return '#dc2626';
}}

function testoDaPunteggio(punteggio) {{
  if (punteggio >= 80) return 'Molto favorevole';
  if (punteggio >= 60) return 'Favorevole';
  if (punteggio >= 40) return 'Possibile con attenzione';
  if (punteggio >= 20) return 'Poco favorevole';
  return 'Sconsigliata';
}}

async function scaricaDatiRealiCelle() {{
  const adesso = Date.now();
  if (datiCelleCache && cacheTimestamp && adesso - cacheTimestamp < CACHE_DURATION_MS) {{
    return datiCelleCache;
  }}

  const stato = document.getElementById('attivita-stato');
  if (stato) stato.textContent = '⏳ Download previsioni ICON-2I reali in corso…';

  const celle = generaCelleCalabria();
  const dimensioneBatch = 50;
  const risultati = [];

  for (let inizio = 0; inizio < celle.length; inizio += dimensioneBatch) {{
    const batch = celle.slice(inizio, inizio + dimensioneBatch);
    const parametri = new URLSearchParams({{
      latitude: batch.map(c => c.latitudine).join(','),
      longitude: batch.map(c => c.longitudine).join(','),
      models: 'italia_meteo_arpae_icon_2i',
      timezone: 'Europe/Rome',
      forecast_days: '1',
      current: 'temperature_2m,apparent_temperature,precipitation,weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m'
    }});

    const risposta = await fetch('https://api.open-meteo.com/v1/forecast?' + parametri.toString());
    if (!risposta.ok) throw new Error('Errore Open-Meteo ' + risposta.status);

    const datiBatch = await risposta.json();
    const arrayDati = Array.isArray(datiBatch) ? datiBatch : [datiBatch];

    batch.forEach(function(cella, indice) {{
      const dati = arrayDati[indice] || {{}};
      risultati.push({{
        ...cella,
        meteo: dati.current || {{}}
      }});
    }});

    if (stato) {{
      stato.textContent = `⏳ Previsioni reali: ${{Math.min(inizio + batch.length, celle.length)}}/${{celle.length}} celle…`;
    }}
  }}

  datiCelleCache = risultati;
  cacheTimestamp = Date.now();
  return risultati;
}}

function inizializzaMappaAttivita() {{
  if (attivitaMap) return;
  attivitaMap = L.map('attivita-map', {{
    center: [39.0, 16.45], zoom: 8, minZoom: 7, maxZoom: 12
  }});
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '© OpenStreetMap'
  }}).addTo(attivitaMap);
}}

async function aggiornaMappaAttivita() {{
  if (!attivitaMap) return;
  const selettore = document.getElementById('attivita-selector');
  const tipo = selettore ? selettore.value : 'escursionismo';
  const stato = document.getElementById('attivita-stato');

  try {{
    const datiCelle = await scaricaDatiRealiCelle();
    if (attivitaLayer) attivitaMap.removeLayer(attivitaLayer);
    attivitaLayer = L.layerGroup().addTo(attivitaMap);

    datiCelle.forEach(function(cella) {{
      const meteo = cella.meteo || {{}};
      const punteggio = punteggioAttivitaReale(meteo, tipo);
      const colore = coloreDaPunteggio(punteggio);
      const livello = testoDaPunteggio(punteggio);
      const latSud = cella.latitudine - PASSO_LAT / 2;
      const latNord = cella.latitudine + PASSO_LAT / 2;
      const lonOvest = cella.longitudine - PASSO_LON / 2;
      const lonEst = cella.longitudine + PASSO_LON / 2;

      const rettangolo = L.rectangle([[latSud, lonOvest], [latNord, lonEst]], {{
        color: colore, weight: 1, fillColor: colore, fillOpacity: 0.55
      }});

      rettangolo.bindPopup(`
        <div style="min-width:220px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.55;">
          <strong style="font-size:15px;">${{nomeAttivita(tipo)}}</strong><br>
          <span style="color:${{colore}};font-weight:800;">${{livello}} · ${{punteggio}}/100</span>
          <hr style="border:0;border-top:1px solid #dbe8ec;margin:8px 0;">
          <b>Condizioni ICON-2I</b><br>
          🌡️ ${{Number(meteo.temperature_2m || 0).toFixed(1)}} °C, percepita ${{Number(meteo.apparent_temperature || 0).toFixed(1)}} °C<br>
          🌧️ ${{Number(meteo.precipitation || 0).toFixed(1)}} mm<br>
          💨 ${{Number(meteo.wind_speed_10m || 0).toFixed(0)}} km/h, raffiche ${{Number(meteo.wind_gusts_10m || 0).toFixed(0)}} km/h<br>
          ☁️ ${{Number(meteo.cloud_cover || 0).toFixed(0)}}% · ${{etichettaMeteo(Number(meteo.weather_code || 0))}}<br>
          <small style="color:#607987;">Centro: ${{cella.latitudine.toFixed(3)}}°, ${{cella.longitudine.toFixed(3)}}°</small>
        </div>
      `);
      attivitaLayer.addLayer(rettangolo);
    }});

    if (stato) {{
      const orario = new Date(cacheTimestamp).toLocaleTimeString('it-IT', {{hour:'2-digit',minute:'2-digit'}});
      stato.textContent = `✅ ${{datiCelle.length}} celle con dati ICON-2I reali · cache 15 min · ${{orario}}`;
    }}
  }} catch (errore) {{
    console.error(errore);
    if (stato) stato.textContent = '❌ Errore nel download: ' + errore.message;
  }}
}}

function apriVistaAttivita() {{
  mostraVista('attivita');
  inizializzaMappaAttivita();
  setTimeout(function() {{
    if (attivitaMap) attivitaMap.invalidateSize();
    aggiornaMappaAttivita();
  }}, 250);
}}

fetch(
  "https://api.rainviewer.com/public/weather-maps.json"
)
  .then(function(response) {{
    return response.json();
  }})
  .then(function(payload) {{
    const frames = (
      payload
      && payload.radar
      && payload.radar.past
    ) ? payload.radar.past : [];

    radarTimes = frames.map(function(frame) {{
      return frame.time;
    }});

    frames.forEach(function(frame) {{
      const layer = L.tileLayer(
        "https://tilecache.rainviewer.com"
          + frame.path
          + "/256/{{z}}/{{x}}/{{y}}/2/1_1.png",
        {{
          opacity: 0,
          zIndex: 100,
          maxNativeZoom: 6,
          maxZoom: 18
        }}
      );

      layer.addTo(radarMap);
      radarLayers[frame.time] = layer;
    }});

    if (radarTimes.length > 0) {{
      radarFrameIndex = radarTimes.length - 1;
      visualizzaFrameRadar(radarFrameIndex);
      avviaRadar();
    }} else {{
      const timestamp = document.getElementById("radar-timestamp");

      if (timestamp) {{
        timestamp.textContent = "frame non disponibile";
      }}
    }}
  }})
  .catch(function() {{
    const timestamp = document.getElementById("radar-timestamp");

    if (timestamp) {{
      timestamp.textContent = "radar temporaneamente non disponibile";
    }}
  }});

/* ---------- AVVIO INIZIALE ---------- */

document.addEventListener("DOMContentLoaded", function() {{
  mostraVista("home");
}});
</script>

<!-- ===================== COPYRIGHT ===================== -->
<footer class="cml-copyright">
  <div><strong>Calabria Meteo Lab</strong> · © 2026 Saverio Campanella · Tutti i diritti riservati</div>
  <div>Codice, interfaccia e contenuti dell’applicazione sono protetti da copyright.</div>
</footer>

</body>
</html>
"""

    return documento_html


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
            placeholder=(
                "Scrivi es. Cosenza, Tropea, Scilla, "
                "Camigliatello Silano, Serra San Bruno..."
            ),
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

    documento = genera_app_completa(
        luogo,
        latitudine,
        longitudine,
        dati_terrestri,
        dati_orari,
        dati_giornalieri,
        dati_mare,
        distanza_mare_km,
    )

    components.html(
        documento,
        height=4300,
        scrolling=True,
    )

except Exception as errore:
    st.error(str(errore))


# =============================================================================
# PERCORSO METEO‑ASSISTITO
# =============================================================================

st.markdown("---")

st.header("🚗 Percorso meteo‑assistito")

st.markdown(
    """
    Calcola il percorso migliore tra due località e ricevi un consiglio sull'orario
    di partenza in base alle condizioni meteorologiche previste (pioggia, temporali,
    vento, neve, visibilità).
    """
)

colonna_1, colonna_2 = st.columns(2)

with colonna_1:
    partenza = st.text_input(
        "Luogo di partenza",
        placeholder="Es. Crotone",
        key="percorso_partenza",
    )

with colonna_2:
    arrivo = st.text_input(
        "Luogo di arrivo",
        placeholder="Es. Catanzaro",
        key="percorso_arrivo",
    )

colonna_3, colonna_4, colonna_5 = st.columns(3)

with colonna_3:
    data_partenza = st.date_input(
        "Data di partenza",
        value=datetime.now().date(),
        key="percorso_data",
    )

with colonna_4:
    ora_partenza = st.time_input(
        "Ora di partenza",
        value=datetime.now().time(),
        key="percorso_ora",
    )

with colonna_5:
    mezzo = st.selectbox(
        "Mezzo di trasporto",
        ["Automobile", "Bicicletta", "A piedi"],
        key="percorso_mezzo",
    )

if st.button("Calcola percorso", key="percorso_calcola"):
    if not partenza or not arrivo:
        st.error("Inserisci sia il luogo di partenza che quello di arrivo.")
    else:
        try:
            with st.spinner("Geocodifica delle località in corso..."):
                nome_partenza, lat_partenza, lon_partenza = geocodifica_generale(partenza)
                nome_arrivo, lat_arrivo, lon_arrivo = geocodifica_generale(arrivo)

            with st.spinner("Calcolo del percorso stradale..."):
                # Nota: senza API key di OpenRouteService, questa chiamata fallirà.
                # Per un uso reale, ottieni una API key gratuita da https://openrouteservice.org/
                percorso = scarica_percorso_ors(
                    lat_partenza,
                    lon_partenza,
                    lat_arrivo,
                    lon_arrivo,
                    profilo="driving-car",
                    api_key=eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjhlOTE0MDk3MjlhNjRkYTU4M2RhNWMwNmFmNjlhNTlmIiwiaCI6Im11cm11cjY0In0=,  # Inserisci la tua API key qui
                )

            with st.spinner("Estrazione punti lungo il percorso..."):
                punti = estrai_punti_percorso(percorso["geometria"], numero_punti=12)

            with st.spinner("Scaricamento previsioni meteo lungo il percorso..."):
                dati_meteo = scarica_meteo_punti_percorso(
                    punti,
                    data_partenza,
                    ora_partenza,
                    percorso["durata_secondi"] / 60.0,
                )

            with st.spinner("Valutazione condizioni meteo..."):
                valutazione = valuta_percorso_completo(dati_meteo)

            with st.spinner("Confronto orari di partenza..."):
                risultati = confronta_orari_partenza(
                    percorso,
                    data_partenza,
                    ora_partenza,
                    punti,
                )

            consiglio = genera_consiglio_orario(risultati, ora_partenza)

            riepilogo_html = genera_riepilogo_percorso_html(
                percorso,
                valutazione,
                consiglio,
                nome_partenza,
                nome_arrivo,
            )

            components.html(riepilogo_html, height=600, scrolling=True)

            # Mostra tabella con classifica orari
            if risultati:
                st.subheader("📊 Classifica orari di partenza")
                dati_tabella = []
                for r in risultati[:5]:
                    dati_tabella.append({
                        "Orario": r["orario_partenza"].strftime("%H:%M"),
                        "Indice meteo medio": r["indice_rischio_medio"],
                        "Indice meteo max": r["indice_rischio_max"],
                    })
                df_tabella = pd.DataFrame(dati_tabella)
                st.dataframe(df_tabella, hide_index=True, use_container_width=True)

        except Exception as errore:
            st.error(f"Errore nel calcolo del percorso: {errore}")
            st.info(
                "Nota: il calcolo del percorso richiede una API key di OpenRouteService. "
                "Ottienine una gratuita su https://openrouteservice.org/ e inseriscila nel codice."
            )

