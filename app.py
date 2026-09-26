import html
from datetime import datetime
from zoneinfo import ZoneInfo
import json

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

st.markdown("""
<style>
  #MainMenu {visibility: hidden;}
  header {visibility: hidden;}
  footer {visibility: hidden;}
  .block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 1400px !important;
  }
</style>
""", unsafe_allow_html=True)

API_URL = "https://api.open-meteo.com/v1/forecast"
MODELLO = "italia_meteo_arpae_icon_2i"
FUSO = ZoneInfo("Europe/Rome")
GIORNI = 3

COMUNI = {
    "Amantea": (39.1331, 16.0746),
    "Belvedere Marittimo": (39.7833, 15.8000),
    "Bisignano": (39.3667, 16.2167),
    "Catanzaro": (38.9098, 16.5877),
    "Castrovillari": (39.8167, 16.2000),
    "Cirò Marina": (39.3703, 17.1247),
    "Corigliano-Rossano": (39.5900, 16.5190),
    "Cosenza": (39.2983, 16.2537),
    "Crotone": (39.0808, 17.1271),
    "Diamante": (39.7333, 15.7833),
    "Isola di Capo Rizzuto": (38.9597, 17.0924),
    "Lamezia Terme": (38.9708, 16.3189),
    "Locri": (38.2415, 16.2624),
    "Paola": (39.3667, 16.0333),
    "Palmi": (38.3594, 15.8510),
    "Praia a Mare": (39.8932, 15.7800),
    "Reggio Calabria": (38.1113, 15.6473),
    "Rende": (39.3500, 16.2167),
    "Roccella Ionica": (38.3225, 16.4038),
    "Rossano": (39.5900, 16.5190),
    "Scalea": (39.7833, 15.7833),
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

GIORNI_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

CODICI = {
    0: ("☀️", "Sereno"), 1: ("🌤️", "Quasi sereno"), 2: ("⛅", "Parzialmente nuvoloso"), 3: ("☁️", "Coperto"),
    45: ("🌫️", "Nebbia"), 48: ("🌫️", "Nebbia con brina"),
    51: ("🌦️", "Pioviggine debole"), 53: ("🌦️", "Pioviggine moderata"), 55: ("🌧️", "Pioviggine intensa"),
    61: ("🌧️", "Pioggia debole"), 63: ("🌧️", "Pioggia moderata"), 65: ("🌧️", "Pioggia forte"),
    71: ("❄️", "Neve debole"), 73: ("❄️", "Neve moderata"), 75: ("❄️", "Neve forte"),
    80: ("🌦️", "Rovesci deboli"), 81: ("🌧️", "Rovesci moderati"), 82: ("🌧️", "Rovesci forti"),
    95: ("⛈️", "Temporale"), 96: ("⛈️", "Temporale con grandine"), 99: ("⛈️", "Temporale con forte grandine"),
}

CURRENT = ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "weather_code", "cloud_cover", "pressure_msl", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"]
HOURLY = ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "precipitation", "weather_code", "cloud_cover", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"]
DAILY = ["weather_code", "temperature_2m_max", "temperature_2m_min", "sunrise", "sunset", "moonrise", "moonset", "moon_phase", "precipitation_sum", "wind_speed_10m_max", "wind_gusts_10m_max", "wind_direction_10m_dominant"]

def numero(x, decimali=1, unita=""):
    try:
        if x is None or pd.isna(x): return "—"
        return f"{float(x):.{decimali}f}{unita}"
    except: return "—"

def direzione(gradi):
    try:
        if gradi is None or pd.isna(gradi): return "—"
        direzioni = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
        return direzioni[int((float(gradi) + 22.5) // 45) % 8]
    except: return "—"

def meteo(codice):
    try:
        if codice is None or pd.isna(codice): return "❔", "Non disponibile"
        return CODICI.get(int(codice), ("❔", "Non disponibile"))
    except: return "❔", "Non disponibile"

def data_it(x):
    try:
        d = pd.Timestamp(x)
        return f"{GIORNI_IT[d.weekday()]} {d.day} {MESI_IT[d.month - 1]}"
    except: return "Data non disponibile"

def ora_it(x):
    try:
        if x is None or pd.isna(x): return "—"
        return pd.Timestamp(x).strftime("%H:%M")
    except: return "—"

def fase_lunare(valore):
    try:
        if valore is None or pd.isna(valore): return "🌙 Luna"
        fase = float(valore)
        if fase < 0.03 or fase > 0.97: return "🌑 Luna nuova"
        if fase < 0.22: return "🌒 Falce crescente"
        if fase < 0.28: return "🌓 Primo quarto"
        if fase < 0.47: return "🌔 Gibbosa crescente"
        if fase < 0.53: return "🌕 Luna piena"
        if fase < 0.72: return "🌖 Gibbosa calante"
        if fase < 0.78: return "🌗 Ultimo quarto"
        return "🌘 Falce calante"
    except: return "🌙 Luna"

def calcola_dati_diurni(ore_giorno, alba, tramonto):
    if ore_giorno.empty: return 0, 0
    if alba is not None and tramonto is not None:
        ore_diurne = ore_giorno.loc[(ore_giorno["time"] >= pd.Timestamp(alba)) & (ore_giorno["time"] <= pd.Timestamp(tramonto))]
    else:
        ore_diurne = ore_giorno.loc[(ore_giorno["time"].dt.hour >= 7) & (ore_giorno["time"].dt.hour <= 20)]
    df_target = ore_diurne if not ore_diurne.empty else ore_giorno
    nubi_media = round(df_target["cloud_cover"].mean()) if "cloud_cover" in df_target else 0
    codici_severi = [99, 96, 95, 82, 81, 80, 65, 63, 61, 55, 53, 51]
    for c_sev in codici_severi:
        if (df_target["weather_code"] == c_sev).sum() >= 2: return c_sev, nubi_media
    return df_target["weather_code"].mode()[0] if not df_target.empty else 0, nubi_media

def risolvi_citta(testo):
    nome = testo.strip()
    if not nome: raise ValueError("Inserisci il nome di un comune o località della Calabria.")
    indice = {c.casefold(): c for c in COMUNI}
    nome_alias = ALIASES.get(nome.casefold(), nome)
    if nome_alias.casefold() in indice:
        citta = indice[nome_alias.casefold()]
        return citta, COMUNI[citta][0], COMUNI[citta][1]
    try:
        geocoder = Nominatim(user_agent="calabria_meteo_lab_v18", timeout=8)
        risposta = geocoder.geocode(f"{nome}, Calabria, Italia", exactly_one=True, addressdetails=True, timeout=8)
    except (GeocoderServiceError, GeocoderTimedOut) as exc:
        raise RuntimeError(f"Località '{nome}' non trovata. Usa uno dei comuni nella lista.") from exc
    if risposta is None: raise ValueError(f"Località «{nome}» non trovata.")
    indirizzo = risposta.raw.get("address", {})
    regione = str(indirizzo.get("state", "") or indirizzo.get("region", "")).casefold()
    lat, lon = float(risposta.latitude), float(risposta.longitude)
    if not ("calabria" in regione and (37.75 <= lat <= 40.15) and (15.60 <= lon <= 17.25)):
        raise ValueError(f"❌ «{nome}» non è in Calabria.")
    return indirizzo.get("city") or indirizzo.get("town") or nome.title(), lat, lon

def scarica_previsione(lat, lon):
    params = {"latitude": lat, "longitude": lon, "models": MODELLO, "timezone": "Europe/Rome", "forecast_days": GIORNI, "temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm", "current": ",".join(CURRENT), "hourly": ",".join(HOURLY), "daily": ",".join(DAILY)}
    try:
        r = requests.get(API_URL, params=params, timeout=25)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        raise RuntimeError(f"Errore nella ricezione dei dati: {exc}")

def prepara(dati):
    ore_raw = pd.DataFrame(dati["hourly"])
    giorni = pd.DataFrame(dati["daily"])
    ore_raw["time"] = pd.to_datetime(ore_raw["time"])
    giorni["time"] = pd.to_datetime(giorni["time"])
    codici_prevalenti, nuvolosita_giornaliera = [], []
    for _, g in giorni.iterrows():
        ore_del_giorno = ore_raw.loc[ore_raw["time"].dt.date == g["time"].date()]
        cod_prev, nubi_prev = calcola_dati_diurni(ore_del_giorno, g.get("sunrise"), g.get("sunset"))
        codici_prevalenti.append(cod_prev)
        nuvolosita_giornaliera.append(nubi_prev)
    giorni["weather_code_prevalente"] = codici_prevalenti
    giorni["cloud_cover_diurno"] = nuvolosita_giornaliera
    giorni["Da"] = giorni["wind_direction_10m_dominant"].map(direzione)
    giorni["Fase lunare"] = giorni["moon_phase"].map(fase_lunare)
    ora_locale = datetime.now(FUSO).replace(tzinfo=None)
    ore = ore_raw.loc[ore_raw["time"] >= pd.Timestamp(ora_locale).floor("h")].copy()
    ore["Icona"] = ore["weather_code"].map(lambda c: meteo(c)[0])
    ore["Scenario"] = ore["weather_code"].map(lambda c: meteo(c)[1])
    ore["Da"] = ore["wind_direction_10m"].map(direzione)
    return ore.reset_index(drop=True), giorni.reset_index(drop=True)

def valuta_allerta_giornaliera(riga):
    precip = float(riga.get("precipitation_sum", 0) or 0)
    raffiche_max = float(riga.get("wind_gusts_10m_max", 0) or 0)
    weather_code = int(riga.get("weather_code_prevalente", riga.get("weather_code", 0)))
    if precip >= 100 or raffiche_max >= 100 or weather_code in [96, 99]:
        return "rosso", "temporali" if weather_code in [95, 96, 99] or precip >= 80 else ("vento" if raffiche_max >= 100 else "pioggia")
    if precip >= 50 or raffiche_max >= 70 or weather_code in [95, 96, 99]:
        return "arancione", "temporali" if weather_code in [95, 96, 99] or precip >= 40 else ("vento" if raffiche_max >= 70 else "pioggia")
    if precip >= 20 or raffiche_max >= 50 or weather_code in [80, 81, 82]:
        return "giallo", "temporali" if weather_code in [80, 81, 82, 95, 96, 99] else ("pioggia" if precip >= 20 else "vento")
    return "verde", "nessuno"

def badge_allerta_html(livello, tipo):
    colori = {"verde": ("#10b981", "#059669", "Nessuna criticità"), "giallo": ("#fbbf24", "#d97706", "Allerta meteo"), "arancione": ("#f97316", "#ea580c", "Allerta moderata"), "rosso": ("#ef4444", "#dc2626", "Allerta critica")}
    bg, border, label = colori.get(livello, colori["verde"])
    icone = {"temporali": "⛈️", "pioggia": "🌧️", "vento": "💨", "nessuno": "✅"}
    return f'<div class="cml-alert-badge" style="background:{bg};border-color:{border};color:white;display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:12px;border:2px solid rgba(255,255,255,0.3);font-size:12px;font-weight:700;box-shadow:0 4px 12px rgba(0,0,0,0.15);"><span style="font-size:18px;">{icone.get(tipo,"✅")}</span><span>{label} · {tipo.title()}</span></div>'

def genera_grafico_orario(ore_giorno):
    ore_list = ore_giorno["time"].dt.strftime("%H:%M").tolist()
    temp_list = [round(x, 1) if pd.notna(x) else 0 for x in ore_giorno["temperature_2m"].fillna(0).tolist()]
    pioggia_list = [round(x, 1) if pd.notna(x) else 0 for x in ore_giorno["precipitation"].fillna(0).tolist()]
    vento_list = [round(x, 0) if pd.notna(x) else 0 for x in ore_giorno["wind_speed_10m"].fillna(0).tolist()]
    return f"""
    <div style="margin:20px 0;padding:20px;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
      <canvas id="meteoChart"></canvas>
    </div>
    <script>
      const ctx = document.getElementById('meteoChart').getContext('2d');
      new Chart(ctx, {{
        type: 'line',
        data: {{
          labels: {ore_list},
          datasets: [
            {{label:'Temp. °C',data:{temp_list},borderColor:'#f97316',backgroundColor:'rgba(249,115,22,0.1)',yAxisID:'y',tension:0.4,fill:true}},
            {{label:'Pioggia mm',data:{pioggia_list},borderColor:'#3b82f6',backgroundColor:'rgba(59,130,246,0.1)',yAxisID:'y1',tension:0.4,fill:true}},
            {{label:'Vento km/h',data:{vento_list},borderColor:'#10b981',backgroundColor:'rgba(16,185,129,0.1)',yAxisID:'y2',tension:0.4,borderDash:[5,5]}}
          ]
        }},
        options: {{
          responsive: true,
          interaction: {{mode:'index',intersect:false}},
          scales: {{
            x: {{grid:{{color:'rgba(0,0,0,0.05)'}}}},
            y: {{type:'linear',display:true,position:'left',title:{{display:true,text:'Temperatura (°C)'}},grid:{{color:'rgba(0,0,0,0.05)'}}}},
            y1: {{type:'linear',display:true,position:'right',title:{{display:true,text:'Pioggia (mm)'}},grid:{{drawOnChartArea:false}},min:0}},
            y2: {{type:'linear',display:true,position:'right',title:{{display:true,text:'Vento (km/h)'}},grid:{{drawOnChartArea:false}},min:0}}
          }},
          plugins: {{legend:{{position:'top'}},tooltip:{{mode:'index',intersect:false}}}}
        }}
      }});
    </script>
    """

def genera_app_completa(luogo, lat, lon, dati, ore, giorni):
    cur = dati["current"]
    ico_cur, desc_cur = meteo(cur.get("weather_code"))
    
    # Calcola allerta massima
    allerta_max, tipo_max = "verde", "nessuno"
    for _, r in giorni.iterrows():
        livello, tipo = valuta_allerta_giornaliera(r)
        if livello == "rosso":
            allerta_max, tipo_max = "rosso", tipo
            break
        elif livello == "arancione":
            allerta_max, tipo_max = "arancione", tipo
    
    # Banner avviso
    banner_html = ""
    if allerta_max in ["giallo", "arancione", "rosso"]:
        colori_banner = {"giallo": ("#fef3c7", "#d97706", "⚠️"), "arancione": ("#ffedd5", "#ea580c", "🟠"), "rosso": ("#fee2e2", "#dc2626", "🔴")}
        bg, border, icona = colori_banner[allerta_max]
        banner_html = f'<div style="background:{bg};border-left:4px solid {border};padding:16px 20px;margin:12px 0 24px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.08);display:flex;align-items:center;gap:12px;"><span style="font-size:24px;">{icona}</span><div><div style="font-weight:800;color:{border};font-size:14px;">ALLERTA METEO {allerta_max.upper()}</div><div style="color:#64748b;font-size:13px;">Rischio {tipo_max} per {luogo}. Consulta le previsioni e prendi precauzioni.</div></div></div>'
    
    metriche = [("🌡️", "Percepita", numero(cur.get("apparent_temperature"), 1, " °C")), ("💧", "Umidità", numero(cur.get("relative_humidity_2m"), 0, " %")), ("☁️", "Nuvolosità", numero(cur.get("cloud_cover"), 0, " %")), ("💨", "Vento", numero(cur.get("wind_speed_10m"), 0, " km/h")), ("🧭", "Provenienza", direzione(cur.get("wind_direction_10m"))), ("🌬️", "Raffica", numero(cur.get("wind_gusts_10m"), 0, " km/h")), ("🌀", "Pressione", numero(cur.get("pressure_msl"), 1, " hPa"))]
    metriche_html = "".join([f'<div class="cml-metric-card" style="display:flex;align-items:center;gap:14px;min-height:72px;padding:16px 18px;border:1px solid rgba(241,245,249,0.8);border-radius:16px;background:linear-gradient(135deg,rgba(255,255,255,0.9),rgba(248,250,252,0.8));transition:all 0.25s ease;"><div style="display:flex;align-items:center;justify-content:center;width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,#ffffff,#f8fafc);font-size:24px;">{m[0]}</div><div style="display:flex;flex-direction:column;gap:4px;"><div style="color:var(--cml-muted);font-size:11px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;">{m[1]}</div><div style="color:var(--cml-ink);font-size:17px;font-weight:800;">{m[2]}</div></div></div>' for m in metriche])

    etichette = ["OGGI", "DOMANI", "DOPODOMANI"]
    carte_html = []
    for idx, (_, r) in enumerate(giorni.iterrows()):
        tag = etichette[idx] if idx < len(etichette) else "PROSSIMAMENTE"
        cod_effettivo = r.get("weather_code_prevalente", r["weather_code"])
        nubi_effettive = r.get("cloud_cover_diurno", 0)
        ico, desc = meteo(cod_effettivo)
        fase = html.escape(str(r.get("Fase lunare", "🌙 Luna")))
        livello_allerta, tipo_rischio = valuta_allerta_giornaliera(r)
        badge_allerta = badge_allerta_html(livello_allerta, tipo_rischio)
        badge_bg = {"sereno": "linear-gradient(135deg,#ffd700,#ffb347)", "nuvoloso": "linear-gradient(135deg,#b0c4de,#87a3c9)", "pioggia": "linear-gradient(135deg,#4a90e2,#357abd)", "neve": "linear-gradient(135deg,#6c7a89,#5a6573)", "temporale": "linear-gradient(135deg,#8e44ad,#6c3483)"}
        bg_key = "temporale" if cod_effettivo in [95,96,99] else "neve" if cod_effettivo in range(71,87) else "pioggia" if cod_effettivo in range(51,68) else "nuvoloso" if cod_effettivo in [2,3,45,48] else "sereno"
        
        carte_html.append(f"""
        <div class="cml-day-card" style="position:relative;overflow:hidden;padding:28px;border:1px solid rgba(255,255,255,0.4);border-radius:24px;background:rgba(255,255,255,0.85);backdrop-filter:blur(20px);color:var(--cml-ink);box-shadow:0 8px 24px rgba(0,0,0,0.08);transition:all 0.3s ease;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <span style="padding:6px 14px;background:linear-gradient(135deg,var(--cml-primary),var(--cml-primary-dark));border-radius:999px;color:#ffffff;font-size:11px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;">{tag}</span>
            <span style="color:var(--cml-muted);font-size:12px;font-weight:600;">{html.escape(data_it(r["time"]))}</span>
          </div>
          <div style="margin-bottom:16px;">{badge_allerta}</div>
          <div style="display:flex;align-items:center;gap:20px;margin-bottom:24px;">
            <div style="display:flex;align-items:center;justify-content:center;width:72px;height:72px;border-radius:20px;font-size:38px;background:{badge_bg.get(bg_key,badge_bg['sereno'])};box-shadow:0 8px 24px rgba(0,0,0,0.15);">{ico}</div>
            <div style="display:flex;flex-direction:column;gap:6px;">
              <div style="font-size:18px;font-weight:800;line-height:1.3;">{html.escape(desc)}</div>
              <div style="display:inline-flex;padding:6px 12px;border-radius:999px;background:linear-gradient(135deg,rgba(224,231,255,0.9),rgba(199,210,254,0.8));color:#4338ca;font-size:11px;font-weight:700;">{fase}</div>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px;padding:16px;background:linear-gradient(135deg,rgba(248,250,252,0.9),rgba(241,245,249,0.8));border-radius:16px;border:1px solid rgba(226,232,240,0.6);">
            <div style="display:flex;flex-direction:column;gap:6px;align-items:center;"><span style="color:var(--cml-muted);font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">MINIMA</span><span style="font-size:24px;font-weight:900;color:#0284c7;">↓ {numero(r["temperature_2m_min"],1,"°")}</span></div>
            <div style="display:flex;flex-direction:column;gap:6px;align-items:center;"><span style="color:var(--cml-muted);font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">MASSIMA</span><span style="font-size:24px;font-weight:900;color:var(--cml-orange);">↑ {numero(r["temperature_2m_max"],1,"°")}</span></div>
          </div>
          <div style="display:flex;flex-direction:column;gap:12px;margin-bottom:20px;padding-bottom:20px;border-bottom:1px solid rgba(226,232,240,0.6);">
            <div style="display:flex;align-items:center;gap:12px;"><span style="width:28px;height:28px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,rgba(240,249,255,0.9),rgba(224,242,254,0.8));border-radius:8px;font-size:16px;">☁️</span><span style="color:var(--cml-muted);font-size:13px;font-weight:600;flex:1;">Nuvolosità diurna</span><span style="color:var(--cml-ink);font-size:14px;font-weight:800;white-space:nowrap;">{nubi_effettive}%</span></div>
            <div style="display:flex;align-items:center;gap:12px;"><span style="width:28px;height:28px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,rgba(240,249,255,0.9),rgba(224,242,254,0.8));border-radius:8px;font-size:16px;">🌧️</span><span style="color:var(--cml-muted);font-size:13px;font-weight:600;flex:1;">Precipitazione</span><span style="color:var(--cml-ink);font-size:14px;font-weight:800;white-space:nowrap;">{numero(r["precipitation_sum"],1," mm")}</span></div>
            <div style="display:flex;align-items:center;gap:12px;"><span style="width:28px;height:28px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,rgba(240,249,255,0.9),rgba(224,242,254,0.8));border-radius:8px;font-size:16px;">💨</span><span style="color:var(--cml-muted);font-size:13px;font-weight:600;flex:1;">Vento max</span><span style="color:var(--cml-ink);font-size:14px;font-weight:800;white-space:nowrap;">{numero(r["wind_speed_10m_max"],0," km/h")}</span></div>
            <div style="display:flex;align-items:center;gap:12px;"><span style="width:28px;height:28px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,rgba(240,249,255,0.9),rgba(224,242,254,0.8));border-radius:8px;font-size:16px;">🌬️</span><span style="color:var(--cml-muted);font-size:13px;font-weight:600;flex:1;">Raffica max</span><span style="color:var(--cml-ink);font-size:14px;font-weight:800;white-space:nowrap;">{numero(r["wind_gusts_10m_max"],0," km/h")}</span></div>
            <div style="display:flex;align-items:center;gap:12px;"><span style="width:28px;height:28px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,rgba(240,249,255,0.9),rgba(224,242,254,0.8));border-radius:8px;font-size:16px;">🧭</span><span style="color:var(--cml-muted);font-size:13px;font-weight:600;flex:1;">Direzione dom.</span><span style="color:var(--cml-ink);font-size:14px;font-weight:800;white-space:nowrap;">{html.escape(str(r["Da"]))}</span></div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <div style="display:flex;flex-direction:column;align-items:center;gap:6px;padding:12px;background:linear-gradient(135deg,rgba(250,250,250,0.9),rgba(244,246,248,0.8));border-radius:12px;border:1px solid rgba(226,232,240,0.6);"><span style="font-size:20px;">☀️</span><span style="color:var(--cml-muted);font-size:10px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">Alba</span><span style="color:var(--cml-ink);font-size:14px;font-weight:800;">{ora_it(r.get("sunrise"))}</span></div>
            <div style="display:flex;flex-direction:column;align-items:center;gap:6px;padding:12px;background:linear-gradient(135deg,rgba(250,250,250,0.9),rgba(244,246,248,0.8));border-radius:12px;border:1px solid rgba(226,232,240,0.6);"><span style="font-size:20px;">🌇</span><span style="color:var(--cml-muted);font-size:10px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">Tramonto</span><span style="color:var(--cml-ink);font-size:14px;font-weight:800;">{ora_it(r.get("sunset"))}</span></div>
            <div style="display:flex;flex-direction:column;align-items:center;gap:6px;padding:12px;background:linear-gradient(135deg,rgba(250,250,250,0.9),rgba(244,246,248,0.8));border-radius:12px;border:1px solid rgba(226,232,240,0.6);"><span style="font-size:20px;">🌙</span><span style="color:var(--cml-muted);font-size:10px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">Sorge</span><span style="color:var(--cml-ink);font-size:14px;font-weight:800;">{ora_it(r.get("moonrise"))}</span></div>
            <div style="display:flex;flex-direction:column;align-items:center;gap:6px;padding:12px;background:linear-gradient(135deg,rgba(250,250,250,0.9),rgba(244,246,248,0.8));border-radius:12px;border:1px solid rgba(226,232,240,0.6);"><span style="font-size:20px;">🌘</span><span style="color:var(--cml-muted);font-size:10px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">Tramonta</span><span style="color:var(--cml-ink);font-size:14px;font-weight:800;">{ora_it(r.get("moonset"))}</span></div>
          </div>
        </div>
        """)

    # Grafico orario (primo giorno)
    primo_giorno = ore["time"].dt.date.unique()[0]
    ore_primo_giorno = ore.loc[ore["time"].dt.date == primo_giorno]
    grafico_html = genera_grafico_orario(ore_primo_giorno)

    # Tabella oraria
    date_disponibili = sorted(ore["time"].dt.date.unique())
    pulsanti_tab_html, sezioni_tabelle_html = [], []
    for idx, d in enumerate(date_disponibili):
        active_cls = "active" if idx == 0 else ""
        display_style = "display: block;" if idx == 0 else "display: none;"
        data_str = str(d)
        pulsanti_tab_html.append(f'<button class="cml-tab-btn {active_cls}" onclick="mostraGiorno(\'{data_str}\',this)" style="padding:12px 24px;background:rgba(255,255,255,0.9);border:2px solid rgba(226,232,240,0.8);border-radius:14px;font-size:14px;font-weight:700;color:var(--cml-muted);cursor:pointer;transition:all 0.25s ease;white-space:nowrap;">📅 {data_it(d).title()}</button>')
        ore_giorno = ore.loc[ore["time"].dt.date == d]
        righe_tabella = []
        for _, riga in ore_giorno.iterrows():
            riga_bg = "cml-row-sereno" if riga["weather_code"] in [0,1] else "cml-row-nuvoloso" if riga["weather_code"] in [2,3] else "cml-row-pioggia" if riga["weather_code"] in range(51,68) else "cml-row-neve" if riga["weather_code"] in range(71,87) else "cml-row-temporale"
            righe_tabella.append(f'<tr class="{riga_bg}"><td style="height:50px;padding:0 12px;border-bottom:1px solid rgba(241,245,249,0.8);text-align:center;color:var(--cml-primary-dark);font-weight:800;font-size:14px;">{riga["time"].strftime("%H:%M")}</td><td style="text-align:left;"><div style="display:flex;align-items:center;gap:12px;"><span style="display:inline-flex;align-items:center;justify-content:center;flex:0 0 34px;width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#ffffff,#f8fafc);font-size:20px;box-shadow:0 2px 6px rgba(0,0,0,0.08);">{riga["Icona"]}</span><span style="display:block;overflow:hidden;text-overflow:ellipsis;line-height:1.3;font-weight:600;">{riga["Scenario"]}</span></div></td><td style="text-align:right;">{numero(riga["temperature_2m"])}</td><td style="text-align:right;">{numero(riga["apparent_temperature"])}</td><td style="text-align:right;">{numero(riga["precipitation"])}</td><td style="text-align:right;">{numero(riga["wind_speed_10m"],0)}</td><td style="text-align:center;color:var(--cml-muted);font-weight:800;">{riga["Da"]}</td><td style="text-align:right;">{numero(riga["wind_gusts_10m"],0)}</td><td style="text-align:right;">{numero(riga["cloud_cover"],0)}</td><td style="text-align:right;">{numero(riga["relative_humidity_2m"],0)}</td></tr>')
        sezioni_tabelle_html.append(f'<div id="tab-{data_str}" class="cml-day-table-container" style="{display_style}"><div style="width:100%;max-width:100%;overflow-x:auto;border:2px solid rgba(226,232,240,0.8);border-radius:20px;background:rgba(255,255,255,0.95);backdrop-filter:blur(20px);box-shadow:0 8px 32px rgba(0,0,0,0.08);margin-bottom:16px;"><table style="width:100%;min-width:1100px;table-layout:fixed;border-collapse:separate;border-spacing:0;color:var(--cml-ink);font:13px -apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Arial,sans-serif;white-space:nowrap;"><colgroup><col style="width:7%;"><col style="width:22%;"><col style="width:9%;"><col style="width:9%;"><col style="width:9%;"><col style="width:9%;"><col style="width:7%;"><col style="width:10%;"><col style="width:7%;"><col style="width:7%;"></colgroup><thead><tr><th style="height:54px;padding:0 12px;background:linear-gradient(135deg,var(--cml-primary),var(--cml-primary-dark));color:#ffffff;text-align:center;vertical-align:middle;font-size:12px;font-weight:800;letter-spacing:0.5px;line-height:1.2;text-transform:uppercase;position:sticky;top:0;z-index:10;border-top-left-radius:18px;">Ora</th><th style="text-align:left;">Scenario</th><th style="text-align:center;">Temp. °C</th><th style="text-align:center;">Percepita °C</th><th style="text-align:center;">Pioggia mm</th><th style="text-align:center;">Vento km/h</th><th style="text-align:center;">Da</th><th style="text-align:center;">Raffica km/h</th><th style="text-align:center;">Nubi %</th><th style="text-align:center;border-top-right-radius:18px;">Umidità %</th></tr></thead><tbody>{"".join(righe_tabella)}</tbody></table></div></div>')

    # Mappa regionale
    mappa_html = f"""
    <div style="overflow:hidden;border:1px solid rgba(255,255,255,0.3);border-radius:24px;background:rgba(255,255,255,0.9);backdrop-filter:blur(20px);padding:28px;box-shadow:0 8px 32px rgba(0,0,0,0.08);margin-bottom:32px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;flex-wrap:wrap;gap:14px;">
        <div>
          <h2 style="font-size:22px;font-weight:800;color:var(--cml-ink);margin:0;">🗺️ Mappa della Calabria</h2>
          <div style="font-size:12px;color:var(--cml-muted);margin-top:2px;">Clicca su un comune per vedere le previsioni</div>
        </div>
      </div>
      <div id="mappa-calabria" style="width:100%;height:520px;border-radius:16px;border:2px solid rgba(226,232,240,0.8);"></div>
    </div>
    <script>
      var mappaCalabria = L.map('mappa-calabria', {{center:[39.0,16.5],zoom:8,minZoom:7,maxZoom:11,zoomControl:true}});
      L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{attribution:'&copy; OpenStreetMap contributors',maxZoom:18}}).addTo(mappaCalabria);
      var comuniCalabria = {json.dumps(COMUNI)};
      var markerCalabria = {{}};
      for (var nome in comuniCalabria) {{
        var coords = comuniCalabria[nome];
        var marker = L.marker(coords,{{title:nome}}).addTo(mappaCalabria);
        marker.on('click',function(){{
          var nomeComune = this.options.title;
          var inputComune = document.querySelector('input[placeholder*="Località"]');
          if (inputComune) {{ inputComune.value = nomeComune; document.querySelector('button[type="submit"]').click(); }}
        }});
        markerCalabria[nome] = marker;
      }}
      var comuneAttuale = "{luogo}";
      if (markerCalabria[comuneAttuale]) {{
        var coords = comuniCalabria[comuneAttuale];
        markerCalabria[comuneAttuale].setIcon(L.divIcon({{className:'cml-marker-attivo',html:'<div style="width:24px;height:24px;background:#ef4444;border:3px solid white;border-radius:50%;box-shadow:0 0 0 3px rgba(239,68,68,0.5);"></div>',iconSize:[24,24],iconAnchor:[12,12]}}));
        mappaCalabria.setView(coords,10);
      }}
    </script>
    """

    # Ricerca autocomplete
    ricerca_html = """
    <script>
      var inputComune = document.querySelector('input[placeholder*="Località"]');
      if (inputComune) {
        var suggerimenti = document.createElement('div');
        suggerimenti.id = 'suggerimenti-comuni';
        suggerimenti.style.cssText = 'position:absolute;background:white;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.1);max-height:300px;overflow-y:auto;z-index:1000;display:none;width:100%;';
        inputComune.style.position = 'relative';
        inputComune.parentNode.insertBefore(suggerimenti, inputComune.nextSibling);
        var comuniLista = Object.keys({json.dumps(COMUNI)});
        inputComune.addEventListener('input',function(){
          var testo = this.value.toLowerCase();
          if (testo.length < 2) {{ suggerimenti.style.display = 'none'; return; }}
          var filtrati = comuniLista.filter(function(c){return c.toLowerCase().includes(testo);}).slice(0,8);
          if (filtrati.length > 0) {{
            suggerimenti.innerHTML = filtrati.map(function(c){return '<div style="padding:10px 14px;cursor:pointer;border-bottom:1px solid #f1f5f9;" onmouseover="this.style.background=\'#f0f9ff\'" onmouseout="this.style.background=\'white\'" onclick="document.querySelector(\'input[placeholder*=\\\"Località\\\"]\').value=\\'' + c + '\\';this.parentNode.style.display=\'none\';document.querySelector(\'button[type=\\\"submit\\\"]\').click();">' + c + '</div>';}).join('');
            suggerimenti.style.display = 'block';
          }} else {{ suggerimenti.style.display = 'none'; }}
        });
        document.addEventListener('click',function(e){if(!inputComune.contains(e.target)){suggerimenti.style.display='none';}});
      }
    </script>
    """

    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root{{--cml-ink:#0f172a;--cml-muted:#64748b;--cml-line:#e2e8f0;--cml-primary:#0ea5e9;--cml-primary-dark:#0284c7;--cml-orange:#f97316;--cml-blue:#3b82f6;--cml-green:#10b981;--cml-purple:#8b5cf6;--cml-red:#ef4444;--cml-yellow:#f59e0b}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;color:var(--cml-ink);background:linear-gradient(135deg,#f0f9ff 0%,#e0f2fe 50%,#f0f9ff 100%);padding:8px;line-height:1.5;min-height:100vh}}
.cml-hero{{position:relative;overflow:hidden;border-radius:32px;padding:48px 48px 40px;margin:12px 0 24px;color:#fff;background:rgba(255,255,255,0.15);backdrop-filter:blur(20px);box-shadow:0 20px 60px rgba(0,0,0,0.15);border:1px solid rgba(255,255,255,0.2)}}
.cml-brand{{display:inline-flex;align-items:center;gap:12px;padding:8px 16px;background:rgba(255,255,255,0.2);backdrop-filter:blur(8px);border-radius:999px;color:#ffffff;font-size:11px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;border:1px solid rgba(255,255,255,0.3)}}
.cml-brand-mark{{width:12px;height:12px;border-radius:50%;background:linear-gradient(135deg,#fde047,#fbbf24);box-shadow:0 0 0 6px rgba(253,224,71,0.2),0 0 24px rgba(253,224,71,0.8)}}
.cml-hero h1{{margin:20px 0 12px;font-size:44px;font-weight:800;letter-spacing:-1.5px;line-height:1.1;background:linear-gradient(135deg,#ffffff,#e0f2fe);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
.cml-hero p{{max-width:720px;margin:0;color:rgba(255,255,255,0.9);font-size:15px;line-height:1.7}}
.cml-current{{overflow:hidden;margin:24px 0 32px;border:1px solid rgba(255,255,255,0.3);border-radius:24px;background:rgba(255,255,255,0.85);backdrop-filter:blur(20px);box-shadow:0 8px 32px rgba(0,0,0,0.1)}}
.cml-current-main{{display:flex;align-items:center;justify-content:space-between;gap:32px;padding:36px 40px;background:linear-gradient(135deg,rgba(255,255,255,0.9),rgba(240,249,255,0.8));border-bottom:1px solid rgba(226,232,240,0.5)}}
.cml-kicker{{display:inline-flex;align-items:center;gap:8px;padding:6px 14px;background:rgba(14,165,233,0.15);border-radius:999px;color:var(--cml-primary-dark);font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:14px}}
.cml-place-block h2{{margin:12px 0 10px;color:var(--cml-ink);font-size:34px;font-weight:800}}
.cml-condition{{display:inline-flex;align-items:center;gap:10px;padding:8px 16px;background:rgba(255,255,255,0.9);border-radius:12px;color:var(--cml-muted);font-size:17px;font-weight:600}}
.cml-temperature{{display:flex;align-items:flex-start;color:var(--cml-orange);font-weight:900;line-height:0.9}}
.cml-temperature span{{font-size:86px;letter-spacing:-8px}}
.cml-temperature small{{margin:12px 0 0 8px;font-size:28px;color:var(--cml-orange)}}
.cml-metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;padding:24px 32px}}
.cml-metric-card{{transition:all 0.25s ease}}
.cml-metric-card:hover{{background:linear-gradient(135deg,rgba(240,249,255,0.95),rgba(224,242,254,0.9));border-color:var(--cml-primary);transform:translateY(-2px);box-shadow:0 8px 20px rgba(14,165,233,0.2)}}
.cml-metric-lbl{{color:var(--cml-muted);font-size:11px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase}}
.cml-metric-val{{color:var(--cml-ink);font-size:17px;font-weight:800}}
.cml-current-footer{{display:flex;flex-wrap:wrap;gap:12px 28px;padding:16px 32px;border-top:1px solid rgba(226,232,240,0.6);background:rgba(250,250,250,0.6);color:var(--cml-muted);font-size:12px}}
.cml-current-footer b{{color:var(--cml-ink);font-weight:700}}
.cml-radar-box{{overflow:hidden;border:1px solid rgba(255,255,255,0.3);border-radius:24px;background:rgba(255,255,255,0.9);backdrop-filter:blur(20px);padding:28px;box-shadow:0 8px 32px rgba(0,0,0,0.08);margin-bottom:32px}}
.cml-radar-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;flex-wrap:wrap;gap:14px}}
.cml-radar-header h2{{font-size:22px;font-weight:800;color:var(--cml-ink);margin:0}}
.cml-radar-btn{{display:inline-flex;align-items:center;gap:8px;padding:10px 20px;background:linear-gradient(135deg,var(--cml-primary),var(--cml-primary-dark));border:none;border-radius:12px;font-size:13px;font-weight:700;color:#ffffff;cursor:pointer;box-shadow:0 4px 12px rgba(14,165,233,0.3)}}
#radar-map{{width:100%;height:520px;border-radius:16px;border:2px solid rgba(226,232,240,0.8)}}
.cml-radar-legend{{display:flex;justify-content:space-between;align-items:center;margin-top:16px;padding:14px 18px;background:linear-gradient(135deg,rgba(240,249,255,0.9),rgba(224,242,254,0.8));border-radius:12px;font-size:12px;color:var(--cml-muted);gap:12px;border:1px solid rgba(186,230,253,0.6)}}
.cml-section-title{{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin:40px 0 20px}}
.cml-section-title span{{color:var(--cml-primary);font-size:11px;font-weight:800;letter-spacing:2px;text-transform:uppercase}}
.cml-section-title h2{{margin:8px 0 6px;color:var(--cml-ink);font-size:28px;font-weight:800}}
.cml-section-title p{{margin:0;color:var(--cml-muted);font-size:14px}}
.cml-pill{{padding:8px 16px;border-radius:999px;background:linear-gradient(135deg,rgba(224,242,254,0.9),rgba(186,230,253,0.8));color:var(--cml-primary-dark);font-size:12px;font-weight:800;border:1px solid rgba(186,230,253,0.6)}}
.cml-days-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px;margin-bottom:28px}}
.cml-day-card{{transition:all 0.3s ease}}
.cml-day-card:hover{{transform:translateY(-4px);box-shadow:0 16px 40px rgba(0,0,0,0.15)}}
.cml-alert-badge{{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:12px;border:2px solid rgba(255,255,255,0.3);font-size:12px;font-weight:700;box-shadow:0 4px 12px rgba(0,0,0,0.15)}}
.cml-hour-header{{position:relative;overflow:hidden;margin-top:16px;padding:32px 32px;border-radius:24px;color:#fff;background:linear-gradient(135deg,rgba(30,58,95,0.95),rgba(59,89,152,0.9) 55%,rgba(74,105,168,0.85));backdrop-filter:blur(10px);box-shadow:0 12px 36px rgba(59,89,152,0.3)}}
.cml-hour-header span{{color:rgba(186,230,253,0.9);font-size:11px;font-weight:800;letter-spacing:2px;text-transform:uppercase}}
.cml-hour-header h2{{margin:10px 0 8px;color:#ffffff;font-size:28px;font-weight:800}}
.cml-hour-header p{{margin:0;color:rgba(219,234,255,0.9);font-size:14px;line-height:1.6}}
.cml-tabs-bar{{display:flex;gap:12px;margin:20px 0 16px;overflow-x:auto;padding-bottom:6px}}
.cml-tab-btn{{padding:12px 24px;background:rgba(255,255,255,0.9);border:2px solid rgba(226,232,240,0.8);border-radius:14px;font-size:14px;font-weight:700;color:var(--cml-muted);cursor:pointer;transition:all 0.25s ease;white-space:nowrap}}
.cml-tab-btn:hover{{background:rgba(240,249,255,0.95);border-color:var(--cml-primary);color:var(--cml-primary-dark);transform:translateY(-2px)}}
.cml-tab-btn.active{{background:linear-gradient(135deg,var(--cml-primary),var(--cml-primary-dark));color:#ffffff;border-color:var(--cml-primary);box-shadow:0 6px 16px rgba(14,165,233,0.35);transform:translateY(-2px)}}
.cml-table-wrap{{width:100%;max-width:100%;overflow-x:auto;border:2px solid rgba(226,232,240,0.8);border-radius:20px;background:rgba(255,255,255,0.95);backdrop-filter:blur(20px);box-shadow:0 8px 32px rgba(0,0,0,0.08);margin-bottom:16px}}
.cml-table{{width:100%;min-width:1100px;table-layout:fixed;border-collapse:separate;border-spacing:0;color:var(--cml-ink);font:13px -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;white-space:nowrap}}
.cml-table th{{height:54px;padding:0 12px;background:linear-gradient(135deg,var(--cml-primary),var(--cml-primary-dark));color:#ffffff;text-align:center;vertical-align:middle;font-size:12px;font-weight:800;letter-spacing:0.5px;line-height:1.2;text-transform:uppercase;position:sticky;top:0;z-index:10}}
.cml-table th:first-child{{border-top-left-radius:18px}}
.cml-table th:last-child{{border-top-right-radius:18px}}
.cml-table td{{height:50px;padding:0 12px;border-bottom:1px solid rgba(241,245,249,0.8);text-align:center;vertical-align:middle;line-height:1.3;font-variant-numeric:tabular-nums;transition:all 0.15s ease}}
.cml-table td:first-child{{color:var(--cml-primary-dark);font-weight:800;font-size:14px}}
.cml-table tbody tr:nth-child(even){{background:rgba(250,250,250,0.6)}}
.cml-table tbody tr:hover{{background:linear-gradient(135deg,rgba(240,249,255,0.95),rgba(224,242,254,0.9));transform:scale(1.005)}}
.cml-table tbody tr:last-child td{{border-bottom:0}}
.cml-table tr.cml-row-sereno:hover{{background:linear-gradient(135deg,rgba(254,243,199,0.9),rgba(253,230,138,0.85))!important}}
.cml-table tr.cml-row-nuvoloso:hover{{background:linear-gradient(135deg,rgba(224,231,255,0.9),rgba(199,210,254,0.85))!important}}
.cml-table tr.cml-row-pioggia:hover{{background:linear-gradient(135deg,rgba(219,234,255,0.9),rgba(191,219,254,0.85))!important}}
.cml-table tr.cml-row-neve:hover{{background:linear-gradient(135deg,rgba(241,245,249,0.9),rgba(226,232,240,0.85))!important}}
.cml-table tr.cml-row-temporale:hover{{background:linear-gradient(135deg,rgba(233,213,255,0.9),rgba(216,180,254,0.85))!important}}
.cml-table tr.cml-night-row{{background:linear-gradient(90deg,rgba(15,23,42,0.95),rgba(30,41,59,0.9))!important}}
.cml-table tr.cml-night-row td{{color:rgba(226,232,240,0.95)!important;border-bottom-color:rgba(51,65,85,0.8)!important}}
.cml-table tr.cml-night-row .cml-table-icon{{background:linear-gradient(135deg,rgba(30,41,59,0.9),rgba(15,23,42,0.95));color:#fde68a;font-size:22px;box-shadow:0 2px 8px rgba(253,230,138,0.3)}}
.cml-table tr.cml-night-row .cml-table-scenario{{color:#fde68a!important;font-weight:800}}
.cml-table tr.cml-night-row td:first-child{{color:rgba(125,211,252,0.95)!important}}
.cml-table tr.cml-night-row td:nth-child(7){{color:rgba(186,230,253,0.95)!important}}
.cml-note{{margin:20px 0 24px;padding:18px 22px;border:2px solid rgba(253,230,138,0.8);border-left:5px solid var(--cml-yellow);border-radius:16px;background:linear-gradient(135deg,rgba(254,243,199,0.9),rgba(253,230,138,0.85));backdrop-filter:blur(10px);color:rgba(120,52,15,0.9);font-size:13px;line-height:1.7}}
.cml-note b{{color:rgba(146,64,14,0.95);font-weight:800}}
</style>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
function mostraGiorno(dataId,btn){{var tabs=document.getElementsByClassName("cml-day-table-container");for(var i=0;i<tabs.length;i++){{tabs[i].style.display="none"}}var buttons=document.getElementsByClassName("cml-tab-btn");for(var i=0;i<buttons.length;i++){{buttons[i].classList.remove("active")}}document.getElementById("tab-"+dataId).style.display="block";btn.classList.add("active")}}
</script>
</head>
<body>

<div class="cml-hero">
  <div class="cml-brand"><span class="cml-brand-mark"></span>CALABRIA · METEOROLOGIA LOCALE</div>
  <h1>Calabria Meteo Lab</h1>
  <p>Previsione puntuale ad alta risoluzione per la Calabria. Cerca una località e leggi subito temperatura, cielo, vento, precipitazioni e sviluppo delle prossime 72 ore.</p>
</div>

{banner_html}

<div class="cml-current">
  <div class="cml-current-main">
    <div class="cml-place-block">
      <div class="cml-kicker"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#10b981;margin-right:7px;"></span>ICON-2I · PREVISIONE PUNTUALE</div>
      <h2>📍 {html.escape(luogo)}</h2>
      <div class="cml-condition">{ico_cur} {html.escape(desc_cur)}</div>
    </div>
    <div class="cml-temperature"><span>{numero(cur.get("temperature_2m"),1,"")}</span><small>°C</small></div>
  </div>
  <div class="cml-metrics">{metriche_html}</div>
  <div class="cml-current-footer">
    <span>◷ Valido alle <b>{html.escape(str(cur.get("time","—")))}</b></span>
    <span>◉ Fuso <b>Europe/Rome</b></span>
    <span>◌ Fonte <b>ItaliaMeteo–ARPAE</b></span>
  </div>
</div>

<div class="cml-radar-box">
  <div class="cml-radar-header">
    <div><h2>📡 Radar Precipitazioni Live</h2><div style="font-size:12px;color:var(--cml-muted);margin-top:2px;">Mosaico Nazionale DPC · Riflettività radar in tempo reale</div></div>
    <div style="display:flex;gap:10px;align-items:center;"><button class="cml-radar-btn" id="btn-play" onclick="togglePlay()">⏸️ Pausa</button></div>
  </div>
  <div id="radar-map"></div>
  <div class="cml-radar-legend">
    <div>⚡ <b>Rete Radar:</b> Dipartimento Protezione Civile (DPC)</div>
    <div>Scansione: <span id="radar-timestamp" style="font-weight:800;color:var(--cml-primary-dark);font-size:13px;">Caricamento...</span></div>
  </div>
</div>

{mappa_html}

<div class="cml-section-title">
  <div><span>ORIZZONTE PREVISIONALE</span><h2>📅 I prossimi tre giorni</h2><p>Condizione prevalente diurna, nuvolosità, temperature, precipitazioni, vento e ciclo lunare.</p></div>
  <div class="cml-pill">72 ore</div>
</div>
<div class="cml-days-grid">{''.join(carte_html)}</div>
<div class="cml-note">ℹ️ Le schede mostrano la <b>condizione prevalente e la nuvolosità media diurna</b> (alba-tramonto). Temperature, vento e pioggia sono valori estremi/cumulati sulle 24h. I livelli di allerta sono calcolati in base alle soglie della Protezione Civile.</div>

<div class="cml-hour-header">
  <span>DETTAGLIO ORARIO</span>
  <h2>🕒 Previsione ora per ora</h2>
  <p>Seleziona un giorno per vedere l'evoluzione oraria del modello ICON-2I.</p>
</div>

{grafico_html}

<div class="cml-tabs-bar">{''.join(pulsanti_tab_html)}</div>
{''.join(sezioni_tabelle_html)}

<div class="cml-note">ℹ️ <b>Modello ICON-2I:</b> Previsione deterministica ad alta risoluzione (2.2 km) di ItaliaMeteo–ARPAE. Aggiornata 2× al giorno (00/12 UTC), orizzonte 72h.</div>

<script>
var lat={lat};var lon={lon};
var map=L.map('radar-map',{{center:[lat,lon],zoom:8,minZoom:5,maxZoom:18,zoomControl:true}});
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{attribution:'&copy; OpenStreetMap contributors',maxZoom:18}}).addTo(map);
var redPinIcon=L.divIcon({{className:'cml-pin-wrapper',html:'<div style="width:20px;height:20px;background:linear-gradient(135deg,#ef4444,#dc2626);border:3px solid #ffffff;border-radius:50%;box-shadow:0 0 0 3px rgba(239,68,68,0.4);"></div>',iconSize:[20,20],iconAnchor:[10,10]}});
L.marker([lat,lon],{{icon:redPinIcon,title:'{html.escape(luogo)}'}}).addTo(map);
var timestamps=[];var radarLayers={{}};var currentFrame=0;var isPlaying=true;var animationTimer=null;
fetch('https://api.rainviewer.com/public/weather-maps.json').then(res=>res.json()).then(apiData=>{{var frames=apiData.radar.past;timestamps=frames.map(f=>f.time);frames.forEach(f=>{{var layer=L.tileLayer('https://tilecache.rainviewer.com'+f.path+'/256/{{z}}/{{x}}/{{y}}/2/1_1.png',{{opacity:0,zIndex:100,maxNativeZoom:6,maxZoom:18}});layer.addTo(map);radarLayers[f.time]=layer}});currentFrame=timestamps.length-1;showFrame(currentFrame);startAnimation()}});
function showFrame(index){{if(timestamps.length===0)return;if(radarLayers[timestamps[currentFrame]]){{radarLayers[timestamps[currentFrame]].setOpacity(0)}}currentFrame=index;var time=timestamps[currentFrame];if(radarLayers[time]){{radarLayers[time].setOpacity(0.75)}}var date=new Date(time*1000);var ore=('0'+date.getHours()).slice(-2);var min=('0'+date.getMinutes()).slice(-2);document.getElementById('radar-timestamp').innerText=ore+':'+min+' (Ora Locale)'}}
function startAnimation(){{if(animationTimer)clearInterval(animationTimer);animationTimer=setInterval(()=>{{var next=(currentFrame+1)%timestamps.length;showFrame(next)}},750)}}
function togglePlay(){{var btn=document.getElementById('btn-play');if(isPlaying){{clearInterval(animationTimer);btn.innerText='▶️ Play';isPlaying=false}}else{{startAnimation();btn.innerText='⏸️ Pausa';isPlaying=true}}}}
</script>

{ricerca_html}

</body>
</html>"""

    return html_content

st.markdown("### 🔍 Seleziona Località Calabrese")

with st.form("search_form", clear_on_submit=False):
    col_in, col_btn = st.columns([4, 1])
    with col_in:
        testo_citta = st.text_input("Località", value="Cosenza", placeholder="Scrivi es. Cosenza, Tropea, Soverato, Reggio Calabria, Catanzaro...", label_visibility="collapsed")
    with col_btn:
        invia = st.form_submit_button("Aggiorna Previsione", use_container_width=True, type="primary")

try:
    luogo, lat, lon = risolvi_citta(testo_citta)
    with st.spinner(f"Elaborazione modello ICON-2I e Radar Live per {luogo}..."):
        dati_meteo = scarica_previsione(lat, lon)
        df_ore, df_giorni = prepara(dati_meteo)
    doc_html = genera_app_completa(luogo, lat, lon, dati_meteo, df_ore, df_giorni)
    components.html(doc_html, height=3200, scrolling=True)
except Exception as errore:
    st.error(f"{errore}")
