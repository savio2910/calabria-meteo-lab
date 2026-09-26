import html
import json
import math
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
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
        max-width: 1400px !important;
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
      }
      [data-testid="stAppViewContainer"] { background: #eef5f8; }
      [data-testid="stHeader"] { background: transparent; }
      iframe { background: #eef5f8 !important; }
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
    "lunedì", "martedì", "mercoledì", "giovedì",
    "venerdì", "sabato", "domenica",
]

MESI_IT = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]

CODICI_METEO = {
    0: ("☀️", "Sereno"), 1: ("🌤️", "Quasi sereno"),
    2: ("⛅", "Parzialmente nuvoloso"), 3: ("☁️", "Coperto"),
    45: ("🌫️", "Nebbia"), 48: ("🌫️", "Nebbia con brina"),
    51: ("🌦️", "Pioviggine debole"), 53: ("🌦️", "Pioviggine moderata"),
    55: ("🌧️", "Pioviggine intensa"), 56: ("🌧️", "Pioggia gelata debole"),
    57: ("🌧️", "Pioggia gelata intensa"), 61: ("🌧️", "Pioggia debole"),
    63: ("🌧️", "Pioggia moderata"), 65: ("🌧️", "Pioggia forte"),
    66: ("🌨️", "Pioggia gelata debole"), 67: ("🌨️", "Pioggia gelata forte"),
    71: ("❄️", "Neve debole"), 73: ("❄️", "Neve moderata"),
    75: ("❄️", "Neve forte"), 77: ("❄️", "Granelli di neve"),
    80: ("🌦️", "Rovesci deboli"), 81: ("🌧️", "Rovesci moderati"),
    82: ("🌧️", "Rovesci forti"), 85: ("🌨️", "Rovesci nevosi deboli"),
    86: ("🌨️", "Rovesci nevosi forti"), 95: ("⛈️", "Temporale"),
    96: ("⛈️", "Temporale con grandine"),
    99: ("⛈️", "Temporale con forte grandine"),
}

VARIABILI_CORRENTI = [
    "temperature_2m", "relative_humidity_2m", "apparent_temperature",
    "weather_code", "cloud_cover", "pressure_msl", "wind_speed_10m",
    "wind_direction_10m", "wind_gusts_10m",
]

VARIABILI_ORARIE = [
    "temperature_2m", "relative_humidity_2m", "apparent_temperature",
    "precipitation", "weather_code", "cloud_cover", "wind_speed_10m",
    "wind_direction_10m", "wind_gusts_10m",
]

VARIABILI_GIORNALIERE = [
    "weather_code", "temperature_2m_max", "temperature_2m_min",
    "sunrise", "sunset", "moonrise", "moonset", "moon_phase",
    "precipitation_sum", "wind_speed_10m_max", "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
]

VARIABILI_MARINE_CORRENTI = [
    "wave_height", "wave_direction", "wave_period", "wave_peak_period",
    "wind_wave_height", "wind_wave_direction", "wind_wave_period",
    "swell_wave_height", "swell_wave_direction", "swell_wave_period",
    "sea_surface_temperature",
]

VARIABILI_MARINE_ORARIE = VARIABILI_MARINE_CORRENTI.copy()
VARIABILI_MARINE_GIORNALIERE = [
    "wave_height_max", "wave_direction_dominant", "wave_period_max",
    "wind_wave_height_max", "swell_wave_height_max",
    "swell_wave_direction_dominant",
]

# =============================================================================
# FORMATTAZIONE E ICONE
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
        return direzioni[int((float(gradi) + 22.5) // 45) % 8]
    except (TypeError, ValueError):
        return "—"


def meteo(codice):
    try:
        if codice is None or pd.isna(codice):
            return "❔", "Non disponibile"
        return CODICI_METEO.get(int(codice), ("❔", "Non disponibile"))
    except (TypeError, ValueError):
        return "❔", "Non disponibile"


def icona_notturna_svg(codice):
    try:
        codice = int(codice)
    except (TypeError, ValueError):
        return "❔"

    if codice in [0, 1]:
        return """
        <svg class="cml-weather-svg" viewBox="0 0 64 64" aria-label="Luna serena">
          <circle cx="31" cy="28" r="18" fill="#FDE68A"/>
          <circle cx="40" cy="20" r="18" fill="#142549"/>
          <circle cx="20" cy="20" r="2" fill="#FBBF24" opacity=".7"/>
          <circle cx="24" cy="36" r="2.5" fill="#FBBF24" opacity=".6"/>
        </svg>
        """

    if codice == 2:
        return """
        <svg class="cml-weather-svg" viewBox="0 0 64 64" aria-label="Luna parzialmente nuvolosa">
          <circle cx="27" cy="25" r="17" fill="#FDE68A"/>
          <circle cx="36" cy="17" r="17" fill="#142549"/>
          <path d="M16 47 C16 41 20 37 26 37 C28 31 34 28 39 31 C44 31 48 35 48 40 C53 40 56 43 56 47 C56 52 52 55 47 55 L22 55 C18 55 15 52 15 48 Z" fill="#DCEAF1" stroke="#AABFCB" stroke-width="1.5"/>
        </svg>
        """

    if codice == 3:
        return """
        <svg class="cml-weather-svg" viewBox="0 0 64 64" aria-label="Cielo coperto">
          <path d="M10 42 C10 35 16 30 23 30 C26 22 34 18 42 22 C49 22 55 28 55 36 C60 36 63 40 63 45 C63 51 58 55 52 55 L19 55 C13 55 9 50 9 44 Z" fill="#AABBC6" stroke="#8196A3" stroke-width="1.5"/>
        </svg>
        """

    if codice in [45, 48]:
        return """
        <svg class="cml-weather-svg" viewBox="0 0 64 64" aria-label="Nebbia notturna">
          <circle cx="24" cy="22" r="14" fill="#FDE68A"/>
          <circle cx="32" cy="15" r="14" fill="#142549"/>
          <path d="M10 39 H54 M7 46 H49 M13 53 H57" stroke="#B7C7D1" stroke-width="4" stroke-linecap="round" opacity=".95"/>
        </svg>
        """

    if codice in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
        return """
        <svg class="cml-weather-svg" viewBox="0 0 64 64" aria-label="Pioggia notturna">
          <circle cx="25" cy="22" r="15" fill="#FDE68A"/>
          <circle cx="33" cy="15" r="15" fill="#142549"/>
          <path d="M12 42 C12 36 17 32 23 32 C26 26 32 24 38 27 C44 27 49 32 49 38 C54 38 57 41 57 46 C57 51 53 54 48 54 L20 54 C15 54 11 50 11 45 Z" fill="#AFC8D8" stroke="#7B9EB3" stroke-width="1.5"/>
          <path d="M23 56 L20 62 M34 56 L31 62 M45 56 L42 62" stroke="#41A6DF" stroke-width="3" stroke-linecap="round"/>
        </svg>
        """

    if codice in [71, 73, 75, 77, 85, 86]:
        return """
        <svg class="cml-weather-svg" viewBox="0 0 64 64" aria-label="Neve notturna">
          <circle cx="25" cy="22" r="15" fill="#FDE68A"/>
          <circle cx="33" cy="15" r="15" fill="#142549"/>
          <path d="M12 42 C12 36 17 32 23 32 C26 26 32 24 38 27 C44 27 49 32 49 38 C54 38 57 41 57 46 C57 51 53 54 48 54 L20 54 C15 54 11 50 11 45 Z" fill="#D9EAF3" stroke="#9AB7C7" stroke-width="1.5"/>
          <g stroke="#F8FDFF" stroke-width="2" stroke-linecap="round">
            <path d="M23 57 L23 63 M20 60 L26 60"/>
            <path d="M35 57 L35 63 M32 60 L38 60"/>
            <path d="M47 57 L47 63 M44 60 L50 60"/>
          </g>
        </svg>
        """

    if codice in [95, 96, 99]:
        return """
        <svg class="cml-weather-svg" viewBox="0 0 64 64" aria-label="Temporale notturno">
          <circle cx="25" cy="21" r="15" fill="#FDE68A"/>
          <circle cx="33" cy="14" r="15" fill="#142549"/>
          <path d="M11 42 C11 35 17 31 23 31 C26 25 33 23 39 26 C46 26 50 31 50 37 C55 37 58 41 58 46 C58 51 54 54 49 54 L20 54 C14 54 10 50 10 44 Z" fill="#657A91" stroke="#43576C" stroke-width="1.5"/>
          <path d="M36 49 L29 61 L35 61 L31 68 L44 54 L38 54 Z" fill="#FFD54A" stroke="#F59E0B" stroke-width="1"/>
        </svg>
        """

    return "❔"


def icona_meteo_oraria(codice, notte=False):
    icona_diurna, descrizione = meteo(codice)
    if notte:
        return icona_notturna_svg(codice), descrizione
    return icona_diurna, descrizione


def data_it(valore):
    try:
        data = pd.Timestamp(valore)
        return f"{GIORNI_IT[data.weekday()]} {data.day} {MESI_IT[data.month - 1]}"
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
        if any(x is None or pd.isna(x) for x in (ora, alba, tramonto)):
            return False
        istante = pd.Timestamp(ora)
        return istante < pd.Timestamp(alba) or istante >= pd.Timestamp(tramonto)
    except (TypeError, ValueError):
        return False


# =============================================================================
# NORMALIZZAZIONE E COSTA
# =============================================================================

def normalizza_comune(nome):
    if nome is None:
        return ""
    testo = str(nome).strip().casefold()
    testo = testo.replace("’", "'").replace("`", "'")
    testo = testo.replace("-", " ").replace("_", " ")
    testo = unicodedata.normalize("NFKD", testo)
    testo = "".join(c for c in testo if not unicodedata.combining(c))
    testo = " ".join(testo.split())
    alias = {
        "reggio di calabria": "reggio calabria",
        "corigliano rossano": "corigliano rossano",
        "isola capo rizzuto": "isola di capo rizzuto",
        "sant ilario dello ionio": "sant ilario dello ionio",
    }
    return alias.get(testo, testo)


@st.cache_data(ttl=3600, show_spinner=False)
def carica_comuni_costieri():
    if not FILE_COMUNI_COSTIERI.exists():
        raise FileNotFoundError(
            "Manca il file comuni_costieri_calabria.csv nella stessa cartella di app.py."
        )
    dataframe = pd.read_csv(FILE_COMUNI_COSTIERI)
    if "comune" not in dataframe.columns:
        raise ValueError("Il CSV deve contenere una colonna chiamata 'comune'.")
    elenco = dataframe["comune"].dropna().astype(str).str.strip()
    return {normalizza_comune(nome) for nome in elenco if nome}


def comune_e_costiero(comune_amministrativo, elenco_costieri):
    return normalizza_comune(comune_amministrativo) in elenco_costieri


# =============================================================================
# GEOLOCALIZZAZIONE
# =============================================================================

@st.cache_data(ttl=86400, show_spinner=False)
def geocodifica_calabria(nome):
    try:
        geocoder = Nominatim(user_agent="calabria_meteo_lab_v24", timeout=15)
        risposta = geocoder.geocode(
            f"{nome}, Calabria, Italia",
            exactly_one=True,
            addressdetails=True,
            timeout=15,
        )
    except (GeocoderServiceError, GeocoderTimedOut) as exc:
        raise RuntimeError(
            "Servizio di geolocalizzazione temporaneamente non disponibile."
        ) from exc

    if risposta is None:
        raise ValueError(f"Località «{nome}» non trovata.")

    indirizzo = risposta.raw.get("address", {})
    regione = str(indirizzo.get("state", "") or indirizzo.get("region", "")).casefold()
    latitudine = float(risposta.latitude)
    longitudine = float(risposta.longitude)

    in_calabria = "calabria" in regione or (
        37.75 <= latitudine <= 40.15 and 15.60 <= longitudine <= 17.25
    )
    if not in_calabria:
        raise ValueError(f"❌ «{nome}» non è in Calabria.")

    nome_risolto = (
        indirizzo.get("city")
        or indirizzo.get("town")
        or indirizzo.get("village")
        or indirizzo.get("hamlet")
        or indirizzo.get("municipality")
        or nome.title()
    )

    chiavi = [
        "municipality", "city", "town", "village", "hamlet",
        "suburb", "city_district", "district", "borough", "county",
    ]
    candidati = [nome, nome_risolto]
    candidati.extend(str(indirizzo[k]) for k in chiavi if indirizzo.get(k))
    candidati = list(dict.fromkeys(candidati))

    return nome_risolto, latitudine, longitudine, candidati


def risolvi_localita(testo):
    nome = str(testo).strip()
    if not nome:
        raise ValueError("Inserisci una località calabrese.")

    indice = {comune.casefold(): comune for comune in COMUNI_RAPIDI}
    nome_norm = ALIASES.get(nome.casefold(), nome)

    if nome_norm.casefold() in indice:
        comune = indice[nome_norm.casefold()]
        latitudine, longitudine = COMUNI_RAPIDI[comune]
        return comune, latitudine, longitudine, [comune, nome_norm, nome]

    return geocodifica_calabria(nome_norm)


# =============================================================================
# API
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
        risposta = requests.get(API_METEO_URL, params=parametri, timeout=25)
        risposta.raise_for_status()
        return risposta.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Errore nella ricezione dei dati ICON-2I: {exc}") from exc


def distanza_haversine_km(lat1, lon1, lat2, lon2):
    raggio = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return raggio * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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
        risposta = requests.get(API_MARE_URL, params=parametri, timeout=25)
        risposta.raise_for_status()
        dati = risposta.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Errore nella ricezione della previsione marina: {exc}") from exc

    lat_mare = float(dati.get("latitude", latitudine))
    lon_mare = float(dati.get("longitude", longitudine))
    distanza = distanza_haversine_km(latitudine, longitudine, lat_mare, lon_mare)
    return dati, distanza


# =============================================================================
# PREPARAZIONE DATI
# =============================================================================

def calcola_dati_diurni(ore_giorno, alba, tramonto):
    if ore_giorno.empty:
        return 0, 0
    if alba is not None and tramonto is not None:
        ore_diurne = ore_giorno.loc[
            (ore_giorno["time"] >= pd.Timestamp(alba))
            & (ore_giorno["time"] <= pd.Timestamp(tramonto))
        ]
    else:
        ore_diurne = ore_giorno.loc[
            (ore_giorno["time"].dt.hour >= 7)
            & (ore_giorno["time"].dt.hour <= 20)
        ]

    target = ore_diurne if not ore_diurne.empty else ore_giorno
    nubi = round(target["cloud_cover"].mean()) if "cloud_cover" in target else 0

    for codice in [99, 96, 95, 82, 81, 80, 65, 63, 61, 55, 53, 51]:
        if (target["weather_code"] == codice).sum() >= 2:
            return codice, nubi

    return (target["weather_code"].mode().iloc[0] if not target.empty else 0), nubi


def prepara_dati_terrestri(dati):
    ore_raw = pd.DataFrame(dati["hourly"])
    giorni = pd.DataFrame(dati["daily"])
    ore_raw["time"] = pd.to_datetime(ore_raw["time"])
    giorni["time"] = pd.to_datetime(giorni["time"])

    codici, nubi = [], []
    for _, riga in giorni.iterrows():
        ore_giorno = ore_raw.loc[ore_raw["time"].dt.date == riga["time"].date()]
        codice, cloud = calcola_dati_diurni(ore_giorno, riga.get("sunrise"), riga.get("sunset"))
        codici.append(codice)
        nubi.append(cloud)

    giorni["weather_code_prevalente"] = codici
    giorni["cloud_cover_diurno"] = nubi
    giorni["Da"] = giorni["wind_direction_10m_dominant"].map(direzione)
    giorni["Fase lunare"] = giorni["moon_phase"].map(fase_lunare)

    ora_locale = datetime.now(FUSO_ORARIO).replace(tzinfo=None)
    ore = ore_raw.loc[ore_raw["time"] >= pd.Timestamp(ora_locale).floor("h")].copy()
    ore["Da"] = ore["wind_direction_10m"].map(direzione)

    notti = []
    for _, riga in ore.iterrows():
        righe = giorni.loc[giorni["time"].dt.date == riga["time"].date()]
        if righe.empty:
            notti.append(False)
        else:
            giorno = righe.iloc[0]
            notti.append(e_notte(riga["time"], giorno.get("sunrise"), giorno.get("sunset")))

    ore["Notte"] = notti
    icone = ore.apply(lambda r: icona_meteo_oraria(r["weather_code"], bool(r["Notte"])), axis=1)
    ore["Icona"] = icone.map(lambda x: x[0])
    ore["Scenario"] = icone.map(lambda x: x[1])

    return ore.reset_index(drop=True), giorni.reset_index(drop=True)


# =============================================================================
# STATO DEL MARE E RISCHIO
# =============================================================================

def stato_mare_da_onda(altezza):
    try:
        if altezza is None or pd.isna(altezza):
            return "Non disponibile", "⚪", "cml-mare-nd"
        h = float(altezza)
        if h < 0.10:
            return "Calmo", "🟦", "cml-mare-calmo"
        if h < 0.50:
            return "Quasi calmo", "🟦", "cml-mare-quasi-calmo"
        if h < 1.25:
            return "Poco mosso", "🟩", "cml-mare-poco-mosso"
        if h < 2.50:
            return "Mosso", "🟨", "cml-mare-mosso"
        if h < 4.00:
            return "Molto mosso", "🟧", "cml-mare-molto-mosso"
        if h < 6.00:
            return "Agitato", "🟥", "cml-mare-agitato"
        return "Molto agitato", "🟥", "cml-mare-molto-agitato"
    except (TypeError, ValueError):
        return "Non disponibile", "⚪", "cml-mare-nd"


def valuta_rischio_locale(riga):
    precipitazione = float(riga.get("precipitation_sum", 0) or 0)
    raffica = float(riga.get("wind_gusts_10m_max", 0) or 0)
    codice = int(riga.get("weather_code_prevalente", riga.get("weather_code", 0)))

    if precipitazione >= 100 or raffica >= 100 or codice in [96, 99]:
        return "rosso", "temporali" if codice in [95, 96, 99] else ("vento" if raffica >= 100 else "precipitazioni")
    if precipitazione >= 50 or raffica >= 70 or codice in [95, 96, 99]:
        return "arancione", "temporali" if codice in [95, 96, 99] else ("vento" if raffica >= 70 else "precipitazioni")
    if precipitazione >= 20 or raffica >= 50 or codice in [80, 81, 82]:
        return "giallo", "rovesci" if codice in [80, 81, 82] else ("vento" if raffica >= 50 else "precipitazioni")
    return "verde", "nessuna criticità"


def badge_rischio_html(livello, rischio):
    palette = {
        "verde": ("#12855c", "✅", "Nessuna criticità stimata"),
        "giallo": ("#b77906", "⚠️", "Attenzione meteorologica"),
        "arancione": ("#d85d05", "🟠", "Rischio meteorologico elevato"),
        "rosso": ("#be2635", "🔴", "Rischio meteorologico molto elevato"),
    }
    colore, icona, testo = palette.get(livello, palette["verde"])
    return f'<span class="cml-risk-badge" style="background:{colore};"><span>{icona}</span><span>{html.escape(testo)} · {html.escape(rischio.title())}</span></span>'


# =============================================================================
# GENERAZIONE APP
# =============================================================================

def genera_app_completa(luogo, latitudine, longitudine, dati_terrestri, ore, giorni, dati_mare=None, distanza_mare_km=None):
    corrente = dati_terrestri["current"]
    icona_corrente, descrizione_corrente = meteo(corrente.get("weather_code"))

    metriche = [
        ("🌡️", "Percepita", numero(corrente.get("apparent_temperature"), 1, " °C")),
        ("💧", "Umidità", numero(corrente.get("relative_humidity_2m"), 0, " %")),
        ("☁️", "Nuvolosità", numero(corrente.get("cloud_cover"), 0, " %")),
        ("💨", "Vento", numero(corrente.get("wind_speed_10m"), 0, " km/h")),
        ("🧭", "Provenienza", direzione(corrente.get("wind_direction_10m"))),
        ("🌬️", "Raffica", numero(corrente.get("wind_gusts_10m"), 0, " km/h")),
        ("🌀", "Pressione", numero(corrente.get("pressure_msl"), 1, " hPa")),
    ]

    metriche_html = "".join(
        f'<div class="cml-metric-card"><div class="cml-metric-icon">{icona}</div><div><div class="cml-metric-label">{html.escape(etichetta)}</div><div class="cml-metric-value">{html.escape(valore)}</div></div></div>'
        for icona, etichetta, valore in metriche
    )

    mare_html = ""
    if dati_mare is not None and dati_mare.get("current"):
        cm = dati_mare["current"]
        altezza = cm.get("wave_height")
        stato, icona, classe = stato_mare_da_onda(altezza)
        mare_html = f'''
        <section class="cml-marine-box">
          <div class="cml-marine-head"><div><span class="cml-eyebrow">BOLLETTINO COSTIERO</span><h2>🌊 Vento e stato del mare</h2><p>Previsione marina per il comune costiero. Cella modellistica a circa {numero(distanza_mare_km, 1, " km")} dal punto selezionato.</p></div><div class="cml-sea-status {classe}"><span>{icona}</span><div><small>STATO DEL MARE</small><strong>{html.escape(stato)}</strong></div></div></div>
          <div class="cml-marine-grid">
            <div class="cml-marine-card"><span>🌊 Altezza onda</span><strong>{numero(altezza, 2, " m")}</strong><small>Onda significativa</small></div>
            <div class="cml-marine-card"><span>🧭 Provenienza onda</span><strong>{direzione(cm.get("wave_direction"))}</strong><small>{numero(cm.get("wave_direction"), 0, "°")}</small></div>
            <div class="cml-marine-card"><span>〰️ Periodo medio</span><strong>{numero(cm.get("wave_period"), 1, " s")}</strong><small>Intervallo medio d'onda</small></div>
            <div class="cml-marine-card"><span>📈 Periodo di picco</span><strong>{numero(cm.get("wave_peak_period"), 1, " s")}</strong><small>Energia dominante</small></div>
            <div class="cml-marine-card"><span>💨 Mare del vento</span><strong>{numero(cm.get("wind_wave_height"), 2, " m")}</strong><small>Componente wind sea</small></div>
            <div class="cml-marine-card"><span>🌐 Mare di fondo</span><strong>{numero(cm.get("swell_wave_height"), 2, " m")}</strong><small>Componente swell</small></div>
            <div class="cml-marine-card"><span>🌡️ Temperatura mare</span><strong>{numero(cm.get("sea_surface_temperature"), 1, " °C")}</strong><small>Temperatura superficiale</small></div>
          </div>
          <div class="cml-marine-note">ℹ️ La direzione indica <b>da dove proviene</b> il moto ondoso. I valori sono modellistici e non sostituiscono fonti nautiche o avvisi ufficiali.</div>
        </section>
        '''

    etichette = ["OGGI", "DOMANI", "DOPODOMANI"]
    carte = []
    for indice, (_, riga) in enumerate(giorni.iterrows()):
        codice = riga.get("weather_code_prevalente", riga.get("weather_code"))
        icona, descrizione = meteo(codice)
        livello, rischio = valuta_rischio_locale(riga)
        classe_icona = "cml-icon-thunder" if codice in [95, 96, 99] else "cml-icon-snow" if codice in range(71, 87) else "cml-icon-rain" if codice in range(51, 68) or codice in range(80, 83) else "cml-icon-cloud" if codice in [2, 3, 45, 48] else "cml-icon-sun"
        carte.append(f'''
        <article class="cml-day-card"><div class="cml-day-head"><span class="cml-day-tag">{etichette[indice] if indice < len(etichette) else "PROSSIMAMENTE"}</span><span class="cml-day-date">{html.escape(data_it(riga["time"]))}</span></div><div class="cml-risk-row">{badge_rischio_html(livello, rischio)}</div><div class="cml-day-weather"><div class="cml-day-icon {classe_icona}">{icona}</div><div><div class="cml-day-description">{html.escape(descrizione)}</div><div class="cml-day-moon">{html.escape(str(riga.get("Fase lunare", "🌙 Luna")))}</div></div></div><div class="cml-temperature-grid"><div class="cml-temp-box"><span>MINIMA</span><strong class="cml-temp-min">↓ {numero(riga["temperature_2m_min"], 1, "°")}</strong></div><div class="cml-temp-box"><span>MASSIMA</span><strong class="cml-temp-max">↑ {numero(riga["temperature_2m_max"], 1, "°")}</strong></div></div><div class="cml-day-details"><div><span>☁️ Nuvolosità diurna</span><b>{numero(riga.get("cloud_cover_diurno"), 0, " %")}</b></div><div><span>🌧️ Precipitazione</span><b>{numero(riga.get("precipitation_sum"), 1, " mm")}</b></div><div><span>💨 Vento massimo</span><b>{numero(riga.get("wind_speed_10m_max"), 0, " km/h")}</b></div><div><span>🌬️ Raffica massima</span><b>{numero(riga.get("wind_gusts_10m_max"), 0, " km/h")}</b></div><div><span>🧭 Direzione dominante</span><b>{html.escape(str(riga.get("Da", "—")))}</b></div></div><div class="cml-astro-grid"><div><span>☀️ Alba</span><b>{ora_it(riga.get("sunrise"))}</b></div><div><span>🌇 Tramonto</span><b>{ora_it(riga.get("sunset"))}</b></div><div><span>🌙 Sorge</span><b>{ora_it(riga.get("moonrise"))}</b></div><div><span>🌘 Tramonta</span><b>{ora_it(riga.get("moonset"))}</b></div></div></article>
        ''')

    date_disponibili = sorted(ore["time"].dt.date.unique())
    if not date_disponibili:
        raise RuntimeError("Nessun dato orario disponibile.")

    dati_grafici = {}
    pulsanti = []
    tabelle = []

    for indice, data_giorno in enumerate(date_disponibili):
        chiave = str(data_giorno)
        ore_giorno = ore.loc[ore["time"].dt.date == data_giorno]
        dati_grafici[chiave] = {
            "ore": ore_giorno["time"].dt.strftime("%H:%M").tolist(),
            "temperatura": [round(float(v), 1) if pd.notna(v) else None for v in ore_giorno["temperature_2m"].tolist()],
            "vento": [round(float(v), 1) if pd.notna(v) else None for v in ore_giorno["wind_speed_10m"].tolist()],
            "precipitazione": [round(float(v), 1) if pd.notna(v) else None for v in ore_giorno["precipitation"].tolist()],
        }
        pulsanti.append(f'<button class="cml-tab-btn {"active" if indice == 0 else ""}" type="button" onclick="mostraGiorno(\'{chiave}\', this)">📅 {html.escape(data_it(data_giorno).title())}</button>')
        righe = []
        for _, riga in ore_giorno.iterrows():
            notte = "cml-night-row" if bool(riga.get("Notte", False)) else ""
            righe.append(f'<tr class="{notte}"><td>{riga["time"].strftime("%H:%M")}</td><td class="cml-scenario-cell"><span class="cml-table-icon">{riga["Icona"]}</span><span>{html.escape(str(riga["Scenario"]))}</span></td><td>{numero(riga["temperature_2m"], 1)}</td><td>{numero(riga["apparent_temperature"], 1)}</td><td>{numero(riga["precipitation"], 1)}</td><td>{numero(riga["wind_speed_10m"], 0)}</td><td>{html.escape(str(riga["Da"]))}</td><td>{numero(riga["wind_gusts_10m"], 0)}</td><td>{numero(riga["cloud_cover"], 0)}</td><td>{numero(riga["relative_humidity_2m"], 0)}</td></tr>')
        tabelle.append(f'<div id="tab-{chiave}" class="cml-day-table-container" style="{"display:block;" if indice == 0 else "display:none;"}"><div class="cml-table-wrap"><table class="cml-table"><thead><tr><th>Ora</th><th>Scenario</th><th>Temp. °C</th><th>Percepita °C</th><th>Pioggia mm</th><th>Vento km/h</th><th>Da</th><th>Raffica km/h</th><th>Nubi %</th><th>Umidità %</th></tr></thead><tbody>{"".join(righe)}</tbody></table></div></div>')

    chiave_iniziale = str(date_disponibili[0])
    dati_grafici_json = json.dumps(dati_grafici, ensure_ascii=False)

    html_finale = f'''<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><script src="https://cdn.jsdelivr.net/npm/chart.js"></script><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><style>
:root{{--ink:#102b3b;--muted:#607987;--orange:#f26e17;--page:#eef5f8}}*{{box-sizing:border-box}}body{{margin:0;padding:8px;min-height:100vh;color:var(--ink);background:var(--page);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;line-height:1.45}}.cml-hero{{position:relative;overflow:hidden;margin:8px 0 22px;padding:42px 46px 38px;border:1px solid #07516c;border-radius:28px;color:#fff;background:linear-gradient(135deg,#06324d 0%,#075b78 52%,#087f91 100%);box-shadow:0 14px 32px rgba(9,61,83,.22)}}.cml-brand{{display:inline-flex;align-items:center;gap:10px;padding:8px 15px;border:1px solid rgba(255,255,255,.25);border-radius:999px;background:rgba(0,35,55,.35);color:#d7f7fa;font-size:11px;font-weight:800;letter-spacing:2px}}.cml-brand-mark{{width:11px;height:11px;border-radius:50%;background:#ffd45c;box-shadow:0 0 0 5px rgba(255,212,92,.18)}}.cml-hero h1{{margin:19px 0 10px;color:#fff;font-size:44px;font-weight:800;letter-spacing:-1.5px;line-height:1.1}}.cml-hero p{{max-width:760px;margin:0;color:#e2f5f8;font-size:15px;line-height:1.7}}.cml-current,.cml-marine-box,.cml-radar-box,.cml-day-card,.cml-chart-box{{border:1px solid #d5e4e9;border-radius:24px;background:#fff;box-shadow:0 8px 28px rgba(23,67,84,.10)}}.cml-current{{overflow:hidden;margin:22px 0 25px}}.cml-current-main{{display:flex;align-items:center;justify-content:space-between;gap:28px;padding:34px 38px;border-bottom:1px solid #e2edf0}}.cml-kicker{{display:inline-flex;align-items:center;gap:8px;padding:7px 13px;border-radius:999px;background:#e3f5f8;color:#087087;font-size:11px;font-weight:800;letter-spacing:1.2px}}.cml-live-dot{{width:8px;height:8px;border-radius:50%;background:#18a579;box-shadow:0 0 0 4px rgba(24,165,121,.16)}}.cml-place-block h2{{margin:13px 0 10px;font-size:35px}}.cml-condition{{display:inline-flex;align-items:center;gap:8px;padding:8px 13px;border:1px solid #e1edf0;border-radius:11px;color:#4d6570;background:#f8fbfc;font-size:16px;font-weight:650}}.cml-temperature{{display:flex;align-items:flex-start;color:var(--orange);font-weight:900;line-height:.9;white-space:nowrap}}.cml-temperature span{{font-size:84px;letter-spacing:-7px}}.cml-temperature small{{margin:10px 0 0 8px;font-size:28px}}.cml-metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;padding:22px 28px}}.cml-metric-card{{display:flex;align-items:center;gap:13px;min-height:70px;padding:14px 16px;border:1px solid #dce9ed;border-radius:15px;background:#f7fbfc}}.cml-metric-icon{{display:flex;align-items:center;justify-content:center;width:42px;height:42px;border:1px solid #e2edef;border-radius:12px;background:#fff;font-size:23px}}.cml-metric-label{{color:var(--muted);font-size:10px;font-weight:800;letter-spacing:.7px;text-transform:uppercase}}.cml-metric-value{{margin-top:4px;color:var(--ink);font-size:17px;font-weight:850}}.cml-current-footer{{display:flex;flex-wrap:wrap;gap:8px 25px;padding:14px 28px;border-top:1px solid #e3edf0;background:#f8fbfc;color:var(--muted);font-size:12px}}.cml-current-footer b{{color:#294e5c}}.cml-marine-box{{margin:0 0 30px;padding:26px}}.cml-marine-head{{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:20px;flex-wrap:wrap}}.cml-eyebrow{{color:#087087;font-size:10px;font-weight:900;letter-spacing:1.8px}}.cml-marine-head h2{{margin:6px 0 4px;font-size:25px}}.cml-marine-head p{{margin:0;color:var(--muted);font-size:12px}}.cml-sea-status{{display:flex;align-items:center;gap:10px;min-width:190px;padding:13px 16px;border-radius:14px;color:#fff}}.cml-sea-status>span{{font-size:28px}}.cml-sea-status small{{display:block;margin-bottom:3px;color:rgba(255,255,255,.84);font-size:10px;font-weight:800;letter-spacing:.9px}}.cml-sea-status strong{{display:block;font-size:17px}}.cml-mare-calmo{{background:#0d77a7}}.cml-mare-quasi-calmo{{background:#168db7}}.cml-mare-poco-mosso{{background:#278b5e}}.cml-mare-mosso{{background:#c18a1c}}.cml-mare-molto-mosso{{background:#d16418}}.cml-mare-agitato{{background:#c3313d}}.cml-mare-molto-agitato{{background:#8b1e29}}.cml-mare-nd{{background:#6d7d86}}.cml-marine-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px}}.cml-marine-card{{display:flex;flex-direction:column;gap:5px;min-height:105px;padding:15px;border:1px solid #dbe8ec;border-radius:15px;background:#f7fbfc}}.cml-marine-card span{{color:#54707c;font-size:12px;font-weight:700}}.cml-marine-card strong{{color:#143b4b;font-size:22px}}.cml-marine-card small{{color:#768c95;font-size:11px}}.cml-marine-note{{margin-top:16px;padding:12px 15px;border:1px solid #bfe1ea;border-left:4px solid #168db7;border-radius:11px;background:#ecf9fc;color:#3d6270;font-size:12px;line-height:1.6}}.cml-radar-box{{margin-bottom:32px;padding:26px}}.cml-radar-head{{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:16px;flex-wrap:wrap}}.cml-radar-head h2{{margin:0;font-size:23px}}.cml-radar-head p{{margin:3px 0 0;color:var(--muted);font-size:12px}}.cml-radar-btn{{border:0;border-radius:11px;padding:10px 16px;background:linear-gradient(135deg,#0c7f96,#075d74);color:#fff;cursor:pointer;font-size:13px;font-weight:800}}#radar-map{{width:100%;height:480px;border:1px solid #d8e7eb;border-radius:16px}}.cml-radar-footer{{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px 20px;margin-top:14px;padding:12px 15px;border:1px solid #dcebef;border-radius:12px;background:#f5fafb;color:var(--muted);font-size:12px}}.cml-radar-time{{color:#087087;font-weight:850}}.cml-section-title{{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin:38px 0 18px}}.cml-section-title span{{color:#0b7f98;font-size:10px;font-weight:900;letter-spacing:1.8px}}.cml-section-title h2{{margin:7px 0 5px;font-size:28px}}.cml-section-title p{{margin:0;color:var(--muted);font-size:13px}}.cml-pill{{padding:8px 14px;border:1px solid #bfe2e8;border-radius:999px;background:#e7f6f8;color:#087087;font-size:12px;font-weight:850;white-space:nowrap}}.cml-days-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}}.cml-day-card{{padding:23px}}.cml-day-head{{display:flex;align-items:center;justify-content:space-between;gap:10px}}.cml-day-tag{{padding:6px 12px;border-radius:999px;background:linear-gradient(135deg,#0e95ab,#087087);color:#fff;font-size:10px;font-weight:900;letter-spacing:1px}}.cml-day-date{{color:var(--muted);font-size:12px;font-weight:700;text-transform:capitalize}}.cml-risk-row{{margin:14px 0}}.cml-risk-badge{{display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border-radius:10px;color:#fff;font-size:11px;font-weight:800}}.cml-day-weather{{display:flex;align-items:center;gap:16px;margin-bottom:20px}}.cml-day-icon{{display:flex;align-items:center;justify-content:center;flex-shrink:0;width:68px;height:68px;border-radius:19px;font-size:35px;box-shadow:0 6px 14px rgba(23,67,84,.15)}}.cml-icon-sun{{background:linear-gradient(135deg,#ffe99a,#f9b843)}}.cml-icon-cloud{{background:linear-gradient(135deg,#dbe6ea,#93aab5)}}.cml-icon-rain{{background:linear-gradient(135deg,#9ed4ef,#327eae)}}.cml-icon-snow{{background:linear-gradient(135deg,#eff9ff,#b8d5e3)}}.cml-icon-thunder{{background:linear-gradient(135deg,#cbb3e6,#67458b)}}.cml-day-description{{font-size:18px;font-weight:850}}.cml-day-moon{{display:inline-flex;margin-top:6px;padding:5px 9px;border-radius:999px;background:#eef2ff;color:#48538f;font-size:11px;font-weight:750}}.cml-temperature-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:17px;padding:13px;border:1px solid #e1ebee;border-radius:15px;background:#f8fbfc}}.cml-temp-box{{display:flex;flex-direction:column;align-items:center;gap:4px}}.cml-temp-box span{{color:var(--muted);font-size:10px;font-weight:850;letter-spacing:1px}}.cml-temp-box strong{{font-size:24px}}.cml-temp-min{{color:#167aa9}}.cml-temp-max{{color:var(--orange)}}.cml-day-details{{display:grid;gap:9px;margin-bottom:18px;padding-bottom:17px;border-bottom:1px solid #e4edef}}.cml-day-details div{{display:flex;justify-content:space-between;gap:10px;color:#536d78;font-size:13px}}.cml-day-details b{{color:#234b59;white-space:nowrap}}.cml-astro-grid{{display:grid;grid-template-columns:1fr 1fr;gap:9px}}.cml-astro-grid div{{display:flex;justify-content:space-between;gap:6px;padding:9px;border:1px solid #e3edef;border-radius:10px;background:#fafcfd;color:#637b85;font-size:11px}}.cml-astro-grid b{{color:#254c5a}}.cml-note{{margin:18px 0 25px;padding:15px 18px;border:1px solid #f0dca8;border-left:5px solid #dc9c2d;border-radius:14px;background:#fff8e7;color:#67552d;font-size:13px;line-height:1.6}}.cml-hour-header{{position:relative;overflow:hidden;margin-top:12px;padding:29px 31px;border-radius:22px;background:linear-gradient(135deg,#122a50,#274d85);color:#fff;box-shadow:0 12px 28px rgba(25,50,98,.22)}}.cml-hour-header span{{color:#aeeaf2;font-size:10px;font-weight:850;letter-spacing:1.8px}}.cml-hour-header h2{{margin:9px 0 6px;font-size:28px}}.cml-hour-header p{{margin:0;color:#dceaff;font-size:13px}}.cml-chart-box{{margin:20px 0 14px;padding:20px}}.cml-chart-title{{margin-bottom:4px;font-size:18px;font-weight:850}}.cml-chart-subtitle{{margin-bottom:15px;color:var(--muted);font-size:12px}}.cml-chart-canvas-wrap{{position:relative;height:330px}}.cml-tabs-bar{{display:flex;gap:10px;margin:18px 0 14px;overflow-x:auto;padding-bottom:5px}}.cml-tab-btn{{border:1px solid #cfe2e7;border-radius:12px;padding:10px 16px;background:#fff;color:#3b6371;cursor:pointer;font-size:13px;font-weight:800;white-space:nowrap}}.cml-tab-btn.active{{border-color:#087087;background:linear-gradient(135deg,#0d90a7,#087087);color:#fff;box-shadow:0 5px 12px rgba(8,112,135,.25)}}.cml-table-wrap{{width:100%;overflow-x:auto;border:1px solid #d5e4e9;border-radius:18px;background:#fff;box-shadow:0 8px 28px rgba(23,67,84,.10)}}.cml-table{{width:100%;min-width:1080px;border-collapse:separate;border-spacing:0;font-size:13px;white-space:nowrap}}.cml-table th{{padding:15px 10px;background:linear-gradient(135deg,#0b7f98,#075d74);color:#fff;font-size:11px;font-weight:850;text-align:center;text-transform:uppercase}}.cml-table td{{padding:11px 10px;border-bottom:1px solid #e7eff1;color:#284d5a;text-align:right;font-variant-numeric:tabular-nums}}.cml-table td:first-child{{color:#087087;font-weight:850;text-align:center}}.cml-table td:nth-child(2){{text-align:left}}.cml-table td:nth-child(7){{text-align:center;font-weight:800}}.cml-table tbody tr:nth-child(even){{background:#f8fbfc}}.cml-scenario-cell{{display:flex;align-items:center;gap:9px;min-width:180px;font-weight:650}}.cml-table-icon{{display:inline-flex;align-items:center;justify-content:center;flex:0 0 38px;width:38px;height:38px;overflow:visible;border:1px solid #e2edef;border-radius:10px;background:#fff;font-size:18px}}.cml-weather-svg{{display:block;width:35px;height:35px;overflow:visible}}.cml-night-row{{background:linear-gradient(90deg,#142549,#203b68)!important}}.cml-night-row td{{border-bottom-color:rgba(255,255,255,.10);color:#e5f0ff}}.cml-night-row td:first-child{{color:#a8eaf5}}.cml-night-row .cml-scenario-cell{{color:#ffedb2}}.cml-night-row .cml-table-icon{{border-color:rgba(255,255,255,.22);background:#142549;box-shadow:0 2px 8px rgba(253,230,138,.18)}}
@media (max-width:760px){{body{{padding:4px}}.cml-hero{{padding:31px 25px}}.cml-hero h1{{font-size:34px}}.cml-current-main{{align-items:flex-start;flex-direction:column;padding:26px 24px}}.cml-temperature span{{font-size:69px}}.cml-metrics{{padding:18px}}.cml-marine-box,.cml-radar-box{{padding:18px}}#radar-map{{height:390px}}.cml-section-title{{align-items:flex-start;flex-direction:column}}.cml-hour-header{{padding:24px}}.cml-chart-canvas-wrap{{height:280px}}}}
</style>
</head>
<body>
<section class="cml-hero"><div class="cml-brand"><span class="cml-brand-mark"></span>CALABRIA · METEOROLOGIA LOCALE</div><h1>Calabria Meteo Lab</h1><p>Previsioni ad alta risoluzione per la Calabria. Cerca una località e consulta subito temperatura, cielo, vento, precipitazioni e sviluppo delle prossime 72 ore.</p></section>
<section class="cml-current"><div class="cml-current-main"><div class="cml-place-block"><div class="cml-kicker"><span class="cml-live-dot"></span>ICON-2I · PREVISIONE LOCALE</div><h2>📍 {html.escape(luogo)}</h2><div class="cml-condition">{icona_corrente} {html.escape(descrizione_corrente)}</div></div><div class="cml-temperature"><span>{numero(corrente.get("temperature_2m"), 1, "")}</span><small>°C</small></div></div><div class="cml-metrics">{metriche_html}</div><div class="cml-current-footer"><span>◷ Valido alle <b>{html.escape(str(corrente.get("time", "—")))}</b></span><span>◉ Fuso <b>Europe/Rome</b></span><span>◌ Fonte <b>ItaliaMeteo–ARPAE</b></span></div></section>
{mare_html}
<section class="cml-radar-box"><div class="cml-radar-head"><div><h2>📡 Radar precipitazioni live</h2><p>Sequenza radar RainViewer centrata sulla località selezionata.</p></div><button class="cml-radar-btn" id="btn-play" type="button" onclick="togglePlayRadar()">⏸ Pausa</button></div><div id="radar-map"></div><div class="cml-radar-footer"><span>🛰️ OpenStreetMap · RainViewer</span><span>Frame: <span id="radar-timestamp" class="cml-radar-time">caricamento...</span></span></div></section>
<section class="cml-section-title"><div><span>ORIZZONTE PREVISIONALE</span><h2>📅 I prossimi tre giorni</h2><p>Scenario prevalente, estremi termici, precipitazioni, vento e astronomia locale.</p></div><div class="cml-pill">72 ore</div></section><section class="cml-days-grid">{"".join(carte_html)}</section><div class="cml-note">ℹ️ Le schede mostrano la condizione prevalente e la nuvolosità media diurna. I valori sono modellistici e l'indicatore colorato non è un'allerta ufficiale.</div>
<section class="cml-hour-header"><span>DETTAGLIO ORARIO</span><h2>🕒 Previsione ora per ora</h2><p>Seleziona un giorno: grafico e tabella cambieranno insieme.</p></section><section class="cml-chart-box"><div class="cml-chart-title">📊 Andamento meteorologico orario</div><div class="cml-chart-subtitle">Temperatura, vento e precipitazione oraria.</div><div class="cml-chart-canvas-wrap"><canvas id="meteoChart"></canvas></div></section><div class="cml-tabs-bar">{"".join(pulsanti_tabs)}</div><section>{"".join(tabelle_html)}</section>
<script>
const datiGraficiPerGiorno = {dati_grafici_json};
let chart = null;
function creaGrafico(k){{const d=datiGraficiPerGiorno[k];const c=document.getElementById("meteoChart");if(!d||!c)return;chart=new Chart(c.getContext("2d"),{{type:"line",data:{{labels:d.ore,datasets:[{{label:"Temperatura °C",data:d.temperatura,borderColor:"#ef6c16",backgroundColor:"rgba(239,108,22,.12)",yAxisID:"t",tension:.35,fill:true}},{{label:"Vento km/h",data:d.vento,borderColor:"#0a8b72",yAxisID:"v",borderDash:[7,4],tension:.3}},{{label:"Precipitazione mm",data:d.precipitazione,type:"bar",backgroundColor:"rgba(47,137,202,.68)",borderColor:"#1679ba",yAxisID:"p"}}]}},options:{{responsive:true,maintainAspectRatio:false,interaction:{{mode:"index",intersect:false}},scales:{{t:{{type:"linear",position:"left",title:{{display:true,text:"Temperatura °C"}}}},v:{{type:"linear",position:"right",min:0,title:{{display:true,text:"Vento km/h"}},grid:{{drawOnChartArea:false}}}},p:{{type:"linear",position:"right",min:0,title:{{display:true,text:"Pioggia mm"}},grid:{{drawOnChartArea:false}}}}}}}}}});}}
function aggiornaGrafico(k){{const d=datiGraficiPerGiorno[k];if(!d||!chart)return;chart.data.labels=d.ore;chart.data.datasets[0].data=d.temperatura;chart.data.datasets[1].data=d.vento;chart.data.datasets[2].data=d.precipitazione;chart.update();}}
function mostraGiorno(k,b){{document.querySelectorAll(".cml-day-table-container").forEach(x=>x.style.display="none");document.querySelectorAll(".cml-tab-btn").forEach(x=>x.classList.remove("active"));const t=document.getElementById("tab-"+k);if(t)t.style.display="block";b.classList.add("active");aggiornaGrafico(k);}}
creaGrafico("{chiave_iniziale}");
const radarMap=L.map("radar-map",{{center:[{latitudine},{longitudine}],zoom:8,minZoom:5,maxZoom:18}});L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",{{attribution:"&copy; OpenStreetMap contributors"}}).addTo(radarMap);L.marker([{latitudine},{longitudine}]).addTo(radarMap);
let radarTimes=[],radarLayers={{}},radarIndex=0,radarTimer=null,radarPlaying=true;
function showRadar(i){{if(!radarTimes.length)return;if(radarLayers[radarTimes[radarIndex]])radarLayers[radarTimes[radarIndex]].setOpacity(0);radarIndex=i;const t=radarTimes[i];if(radarLayers[t])radarLayers[t].setOpacity(.72);const d=new Date(t*1000);document.getElementById("radar-timestamp").textContent=String(d.getHours()).padStart(2,"0")+":"+String(d.getMinutes()).padStart(2,"0")+" (ora locale)";}}
function startRadar(){{clearInterval(radarTimer);radarTimer=setInterval(()=>showRadar((radarIndex+1)%radarTimes.length),800);}}
function togglePlayRadar(){{const b=document.getElementById("btn-play");if(radarPlaying){{clearInterval(radarTimer);radarPlaying=false;b.textContent="▶ Play"}}else{{startRadar();radarPlaying=true;b.textContent="⏸ Pausa"}}}}
fetch("https://api.rainviewer.com/public/weather-maps.json").then(r=>r.json()).then(p=>{{const frames=p&&p.radar&&p.radar.past?p.radar.past:[];radarTimes=frames.map(f=>f.time);frames.forEach(f=>{{const l=L.tileLayer("https://tilecache.rainviewer.com"+f.path+"/256/{{z}}/{{x}}/{{y}}/2/1_1.png",{{opacity:0,zIndex:100,maxNativeZoom:6,maxZoom:18}});l.addTo(radarMap);radarLayers[f.time]=l;}});if(radarTimes.length){{radarIndex=radarTimes.length-1;showRadar(radarIndex);startRadar()}}}}).catch(()=>document.getElementById("radar-timestamp").textContent="radar non disponibile");
</script></body></html>'''

    return html_finale


try:
    COMUNI_COSTIERI = carica_comuni_costieri()
except (FileNotFoundError, ValueError) as errore:
    st.error(str(errore))
    st.stop()

st.markdown("## 🔎 Seleziona località calabrese")

with st.form("search_form", clear_on_submit=False):
    col_input, col_button = st.columns([4, 1])
    with col_input:
        testo_localita = st.text_input("Località", value="Cosenza", placeholder="Scrivi es. Cosenza, Trebisacce, Tropea, Scilla, Camigliatello Silano...", label_visibility="collapsed")
    with col_button:
        st.form_submit_button("Aggiorna previsione", use_container_width=True, type="primary")

try:
    luogo, latitudine, longitudine, candidati_localita = risolvi_localita(testo_localita)

    with st.spinner(f"Elaborazione previsione ICON-2I e radar per {luogo}..."):
        dati_terrestri = scarica_previsione_terrestre(latitudine, longitudine)
        dati_orari, dati_giornalieri = prepara_dati_terrestri(dati_terrestri)

        is_costiero = any(
            normalizza_comune(candidato) in COMUNI_COSTIERI
            for candidato in candidati_localita
        )

        dati_mare = None
        distanza_mare_km = None

        if is_costiero:
            try:
                dati_mare, distanza_mare_km = scarica_previsione_mare(latitudine, longitudine)
            except RuntimeError:
                dati_mare = None
                distanza_mare_km = None

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

    components.html(documento, height=4300, scrolling=True)

except Exception as errore:
    st.error(str(errore))
