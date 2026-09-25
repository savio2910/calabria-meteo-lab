# =====================================================================
# CALABRIA METEO LAB — VERSIONE STREAMLIT DEFINITIVA
# RENDERING DIRETTO CON CSS EMBEDDED
# =====================================================================

import html
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim

# =====================================================================
# CONFIGURAZIONE PAGINA
# =====================================================================
st.set_page_config(
    page_title="Calabria Meteo Lab",
    page_icon="🌤️",
    layout="wide",
)

API_URL = "https://api.open-meteo.com/v1/forecast"
MODELLO = "italia_meteo_arpae_icon_2i"
FUSO = ZoneInfo("Europe/Rome")
GIORNI = 3

# =====================================================================
# LOCALITÀ CALABRESI E BOUNDING BOX RIGIDO
# =====================================================================
COMUNI = {
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
    "reggio di calabria": "Reggio Calabria",
    "reggio": "Reggio Calabria",
    "rossano": "Corigliano-Rossano",
    "corigliano": "Corigliano-Rossano",
    "isola capo rizzuto": "Isola di Capo Rizzuto",
}

GIORNI_IT = [
    "lunedì", "martedì", "mercoledì", "giovedì",
    "venerdì", "sabato", "domenica",
]

MESI_IT = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]

CODICI = {
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

CURRENT = [
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

HOURLY = [
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

DAILY = [
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

# =====================================================================
# FORMATTAZIONE
# =====================================================================
def numero(x, decimali=1, unita=""):
    try:
        if x is None or pd.isna(x):
            return "—"
        return f"{float(x):.{decimali}f}{unita}"
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
        return CODICI.get(int(codice), ("❔", "Non disponibile"))
    except (TypeError, ValueError):
        return "❔", "Non disponibile"

def data_it(x):
    try:
        d = pd.Timestamp(x)
        return f"{GIORNI_IT[d.weekday()]} {d.day} {MESI_IT[d.month - 1]}"
    except (TypeError, ValueError):
        return "Data non disponibile"

def ora_it(x):
    try:
        if x is None or pd.isna(x):
            return "—"
        return pd.Timestamp(x).strftime("%H:%M")
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

def riga_giornaliera(ora, giorni):
    try:
        data_ora = pd.Timestamp(ora).date()
        righe = giorni.loc[giorni["time"].dt.date == data_ora]
        return None if righe.empty else righe.iloc[0]
    except (TypeError, ValueError):
        return None

def e_notte(ora, alba, tramonto):
    try:
        if any(x is None or pd.isna(x) for x in (ora, alba, tramonto)):
            return False
        return (
            pd.Timestamp(ora) < pd.Timestamp(alba)
            or pd.Timestamp(ora) >= pd.Timestamp(tramonto)
        )
    except (TypeError, ValueError):
        return False

# =====================================================================
# GEOCODIFICA RIGIDA (BLOCCO COMPLETO FUORI CALABRIA)
# =====================================================================
def risolvi_citta(testo):
    nome = testo.strip()
    if not nome:
        raise ValueError("Inserisci il nome di un comune o località della Calabria.")

    indice = {nome_comune.casefold(): nome_comune for nome_comune in COMUNI}
    nome_alias = ALIASES.get(nome.casefold(), nome)
    chiave = nome_alias.casefold()

    if chiave in indice:
        citta = indice[chiave]
        lat, lon = COMUNI[citta]
        return citta, lat, lon

    try:
        geocoder = Nominatim(user_agent="calabria_meteo_lab_v2", timeout=12)
        risposta = geocoder.geocode(
            f"{nome}, Italia",
            exactly_one=True,
            addressdetails=True,
            timeout=12,
        )
    except (GeocoderServiceError, GeocoderTimedOut) as exc:
        raise RuntimeError("Servizio di geolocalizzazione momentaneamente non disponibile.") from exc

    if risposta is None:
        raise ValueError(f"Località «{nome}» non trovata. Inserisci un comune calabrese.")

    indirizzo = risposta.raw.get("address", {})
    regione = str(indirizzo.get("state", "") or indirizzo.get("region", "")).casefold()
    lat, lon = float(risposta.latitude), float(risposta.longitude)

    # Verifica geografica e amministrativa ferrea
    is_calabria = "calabria" in regione
    in_bounds = (37.75 <= lat <= 40.15) and (15.60 <= lon <= 17.25)

    if not (is_calabria and in_bounds):
        raise ValueError(
            f"❌ «{nome}» non è in Calabria ({regione.title() if regione else 'Fuori regione'}). "
            f"Calabria Meteo Lab è attivo esclusivamente per il territorio calabrese."
        )

    nome_risolto = indirizzo.get("city") or indirizzo.get("town") or indirizzo.get("village") or nome.title()
    return nome_risolto, lat, lon

# =====================================================================
# DOWNLOAD DATI E PREPARAZIONE
# =====================================================================
def scarica_previsione(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "models": MODELLO,
        "timezone": "Europe/Rome",
        "forecast_days": GIORNI,
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "current": ",".join(CURRENT),
        "hourly": ",".join(HOURLY),
        "daily": ",".join(DAILY),
    }
    try:
        r = requests.get(API_URL, params=params, timeout=25)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        raise RuntimeError(f"Errore nel download dei dati ICON-2I: {exc}")

def prepara(dati):
    ore = pd.DataFrame(dati["hourly"])
    giorni = pd.DataFrame(dati["daily"])

    ore["time"] = pd.to_datetime(ore["time"])
    giorni["time"] = pd.to_datetime(giorni["time"])

    ora_locale = datetime.now(FUSO).replace(tzinfo=None)
    ore = ore.loc[ore["time"] >= pd.Timestamp(ora_locale).floor("h")].copy()

    giorni["Scenario"] = giorni["weather_code"].map(lambda c: " ".join(meteo(c)))
    giorni["Da"] = giorni["wind_direction_10m_dominant"].map(direzione)
    giorni["Fase lunare"] = giorni["moon_phase"].map(fase_lunare)

    ore["Icona"] = ore["weather_code"].map(lambda c: meteo(c)[0])
    ore["Scenario"] = ore["weather_code"].map(lambda c: meteo(c)[1])
    ore["Da"] = ore["wind_direction_10m"].map(direzione)

    ore["Notte"] = ore.apply(
        lambda riga: (
            False
            if riga_giornaliera(riga["time"], giorni) is None
            else e_notte(
                riga["time"],
                riga_giornaliera(riga["time"], giorni).get("sunrise"),
                riga_giornaliera(riga["time"], giorni).get("sunset"),
            )
        ),
        axis=1,
    )

    return ore.reset_index(drop=True), giorni.reset_index(drop=True)

# =====================================================================
# BLOCCHI HTML & CSS
# =====================================================================
CSS_GLOBAL = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

body, .stApp {
  font-family: 'Plus Jakarta Sans', Arial, sans-serif !important;
  background-color: #f6fafd !important;
  color: #102b3b;
}

.cml-container {
  max-width: 1200px;
  margin: 0 auto;
}

/* HERO */
.cml-hero {
  border-radius: 24px;
  padding: 32px 36px;
  margin-bottom: 24px;
  color: #fff;
  background: radial-gradient(circle at 85% 20%, rgba(117,241,244,.35), transparent 30%),
              linear-gradient(135deg, #071e3d 0%, #0c4d68 55%, #149c9e 100%);
  box-shadow: 0 16px 36px rgba(7,30,61,.18);
}
.cml-hero h1 { margin: 10px 0 6px; font-size: 34px; font-weight: 800; color: #fff; }
.cml-hero p { margin: 0; font-size: 14px; color: #d6f4f7; max-width: 700px; line-height: 1.6; }

/* PANNELLO ATTUALE */
.cml-card-current {
  background: #ffffff;
  border-radius: 20px;
  border: 1px solid #dcebef;
  box-shadow: 0 10px 28px rgba(16,43,59,.06);
  margin-bottom: 28px;
  overflow: hidden;
}
.cml-current-header {
  padding: 24px 28px;
  background: linear-gradient(110deg, #ffffff 40%, #edf9fb 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e7f1f4;
}
.cml-current-loc { font-size: 28px; font-weight: 800; color: #102b3b; margin: 4px 0; }
.cml-current-cond { font-size: 17px; color: #476572; font-weight: 600; }
.cml-current-temp { font-size: 64px; font-weight: 800; color: #ed8750; line-height: 1; }

.cml-metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  padding: 20px 28px;
  background: #ffffff;
}
.cml-metric-box {
  background: #f4fafb;
  border: 1px solid #e1edf0;
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.cml-metric-icon { font-size: 22px; }
.cml-metric-lbl { font-size: 11px; color: #698290; font-weight: 600; text-transform: uppercase; }
.cml-metric-val { font-size: 15px; font-weight: 700; color: #102b3b; }

/* 3 GIORNI */
.cml-section-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin: 24px 0 14px;
}
.cml-section-head h2 { font-size: 22px; font-weight: 800; color: #102b3b; margin: 0; }
.cml-days-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 18px;
  margin-bottom: 32px;
}
.cml-day-card {
  background: #ffffff;
  border: 1px solid #dcebef;
  border-radius: 18px;
  padding: 20px;
  box-shadow: 0 8px 20px rgba(16,43,59,.04);
}
.cml-day-tag { font-size: 11px; font-weight: 800; color: #087b8e; letter-spacing: 1px; }
.cml-day-date { font-size: 13px; font-weight: 700; color: #355364; float: right; }
.cml-day-main { display: flex; align-items: center; gap: 14px; margin: 14px 0; }
.cml-day-symbol { font-size: 34px; background: #fff4d9; padding: 10px; border-radius: 14px; }
.cml-day-desc { font-size: 16px; font-weight: 700; color: #102b3b; }
.cml-day-moon { font-size: 11px; font-weight: 600; color: #436280; background: #eef5fc; padding: 3px 8px; border-radius: 6px; display: inline-block; margin-top: 4px; }

.cml-day-temps {
  display: flex;
  justify-content: space-around;
  padding: 10px 0;
  margin: 10px 0;
  border-top: 1px solid #edf4f6;
  border-bottom: 1px solid #edf4f6;
}
.cml-tmin { color: #1c8ca6; font-size: 18px; font-weight: 800; }
.cml-tmax { color: #ed8750; font-size: 18px; font-weight: 800; }

.cml-day-row { display: flex; justify-content: space-between; font-size: 12px; margin: 6px 0; color: #4a6370; }
.cml-day-row b { color: #102b3b; }

.cml-astro-box {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #dcebef;
  font-size: 11px;
}
.cml-astro-box div { background: #f7fbfc; padding: 6px 8px; border-radius: 6px; }

/* TABELLA ORARIA */
.cml-table-wrap {
  width: 100%;
  overflow-x: auto;
  background: #ffffff;
  border: 1px solid #dcebef;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(16,43,59,.05);
  margin-top: 12px;
}
.cml-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  text-align: right;
  white-space: nowrap;
}
.cml-table th {
  background: #0b687c;
  color: #ffffff;
  font-weight: 700;
  padding: 12px 14px;
  text-align: right;
  font-size: 12px;
}
.cml-table th:first-child, .cml-table td:first-child { text-align: center; }
.cml-table th:nth-child(2), .cml-table td:nth-child(2) { text-align: left; }
.cml-table td {
  padding: 10px 14px;
  border-bottom: 1px solid #edf4f6;
  color: #102b3b;
}
.cml-table tr:nth-child(even) { background-color: #f9fcfd; }
.cml-table tr.cml-night {
  background: #132448 !important;
  color: #eaf1ff !important;
}
.cml-table tr.cml-night td {
  border-bottom: 1px solid #203565;
  color: #eaf1ff !important;
}
.cml-table tr.cml-night .cml-night-txt {
  color: #ffde8a !important;
  font-weight: 700;
}
</style>
"""

# Iniezione globale degli stili
st.markdown(CSS_GLOBAL, unsafe_allow_html=True)

# Header App
st.markdown("""
<div class="cml-container">
  <div class="cml-hero">
    <div style="font-size:11px;font-weight:800;letter-spacing:2px;color:#a6edf2;">CALABRIA · METEOROLOGIA LOCALE</div>
    <h1>Calabria Meteo Lab</h1>
    <p>Previsione ad alta risoluzione <b>ICON-2I (ItaliaMeteo–ARPAE)</b> per i comuni calabresi. Analisi tri-oraria, parametri atmosferici ed effemeridi.</p>
  </div>
</div>
""", unsafe_allow_html=True)

# Barra di ricerca
col1, col2 = st.columns([4, 1])
with col1:
    comune_selezionato = st.text_input(
        "Località calabrese",
        value="Lamezia Terme",
        label_visibility="collapsed",
        placeholder="Inserisci un comune della Calabria (es. Cosenza, Tropea, Catanzaro...)",
    )
with col2:
    btn_aggiorna = st.button("Aggiorna Previsione", type="primary", use_container_width=True)

if comune_selezionato:
    try:
        luogo, lat, lon = risolvi_citta(comune_selezionato)
        
        with st.spinner("Elaborazione modello ICON-2I in corso..."):
            dati = scarica_previsione(lat, lon)
            ore, giorni = prepara(dati)

        # 1. METEO ATTUALE
        cur = dati["current"]
        ico_cur, desc_cur = meteo(cur.get("weather_code"))
        
        st.markdown(f"""
        <div class="cml-container">
          <div class="cml-card-current">
            <div class="cml-current-header">
              <div>
                <div style="font-size:11px;font-weight:800;color:#087b8e;letter-spacing:1px;">● MODELLO ICON-2I ATTIVO</div>
                <div class="cml-current-loc">📍 {html.escape(luogo)}</div>
                <div class="cml-current-cond">{ico_cur} {html.escape(desc_cur)}</div>
              </div>
              <div class="cml-current-temp">{numero(cur.get("temperature_2m"), 1, "°C")}</div>
            </div>
            <div class="cml-metrics-grid">
              <div class="cml-metric-box"><div class="cml-metric-icon">🌡️</div><div><div class="cml-metric-lbl">Percepita</div><div class="cml-metric-val">{numero(cur.get("apparent_temperature"), 1, " °C")}</div></div></div>
              <div class="cml-metric-box"><div class="cml-metric-icon">💧</div><div><div class="cml-metric-lbl">Umidità</div><div class="cml-metric-val">{numero(cur.get("relative_humidity_2m"), 0, " %")}</div></div></div>
              <div class="cml-metric-box"><div class="cml-metric-icon">☁️</div><div><div class="cml-metric-lbl">Nuvolosità</div><div class="cml-metric-val">{numero(cur.get("cloud_cover"), 0, " %")}</div></div></div>
              <div class="cml-metric-box"><div class="cml-metric-icon">💨</div><div><div class="cml-metric-lbl">Vento</div><div class="cml-metric-val">{numero(cur.get("wind_speed_10m"), 0, " km/h")}</div></div></div>
              <div class="cml-metric-box"><div class="cml-metric-icon">🧭</div><div><div class="cml-metric-lbl">Direzione</div><div class="cml-metric-val">{direzione(cur.get("wind_direction_10m"))}</div></div></div>
              <div class="cml-metric-box"><div class="cml-metric-icon">🌬️</div><div><div class="cml-metric-lbl">Raffica</div><div class="cml-metric-val">{numero(cur.get("wind_gusts_10m"), 0, " km/h")}</div></div></div>
              <div class="cml-metric-box"><div class="cml-metric-icon">🌀</div><div><div class="cml-metric-lbl">Pressione</div><div class="cml-metric-val">{numero(cur.get("pressure_msl"), 1, " hPa")}</div></div></div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # 2. CARTE 3 GIORNI
        cards_html = []
        etichette = ["OGGI", "DOMANI", "DOPODOMANI"]
        for idx, (_, r) in enumerate(giorni.iterrows()):
            tag = etichette[idx] if idx < len(etichette) else "PROSSIMAMENTE"
            ico, desc = meteo(r["weather_code"])
            cards_html.append(f"""
            <div class="cml-day-card">
              <div><span class="cml-day-tag">{tag}</span><span class="cml-day-date">{data_it(r["time"])}</span></div>
              <div class="cml-day-main">
                <div class="cml-day-symbol">{ico}</div>
                <div><div class="cml-day-desc">{desc}</div><div class="cml-day-moon">{r.get("Fase lunare", "🌙")}</div></div>
              </div>
              <div class="cml-day-temps">
                <div><small style="color:#698290;font-size:10px;">MINIMA</small><div class="cml-tmin">↓ {numero(r["temperature_2m_min"], 1, "°")}</div></div>
                <div><small style="color:#698290;font-size:10px;">MASSIMA</small><div class="cml-tmax">↑ {numero(r["temperature_2m_max"], 1, "°")}</div></div>
              </div>
              <div class="cml-day-row"><span>🌧️ Pioggia tot.</span><b>{numero(r["precipitation_sum"], 1, " mm")}</b></div>
              <div class="cml-day-row"><span>💨 Vento max</span><b>{numero(r["wind_speed_10m_max"], 0, " km/h")} ({r["Da"]})</b></div>
              <div class="cml-day-row"><span>🌬️ Raffica max</span><b>{numero(r["wind_gusts_10m_max"], 0, " km/h")}</b></div>
              <div class="cml-astro-box">
                <div>☀️ Alba: <b>{ora_it(r.get("sunrise"))}</b></div>
                <div>🌇 Tramonto: <b>{ora_it(r.get("sunset"))}</b></div>
                <div>🌙 Sorge: <b>{ora_it(r.get("moonrise"))}</b></div>
                <div>🌘 Tramonta: <b>{ora_it(r.get("moonset"))}</b></div>
              </div>
            </div>
            """)

        st.markdown(f"""
        <div class="cml-container">
          <div class="cml-section-head">
            <h2>📅 Quadro Giornaliero (72 ore)</h2>
            <span style="font-size:12px;font-weight:700;color:#087b8e;">ICON-2I HIGH RESOLUTION</span>
          </div>
          <div class="cml-days-grid">{''.join(cards_html)}</div>
        </div>
        """, unsafe_allow_html=True)

        # 3. DETTAGLIO ORARIO
        st.markdown("""
        <div class="cml-container">
          <div class="cml-section-head">
            <h2>🕒 Dettaglio Orario</h2>
          </div>
        </div>
        """, unsafe_allow_html=True)

        date_disponibili = sorted(ore["time"].dt.date.unique())
        scelta_giorno = st.selectbox(
            "Seleziona il giorno per la tabella oraria:",
            options=date_disponibili,
            format_func=lambda d: data_it(d).title(),
        )

        ore_filtrate = ore.loc[ore["time"].dt.date == scelta_giorno]

        rows_html = []
        for _, riga in ore_filtrate.iterrows():
            is_n = bool(riga.get("Notte", False))
            cls_row = "cml-night" if is_n else ""
            txt_cls = "cml-night-txt" if is_n else ""
            
            rows_html.append(f"""
            <tr class="{cls_row}">
              <td style="font-weight:700;">{riga["time"].strftime("%H:%M")}</td>
              <td class="{txt_cls}">{riga["Icona"]} {riga["Scenario"]}</td>
              <td style="font-weight:700;">{numero(riga["temperature_2m"])}</td>
              <td>{numero(riga["apparent_temperature"])}</td>
              <td>{numero(riga["precipitation"])}</td>
              <td>{numero(riga["wind_speed_10m"], 0)}</td>
              <td style="text-align:center;"><b>{riga["Da"]}</b></td>
              <td>{numero(riga["wind_gusts_10m"], 0)}</td>
              <td>{numero(riga["cloud_cover"], 0)}</td>
              <td>{numero(riga["relative_humidity_2m"], 0)}</td>
            </tr>
            """)

        table_full = f"""
        <div class="cml-container">
          <div class="cml-table-wrap">
            <table class="cml-table">
              <thead>
                <tr>
                  <th>Ora</th>
                  <th>Cielo</th>
                  <th>Temp. (°C)</th>
                  <th>Percepita (°C)</th>
                  <th>Pioggia (mm)</th>
                  <th>Vento (km/h)</th>
                  <th style="text-align:center;">Da</th>
                  <th>Raffica (km/h)</th>
                  <th>Nubi (%)</th>
                  <th>Umidità (%)</th>
                </tr>
              </thead>
              <tbody>
                {''.join(rows_html)}
              </tbody>
            </table>
          </div>
          <div style="font-size:12px;color:#678292;margin-top:10px;padding:8px 12px;background:#ebf4f7;border-radius:8px;">
            ℹ️ Le righe con sfondo blu notte rappresentano le ore comprese tra il tramonto e l'alba per la località selezionata.
          </div>
        </div>
        """
        st.markdown(table_full, unsafe_allow_html=True)

    except Exception as err:
        st.error(str(err))
