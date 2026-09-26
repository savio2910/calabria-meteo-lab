import html
import json
import math
from datetime import datetime
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

# Il pannello mare viene mostrato solo se la cella marina modellistica
# selezionata dall'API è abbastanza vicina alla località terrestre.
SOGLIA_COSTA_KM = 5.0

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
        if any(valore is None or pd.isna(valore) for valore in (ora, alba, tramonto)):
            return False

        istante = pd.Timestamp(ora)

        return (
            istante < pd.Timestamp(alba)
            or istante >= pd.Timestamp(tramonto)
        )

    except (TypeError, ValueError):
        return False


# =============================================================================
# GEOLOCALIZZAZIONE
# =============================================================================

@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def geocodifica_calabria(nome):
    """
    Ricerca libera di comuni, frazioni e località calabresi.
    Il risultato viene mantenuto in cache per 24 ore.
    """
    try:
        geocoder = Nominatim(
            user_agent="calabria_meteo_lab_v22",
            timeout=15,
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

    return nome_risolto, latitudine, longitudine


def risolvi_localita(testo):
    """
    Per le località più cercate evita il geocoder.
    Per tutte le altre usa la ricerca libera in Calabria.
    """
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

        return comune, latitudine, longitudine

    return geocodifica_calabria(nome_normalizzato)


# =============================================================================
# API TERRESTRE ICON-2I
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


# =============================================================================
# API MARINA
# =============================================================================

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
    """
    Richiede una cella marina tramite cell_selection='sea'.
    """
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


def stato_mare_da_onda(altezza_onda):
    """
    Classificazione descrittiva basata sulla significant wave height.
    Non sostituisce i bollettini nautici o le comunicazioni ufficiali.
    """
    try:
        if altezza_onda is None or pd.isna(altezza_onda):
            return "Non disponibile", "⚪", "cml-mare-nd"

        altezza = float(altezza_onda)

        if altezza < 0.10:
            return "Calmo", "🟦", "cml-mare-calmo"

        if altezza < 0.50:
            return "Quasi calmo", "🟦", "cml-mare-quasi-calmo"

        if altezza < 1.25:
            return "Poco mosso", "🟩", "cml-mare-poco-mosso"

        if altezza < 2.50:
            return "Mosso", "🟨", "cml-mare-mosso"

        if altezza < 4.00:
            return "Molto mosso", "🟧", "cml-mare-molto-mosso"

        if altezza < 6.00:
            return "Agitato", "🟥", "cml-mare-agitato"

        return "Molto agitato", "🟥", "cml-mare-molto-agitato"

    except (TypeError, ValueError):
        return "Non disponibile", "⚪", "cml-mare-nd"


def prepara_dati_mare(dati_mare):
    ore_mare = pd.DataFrame(
        dati_mare.get("hourly", {})
    )

    if ore_mare.empty:
        return ore_mare

    ore_mare["time"] = pd.to_datetime(
        ore_mare["time"]
    )

    if "wave_direction" in ore_mare.columns:
        ore_mare["Direzione onda"] = ore_mare[
            "wave_direction"
        ].map(direzione)

    if "wave_height" in ore_mare.columns:
        stato = ore_mare["wave_height"].map(
            stato_mare_da_onda
        )

        ore_mare["Stato mare"] = stato.map(
            lambda risultato: risultato[0]
        )

        ore_mare["Icona mare"] = stato.map(
            lambda risultato: risultato[1]
        )

    return ore_mare


# =============================================================================
# PREPARAZIONE DATI TERRESTRI
# =============================================================================

def calcola_dati_diurni(ore_giorno, alba, tramonto):
    if ore_giorno.empty:
        return 0, 0

    if alba is not None and tramonto is not None:
        alba_ts = pd.Timestamp(alba)
        tramonto_ts = pd.Timestamp(tramonto)

        ore_diurne = ore_giorno.loc[
            (ore_giorno["time"] >= alba_ts)
            & (ore_giorno["time"] <= tramonto_ts)
        ]
    else:
        ore_diurne = ore_giorno.loc[
            (ore_giorno["time"].dt.hour >= 7)
            & (ore_giorno["time"].dt.hour <= 20)
        ]

    dati_target = (
        ore_diurne
        if not ore_diurne.empty
        else ore_giorno
    )

    nuvolosita_media = 0

    if "cloud_cover" in dati_target.columns:
        nuvolosita_media = round(
            dati_target["cloud_cover"].mean()
        )

    codici_severi = [
        99, 96, 95, 82, 81, 80,
        65, 63, 61, 55, 53, 51,
    ]

    for codice in codici_severi:
        if (dati_target["weather_code"] == codice).sum() >= 2:
            return codice, nuvolosita_media

    codice_prevalente = (
        dati_target["weather_code"].mode().iloc[0]
        if not dati_target.empty
        else 0
    )

    return codice_prevalente, nuvolosita_media


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

        codice, nubi = calcola_dati_diurni(
            ore_giorno,
            riga_giorno.get("sunrise"),
            riga_giorno.get("sunset"),
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

        informazioni_giorno = righe_giorno.iloc[0]

        valori_notte.append(
            e_notte(
                riga_ora["time"],
                informazioni_giorno.get("sunrise"),
                informazioni_giorno.get("sunset"),
            )
        )

    ore["Notte"] = valori_notte

    return (
        ore.reset_index(drop=True),
        giorni.reset_index(drop=True),
    )


# =============================================================================
# INDICATORE TECNICO LOCALE
# NON E' ALLERTA UFFICIALE
# =============================================================================

def valuta_rischio_locale(riga):
    precipitazione = float(
        riga.get("precipitation_sum", 0) or 0
    )

    raffica = float(
        riga.get("wind_gusts_10m_max", 0) or 0
    )

    codice_meteo = int(
        riga.get(
            "weather_code_prevalente",
            riga.get("weather_code", 0),
        )
    )

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

    icona_corrente, descrizione_corrente = meteo(
        corrente.get("weather_code")
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

    ranking_rischio = {
        "verde": 0,
        "giallo": 1,
        "arancione": 2,
        "rosso": 3,
    }

    livello_massimo = "verde"
    rischio_massimo = "nessuna criticità"

    for _, riga in giorni.iterrows():
        livello, rischio = valuta_rischio_locale(riga)

        if ranking_rischio[livello] > ranking_rischio[livello_massimo]:
            livello_massimo = livello
            rischio_massimo = rischio

    banner_html = ""

    if livello_massimo != "verde":
        colori_banner = {
            "giallo": (
                "#fff8d6",
                "#a56500",
                "⚠️",
            ),
            "arancione": (
                "#fff0df",
                "#bc4f00",
                "🟠",
            ),
            "rosso": (
                "#ffe3e5",
                "#af1d2d",
                "🔴",
            ),
        }

        sfondo, colore, icona = colori_banner[
            livello_massimo
        ]

        banner_html = f"""
        <div
          class="cml-alert-banner"
          style="background:{sfondo};border-left-color:{colore};"
        >
          <div class="cml-alert-symbol">{icona}</div>
          <div>
            <div
              class="cml-alert-title"
              style="color:{colore};"
            >
              ATTENZIONE METEOROLOGICA · LIVELLO {livello_massimo.upper()}
            </div>

            <div class="cml-alert-text">
              Condizioni potenzialmente impegnative per
              <b>{html.escape(rischio)}</b> nel periodo considerato a
              {html.escape(luogo)}. Questo indicatore deriva dai dati
              modellistici e non sostituisce bollettini o allerte ufficiali
              della Protezione Civile.
            </div>
          </div>
        </div>
        """

    mare_html = ""

    if (
        dati_mare is not None
        and isinstance(dati_mare, dict)
        and dati_mare.get("current")
    ):
        corrente_mare = dati_mare["current"]

        altezza_onda = corrente_mare.get(
            "wave_height"
        )

        direzione_onda = corrente_mare.get(
            "wave_direction"
        )

        periodo_onda = corrente_mare.get(
            "wave_period"
        )

        periodo_picco = corrente_mare.get(
            "wave_peak_period"
        )

        altezza_mare_vento = corrente_mare.get(
            "wind_wave_height"
        )

        altezza_swell = corrente_mare.get(
            "swell_wave_height"
        )

        temperatura_mare = corrente_mare.get(
            "sea_surface_temperature"
        )

        stato_mare, icona_mare, classe_mare = (
            stato_mare_da_onda(altezza_onda)
        )

        mare_html = f"""
        <section class="cml-marine-box">
          <div class="cml-marine-head">
            <div>
              <span class="cml-eyebrow">
                BOLLETTINO COSTIERO
              </span>

              <h2>🌊 Vento e stato del mare</h2>

              <p>
                Cella marina modellistica a circa
                {numero(distanza_mare_km, 1, " km")}
                dalla località selezionata.
              </p>
            </div>

            <div class="cml-sea-status {classe_mare}">
              <span>{icona_mare}</span>

              <div>
                <small>STATO DEL MARE</small>
                <strong>{html.escape(stato_mare)}</strong>
              </div>
            </div>
          </div>

          <div class="cml-marine-grid">
            <div class="cml-marine-card">
              <span>🌊 Altezza onda</span>
              <strong>{numero(altezza_onda, 2, " m")}</strong>
              <small>Onda significativa</small>
            </div>

            <div class="cml-marine-card">
              <span>🧭 Provenienza onda</span>
              <strong>{direzione(direzione_onda)}</strong>
              <small>{numero(direzione_onda, 0, "°")}</small>
            </div>

            <div class="cml-marine-card">
              <span>〰️ Periodo medio</span>
              <strong>{numero(periodo_onda, 1, " s")}</strong>
              <small>Intervallo medio d'onda</small>
            </div>

            <div class="cml-marine-card">
              <span>📈 Periodo di picco</span>
              <strong>{numero(periodo_picco, 1, " s")}</strong>
              <small>Energia dominante</small>
            </div>

            <div class="cml-marine-card">
              <span>💨 Mare del vento</span>
              <strong>{numero(altezza_mare_vento, 2, " m")}</strong>
              <small>Componente wind sea</small>
            </div>

            <div class="cml-marine-card">
              <span>🌐 Mare di fondo</span>
              <strong>{numero(altezza_swell, 2, " m")}</strong>
              <small>Componente swell</small>
            </div>

            <div class="cml-marine-card">
              <span>🌡️ Temperatura mare</span>
              <strong>{numero(temperatura_mare, 1, " °C")}</strong>
              <small>Temperatura superficiale</small>
            </div>
          </div>

          <div class="cml-marine-note">
            ℹ️ La direzione indica <b>da dove proviene</b> il moto ondoso.
            I valori sono stimati su griglia marina e possono essere meno
            rappresentativi in prossimità di coste, baie e promontori.
            Per navigazione e sicurezza consulta sempre fonti nautiche e avvisi
            ufficiali.
          </div>
        </section>
        """

    etichette_giorni = [
        "OGGI",
        "DOMANI",
        "DOPODOMANI",
    ]

    carte_html = []

    for indice, (_, riga) in enumerate(giorni.iterrows()):
        tag = (
            etichette_giorni[indice]
            if indice < len(etichette_giorni)
            else "PROSSIMAMENTE"
        )

        codice_effettivo = riga.get(
            "weather_code_prevalente",
            riga.get("weather_code"),
        )

        icona, descrizione = meteo(codice_effettivo)

        fase = html.escape(
            str(riga.get("Fase lunare", "🌙 Luna"))
        )

        livello, rischio = valuta_rischio_locale(riga)

        badge_rischio = badge_rischio_html(
            livello,
            rischio,
        )

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

        carta_html = f"""
        <article class="cml-day-card">
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
        </article>
        """

        carte_html.append(carta_html)

    date_disponibili = sorted(
        ore["time"].dt.date.unique()
    )

    if not date_disponibili:
        raise RuntimeError(
            "Non sono disponibili dati orari futuri per la località selezionata."
        )

    dati_grafici = {}
    pulsanti_tabs = []
    tabelle_html = []

    for indice, data_giorno in enumerate(date_disponibili):
        chiave = str(data_giorno)

        ore_giorno = ore.loc[
            ore["time"].dt.date == data_giorno
        ].copy()

        dati_grafici[chiave] = {
            "ore": ore_giorno["time"].dt.strftime(
                "%H:%M"
            ).tolist(),
            "temperatura": [
                round(float(valore), 1)
                if pd.notna(valore)
                else None
                for valore in ore_giorno[
                    "temperature_2m"
                ].tolist()
            ],
            "vento": [
                round(float(valore), 1)
                if pd.notna(valore)
                else None
                for valore in ore_giorno[
                    "wind_speed_10m"
                ].tolist()
            ],
            "precipitazione": [
                round(float(valore), 1)
                if pd.notna(valore)
                else None
                for valore in ore_giorno[
                    "precipitation"
                ].tolist()
            ],
        }

        classe_attiva = (
            "active"
            if indice == 0
            else ""
        )

        pulsanti_tabs.append(
            f"""
            <button
              class="cml-tab-btn {classe_attiva}"
              type="button"
              onclick="mostraGiorno('{chiave}', this)"
            >
              📅 {html.escape(data_it(data_giorno).title())}
            </button>
            """
        )

        stile_visibilita = (
            "display:block;"
            if indice == 0
            else "display:none;"
        )

        righe_tabella = []

        for _, riga in ore_giorno.iterrows():
            classe_notte = (
                "cml-night-row"
                if bool(riga.get("Notte", False))
                else ""
            )

            righe_tabella.append(
                f"""
                <tr class="{classe_notte}">
                  <td>{riga["time"].strftime("%H:%M")}</td>

                  <td class="cml-scenario-cell">
                    <span class="cml-table-icon">
                      {riga["Icona"]}
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
            <div
              id="tab-{chiave}"
              class="cml-day-table-container"
              style="{stile_visibilita}"
            >
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
            </div>
            """
        )

    chiave_iniziale = str(
        date_disponibili[0]
    )

    dati_grafici_json = json.dumps(
        dati_grafici,
        ensure_ascii=False,
    )

    documento_html = f"""
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta
  name="viewport"
  content="width=device-width, initial-scale=1"
>

<link
  rel="stylesheet"
  href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
>

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

.cml-alert-banner {{
  display: flex;
  align-items: flex-start;
  gap: 13px;
  margin: 0 0 22px;
  padding: 16px 18px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  border-right: 1px solid rgba(0, 0, 0, 0.06);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  border-left: 5px solid;
  border-radius: 14px;
  box-shadow: 0 6px 18px rgba(23, 67, 84, 0.08);
}}

.cml-alert-symbol {{
  font-size: 25px;
  line-height: 1;
}}

.cml-alert-title {{
  margin-bottom: 3px;
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.4px;
}}

.cml-alert-text {{
  color: #4d6570;
  font-size: 13px;
  line-height: 1.55;
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
  background: #f7fbfc;
  transition: transform 0.18s ease, border-color 0.18s ease;
}}

.cml-metric-card:hover {{
  border-color: #89c6d1;
  transform: translateY(-2px);
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

.cml-mare-calmo {{
  background: #0d77a7;
}}

.cml-mare-quasi-calmo {{
  background: #168db7;
}}

.cml-mare-poco-mosso {{
  background: #278b5e;
}}

.cml-mare-mosso {{
  background: #c18a1c;
}}

.cml-mare-molto-mosso {{
  background: #d16418;
}}

.cml-mare-agitato {{
  background: #c3313d;
}}

.cml-mare-molto-agitato {{
  background: #8b1e29;
}}

.cml-mare-nd {{
  background: #6d7d86;
}}

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

.cml-days-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 18px;
}}

.cml-day-card {{
  padding: 23px;
  border: 1px solid #d5e4e9;
  border-radius: 22px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(23, 67, 84, 0.10);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}}

.cml-day-card:hover {{
  transform: translateY(-3px);
  box-shadow: 0 14px 30px rgba(23, 67, 84, 0.15);
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

.cml-icon-sun {{
  background: linear-gradient(135deg, #ffe99a, #f9b843);
}}

.cml-icon-cloud {{
  background: linear-gradient(135deg, #dbe6ea, #93aab5);
}}

.cml-icon-rain {{
  background: linear-gradient(135deg, #9ed4ef, #327eae);
}}

.cml-icon-snow {{
  background: linear-gradient(135deg, #eff9ff, #b8d5e3);
}}

.cml-icon-thunder {{
  background: linear-gradient(135deg, #cbb3e6, #67458b);
}}

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

.cml-hour-header {{
  position: relative;
  overflow: hidden;
  margin-top: 12px;
  padding: 29px 31px;
  border-radius: 22px;
  background: linear-gradient(135deg, #122a50, #274d85);
  color: #ffffff;
  box-shadow: 0 12px 28px rgba(25, 50, 98, 0.22);
}}

.cml-hour-header::after {{
  content: "☾";
  position: absolute;
  top: 0;
  right: 27px;
  color: rgba(255, 255, 255, 0.12);
  font-size: 88px;
}}

.cml-hour-header > * {{
  position: relative;
  z-index: 1;
}}

.cml-hour-header span {{
  color: #aeeaf2;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 1.8px;
}}

.cml-hour-header h2 {{
  margin: 9px 0 6px;
  font-size: 28px;
}}

.cml-hour-header p {{
  margin: 0;
  color: #dceaff;
  font-size: 13px;
}}

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

.cml-tabs-bar {{
  display: flex;
  gap: 10px;
  margin: 18px 0 14px;
  overflow-x: auto;
  padding-bottom: 5px;
}}

.cml-tab-btn {{
  border: 1px solid #cfe2e7;
  border-radius: 12px;
  padding: 10px 16px;
  background: #ffffff;
  color: #3b6371;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
  white-space: nowrap;
  transition: all 0.18s ease;
}}

.cml-tab-btn:hover {{
  border-color: #0b7f98;
  background: #eaf8fa;
}}

.cml-tab-btn.active {{
  border-color: #087087;
  background: linear-gradient(135deg, #0d90a7, #087087);
  color: #ffffff;
  box-shadow: 0 5px 12px rgba(8, 112, 135, 0.25);
}}

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
}}
</style>
</head>

<body>

<section class="cml-hero">
  <div class="cml-brand">
    <span class="cml-brand-mark"></span>
    CALABRIA · METEOROLOGIA LOCALE
  </div>

  <h1>Calabria Meteo Lab</h1>

  <p>
    Previsioni ad alta risoluzione per la Calabria.
    Cerca una località e consulta subito temperatura, cielo, vento,
    precipitazioni e sviluppo delle prossime 72 ore.
  </p>
</section>

{banner_html}

<section class="cml-current">
  <div class="cml-current-main">
    <div class="cml-place-block">
      <div class="cml-kicker">
        <span class="cml-live-dot"></span>
        ICON-2I · PREVISIONE LOCALE
      </div>

      <h2>📍 {html.escape(luogo)}</h2>

      <div class="cml-condition">
        {icona_corrente} {html.escape(descrizione_corrente)}
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

<section class="cml-radar-box">
  <div class="cml-radar-head">
    <div>
      <h2>📡 Radar precipitazioni live</h2>
      <p>
        Sequenza radar disponibile tramite RainViewer,
        centrata sulla località selezionata.
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

<section class="cml-section-title">
  <div>
    <span>ORIZZONTE PREVISIONALE</span>
    <h2>📅 I prossimi tre giorni</h2>
    <p>
      Scenario prevalente diurno, estremi termici,
      precipitazioni, vento e astronomia locale.
    </p>
  </div>

  <div class="cml-pill">72 ore</div>
</section>

<section class="cml-days-grid">
  {''.join(carte_html)}
</section>

<div class="cml-note">
  ℹ️ Le schede mostrano la condizione prevalente e la nuvolosità media nelle ore diurne.
  Temperature, precipitazioni e vento rappresentano estremi o cumulati sulle 24 ore.
  L'indicatore colorato è una valutazione tecnica locale ricavata dai dati previsionali:
  <b>non è un'allerta ufficiale della Protezione Civile.</b>
</div>

<section class="cml-hour-header">
  <span>DETTAGLIO ORARIO</span>
  <h2>🕒 Previsione ora per ora</h2>
  <p>
    Seleziona un giorno: grafico e tabella cambieranno insieme.
  </p>
</section>

<section class="cml-chart-box">
  <div class="cml-chart-title">
    📊 Andamento meteorologico orario
  </div>

  <div class="cml-chart-subtitle">
    Temperatura, vento e precipitazione oraria per il giorno selezionato.
  </div>

  <div class="cml-chart-canvas-wrap">
    <canvas id="meteoChart"></canvas>
  </div>
</section>

<div class="cml-tabs-bar">
  {''.join(pulsanti_tabs)}
</div>

<section>
  {''.join(tabelle_html)}
</section>

<div class="cml-note">
  ℹ️ <b>ICON-2I:</b> modello deterministico ad alta risoluzione di ItaliaMeteo–ARPAE.
  I dati terrestri sono forniti attraverso Open-Meteo.
  Il grafico e la tabella riportano la previsione oraria per la posizione selezionata.
</div>

<script>
const datiGraficiPerGiorno = {dati_grafici_json};
const chiaveGraficoIniziale = "{chiave_iniziale}";

let meteoChartInstance = null;

function creaGrafico(chiave) {{
  const dati = datiGraficiPerGiorno[chiave];

  if (!dati) {{
    return;
  }}

  const canvas = document.getElementById("meteoChart");

  if (!canvas) {{
    return;
  }}

  const context = canvas.getContext("2d");

  meteoChartInstance = new Chart(context, {{
    type: "line",

    data: {{
      labels: dati.ore,

      datasets: [
        {{
          label: "Temperatura °C",
          data: dati.temperatura,
          yAxisID: "temperatura",
          borderColor: "#ef6c16",
          backgroundColor: "rgba(239, 108, 22, 0.12)",
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 3,
          tension: 0.35,
          fill: true
        }},

        {{
          label: "Vento km/h",
          data: dati.vento,
          yAxisID: "vento",
          borderColor: "#0a8b72",
          backgroundColor: "rgba(10, 139, 114, 0.06)",
          pointRadius: 2,
          pointHoverRadius: 4,
          borderWidth: 2.5,
          borderDash: [7, 4],
          tension: 0.3,
          fill: false
        }},

        {{
          label: "Precipitazione mm",
          data: dati.precipitazione,
          yAxisID: "precipitazione",
          type: "bar",
          backgroundColor: "rgba(47, 137, 202, 0.68)",
          borderColor: "#1679ba",
          borderWidth: 1,
          borderRadius: 4
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

        temperatura: {{
          type: "linear",
          position: "left",

          title: {{
            display: true,
            text: "Temperatura °C"
          }},

          grid: {{
            color: "rgba(16, 43, 59, 0.08)"
          }}
        }},

        vento: {{
          type: "linear",
          position: "right",

          title: {{
            display: true,
            text: "Vento km/h"
          }},

          grid: {{
            drawOnChartArea: false
          }},

          min: 0
        }},

        precipitazione: {{
          type: "linear",
          position: "right",
          offset: true,

          title: {{
            display: true,
            text: "Pioggia mm"
          }},

          grid: {{
            drawOnChartArea: false
          }},

          min: 0
        }}
      }}
    }}
  }});
}}

function aggiornaGrafico(chiave) {{
  const dati = datiGraficiPerGiorno[chiave];

  if (!dati || !meteoChartInstance) {{
    return;
  }}

  meteoChartInstance.data.labels = dati.ore;

  meteoChartInstance.data.datasets[0].data =
    dati.temperatura;

  meteoChartInstance.data.datasets[1].data =
    dati.vento;

  meteoChartInstance.data.datasets[2].data =
    dati.precipitazione;

  meteoChartInstance.update();
}}

function mostraGiorno(chiave, bottone) {{
  const sezioni = document.getElementsByClassName(
    "cml-day-table-container"
  );

  for (let i = 0; i < sezioni.length; i += 1) {{
    sezioni[i].style.display = "none";
  }}

  const pulsanti = document.getElementsByClassName(
    "cml-tab-btn"
  );

  for (let i = 0; i < pulsanti.length; i += 1) {{
    pulsanti[i].classList.remove("active");
  }}

  const target = document.getElementById(
    "tab-" + chiave
  );

  if (target) {{
    target.style.display = "block";
  }}

  bottone.classList.add("active");

  aggiornaGrafico(chiave);
}}

creaGrafico(chiaveGraficoIniziale);


const radarMap = L.map("radar-map", {{
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

  const tempoPrecedente = radarTimes[
    radarFrameIndex
  ];

  if (radarLayers[tempoPrecedente]) {{
    radarLayers[tempoPrecedente].setOpacity(0);
  }}

  radarFrameIndex = indice;

  const tempo = radarTimes[radarFrameIndex];

  if (radarLayers[tempo]) {{
    radarLayers[tempo].setOpacity(0.72);
  }}

  const data = new Date(tempo * 1000);

  const ore = String(
    data.getHours()
  ).padStart(2, "0");

  const minuti = String(
    data.getMinutes()
  ).padStart(2, "0");

  const timestamp = document.getElementById(
    "radar-timestamp"
  );

  if (timestamp) {{
    timestamp.textContent =
      ore + ":" + minuti + " (ora locale)";
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

    const prossimo =
      (radarFrameIndex + 1) % radarTimes.length;

    visualizzaFrameRadar(prossimo);
  }}, 800);
}}

function togglePlayRadar() {{
  const bottone = document.getElementById(
    "btn-play"
  );

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

fetch(
  "https://api.rainviewer.com/public/weather-maps.json"
)
  .then(function(response) {{
    return response.json();
  }})
  .then(function(payload) {{
    const frames = payload
      && payload.radar
      && payload.radar.past
      ? payload.radar.past
      : [];

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
      const timestamp = document.getElementById(
        "radar-timestamp"
      );

      if (timestamp) {{
        timestamp.textContent =
          "frame non disponibile";
      }}
    }}
  }})
  .catch(function() {{
    const timestamp = document.getElementById(
      "radar-timestamp"
    );

    if (timestamp) {{
      timestamp.textContent =
        "radar temporaneamente non disponibile";
    }}
  }});
</script>

</body>
</html>
"""

    return documento_html


# =============================================================================
# INTERFACCIA STREAMLIT
# =============================================================================

st.markdown("## 🔎 Seleziona località calabrese")

with st.form("search_form", clear_on_submit=False):
    colonna_input, colonna_bottone = st.columns([4, 1])

    with colonna_input:
        testo_localita = st.text_input(
            "Località",
            value="Cosenza",
            placeholder=(
                "Scrivi es. Cosenza, Tropea, Scilla, "
                "Camigliatello Silano, Serra San Bruno..."
            ),
            label_visibility="collapsed",
        )

    with colonna_bottone:
        st.form_submit_button(
            "Aggiorna previsione",
            use_container_width=True,
            type="primary",
        )


# =============================================================================
# ESECUZIONE
# =============================================================================

try:
    luogo, latitudine, longitudine = risolvi_localita(
        testo_localita
    )

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

        dati_mare = None
        distanza_mare_km = None

        try:
            dati_mare_candidati, distanza_candidata_km = (
                scarica_previsione_mare(
                    latitudine,
                    longitudine,
                )
            )

            if distanza_candidata_km <= SOGLIA_COSTA_KM:
                dati_mare = dati_mare_candidati
                distanza_mare_km = distanza_candidata_km

        except RuntimeError:
            # Il pannello terrestre continua a funzionare anche
            # se la sorgente marina non risponde.
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

    components.html(
        documento,
        height=4200,
        scrolling=True,
    )

except Exception as errore:
    st.error(str(errore))
