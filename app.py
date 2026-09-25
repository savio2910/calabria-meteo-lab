# =====================================================================
# CALABRIA METEO LAB — SOLO CITTÀ
# ARCHITETTURA MONOLITICA AD ALTA PRECISIONE VISIVA (HTML/CSS CONTAINER)
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

st.set_page_config(
    page_title="Calabria Meteo Lab",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Nasconde padding e header nativi di Streamlit per un'esperienza a schermo intero pulita
st.markdown("""
<style>
  #MainMenu {visibility: hidden;}
  header {visibility: hidden;}
  footer {visibility: hidden;}
  .block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 1280px !important;
  }
</style>
""", unsafe_allow_html=True)

API_URL = "https://api.open-meteo.com/v1/forecast"
MODELLO = "italia_meteo_arpae_icon_2i"
FUSO = ZoneInfo("Europe/Rome")
GIORNI = 3

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

def risolvi_citta(testo):
    nome = testo.strip()
    if not nome:
        raise ValueError("Inserisci il nome di un comune della Calabria.")

    indice = {nome_comune.casefold(): nome_comune for nome_comune in COMUNI}
    nome_alias = ALIASES.get(nome.casefold(), nome)
    chiave = nome_alias.casefold()

    if chiave in indice:
        citta = indice[chiave]
        lat, lon = COMUNI[citta]
        return citta, lat, lon

    try:
        geocoder = Nominatim(user_agent="calabria_meteo_lab_standalone", timeout=12)
        risposta = geocoder.geocode(
            f"{nome}, Italia",
            exactly_one=True,
            addressdetails=True,
            timeout=12,
        )
    except (GeocoderServiceError, GeocoderTimedOut) as exc:
        raise RuntimeError("Servizio di ricerca geografica momentaneamente occupato. Riprova tra poco.") from exc

    if risposta is None:
        raise ValueError(f"Località «{nome}» non trovata. Verifica il nome del comune.")

    indirizzo = risposta.raw.get("address", {})
    regione = str(indirizzo.get("state", "") or indirizzo.get("region", "")).casefold()
    lat, lon = float(risposta.latitude), float(risposta.longitude)

    is_calabria = "calabria" in regione
    in_bounds = (37.75 <= lat <= 40.15) and (15.60 <= lon <= 17.25)

    if not (is_calabria and in_bounds):
        reg_txt = f" ({regione.title()})" if regione else ""
        raise ValueError(f"❌ «{nome}»{reg_txt} non si trova in Calabria. Calabria Meteo Lab copre esclusivamente i comuni calabresi.")

    nome_risolto = indirizzo.get("city") or indirizzo.get("town") or indirizzo.get("village") or nome.title()
    return nome_risolto, lat, lon

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
        raise RuntimeError(f"Errore nella ricezione dei dati dal modello ICON-2I: {exc}")

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
# MOTORE DI COSTRUZIONE HTML MONOLITICO
# =====================================================================
def genera_documento_meteo(luogo, dati, ore, giorni, giorno_selezionato):
    cur = dati["current"]
    ico_cur, desc_cur = meteo(cur.get("weather_code"))

    # 1. Metriche attuali
    metriche_html = f"""
    <div class="cml-metric"><div class="cml-metric-icon">🌡️</div><div><div class="cml-metric-lbl">Percepita</div><div class="cml-metric-val">{numero(cur.get("apparent_temperature"), 1, " °C")}</div></div></div>
    <div class="cml-metric"><div class="cml-metric-icon">💧</div><div><div class="cml-metric-lbl">Umidità</div><div class="cml-metric-val">{numero(cur.get("relative_humidity_2m"), 0, " %")}</div></div></div>
    <div class="cml-metric"><div class="cml-metric-icon">☁️</div><div><div class="cml-metric-lbl">Nuvolosità</div><div class="cml-metric-val">{numero(cur.get("cloud_cover"), 0, " %")}</div></div></div>
    <div class="cml-metric"><div class="cml-metric-icon">💨</div><div><div class="cml-metric-lbl">Vento</div><div class="cml-metric-val">{numero(cur.get("wind_speed_10m"), 0, " km/h")}</div></div></div>
    <div class="cml-metric"><div class="cml-metric-icon">🧭</div><div><div class="cml-metric-lbl">Provenienza</div><div class="cml-metric-val">{direzione(cur.get("wind_direction_10m"))}</div></div></div>
    <div class="cml-metric"><div class="cml-metric-icon">🌬️</div><div><div class="cml-metric-lbl">Raffica</div><div class="cml-metric-val">{numero(cur.get("wind_gusts_10m"), 0, " km/h")}</div></div></div>
    <div class="cml-metric"><div class="cml-metric-icon">🌀</div><div><div class="cml-metric-lbl">Pressione</div><div class="cml-metric-val">{numero(cur.get("pressure_msl"), 1, " hPa")}</div></div></div>
    """

    # 2. Schede 3 giorni
    etichette = ["OGGI", "DOMANI", "DOPODOMANI"]
    carte_html = []
    for idx, (_, r) in enumerate(giorni.iterrows()):
        tag = etichette[idx] if idx < len(etichette) else "PROSSIMAMENTE"
        ico, desc = meteo(r["weather_code"])
        fase = html.escape(str(r.get("Fase lunare", "🌙 Luna")))
        
        carte_html.append(f"""
        <div class="cml-day-card">
          <div class="cml-day-top">
            <span class="cml-day-tag">{tag}</span>
            <span class="cml-day-date">{html.escape(data_it(r["time"]))}</span>
          </div>
          <div class="cml-day-main">
            <div class="cml-day-sym">{ico}</div>
            <div>
              <div class="cml-day-desc">{html.escape(desc)}</div>
              <div class="cml-day-moon">{fase}</div>
            </div>
          </div>
          <div class="cml-day-temps">
            <div>
              <small>MINIMA</small>
              <strong class="cml-cold">↓ {numero(r["temperature_2m_min"], 1, "°")}</strong>
            </div>
            <div>
              <small>MASSIMA</small>
              <strong class="cml-warm">↑ {numero(r["temperature_2m_max"], 1, "°")}</strong>
            </div>
          </div>
          <div class="cml-day-row"><span>🌧️ Pioggia totale</span><b>{numero(r["precipitation_sum"], 1, " mm")}</b></div>
          <div class="cml-day-row"><span>💨 Vento max</span><b>{numero(r["wind_speed_10m_max"], 0, " km/h")} ({r["Da"]})</b></div>
          <div class="cml-day-row"><span>🌬️ Raffica max</span><b>{numero(r["wind_gusts_10m_max"], 0, " km/h")}</b></div>
          <div class="cml-astro-grid">
            <div><span>☀️ Alba</span><b>{ora_it(r.get("sunrise"))}</b></div>
            <div><span>🌇 Tramonto</span><b>{ora_it(r.get("sunset"))}</b></div>
            <div><span>🌙 Sorge</span><b>{ora_it(r.get("moonrise"))}</b></div>
            <div><span>🌘 Tramonta</span><b>{ora_it(r.get("moonset"))}</b></div>
          </div>
        </div>
        """)

    # 3. Tabella oraria
    ore_giorno = ore.loc[ore["time"].dt.date == giorno_selezionato]
    righe_tabella = []
    for _, riga in ore_giorno.iterrows():
        is_notte = bool(riga.get("Notte", False))
        classe_riga = "cml-night-row" if is_notte else "cml-day-row"
        
        righe_tabella.append(f"""
        <tr class="{classe_riga}">
          <td class="col-ora">{riga["time"].strftime("%H:%M")}</td>
          <td class="col-scenario"><span class="cml-t-icon">{riga["Icona"]}</span> <span class="cml-t-desc">{riga["Scenario"]}</span></td>
          <td class="col-num"><b>{numero(riga["temperature_2m"])}</b></td>
          <td class="col-num">{numero(riga["apparent_temperature"])}</td>
          <td class="col-num">{numero(riga["precipitation"])}</td>
          <td class="col-num">{numero(riga["wind_speed_10m"], 0)}</td>
          <td class="col-dir">{riga["Da"]}</td>
          <td class="col-num">{numero(riga["wind_gusts_10m"], 0)}</td>
          <td class="col-num">{numero(riga["cloud_cover"], 0)}</td>
          <td class="col-num">{numero(riga["relative_humidity_2m"], 0)}</td>
        </tr>
        """)

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #102b3b;
  background: transparent;
  padding: 4px;
}}

/* HERO */
.cml-hero {{
  position: relative;
  overflow: hidden;
  border-radius: 22px;
  padding: 30px 34px;
  margin-bottom: 22px;
  color: #ffffff;
  background: radial-gradient(circle at 85% 15%, rgba(117,241,244,.38), transparent 26%),
              linear-gradient(125deg, #061b33 0%, #07566f 52%, #13aab2 100%);
  box-shadow: 0 14px 34px rgba(5,57,78,.18);
}}
.cml-brand {{ font-size: 11px; font-weight: 800; letter-spacing: 2px; color: #a9eff3; text-transform: uppercase; margin-bottom: 6px; }}
.cml-hero h1 {{ font-size: 34px; font-weight: 800; letter-spacing: -0.8px; margin-bottom: 8px; color: #ffffff; }}
.cml-hero p {{ font-size: 14px; line-height: 1.6; color: #e1f7f8; max-width: 760px; }}

/* PANNELLO ATTUALE */
.cml-current-box {{
  background: #ffffff;
  border-radius: 20px;
  border: 1px solid #dcebef;
  box-shadow: 0 8px 24px rgba(18,71,89,.07);
  margin-bottom: 26px;
  overflow: hidden;
}}
.cml-current-main {{
  padding: 24px 28px;
  background: linear-gradient(110deg, #ffffff 40%, #edf9fb 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e7f1f4;
}}
.cml-kicker {{ color: #078195; font-size: 11px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; }}
.cml-current-main h2 {{ font-size: 28px; font-weight: 800; color: #102b3b; margin: 4px 0; }}
.cml-condition {{ font-size: 17px; color: #476572; font-weight: 600; }}
.cml-temp-display {{ font-size: 64px; font-weight: 800; color: #ed8750; line-height: 1; letter-spacing: -2px; }}

.cml-metrics-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
  padding: 16px 24px;
  background: #ffffff;
}}
.cml-metric {{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f4f9fa;
  border: 1px solid #e1edf1;
  border-radius: 12px;
}}
.cml-metric-icon {{ font-size: 20px; }}
.cml-metric-lbl {{ font-size: 11px; color: #607987; margin-bottom: 2px; font-weight: 600; }}
.cml-metric-val {{ font-size: 15px; font-weight: 700; color: #102b3b; }}

.cml-current-footer {{
  padding: 10px 24px;
  background: #fafdfe;
  border-top: 1px solid #eaf2f5;
  font-size: 11px;
  color: #698290;
  display: flex;
  gap: 20px;
}}

/* SEZIONE TITOLO */
.cml-sec-title {{
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin: 20px 0 14px;
}}
.cml-sec-title h3 {{ font-size: 22px; font-weight: 800; color: #102b3b; letter-spacing: -0.4px; }}
.cml-pill {{ padding: 6px 12px; border-radius: 999px; background: #e7f6f8; color: #087a8c; font-size: 11px; font-weight: 800; }}

/* 3 GIORNI GRID */
.cml-days-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
  margin-bottom: 28px;
}}
.cml-day-card {{
  background: linear-gradient(145deg, #ffffff 0%, #f5fbfc 58%, #eaf7fa 100%);
  border: 1px solid #dcebef;
  border-radius: 18px;
  padding: 18px;
  box-shadow: 0 6px 18px rgba(22,68,86,.06);
}}
.cml-day-top {{ display: flex; justify-content: space-between; font-size: 11px; font-weight: 800; color: #5e7884; margin-bottom: 12px; }}
.cml-day-tag {{ color: #078195; letter-spacing: 1px; }}
.cml-day-main {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
.cml-day-sym {{ font-size: 32px; background: linear-gradient(145deg, #fff2c9, #ffe5a0); width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; border-radius: 14px; flex-shrink: 0; }}
.cml-day-desc {{ font-size: 16px; font-weight: 700; color: #102b3b; line-height: 1.2; }}
.cml-day-moon {{ font-size: 11px; font-weight: 700; color: #405777; background: #edf4ff; padding: 2px 7px; border-radius: 999px; display: inline-block; margin-top: 4px; }}

.cml-day-temps {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  padding: 10px 0;
  margin: 10px 0;
  border-top: 1px solid #e2edf0;
  border-bottom: 1px solid #e2edf0;
}}
.cml-day-temps small {{ font-size: 9px; font-weight: 700; color: #71858e; letter-spacing: 0.8px; }}
.cml-cold {{ color: #2c91b7; font-size: 20px; font-weight: 800; }}
.cml-warm {{ color: #ed8750; font-size: 20px; font-weight: 800; }}

.cml-day-row {{ display: flex; justify-content: space-between; font-size: 12px; margin: 6px 0; color: #4b6470; }}
.cml-day-row b {{ color: #16495b; font-weight: 700; }}

.cml-astro-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #dcebef;
}}
.cml-astro-grid div {{
  display: flex;
  justify-content: space-between;
  padding: 5px 7px;
  background: rgba(255,255,255,0.7);
  border-radius: 8px;
  font-size: 10px;
}}
.cml-astro-grid span {{ color: #718791; }}
.cml-astro-grid b {{ color: #234c5b; }}

/* INTESTAZIONE TABELLA ORARIA */
.cml-hour-header {{
  border-radius: 16px;
  padding: 18px 22px;
  margin-bottom: 14px;
  color: #ffffff;
  background: linear-gradient(120deg, #0d1939 0%, #24366b 55%, #3f5184 100%);
  box-shadow: 0 8px 20px rgba(21,38,79,.16);
}}
.cml-hour-header span {{ color: #9aeaf1; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; }}
.cml-hour-header h4 {{ font-size: 20px; font-weight: 800; color: #d4b5ff; margin-top: 4px; }}

/* TABELLA ORARIA PREMIUM */
.cml-table-wrap {{
  width: 100%;
  overflow-x: auto;
  border: 1px solid #d9e7ec;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 6px 20px rgba(22,68,86,.06);
  margin-bottom: 12px;
}}
.cml-table {{
  width: 100%;
  min-width: 1050px;
  border-collapse: collapse;
  font-size: 13px;
  color: #102b3b;
  white-space: nowrap;
}}
.cml-table th {{
  height: 44px;
  padding: 0 12px;
  background: #0b687c;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
  text-align: right;
  border-bottom: 2px solid #085161;
}}
.cml-table td {{
  height: 42px;
  padding: 0 12px;
  border-bottom: 1px solid #e7eff2;
  text-align: right;
  font-variant-numeric: tabular-nums;
}}
.col-ora {{ text-align: center !important; font-weight: 700; color: #087b8e; width: 80px; }}
.col-scenario {{ text-align: left !important; }}
.cml-t-icon {{ display: inline-block; width: 24px; font-size: 17px; text-align: center; vertical-align: middle; }}
.cml-t-desc {{ vertical-align: middle; }}
.col-dir {{ text-align: center !important; font-weight: 700; color: #315b6a; width: 60px; }}

.cml-day-row:nth-child(even) {{ background: #f6fafb; }}
.cml-day-row:hover {{ background: #e8f5f7; }}

/* RIGHE NOTTURNE (BLU NOTTE) */
.cml-night-row {{
  background: linear-gradient(90deg, #111d42 0%, #1d2c59 100%) !important;
  color: #edf4ff !important;
}}
.cml-night-row td {{
  border-bottom: 1px solid #23376a;
  color: #edf4ff !important;
}}
.cml-night-row .col-ora {{ color: #a8e5ef !important; }}
.cml-night-row .cml-t-desc {{ color: #f4dda0 !important; font-weight: 700; }}
.cml-night-row .col-dir {{ color: #d4e8f5 !important; }}

.cml-note {{
  padding: 10px 14px;
  border-radius: 10px;
  background: #fff9ea;
  border-left: 4px solid #e5ad4f;
  color: #625237;
  font-size: 12px;
  line-height: 1.5;
  margin-top: 10px;
}}
</style>
</head>
<body>

<div class="cml-hero">
  <div class="cml-brand">CALABRIA · METEOROLOGIA LOCALE</div>
  <h1>Calabria Meteo Lab</h1>
  <p>Previsione ad altissima risoluzione con modello <b>ICON-2I (ItaliaMeteo–ARPAE)</b> a griglia locale 2.2 km per tutti i comuni calabresi.</p>
</div>

<div class="cml-current-box">
  <div class="cml-current-main">
    <div>
      <div class="cml-kicker">● MODELLO ICON-2I ATTIVO</div>
      <h2>📍 {html.escape(luogo)}</h2>
      <div class="cml-condition">{ico_cur} {html.escape(desc_cur)}</div>
    </div>
    <div class="cml-temp-display">{numero(cur.get("temperature_2m"), 1, "°C")}</div>
  </div>
  <div class="cml-metrics-grid">{metriche_html}</div>
  <div class="cml-current-footer">
    <span>◷ Rilevamento: <b>{html.escape(str(cur.get("time", "—")))}</b></span>
    <span>Fuso: <b>Europe/Rome</b></span>
    <span>Fonte: <b>ItaliaMeteo – ARPAE</b></span>
  </div>
</div>

<div class="cml-sec-title">
  <h3>📅 Quadro Previsionale (Prossimi 3 Giorni)</h3>
  <div class="cml-pill">Orizzonte 72 ore</div>
</div>
<div class="cml-days-grid">{''.join(carte_html)}</div>

<div class="cml-hour-header">
  <span>DETTAGLIO ORARIO</span>
  <h4>🕒 Previsione Ora per Ora — {html.escape(data_it(giorno_selezionato)).title()}</h4>
</div>

<div class="cml-table-wrap">
  <table class="cml-table">
    <thead>
      <tr>
        <th style="text-align:center;">Ora</th>
        <th style="text-align:left;">Cielo</th>
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
      {''.join(righe_tabella)}
    </tbody>
  </table>
</div>

<div class="cml-note">
  ℹ️ <b>Guida alla lettura:</b> La precipitazione è espressa in millimetri orari cumulati. Le righe con <b>sfondo blu notte</b> identificano in modo automatico le ore comprese tra il tramonto e l'alba per {html.escape(luogo)}.
</div>

</body>
</html>"""

# =====================================================================
# INTERFACCIA STREAMLIT CONTROLLI
# =====================================================================
st.markdown("### 🔍 Seleziona Località Calabrese")

# Form per evitare reload inutili alla digitazione
with st.form("search_form", clear_on_submit=False):
    col_in, col_btn = st.columns([4, 1])
    with col_in:
        testo_citta = st.text_input(
            "Località",
            value="Lamezia Terme",
            placeholder="Scrivi es. Cosenza, Tropea, Soverato, Reggio Calabria, Catanzaro...",
            label_visibility="collapsed"
        )
    with col_btn:
        invia = st.form_submit_button("Aggiorna Previsione", use_container_width=True, type="primary")

try:
    luogo, lat, lon = risolvi_citta(testo_citta)
    with st.spinner(f"Elaborazione dati ICON-2I per {luogo}..."):
        dati_meteo = scarica_previsione(lat, lon)
        df_ore, df_giorni = prepara(dati_meteo)

    # Selettore giorno orario
    date_disponibili = sorted(df_ore["time"].dt.date.unique())
    col_sel, _ = st.columns([2, 3])
    with col_sel:
        giorno_scelto = st.selectbox(
            "Visualizza dettaglio orario per il giorno:",
            options=date_disponibili,
            format_func=lambda d: data_it(d).title(),
        )

    # Generazione Documento HTML Monolitico
    html_finale = genera_documento_meteo(luogo, dati_meteo, df_ore, df_giorni, giorno_scelto)
    
    # Rendering con altezza dinamica protetta
    components.html(html_finale, height=1950, scrolling=False)

except Exception as errore:
    st.error(f"{errore}")
