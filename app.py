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

st.set_page_config(page_title="Calabria Meteo Lab", page_icon="🌤️", layout="wide")

st.markdown("""
<style>
#MainMenu, header, footer { visibility: hidden; }
.block-container { max-width: 1400px !important; padding-top: 1rem !important; }
[data-testid="stAppViewContainer"] { background: #eef5f8; }
</style>
""", unsafe_allow_html=True)

API_METEO_URL = "https://api.open-meteo.com/v1/forecast"
API_MARE_URL = "https://marine-api.open-meteo.com/v1/marine"
MODELLO_TERRESTRE = "italia_meteo_arpae_icon_2i"
FUSO_ORARIO = ZoneInfo("Europe/Rome")
GIORNI_PREVISIONE = 3
FILE_COMUNI_COSTIERI = Path("comuni_costieri_calabria.csv")

COMUNI_RAPIDI = {
    "Amantea": (39.1331, 16.0746), "Catanzaro": (38.9098, 16.5877),
    "Cirò Marina": (39.3703, 17.1247), "Corigliano-Rossano": (39.5900, 16.5190),
    "Cosenza": (39.2983, 16.2537), "Crotone": (39.0808, 17.1271),
    "Isola di Capo Rizzuto": (38.9597, 17.0924), "Lamezia Terme": (38.9708, 16.3189),
    "Locri": (38.2415, 16.2624), "Palmi": (38.3594, 15.8510),
    "Praia a Mare": (39.8932, 15.7800), "Reggio Calabria": (38.1113, 15.6473),
    "Roccella Ionica": (38.3225, 16.4038), "Sibari": (39.7470, 16.4550),
    "Soverato": (38.6842, 16.5495), "Tropea": (38.6766, 15.8984),
    "Vibo Valentia": (38.6762, 16.1005),
}

ALIASES = {
    "reggio": "Reggio Calabria", "reggio di calabria": "Reggio Calabria",
    "rossano": "Corigliano-Rossano", "corigliano": "Corigliano-Rossano",
    "isola capo rizzuto": "Isola di Capo Rizzuto", "capo rizzuto": "Isola di Capo Rizzuto",
}

GIORNI_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

CODICI_METEO = {
    0: ("☀️", "Sereno"), 1: ("🌤️", "Quasi sereno"), 2: ("⛅", "Parzialmente nuvoloso"), 3: ("☁️", "Coperto"),
    45: ("🌫️", "Nebbia"), 48: ("🌫️", "Nebbia con brina"), 51: ("🌦️", "Pioviggine debole"),
    53: ("🌦️", "Pioviggine moderata"), 55: ("🌧️", "Pioviggine intensa"), 56: ("🌧️", "Pioviggine gelata debole"),
    57: ("🌧️", "Pioviggine gelata intensa"), 61: ("🌧️", "Pioggia debole"), 63: ("🌧️", "Pioggia moderata"),
    65: ("🌧️", "Pioggia forte"), 66: ("🌨️", "Pioggia gelata debole"), 67: ("🌨️", "Pioggia gelata forte"),
    71: ("❄️", "Neve debole"), 73: ("❄️", "Neve moderata"), 75: ("❄️", "Neve forte"), 77: ("❄️", "Granelli di neve"),
    80: ("🌦️", "Rovesci deboli"), 81: ("🌧️", "Rovesci moderati"), 82: ("🌧️", "Rovesci forti"),
    85: ("🌨️", "Rovesci nevosi deboli"), 86: ("🌨️", "Rovesci nevosi forti"), 95: ("⛈️", "Temporale"),
    96: ("⛈️", "Temporale con grandine"), 99: ("⛈️", "Temporale con forte grandine"),
}

VARIABILI_CORRENTI = ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "weather_code", "cloud_cover", "pressure_msl", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"]
VARIABILI_ORARIE = ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "precipitation", "weather_code", "cloud_cover", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"]
VARIABILI_GIORNALIERE = ["weather_code", "temperature_2m_max", "temperature_2m_min", "sunrise", "sunset", "moonrise", "moonset", "moon_phase", "precipitation_sum", "wind_speed_10m_max", "wind_gusts_10m_max", "wind_direction_10m_dominant"]
VARIABILI_MARINE = ["wave_height", "wave_direction", "wave_period", "wave_peak_period", "wind_wave_height", "swell_wave_height", "sea_surface_temperature"]


def numero(valore, decimali=1, unita=""):
    try:
        if valore is None or pd.isna(valore): return "—"
        return f"{float(valore):.{decimali}f}{unita}"
    except (TypeError, ValueError): return "—"


def direzione(gradi):
    try:
        if gradi is None or pd.isna(gradi): return "—"
        return ["N", "NE", "E", "SE", "S", "SO", "O", "NO"][int((float(gradi) + 22.5) // 45) % 8]
    except (TypeError, ValueError): return "—"


def meteo(codice):
    try: return CODICI_METEO.get(int(codice), ("❔", "Non disponibile"))
    except (TypeError, ValueError): return "❔", "Non disponibile"


def data_it(valore):
    try:
        data = pd.Timestamp(valore)
        return f"{GIORNI_IT[data.weekday()]} {data.day} {MESI_IT[data.month - 1]}"
    except (TypeError, ValueError): return "Data non disponibile"


def ora_it(valore):
    try:
        if valore is None or pd.isna(valore): return "—"
        return pd.Timestamp(valore).strftime("%H:%M")
    except (TypeError, ValueError): return "—"


def fase_lunare(valore):
    try:
        f = float(valore)
        if f < .03 or f > .97: return "🌑 Luna nuova"
        if f < .22: return "🌒 Falce crescente"
        if f < .28: return "🌓 Primo quarto"
        if f < .47: return "🌔 Gibbosa crescente"
        if f < .53: return "🌕 Luna piena"
        if f < .72: return "🌖 Gibbosa calante"
        if f < .78: return "🌗 Ultimo quarto"
        return "🌘 Falce calante"
    except (TypeError, ValueError): return "🌙 Luna"


def e_notte(ora, alba, tramonto):
    try:
        if any(v is None or pd.isna(v) for v in (ora, alba, tramonto)): return False
        t = pd.Timestamp(ora)
        return t < pd.Timestamp(alba) or t >= pd.Timestamp(tramonto)
    except (TypeError, ValueError): return False


def icona_meteo_svg(codice, notte=False, dimensione=72):
    try: codice = int(codice)
    except (TypeError, ValueError): codice = 0
    if not notte:
        emoji, _ = meteo(codice)
        return f'<span class="cml-weather-emoji">{emoji}</span>'
    nube = codice in {1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}
    pioggia = codice in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
    neve = codice in {71, 73, 75, 77, 85, 86}
    fulmine = codice in {95, 96, 99}
    nube_svg = '<path d="M20 53 C20 46 26 42 32 43 C34 36 40 32 47 33 C54 33 59 38 60 44 C67 43 73 48 73 54 C73 59 69 62 63 62 L30 62 C24 62 20 59 20 53 Z" fill="#b8c9d7" stroke="#eef7fb" stroke-width="2" />' if nube else ""
    pioggia_svg = '<g stroke="#78c9f4" stroke-width="3" stroke-linecap="round"><line x1="31" y1="57" x2="27" y2="66" /><line x1="43" y1="57" x2="39" y2="66" /><line x1="55" y1="57" x2="51" y2="66" /></g>' if pioggia else ""
    neve_svg = '<g fill="#f7fcff" font-size="15" font-weight="700"><text x="27" y="68">✦</text><text x="40" y="70">✦</text><text x="53" y="67">✦</text></g>' if neve else ""
    fulmine_svg = '<path d="M47 48 L37 64 L44 63 L40 75 L55 56 L48 57 Z" fill="#ffd447" stroke="#fff2a6" stroke-width="1.2" />' if fulmine else ""
    ident = f"cml-night-{dimensione}-{codice}"
    return f'''<svg class="cml-weather-svg" width="{dimensione}" height="{dimensione}" viewBox="0 0 90 90" role="img" aria-label="Icona notturna"><defs><radialGradient id="{ident}"><stop offset="0%" stop-color="#263f72"/><stop offset="100%" stop-color="#101d43"/></radialGradient></defs><rect x="1" y="1" width="88" height="88" rx="22" fill="url(#{ident})"/><circle cx="57" cy="29" r="18" fill="#fff2ad" opacity=".85"/><circle cx="65" cy="23" r="18" fill="#15264e"/><circle cx="18" cy="20" r="1.5" fill="#fff"/><circle cx="75" cy="17" r="1.2" fill="#fff"/>{nube_svg}{pioggia_svg}{neve_svg}{fulmine_svg}</svg>'''


def normalizza_comune(nome):
    testo = unicodedata.normalize("NFKD", str(nome or "").strip().casefold().replace("-", " "))
    return "".join(c for c in testo if not unicodedata.combining(c))


@st.cache_data(ttl=86400, show_spinner=False)
def carica_comuni_costieri():
    if not FILE_COMUNI_COSTIERI.exists(): raise FileNotFoundError("Manca comuni_costieri_calabria.csv.")
    df = pd.read_csv(FILE_COMUNI_COSTIERI)
    if "comune" not in df.columns: raise ValueError("Il CSV deve contenere la colonna 'comune'.")
    return {normalizza_comune(c) for c in df["comune"].dropna()}


def comune_e_costiero(comune, elenco): return normalizza_comune(comune) in elenco


@st.cache_data(ttl=86400, show_spinner=False)
def geocodifica_calabria(nome):
    try:
        risposta = Nominatim(user_agent="calabria_meteo_lab", timeout=15).geocode(f"{nome}, Calabria, Italia", exactly_one=True, addressdetails=True, timeout=15)
    except (GeocoderServiceError, GeocoderTimedOut) as exc:
        raise RuntimeError("Servizio di geolocalizzazione non disponibile.") from exc
    if risposta is None: raise ValueError(f"Località «{nome}» non trovata.")
    indirizzo = risposta.raw.get("address", {})
    lat, lon = float(risposta.latitude), float(risposta.longitude)
    regione = str(indirizzo.get("state", "") or indirizzo.get("region", "")).casefold()
    if not ("calabria" in regione or (37.75 <= lat <= 40.15 and 15.60 <= lon <= 17.25)): raise ValueError(f"«{nome}» non è in Calabria.")
    luogo = indirizzo.get("city") or indirizzo.get("town") or indirizzo.get("village") or indirizzo.get("municipality") or nome.title()
    comune = indirizzo.get("municipality") or indirizzo.get("city") or indirizzo.get("town") or indirizzo.get("village") or luogo
    return luogo, lat, lon, comune


def risolvi_localita(testo):
    nome = str(testo).strip()
    if not nome: raise ValueError("Inserisci una località della Calabria.")
    nome = ALIASES.get(nome.casefold(), nome)
    for comune, (lat, lon) in COMUNI_RAPIDI.items():
        if comune.casefold() == nome.casefold(): return comune, lat, lon, comune
    return geocodifica_calabria(nome)


@st.cache_data(ttl=600, show_spinner=False)
def scarica_previsione_terrestre(lat, lon):
    params = {"latitude": lat, "longitude": lon, "models": MODELLO_TERRESTRE, "timezone": "Europe/Rome", "forecast_days": GIORNI_PREVISIONE, "temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm", "current": ",".join(VARIABILI_CORRENTI), "hourly": ",".join(VARIABILI_ORARIE), "daily": ",".join(VARIABILI_GIORNALIERE)}
    try:
        r = requests.get(API_METEO_URL, params=params, timeout=25); r.raise_for_status(); return r.json()
    except requests.RequestException as exc: raise RuntimeError(f"Errore dati ICON-2I: {exc}") from exc


def distanza_haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088; p1, p2 = math.radians(lat1), math.radians(lat2); dp = math.radians(lat2-lat1); dl = math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


@st.cache_data(ttl=900, show_spinner=False)
def scarica_previsione_mare(lat, lon):
    params = {"latitude": lat, "longitude": lon, "timezone": "Europe/Rome", "forecast_days": GIORNI_PREVISIONE, "cell_selection": "sea", "current": ",".join(VARIABILI_MARINE)}
    try:
        r = requests.get(API_MARE_URL, params=params, timeout=25); r.raise_for_status(); dati = r.json()
    except requests.RequestException as exc: raise RuntimeError(f"Errore dati marini: {exc}") from exc
    return dati, distanza_haversine_km(lat, lon, float(dati.get("latitude", lat)), float(dati.get("longitude", lon)))


def prepara_dati_terrestri(dati):
    ore, giorni = pd.DataFrame(dati["hourly"]), pd.DataFrame(dati["daily"])
    ore["time"], giorni["time"] = pd.to_datetime(ore["time"]), pd.to_datetime(giorni["time"])
    prevalenti, nubi = [], []
    for _, giorno in giorni.iterrows():
        subset = ore.loc[ore["time"].dt.date == giorno["time"].date()]
        diurne = subset.loc[(subset["time"] >= pd.Timestamp(giorno["sunrise"])) & (subset["time"] <= pd.Timestamp(giorno["sunset"]))]
        target = diurne if not diurne.empty else subset
        nubi.append(round(target["cloud_cover"].mean()))
        severi = [99,96,95,82,81,80,65,63,61,55,53,51]
        prevalenti.append(next((c for c in severi if (target["weather_code"] == c).sum() >= 2), int(target["weather_code"].mode().iloc[0]) if not target.empty else 0))
    giorni["weather_code_prevalente"], giorni["cloud_cover_diurno"] = prevalenti, nubi
    giorni["Da"], giorni["Fase lunare"] = giorni["wind_direction_10m_dominant"].map(direzione), giorni["moon_phase"].map(fase_lunare)
    now = datetime.now(FUSO_ORARIO).replace(tzinfo=None)
    ore = ore.loc[ore["time"] >= pd.Timestamp(now).floor("h")].copy()
    notti, icone = [], []
    for _, riga in ore.iterrows():
        giorno = giorni.loc[giorni["time"].dt.date == riga["time"].date()].iloc[0]
        notte = e_notte(riga["time"], giorno["sunrise"], giorno["sunset"]); notti.append(notte); icone.append(icona_meteo_svg(riga["weather_code"], notte, 38))
    ore["Notte"], ore["Icona"] = notti, icone
    ore["Scenario"], ore["Da"] = ore["weather_code"].map(lambda c: meteo(c)[1]), ore["wind_direction_10m"].map(direzione)
    return ore.reset_index(drop=True), giorni.reset_index(drop=True)


def rischio(riga):
    p, g, c = float(riga.get("precipitation_sum",0) or 0), float(riga.get("wind_gusts_10m_max",0) or 0), int(riga.get("weather_code_prevalente",0))
    if p >= 100 or g >= 100 or c in [96,99]: return "rosso"
    if p >= 50 or g >= 70 or c in [95,96,99]: return "arancione"
    if p >= 20 or g >= 50 or c in [80,81,82]: return "giallo"
    return "verde"


def genera_html(luogo, lat, lon, dati, ore, giorni, dati_mare, distanza):
    corrente = dati["current"]; icona, descrizione = meteo(corrente.get("weather_code"))
    metriche = "".join(f'<div class="metric"><span>{i}</span><small>{e}</small><strong>{v}</strong></div>' for i,e,v in [("🌡️","Percepita",numero(corrente.get("apparent_temperature"),1," °C")),("💧","Umidità",numero(corrente.get("relative_humidity_2m"),0," %")),("☁️","Nubi",numero(corrente.get("cloud_cover"),0," %")),("💨","Vento",numero(corrente.get("wind_speed_10m"),0," km/h")),("🧭","Direzione",direzione(corrente.get("wind_direction_10m"))), ("🌬️","Raffica",numero(corrente.get("wind_gusts_10m"),0," km/h")),("🌀","Pressione",numero(corrente.get("pressure_msl"),1," hPa"))])
    mare = ""
    if isinstance(dati_mare, dict) and dati_mare.get("current"):
        cm = dati_mare["current"]; mare = f'<section class="box"><h2>🌊 Stato del mare</h2><p>Cella marina distante {numero(distanza,1," km")}</p><div class="marine"><b>🌊 Onda {numero(cm.get("wave_height"),2," m")}</b><span>Direzione {direzione(cm.get("wave_direction"))}</span><span>Periodo {numero(cm.get("wave_period"),1," s")}</span><span>Temperatura {numero(cm.get("sea_surface_temperature"),1," °C")}</span></div></section>'
    carte = []
    for i, (_, riga) in enumerate(giorni.iterrows()):
        codice = int(riga.get("weather_code_prevalente",0)); _, desc = meteo(codice); icona_giorno = icona_meteo_svg(codice, False, 68)
        carte.append(f'<article class="day"><span class="tag">{["OGGI","DOMANI","DOPODOMANI"][i] if i<3 else "GIORNO"}</span><h3>{html.escape(data_it(riga["time"]))}</h3><span class="risk {rischio(riga)}">{rischio(riga).title()}</span><div class="day-icon">{icona_giorno}</div><h2>{html.escape(desc)}</h2><div class="temps"><b>↓ {numero(riga["temperature_2m_min"],1,"°")}</b><b>↑ {numero(riga["temperature_2m_max"],1,"°")}</b></div><p>☁️ Nubi {numero(riga.get("cloud_cover_diurno"),0," %")}</p><p>🌧️ Pioggia {numero(riga.get("precipitation_sum"),1," mm")}</p><p>💨 Raffica {numero(riga.get("wind_gusts_10m_max"),0," km/h")}</p><p>☀️ {ora_it(riga.get("sunrise"))} · 🌇 {ora_it(riga.get("sunset"))}</p><p>🌙 {html.escape(str(riga.get("Fase lunare","Luna")))}</p></article>')
    tabelle, grafici = [], {}
    for giorno in sorted(ore["time"].dt.date.unique()):
        key = str(giorno); sub = ore.loc[ore["time"].dt.date == giorno]; grafici[key] = {"ore": sub["time"].dt.strftime("%H:%M").tolist(), "temperatura": sub["temperature_2m"].round(1).tolist(), "vento": sub["wind_speed_10m"].round(1).tolist(), "precipitazione": sub["precipitation"].round(1).tolist()}
        righe = "".join(f'<tr class="{"night" if bool(r["Notte"]) else ""}"><td>{r["time"].strftime("%H:%M")}</td><td>{r["Icona"]} {html.escape(str(r["Scenario"]))}</td><td>{numero(r["temperature_2m"],1)}</td><td>{numero(r["precipitation"],1)}</td><td>{numero(r["wind_speed_10m"],0)}</td><td>{r["Da"]}</td><td>{numero(r["cloud_cover"],0)}</td></tr>' for _,r in sub.iterrows())
        tabelle.append(f'<h3>{html.escape(data_it(giorno).title())}</h3><div class="table-wrap"><table><tr><th>Ora</th><th>Scenario</th><th>Temp.</th><th>Pioggia</th><th>Vento</th><th>Da</th><th>Nubi</th></tr>{righe}</table></div>')
    template = r'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><script src="https://cdn.jsdelivr.net/npm/chart.js"></script><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><style>*{box-sizing:border-box}body{margin:0;padding:10px;background:#eef5f8;color:#102b3b;font-family:Arial}.hero,.box,.day,.chart{margin:15px 0;padding:24px;border-radius:22px;background:#fff;box-shadow:0 8px 25px #1743541a}.hero{color:#fff;background:linear-gradient(135deg,#06324d,#087f91)}.current{display:flex;justify-content:space-between;align-items:center}.temperature{font-size:76px;color:#f26e17;font-weight:900}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px}.metric{padding:14px;border:1px solid #dce9ed;border-radius:14px;background:#f7fbfc}.metric span{font-size:23px}.metric small,.metric strong{display:block;margin-top:4px}.metric small{color:#607987}.marine{display:flex;gap:15px;flex-wrap:wrap}.days{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:15px}.day{margin:0}.tag{padding:6px 10px;border-radius:99px;background:#087087;color:#fff;font-size:11px}.risk{display:inline-block;padding:6px 10px;border-radius:8px;color:#fff}.verde{background:#12855c}.giallo{background:#b77906}.arancione{background:#d85d05}.rosso{background:#be2635}.day-icon{margin:15px 0}.temps{display:flex;justify-content:space-around;padding:12px;background:#f7fbfc;border-radius:12px}.temps b:first-child{color:#167aa9}.temps b:last-child{color:#f26e17}.table-wrap{overflow-x:auto}.table-wrap table{width:100%;min-width:800px;border-collapse:collapse}.table-wrap th{padding:11px;background:#087087;color:#fff}.table-wrap td{padding:9px;border-bottom:1px solid #e0eaed}.night{background:#142549!important;color:#e5f0ff}.chart-area{height:330px}#map{height:420px;border-radius:15px}.cml-weather-svg{vertical-align:middle}.day-icon .cml-weather-svg{width:68px;height:68px}.table-wrap .cml-weather-svg{width:38px;height:38px}@media(max-width:760px){.hero{padding:22px}.current{display:block}.temperature{font-size:58px}.box,.day,.chart{padding:18px}}</style></head><body><section class="hero"><h1>Calabria Meteo Lab</h1><p>Previsioni locali con icone notturne SVG.</p></section><section class="box current"><div><h2>📍 __LUOGO__</h2><p>__ICONA__ __DESCRIZIONE__</p></div><div class="temperature">__TEMPERATURA__ °C</div></section><section class="box"><div class="metrics">__METRICHE__</div></section>__MARE__<section class="box"><h2>📡 Radar precipitazioni</h2><div id="map"></div></section><section><h2>📅 Prossimi giorni</h2><div class="days">__CARTE__</div></section><section class="chart"><h2>🕒 Dettaglio orario</h2><div class="chart-area"><canvas id="chart"></canvas></div></section><section>__TABELLE__</section><script>const dati=__DATI__;const key=Object.keys(dati)[0];if(key){const d=dati[key];new Chart(document.getElementById('chart'),{type:'line',data:{labels:d.ore,datasets:[{label:'Temperatura °C',data:d.temperatura,borderColor:'#ef6c16',tension:.3},{label:'Vento km/h',data:d.vento,borderColor:'#0a8b72',tension:.3}]},options:{responsive:true,maintainAspectRatio:false}})}const map=L.map('map').setView([__LAT__,__LON__],8);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}).addTo(map);L.marker([__LAT__,__LON__]).addTo(map);</script></body></html>'''
    valori = {"LUOGO":html.escape(luogo),"ICONA":icona,"DESCRIZIONE":html.escape(descrizione),"TEMPERATURA":numero(corrente.get("temperature_2m"),1),"METRICHE":metriche,"MARE":mare,"CARTE":"".join(carte),"TABELLE":"".join(tabelle),"DATI":json.dumps(grafici,ensure_ascii=False),"LAT":str(lat),"LON":str(lon)}
    for key, value in valori.items(): template = template.replace("__"+key+"__", value)
    return template

try:
    comuni_costieri = carica_comuni_costieri()
except (FileNotFoundError, ValueError) as errore:
    st.error(str(errore)); st.stop()

st.markdown("## 🔎 Seleziona località calabrese")
with st.form("search_form"):
    col1, col2 = st.columns([4,1])
    with col1: testo_localita = st.text_input("Località", value="Cosenza", label_visibility="collapsed")
    with col2: st.form_submit_button("Aggiorna previsione", use_container_width=True, type="primary")

try:
    luogo, lat, lon, comune = risolvi_localita(testo_localita)
    with st.spinner(f"Elaborazione previsione per {luogo}..."):
        dati = scarica_previsione_terrestre(lat, lon)
        ore, giorni = prepara_dati_terrestri(dati)
        dati_mare = distanza = None
        if comune_e_costiero(comune, comuni_costieri):
            try: dati_mare, distanza = scarica_previsione_mare(lat, lon)
            except RuntimeError: pass
    components.html(genera_html(luogo, lat, lon, dati, ore, giorni, dati_mare, distanza), height=4300, scrolling=True)
except Exception as errore:
    st.error(str(errore))
