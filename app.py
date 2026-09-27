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
API_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"

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
    "surface_pressure",
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

VARIABILI_ORARIE = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "showers",
    "snowfall",
    "weather_code",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "pressure_msl",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "cape",
    "convective_inhibition",
    "lightning_potential",
    "freezing_level_height",
    "wet_bulb_temperature_2m",
    "vapour_pressure_deficit",
]

VARIABILI_TERRESTRI_FISICHE = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "showers",
    "snowfall",
    "weather_code",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "pressure_msl",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "cape",
    "convective_inhibition",
    "lightning_potential",
    "freezing_level_height",
    "wet_bulb_temperature_2m",
    "vapour_pressure_deficit",
]

VARIABILI_PRESSIONE = [
    "temperature_925hPa",
    "relative_humidity_925hPa",
    "wind_speed_925hPa",
    "wind_direction_925hPa",
    "vertical_velocity_925hPa",
    "geopotential_height_925hPa",

    "temperature_850hPa",
    "relative_humidity_850hPa",
    "wind_speed_850hPa",
    "wind_direction_850hPa",
    "vertical_velocity_850hPa",
    "geopotential_height_850hPa",

    "temperature_700hPa",
    "relative_humidity_700hPa",
    "wind_speed_700hPa",
    "wind_direction_700hPa",
    "vertical_velocity_700hPa",
    "geopotential_height_700hPa",
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

def numero_quota(valore):
    try:
        if valore is None or pd.isna(valore):
            return "—"

        return f"{float(valore):.0f} m"

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

def componente_verso_montagna(
    velocita_kmh,
    direzione_vento_gradi,
    gradiente_quota_m,
    direzione_gradiente_gradi,
):
    vento_rad = math.radians(direzione_vento_gradi)
    gradiente_rad = math.radians(direzione_gradiente_gradi)

    delta = vento_rad - gradiente_rad

    componente = velocita_kmh * math.cos(delta)

    return componente
    
def limita(valore, minimo=0.0, massimo=1.0):
    return max(minimo, min(massimo, valore))

def stima_sollevamento_orografico(
    vento_verso_rilievo,
    umidita_bassa,
    precipitazione,
    pendenza,
    omega_850=None,
):
    """
    Restituisce:
      - livello: "nullo", "debole", "moderato", "forte"
      - messaggio descrittivo
    """
    indice = indice_orografico(
        vento_verso_rilievo,
        umidita_bassa,
        precipitazione,
        pendenza,
        omega_850=omega_850,
    )

    if indice < 0.15:
        return "nullo", "Sollevamento orografico trascurabile."
    if indice < 0.35:
        return "debole", "Debole sollevamento orografico possibile."
    if indice < 0.60:
        return "moderato", "Sollevamento orografico moderato, possibile aumento di nubi e pioggia sul versante esposto."
    return "forte", "Forte sollevamento orografico: probabile incremento di nubi e precipitazione sul versante esposto."


def stima_effetto_vento_orografico(
    vento_10m,
    vento_verso_rilievo,
    pendenza,
):
    """
    Stima se il vento sui crinali è probabilmente più forte del valore a 10 m.
    Restituisce (livello, messaggio).
    """
    if vento_10m < 5:
        return "nullo", "Vento debole: effetti orografici sul vento poco rilevanti."

    if vento_verso_rilievo < 5 or pendenza < 0.05:
        return "debole", "Possibile leggero rinforzo del vento sui crinali esposti."

    if vento_verso_rilievo < 15 or pendenza < 0.12:
        return "moderato", "Vento probabilmente più intenso sui crinali esposti rispetto alla valle/costa."

    return "forte", "Forte accelerazione orografica del vento sui crinali esposti; in valle/costa il vento può essere più debole."


def stima_effetto_precipitazione_orografica(
    livello_sollevamento,
    precipitazione_oraria,
):
    """
    Da un livello di sollevamento e una precipitazione oraria,
    stima l'effetto sulla pioggia/neve.
    """
    if livello_sollevamento == "nullo":
        return "La precipitazione prevista non è significativamente modificata dall'orografia."

    if precipitazione_oraria < 0.5:
        return (
            f"Sollevamento {livello_sollevamento}: possibile aumento locale della pioviggine "
            "o di brevi rovesci sul versante esposto, anche se i cumulati restano modesti."
        )

    if precipitazione_oraria < 3:
        return (
            f"Sollevamento {livello_sollevamento}: probabile incremento locale della precipitazione "
            "sul versante esposto, con cumulati superiori rispetto alle zone sottovento."
        )

    return (
        f"Sollevamento {livello_sollevamento}: forte enhancement orografico della precipitazione; "
        "possibili valori locali sensibilmente più alti sul versante esposto."
    )

def direzione_localita_verso_griglia(
    lat_localita,
    lon_localita,
    lat_griglia,
    lon_griglia,
):
    """
    Restituisce la direzione (gradi da Nord, senso orario)
    dal punto della località verso il centro della cella.
    """
    dlon = lon_griglia - lon_localita
    dlat = lat_griglia - lat_localita

    angolo_rad = math.atan2(dlon, dlat)
    direzione = math.degrees(angolo_rad)
    if direzione < 0:
        direzione += 360.0
    return direzione


def componente_vento_verso_rilievo_semplice(
    vento_10m,
    direzione_vento_10m,
    lat_localita,
    lon_localita,
    lat_griglia,
    lon_griglia,
    quota_localita,
    quota_griglia,
):
    """
    Stima la componente del vento verso il rilievo usando:
      - direzione località -> griglia come 'direzione del rilievo'
      - differenza di quota per pesare l'effetto.
    Restituisce vento_verso_rilievo (km/h) e pendenza_approssimata.
    """
    # Se la differenza di quota è piccola, consideriamo effetto nullo
    diff_quota = float(quota_griglia) - float(quota_localita)
    if abs(diff_quota) < 40:
        return 0.0, 0.0

    direzione_rilievo = direzione_localita_verso_griglia(
        lat_localita,
        lon_localita,
        lat_griglia,
        lon_griglia,
    )

    vento_rad = math.radians(direzione_vento_10m)
    rilievo_rad = math.radians(direzione_rilievo)

    delta = vento_rad - rilievo_rad
    vento_verso = vento_10m * math.cos(delta)

    # Pendenza approssimata: differenza di quota / distanza
    distanza_km = distanza_haversine_km(
        lat_localita,
        lon_localita,
        lat_griglia,
        lon_griglia,
    )

    if distanza_km < 0.5:
        distanza_km = 0.5

    # diff_quota in metri, distanza in km -> pendenza adimensionale
    pendenza = abs(diff_quota) / (distanza_km * 1000.0)

    return max(0.0, vento_verso), pendenza


def indice_orografico(
    vento_verso_rilievo,
    umidita_bassa,
    precipitazione,
    pendenza,
    omega_850=None,
):
    i_vento = limita(vento_verso_rilievo / 40.0)
    i_umidita = limita((umidita_bassa - 65.0) / 30.0)
    i_precipitazione = limita(precipitazione / 10.0)
    i_pendenza = limita(pendenza / 0.20)

    if omega_850 is None or pd.isna(omega_850):
        i_sollevamento = 0.0
    else:
        # omega negativo = moto ascendente in coordinate di pressione
        i_sollevamento = limita((-float(omega_850)) / 0.5)

    indice = (
        0.30 * i_vento
        + 0.25 * i_umidita
        + 0.20 * i_precipitazione
        + 0.15 * i_pendenza
        + 0.10 * i_sollevamento
    )

    return round(limita(indice), 3)


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

def diagnostica_inversione(
    t_2m,
    t_925,
    t_850,
    umidita_2m,
    vento_10m,
    cloud_cover,
):
    if any(
        valore is None or pd.isna(valore)
        for valore in [t_2m, t_925, t_850]
    ):
        return "Dati insufficienti"

    delta_925_2m = float(t_925) - float(t_2m)
    delta_850_2m = float(t_850) - float(t_2m)

    notte_stabile = (
        float(vento_10m) < 8
        and float(cloud_cover) < 45
    )

    if delta_925_2m > 7 and notte_stabile:
        return "Possibile inversione termica negli strati bassi"

    if delta_925_2m > 4 and float(umidita_2m) > 85:
        return "Strato basso stabile e umido, possibile inversione/nebbia"

    if delta_925_2m < 1:
        return "Profilo quasi neutro o ben rimescolato"

    return "Stratificazione non classificata"

def diagnostica_convezione(cape, cin, lpi, precipitazione_convettiva):
    segnali = 0

    if cape is not None and cape >= 500:
        segnali += 1

    if cin is not None and cin > -100:
        segnali += 1

    if lpi is not None and lpi > 0:
        segnali += 1

    if (
        precipitazione_convettiva is not None
        and precipitazione_convettiva >= 2
    ):
        segnali += 1

    if segnali >= 3:
        return "Convezione potenzialmente significativa"

    if segnali == 2:
        return "Instabilità convettiva presente"

    return "Segnale convettivo debole o assente"


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
        <h2>&#9976 Le prossime ore, in parole chiare</h2>
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

@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def scarica_elevazione(latitudine, longitudine):
    parametri = {
        "latitude": latitudine,
        "longitude": longitudine,
    }

    try:
        risposta = requests.get(
            API_ELEVATION_URL,
            params=parametri,
            timeout=20,
        )

        risposta.raise_for_status()
        dati = risposta.json()

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Errore nel recupero della quota topografica: {exc}"
        ) from exc

    elevazioni = dati.get("elevation")

    if not elevazioni:
        raise RuntimeError(
            "L'API non ha restituito una quota valida."
        )

    try:
        return float(elevazioni[0])

    except (TypeError, ValueError, IndexError) as exc:
        raise RuntimeError(
            "La quota restituita dall'API non è numerica."
        ) from exc
        
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

        dati = risposta.json()

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Errore nella ricezione dei dati ICON-2I: {exc}"
        ) from exc

    dati["_query_latitude"] = latitudine
    dati["_query_longitude"] = longitudine

    return dati

def estrai_quota_griglia(dati_terrestri):
    corrente = dati_terrestri.get("current", {})

    quota = corrente.get("elevation")

    if quota is None:
        quota = dati_terrestri.get("elevation")

    try:
        return float(quota)

    except (TypeError, ValueError):
        return None

def analizza_rappresentativita_altimetrica(
    quota_localita,
    quota_griglia,
):
    risultato = {
        "quota_localita": quota_localita,
        "quota_griglia": quota_griglia,
        "differenza_quota": None,
        "differenza_assoluta": None,
        "classe": "non disponibile",
        "messaggio": (
            "Quota non disponibile: impossibile valutare "
            "la rappresentatività altimetrica."
        ),
    }

    if quota_localita is None or quota_griglia is None:
        return risultato

    differenza = float(quota_griglia) - float(quota_localita)
    differenza_assoluta = abs(differenza)

    risultato["differenza_quota"] = differenza
    risultato["differenza_assoluta"] = differenza_assoluta

    if differenza_assoluta < 50:
        classe = "ottima"
        messaggio = (
            "La quota della località è molto simile a quella "
            "della cella modellistica."
        )

    elif differenza_assoluta < 150:
        classe = "buona"
        messaggio = (
            "La previsione è generalmente rappresentativa, "
            "ma può risentire di differenze locali."
        )

    elif differenza_assoluta < 300:
        classe = "moderata"
        messaggio = (
            "La differenza di quota è significativa: temperatura, "
            "umidità e vento possono differire localmente."
        )

    else:
        classe = "debole"
        messaggio = (
            "La differenza di quota è elevata: la previsione della "
            "cella può non rappresentare bene il centro abitato."
        )

    risultato["classe"] = classe
    risultato["messaggio"] = messaggio

    return risultato

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
    analisi_quota=None,
    comuni_costieri=None,
):
    corrente = dati_terrestri["current"]
    
    if comuni_costieri is None:
        try:
            comuni_costieri = carica_comuni_costieri()
        except Exception:
            comuni_costieri = set()

    if analisi_quota is None:
        analisi_quota = {
            "quota_localita": None,
            "quota_griglia": None,
            "differenza_quota": None,
            "differenza_assoluta": None,
            "classe": "non disponibile",
            "messaggio": "Analisi altimetrica non disponibile.",
        }

    box_orografia_html = genera_box_effetti_orografici_html(
        luogo,
        latitudine,
        longitudine,
        analisi_quota.get("quota_localita"),
        analisi_quota.get("quota_griglia"),
        ore,
        comuni_costieri,
    )

    quota_localita_html = numero_quota(
        analisi_quota.get("quota_localita")
    )

    quota_griglia_html = numero_quota(
        analisi_quota.get("quota_griglia")
    )

    differenza_quota = analisi_quota.get(
        "differenza_quota"
    )

    if (
        differenza_quota is None
        or pd.isna(differenza_quota)
    ):
        differenza_quota_html = "—"
    else:
        segno = "+" if differenza_quota >= 0 else ""
        differenza_quota_html = (
            f"{segno}{float(differenza_quota):.0f} m"
        )

    classe_quota = html.escape(
        str(
            analisi_quota.get(
                "classe",
                "non disponibile",
            )
        )
    )

    messaggio_quota = html.escape(
        str(
            analisi_quota.get(
                "messaggio",
                "Analisi altimetrica non disponibile.",
            )
        )
    )

    icona_corrente, descrizione_corrente = meteo(
        corrente.get("weather_code")
    )
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

        altezza_onda = corrente_mare.get("wave_height")
        direzione_onda = corrente_mare.get("wave_direction")
        periodo_onda = corrente_mare.get("wave_period")
        altezza_mare_vento = corrente_mare.get("wind_wave_height")
        altezza_swell = corrente_mare.get("swell_wave_height")
        temperatura_mare = corrente_mare.get("sea_surface_temperature")

        stato_mare, icona_mare, classe_mare = stato_mare_da_onda(altezza_onda)

        mare_html = f"""
        <section class="cml-marine-box">
          <div class="cml-marine-head">
            <div>
              <span class="cml-eyebrow">
                BOLLETTINO COSTIERO
              </span>

              <h2>🌊 Vento e stato del mare</h2>

              <p>
                Previsione marina per il comune costiero di riferimento.
                La cella modellistica più vicina è a circa
                {numero(distanza_mare_km, 1, " km")}
                dal punto selezionato.
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
            rappresentativi presso baie, porti, promontori e costa molto frastagliata.
            Per navigazione e sicurezza consulta sempre fonti nautiche e avvisi ufficiali.
          </div>
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
  background: #f7fbfc;
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
def genera_box_effetti_orografici_html(
    luogo,
    latitudine,
    longitudine,
    quota_localita,
    quota_griglia,
    ore,
    comuni_costieri,
):
    """
    Genera un HTML con effetti orografici locali dinamici.
    """
    if ore.empty:
        return ""

    # Prendiamo un campione di ore diurne e notturne per le diagnosi
    ora_rif = ore["time"].min()
    ore_24 = ore.loc[
        (ore["time"] >= ora_rif)
        & (ore["time"] < ora_rif + pd.Timedelta(hours=24))
    ].copy()

    if ore_24.empty:
        return ""

    # Dati medi/representativi per la diagnosi
    vento_10m_medio = float(ore_24["wind_speed_10m"].mean())
    direzione_10m_media = float(ore_24["wind_direction_10m"].mean())
    umidita_2m_media = float(ore_24["relative_humidity_2m"].mean())
    precipitazione_oraria_media = float(ore_24["precipitation"].mean())
    cloud_cover_medio = float(ore_24["cloud_cover"].mean())

    # Per inversione, usiamo un'ora notturna rappresentativa
    ore_notte = ore_24.loc[
        (ore_24["Notte"] == True)
    ]
    if ore_notte.empty:
        ore_notte = ore_24

    riga_notte = ore_notte.iloc[0]

    # Direzione e coordinate della griglia: le prendi da dati_terrestri se le hai,
    # altrimenti approssimi con la stessa località (in tal caso effetto nullo).
    # Per ora, assumiamo che la griglia sia circa nella stessa posizione:
    lat_griglia = latitudine
    lon_griglia = longitudine

    vento_verso_rilievo, pendenza = componente_vento_verso_rilievo_semplice(
        vento_10m_medio,
        direzione_10m_media,
        latitudine,
        longitudine,
        lat_griglia,
        lon_griglia,
        quota_localita,
        quota_griglia,
    )

    livello_sollevamento, testo_sollevamento = stima_sollevamento_orografico(
        vento_verso_rilievo,
        umidita_2m_media,
        precipitazione_oraria_media,
        pendenza,
        omega_850=None,
    )

    livello_vento, testo_vento = stima_effetto_vento_orografico(
        vento_10m_medio,
        vento_verso_rilievo,
        pendenza,
    )

    testo_precip = stima_effetto_precipitazione_orografica(
        livello_sollevamento,
        precipitazione_oraria_media,
    )

    # Inversione termica
    t_2m = float(riga_notte["temperature_2m"])
    # Se in futuro aggiungi livelli in quota, passi anche t_925, t_850
    t_925 = t_2m  # placeholder
    t_850 = t_2m  # placeholder
    umidita_2m_notte = float(riga_notte["relative_humidity_2m"])
    vento_10m_notte = float(riga_notte["wind_speed_10m"])
    cloud_cover_notte = float(riga_notte["cloud_cover"])

    testo_inversione = diagnostica_inversione(
        t_2m,
        t_925,
        t_850,
        umidita_2m_notte,
        vento_10m_notte,
        cloud_cover_notte,
    )

    # Costiera vs interna
    is_costiero = comune_e_costiero(luogo, comuni_costieri)

    if is_costiero and livello_sollevamento == "nullo":
        testo_costa = (
            f"{luogo} è un comune costiero e, con la direzione del vento prevista, "
            "non si prevedono significativi effetti di sollevamento orografico."
        )
    elif is_costiero:
        testo_costa = (
            f"Sebbene {luogo} sia un comune costiero, la direzione del vento e la "
            "configurazione orografica locale possono produrre un debole/moderato "
            "sollevamento orografico in alcune situazioni."
        )
    else:
        testo_costa = (
            f"{luogo} è un comune interno: gli effetti orografici possono essere più "
            "marcati, specie sui versanti esposti al flusso umido."
        )

    # Costruzione HTML
    return f"""
    <section class="cml-physical-box">
      <span class="cml-eyebrow">INTERPRETAZIONE FISICA LOCALE</span>
      <h2>⛰️ Effetti orografici e stratificazione per {html.escape(luogo)}</h2>
      <ul>
        <li><b>Sollevamento orografico:</b> {livello_sollevamento.title()}. {html.escape(testo_sollevamento)}</li>
        <li><b>Vento e orografia:</b> {html.escape(testo_vento)}</li>
        <li><b>Precipitazione e orografia:</b> {html.escape(testo_precip)}</li>
        <li><b>Stratificazione notturna:</b> {html.escape(testo_inversione)}</li>
        <li>{html.escape(testo_costa)}</li>
      </ul>
    </section>
    """

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

      <h2>Radar precipitazioni</h2>

      <p>
        Visualizza la sequenza radar delle precipitazioni in tempo quasi
        reale, centrata sulla località selezionata.
      </p>

      <span>Apri radar →</span>
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

      <section class="cml-altitude-box">
        <div class="cml-altitude-head">
          <div>
            <span class="cml-eyebrow">
              RAPPRESENTATIVITÀ TOPOGRAFICA
            </span>
    
            <h2>⛰️ Quota della località e della griglia</h2>
    
            <p>
              Confronto tra il modello digitale del terreno
              e la quota della cella meteorologica ICON-2I.
            </p>
          </div>
    
          <span class="cml-altitude-class
            cml-altitude-{classe_quota}">
            {classe_quota.title()}
          </span>
        </div>
    
        <div class="cml-altitude-grid">
          <div class="cml-altitude-card">
            <span>📍 Quota località</span>
            <strong>{quota_localita_html}</strong>
            <small>DEM topografico</small>
          </div>
    
          <div class="cml-altitude-card">
            <span>🧮 Quota cella ICON-2I</span>
            <strong>{quota_griglia_html}</strong>
            <small>Griglia modellistica</small>
          </div>
    
          <div class="cml-altitude-card">
            <span>↕️ Differenza</span>
            <strong>{differenza_quota_html}</strong>
            <small>Griglia meno località</small>
          </div>
        </div>
    
        <div class="cml-altitude-note">
          ℹ️ {messaggio_quota}
        </div>
      </section>

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
      📡 Radar precipitazioni · {html.escape(luogo)}
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

</section>


<!-- ===================== SCRIPT ===================== -->
<script>
const datiGraficiPerGiorno = {dati_grafici_json};

let meteoChartInstance = null;
let radarMap = null;

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
        quota_localita = scarica_elevazione(
            latitudine,
            longitudine,
        )
        
        quota_griglia = estrai_quota_griglia(
            dati_terrestri,
        )
        
        analisi_quota = analizza_rappresentativita_altimetrica(
            quota_localita,
            quota_griglia,
        )

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

    comuni_costieri = carica_comuni_costieri()
    
    documento_html = genera_app_completa(
        luogo,
        latitudine,
        longitudine,
        dati_terrestri,
        ore,
        giorni,
        dati_mare=dati_mare,
        distanza_mare_km=distanza_mare_km,
        analisi_quota=analisi_quota,
        comuni_costieri=comuni_costieri,
    )

    components.html(
        documento,
        height=4300,
        scrolling=True,
    )

except Exception as errore:
    st.error(str(errore))
