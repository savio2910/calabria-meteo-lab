# =====================================================================
# CALABRIA METEO LAB — CON NUVOLOSITÀ DIURNA NEI 3 GIORNI E RADAR DPC
# ICON-2I VIA OPEN-METEO + RADAR DOPPLER LIVE INTERATTIVO (LEAFLET)
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

st.markdown("""
<style>
  #MainMenu {visibility: hidden;}
  header {visibility: hidden;}
  footer {visibility: hidden;}
  .block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 1300px !important;
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

def calcola_dati_diurni(ore_giorno, alba, tramonto):
    """
    Calcola per la giornata:
    1. Il codice meteo prevalente diurno.
    2. La percentuale di nuvolosità media diurna (dall'alba al tramonto).
    """
    if ore_giorno.empty:
        return 0, 0
    
    if alba is not None and tramonto is not None:
        alba_t = pd.Timestamp(alba)
        tramonto_t = pd.Timestamp(tramonto)
        ore_diurne = ore_giorno.loc[(ore_giorno["time"] >= alba_t) & (ore_giorno["time"] <= tramonto_t)]
    else:
        ore_diurne = ore_giorno.loc[(ore_giorno["time"].dt.hour >= 7) & (ore_giorno["time"].dt.hour <= 20)]

    df_target = ore_diurne if not ore_diurne.empty else ore_giorno
    
    # Nuvolosità media diurna
    nubi_media = round(df_target["cloud_cover"].mean()) if "cloud_cover" in df_target else 0

    # Condizione meteo prevalente
    codici_severi = [99, 96, 95, 82, 81, 80, 65, 63, 61, 55, 53, 51]
    for c_sev in codici_severi:
        if (df_target["weather_code"] == c_sev).sum() >= 2:
            return c_sev, nubi_media

    cod_prev = df_target["weather_code"].mode()[0] if not df_target.empty else 0
    return cod_prev, nubi_media

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
        geocoder = Nominatim(user_agent="calabria_meteo_lab_v11", timeout=12)
        risposta = geocoder.geocode(
            f"{nome}, Italia",
            exactly_one=True,
            addressdetails=True,
            timeout=12,
        )
    except (GeocoderServiceError, GeocoderTimedOut) as exc:
        raise RuntimeError("Servizio di geolocalizzazione momentaneamente non disponibile. Riprova tra poco.") from exc

    if risposta is None:
        raise ValueError(f"Località «{nome}» non trovata. Inserisci un comune calabrese.")

    indirizzo = risposta.raw.get("address", {})
    regione = str(indirizzo.get("state", "") or indirizzo.get("region", "")).casefold()
    lat, lon = float(risposta.latitude), float(risposta.longitude)

    is_calabria = "calabria" in regione
    in_bounds = (37.75 <= lat <= 40.15) and (15.60 <= lon <= 17.25)

    if not (is_calabria and in_bounds):
        reg_txt = f" ({regione.title()})" if regione else ""
        raise ValueError(f"❌ «{nome}»{reg_txt} non è in Calabria. Questa applicazione funziona esclusivamente per le località calabresi.")

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
    ore_raw = pd.DataFrame(dati["hourly"])
    giorni = pd.DataFrame(dati["daily"])

    ore_raw["time"] = pd.to_datetime(ore_raw["time"])
    giorni["time"] = pd.to_datetime(giorni["time"])

    codici_prevalenti = []
    nuvolosita_giornaliera = []

    for _, g in giorni.iterrows():
        g_data = g["time"].date()
        ore_del_giorno = ore_raw.loc[ore_raw["time"].dt.date == g_data]
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
# COSTRUZIONE DOCUMENTO MONOLITICO
# =====================================================================
def genera_app_completa(luogo, lat, lon, dati, ore, giorni):
    cur = dati["current"]
    ico_cur, desc_cur = meteo(cur.get("weather_code"))

    metriche = [
        ("🌡️", "Percepita", numero(cur.get("apparent_temperature"), 1, " °C")),
        ("💧", "Umidità", numero(cur.get("relative_humidity_2m"), 0, " %")),
        ("☁️", "Nuvolosità", numero(cur.get("cloud_cover"), 0, " %")),
        ("💨", "Vento", numero(cur.get("wind_speed_10m"), 0, " km/h")),
        ("🧭", "Provenienza", direzione(cur.get("wind_direction_10m"))),
        ("🌬️", "Raffica", numero(cur.get("wind_gusts_10m"), 0, " km/h")),
        ("🌀", "Pressione", numero(cur.get("pressure_msl"), 1, " hPa")),
    ]
    metriche_html = "".join([
        f'<div class="cml-metric"><div class="cml-metric-icon">{m[0]}</div><div><div class="cml-metric-lbl">{m[1]}</div><div class="cml-metric-val">{m[2]}</div></div></div>'
        for m in metriche
    ])

    etichette = ["OGGI", "DOMANI", "DOPODOMANI"]
    carte_html = []
    for idx, (_, r) in enumerate(giorni.iterrows()):
        tag = etichette[idx] if idx < len(etichette) else "PROSSIMAMENTE"
        
        cod_effettivo = r.get("weather_code_prevalente", r["weather_code"])
        nubi_effettive = r.get("cloud_cover_diurno", 0)
        ico, desc = meteo(cod_effettivo)
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
          <div class="cml-day-row"><span>☁️ Nuvolosità diurna</span><b>{nubi_effettive}%</b></div>
          <div class="cml-day-row"><span>🌧️ Precipitazione</span><b>{numero(r["precipitation_sum"], 1, " mm")}</b></div>
          <div class="cml-day-row"><span>💨 Vento max</span><b>{numero(r["wind_speed_10m_max"], 0, " km/h")}</b></div>
          <div class="cml-day-row"><span>🌬️ Raffica max</span><b>{numero(r["wind_gusts_10m_max"], 0, " km/h")}</b></div>
          <div class="cml-day-row"><span>🧭 Direzione dom.</span><b>{html.escape(str(r["Da"]))}</b></div>
          <div class="cml-astro-grid">
            <div><span>☀️ Alba</span><b>{ora_it(r.get("sunrise"))}</b></div>
            <div><span>🌇 Tramonto</span><b>{ora_it(r.get("sunset"))}</b></div>
            <div><span>🌙 Sorge</span><b>{ora_it(r.get("moonrise"))}</b></div>
            <div><span>🌘 Tramonta</span><b>{ora_it(r.get("moonset"))}</b></div>
          </div>
        </div>
        """)

    date_disponibili = sorted(ore["time"].dt.date.unique())
    pulsanti_tab_html = []
    sezioni_tabelle_html = []

    for idx, d in enumerate(date_disponibili):
        active_cls = "active" if idx == 0 else ""
        display_style = "display: block;" if idx == 0 else "display: none;"
        data_str = str(d)
        
        pulsanti_tab_html.append(f"""
        <button class="cml-tab-btn {active_cls}" onclick="mostraGiorno('{data_str}', this)">
          📅 {data_it(d).title()}
        </button>
        """)

        ore_giorno = ore.loc[ore["time"].dt.date == d]
        righe_tabella = []
        for _, riga in ore_giorno.iterrows():
            is_notte = bool(riga.get("Notte", False))
            classe_riga = "cml-night-row" if is_notte else ""
            
            righe_tabella.append(f"""
            <tr class="{classe_riga}">
              <td>{riga["time"].strftime("%H:%M")}</td>
              <td>
                <span class="cml-table-condition">
                  <span class="cml-table-icon">{riga["Icona"]}</span>
                  <span class="cml-table-scenario">{riga["Scenario"]}</span>
                </span>
              </td>
              <td>{numero(riga["temperature_2m"])}</td>
              <td>{numero(riga["apparent_temperature"])}</td>
              <td>{numero(riga["precipitation"])}</td>
              <td>{numero(riga["wind_speed_10m"], 0)}</td>
              <td>{riga["Da"]}</td>
              <td>{numero(riga["wind_gusts_10m"], 0)}</td>
              <td>{numero(riga["cloud_cover"], 0)}</td>
              <td>{numero(riga["relative_humidity_2m"], 0)}</td>
            </tr>
            """)

        sezioni_tabelle_html.append(f"""
        <div id="tab-{data_str}" class="cml-day-table-container" style="{display_style}">
          <div class="cml-table-wrap">
            <table class="cml-table">
              <colgroup>
                <col class="col-ora">
                <col class="col-scenario">
                <col class="col-temp">
                <col class="col-percepita">
                <col class="col-pioggia">
                <col class="col-vento">
                <col class="col-direzione">
                <col class="col-raffica">
                <col class="col-nubi">
                <col class="col-umidita">
              </colgroup>
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
        """)

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
:root {{
  --cml-ink: #102b3b;
  --cml-muted: #607987;
  --cml-line: #dcebef;
  --cml-orange: #ed8750;
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: Arial, sans-serif;
  color: var(--cml-ink);
  background: transparent;
  padding: 4px;
}}

/* HERO */
.cml-hero {{
  position: relative;
  overflow: hidden;
  border-radius: 28px;
  padding: 38px 40px;
  margin: 8px 0 18px;
  color: #fff;
  background: radial-gradient(circle at 83% 16%, rgba(117,241,244,.4), transparent 23%),
              radial-gradient(circle at 4% 115%, rgba(244,177,86,.22), transparent 30%),
              linear-gradient(125deg, #061b33 0%, #07566f 53%, #13aab2 100%);
  box-shadow: 0 18px 44px rgba(5,57,78,.28);
}}
.cml-hero:before {{
  content: "";
  position: absolute;
  right: -74px;
  top: -122px;
  width: 310px;
  height: 310px;
  border: 38px solid rgba(255,255,255,.09);
  border-radius: 50%;
}}
.cml-brand {{
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #bceff0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2.3px;
}}
.cml-brand-mark {{
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #ffd06b;
  box-shadow: 0 0 0 5px rgba(255,208,107,.18), 0 0 17px rgba(255,208,107,.8);
}}
.cml-hero h1 {{ position: relative; margin: 15px 0 9px; font-size: 38px; letter-spacing: -1.2px; color: #fff; font-weight: bold; }}
.cml-hero p {{ position: relative; max-width: 760px; margin: 0; color: #e1f7f8; font-size: 14px; line-height: 1.7; }}

/* PANNELLO ATTUALE */
.cml-current {{
  overflow: hidden;
  margin: 18px 0 30px;
  border: 1px solid var(--cml-line);
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 12px 32px rgba(18,71,89,.11);
}}
.cml-current-main {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 30px 32px 25px;
  background: radial-gradient(circle at 91% 29%, rgba(255,207,105,.27), transparent 23%),
              linear-gradient(110deg, #fff, #effbfd);
}}
.cml-kicker {{ color: #078195; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; }}
.cml-live-dot {{
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 7px;
  border-radius: 50%;
  background: #19b7a0;
  box-shadow: 0 0 0 4px #d7f7ef, 0 0 12px rgba(25,183,160,.7);
}}
.cml-place-block h2 {{ margin: 10px 0 8px; color: var(--cml-ink); font-size: 30px; letter-spacing: -.7px; }}
.cml-condition {{ color: #476572; font-size: 18px; }}
.cml-temperature {{
  display: flex;
  align-items: flex-start;
  color: var(--cml-orange);
  font-weight: 800;
  line-height: .9;
  white-space: nowrap;
}}
.cml-temperature span {{ font-size: 72px; letter-spacing: -6px; }}
.cml-temperature small {{ margin: 9px 0 0 6px; font-size: 24px; }}

.cml-metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  padding: 18px 24px;
}}
.cml-metric {{
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 64px;
  padding: 10px 12px;
  border: 1px solid #e1edf1;
  border-radius: 14px;
  background: #f2f9fa;
}}
.cml-metric-icon {{ width: 27px; text-align: center; font-size: 21px; }}
.cml-metric-lbl {{ margin-bottom: 4px; color: var(--cml-muted); font-size: 11px; }}
.cml-metric-val {{ color: var(--cml-ink); font-size: 15px; font-weight: 700; }}

.cml-current-footer {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px 22px;
  padding: 12px 27px;
  border-top: 1px solid #e3edf1;
  color: #607985;
  font-size: 12px;
}}
.cml-current-footer b {{ color: #345967; }}

/* RADAR LIVE PROTEZIONE CIVILE */
.cml-radar-box {{
  border: 1px solid var(--cml-line);
  border-radius: 22px;
  background: #ffffff;
  padding: 24px;
  box-shadow: 0 10px 30px rgba(18,71,89,.08);
  margin-bottom: 30px;
}}
.cml-radar-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 10px;
}}
.cml-radar-header h2 {{ font-size: 24px; font-weight: 800; color: var(--cml-ink); margin: 0; }}
.cml-radar-controls {{
  display: flex;
  gap: 8px;
  align-items: center;
}}
.cml-radar-btn {{
  background: #0b687c;
  border: 1px solid #0b687c;
  border-radius: 10px;
  padding: 8px 16px;
  font-size: 12px;
  font-weight: 700;
  color: #ffffff;
  cursor: pointer;
  box-shadow: 0 4px 10px rgba(11,104,124,0.2);
}}
#radar-map {{
  width: 100%;
  height: 480px;
  border-radius: 16px;
  border: 1px solid #dcebef;
  z-index: 1;
}}
.cml-radar-legend {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding: 10px 14px;
  background: #f4f9fa;
  border-radius: 10px;
  font-size: 12px;
  color: #607987;
  flex-wrap: wrap;
  gap: 10px;
}}
.cml-radar-time {{ font-weight: 800; color: #087b8e; font-size: 13px; }}

/* PIN RADAR ROSSO TIPO GOOGLE MAPS */
.cml-map-pin {{
  width: 18px;
  height: 18px;
  background: #e63946;
  border: 3px solid #ffffff;
  border-radius: 50%;
  box-shadow: 0 0 0 2px rgba(230,57,70,0.5), 0 3px 8px rgba(0,0,0,0.4);
}}

/* 3 GIORNI */
.cml-section-title {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin: 0 0 16px;
}}
.cml-section-title span {{ color: #1592a2; font-size: 10px; font-weight: 700; letter-spacing: 1.8px; text-transform: uppercase; }}
.cml-section-title h2 {{ margin: 7px 0 5px; color: var(--cml-ink); font-size: 25px; letter-spacing: -.5px; }}
.cml-section-title p {{ margin: 0; color: var(--cml-muted); font-size: 13px; }}
.cml-pill {{ padding: 8px 13px; border-radius: 999px; background: #e7f6f8; color: #087a8c; font-size: 12px; font-weight: 700; white-space: nowrap; }}

.cml-days-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(245px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}}
.cml-day-card {{
  position: relative;
  overflow: hidden;
  padding: 20px;
  border: 1px solid var(--cml-line);
  border-radius: 21px;
  background: linear-gradient(145deg, #fff 0%, #f5fbfc 58%, #e9f7fa 100%);
  color: var(--cml-ink);
  box-shadow: 0 8px 23px rgba(22,68,86,.08);
}}
.cml-day-top {{ display: flex; justify-content: space-between; gap: 7px; color: #5e7884; font-size: 11px; font-weight: 700; }}
.cml-day-top span:first-child {{ color: #078195; letter-spacing: 1px; }}
.cml-day-main {{ display: flex; align-items: center; gap: 12px; min-height: 64px; margin: 14px 0 8px; }}
.cml-day-sym {{ display: flex; align-items: center; justify-content: center; width: 56px; height: 56px; border-radius: 18px; background: linear-gradient(145deg, #fff2c9, #ffe5a0); font-size: 30px; flex-shrink: 0; }}
.cml-day-desc {{ font-size: 16px; line-height: 1.2; font-weight: bold; }}
.cml-day-moon {{ display: inline-flex; margin-top: 5px; padding: 4px 8px; border-radius: 999px; background: #edf4ff; color: #405777; font-size: 11px; font-weight: 700; }}

.cml-day-temps {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 9px;
  margin-bottom: 12px;
  padding: 11px 0;
  border-top: 1px solid #e2edf0;
  border-bottom: 1px solid #e2edf0;
}}
.cml-day-temps div {{ display: flex; flex-direction: column; gap: 4px; }}
.cml-day-temps small {{ color: #71858e; font-size: 10px; letter-spacing: 1px; }}
.cml-cold {{ color: #2c91b7; font-size: 21px; font-weight: bold; }}
.cml-warm {{ color: var(--cml-orange); font-size: 21px; font-weight: bold; }}

.cml-day-row {{ display: flex; justify-content: space-between; gap: 12px; margin: 8px 0; font-size: 13px; }}
.cml-day-row b {{ white-space: nowrap; color: #16495b; font-weight: bold; }}

.cml-astro-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #dcebef;
}}
.cml-astro-grid div {{ display: flex; justify-content: space-between; gap: 5px; padding: 6px 8px; border-radius: 8px; background: rgba(255,255,255,.75); font-size: 11px; }}
.cml-astro-grid span {{ color: #718791; }}
.cml-astro-grid b {{ color: #234c5b; }}

/* HEADER DETTAGLIO ORARIO */
.cml-hour-header {{
  position: relative;
  overflow: hidden;
  margin-top: 10px;
  padding: 24px 26px;
  border-radius: 20px;
  color: #fff;
  background: radial-gradient(circle at 87% 12%, rgba(116,210,255,.29), transparent 28%),
              linear-gradient(120deg, #0d1939, #24366b 55%, #3f5184);
  box-shadow: 0 12px 29px rgba(21,38,79,.22);
}}
.cml-hour-header:after {{
  content: "☾";
  position: absolute;
  right: 32px;
  top: 6px;
  color: rgba(255,255,255,.8);
  font-size: 70px;
  line-height: 1;
}}
.cml-hour-header span {{ color: #9aeaf1; font-size: 10px; font-weight: 700; letter-spacing: 1.8px; text-transform: uppercase; }}
.cml-hour-header h2 {{ margin: 7px 0 5px; color: #b98cff; font-size: 24px; letter-spacing: -.4px; }}
.cml-hour-header p {{ margin: 0; color: #d9e9ff; font-size: 13px; }}

/* TABS SELETTORE GIORNI INTEGRATO */
.cml-tabs-bar {{
  display: flex;
  gap: 10px;
  margin: 16px 0 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}}
.cml-tab-btn {{
  background: #ffffff;
  border: 1px solid #cce3ea;
  border-radius: 12px;
  padding: 10px 18px;
  font-size: 13px;
  font-weight: 700;
  color: #2b556b;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}}
.cml-tab-btn:hover {{
  background: #e9f7fa;
  border-color: #0b687c;
}}
.cml-tab-btn.active {{
  background: #0b687c;
  color: #ffffff;
  border-color: #0b687c;
  box-shadow: 0 4px 12px rgba(11,104,124,0.25);
}}

/* TABELLA ORARIA */
.cml-table-wrap {{
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  border: 1px solid #d9e7ec;
  border-radius: 17px;
  background: #fff;
  box-shadow: 0 8px 23px rgba(22,68,86,.08);
  margin-bottom: 12px;
}}
.cml-table {{
  width: 100%;
  min-width: 1120px;
  table-layout: fixed;
  border-collapse: separate;
  border-spacing: 0;
  color: var(--cml-ink);
  font: 13px Arial, sans-serif;
  white-space: nowrap;
}}
.cml-table col.col-ora {{ width: 7%; }}
.cml-table col.col-scenario {{ width: 23%; }}
.cml-table col.col-temp {{ width: 10%; }}
.cml-table col.col-percepita {{ width: 10%; }}
.cml-table col.col-pioggia {{ width: 10%; }}
.cml-table col.col-vento {{ width: 10%; }}
.cml-table col.col-direzione {{ width: 7%; }}
.cml-table col.col-raffica {{ width: 11%; }}
.cml-table col.col-nubi {{ width: 6%; }}
.cml-table col.col-umidita {{ width: 6%; }}

.cml-table th {{
  height: 48px;
  padding: 0 12px;
  background: #0b687c;
  color: #fff;
  text-align: center;
  vertical-align: middle;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .1px;
  line-height: 1.15;
}}
.cml-table th:first-child {{ border-top-left-radius: 16px; }}
.cml-table th:last-child {{ border-top-right-radius: 16px; }}

.cml-table td {{
  height: 46px;
  padding: 0 12px;
  border-bottom: 1px solid #e7eff2;
  text-align: center;
  vertical-align: middle;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}}
.cml-table td:first-child {{ color: #087b8e; font-weight: 700; }}
.cml-table th:nth-child(2), .cml-table td:nth-child(2) {{ text-align: left; }}
.cml-table td:nth-child(3), .cml-table td:nth-child(4), .cml-table td:nth-child(5),
.cml-table td:nth-child(6), .cml-table td:nth-child(8), .cml-table td:nth-child(9),
.cml-table td:nth-child(10) {{ text-align: right; }}
.cml-table td:nth-child(7) {{ text-align: center; color: #315b6a; font-weight: 700; }}

.cml-table-condition {{
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 9px;
  width: 100%;
  min-width: 0;
}}
.cml-table-icon {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 30px;
  width: 30px;
  min-width: 30px;
  font-size: 19px;
  line-height: 1;
  text-align: center;
}}
.cml-table-scenario {{
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
}}

.cml-table tbody tr:nth-child(even) {{ background: #f4f9fa; }}
.cml-table tbody tr:hover {{ background: #e5f4f6; }}
.cml-table tbody tr:last-child td {{ border-bottom: 0; }}

/* RIGHE NOTTURNE */
.cml-table tr.cml-night-row {{
  background: linear-gradient(90deg, #111d42 0%, #1d2c59 100%) !important;
  color: #edf4ff !important;
}}
.cml-table tr.cml-night-row .cml-table-icon {{ opacity: 1; filter: none; font-size: 20px; }}
.cml-table tr.cml-night-row .cml-table-scenario {{ color: #f4dda0; font-weight: 700; }}
.cml-table tr.cml-night-row td:first-child {{ color: #a8e5ef; }}
.cml-table tr.cml-night-row td:nth-child(7) {{ color: #d4e8f5; }}

.cml-note {{
  margin: 14px 0 20px;
  padding: 13px 16px;
  border: 1px solid #f2e3bf;
  border-left: 4px solid #e5ad4f;
  border-radius: 11px;
  background: #fff9ea;
  color: #625237;
  font-size: 13px;
  line-height: 1.6;
}}
</style>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
function mostraGiorno(dataId, btn) {{
  var tabs = document.getElementsByClassName("cml-day-table-container");
  for (var i = 0; i < tabs.length; i++) {{
    tabs[i].style.display = "none";
  }}
  var buttons = document.getElementsByClassName("cml-tab-btn");
  for (var i = 0; i < buttons.length; i++) {{
    buttons[i].classList.remove("active");
  }}
  document.getElementById("tab-" + dataId).style.display = "block";
  btn.classList.add("active");
}}
</script>
</head>
<body>

<div class="cml-hero">
  <div class="cml-brand">
    <span class="cml-brand-mark"></span>
    CALABRIA · METEOROLOGIA LOCALE
  </div>
  <h1>Calabria Meteo Lab</h1>
  <p>
    Previsione puntuale ad alta risoluzione per la Calabria.
    Cerca una località e leggi subito temperatura, cielo, vento,
    precipitazioni e sviluppo delle prossime 72 ore.
  </p>
</div>

<div class="cml-current">
  <div class="cml-current-main">
    <div class="cml-place-block">
      <div class="cml-kicker">
        <span class="cml-live-dot"></span>
        ICON-2I · PREVISIONE PUNTUALE
      </div>
      <h2>📍 {html.escape(luogo)}</h2>
      <div class="cml-condition">
        {ico_cur} {html.escape(desc_cur)}
      </div>
    </div>
    <div class="cml-temperature">
      <span>{numero(cur.get("temperature_2m"), 1, "")}</span>
      <small>°C</small>
    </div>
  </div>
  <div class="cml-metrics">{metriche_html}</div>
  <div class="cml-current-footer">
    <span>◷ Valido alle <b>{html.escape(str(cur.get("time", "—")))}</b></span>
    <span>◉ Fuso <b>Europe/Rome</b></span>
    <span>◌ Fonte <b>ItaliaMeteo–ARPAE</b></span>
  </div>
</div>

<!-- ================= RADAR METEO NAZIONALE PROTEZIONE CIVILE ================= -->
<div class="cml-radar-box">
  <div class="cml-radar-header">
    <div>
      <h2>📡 Radar Precipitazioni Live (Mosaico Nazionale DPC)</h2>
      <div style="font-size:12px;color:#607987;margin-top:2px;">Riflettività radar Doppler e precipitazioni in tempo reale centrate sulla posizione selezionata.</div>
    </div>
    <div class="cml-radar-controls">
      <button class="cml-radar-btn" id="btn-play" onclick="togglePlay()">⏸️ Pausa</button>
    </div>
  </div>
  <div id="radar-map"></div>
  <div class="cml-radar-legend">
    <div>⚡ <b>Rete Radar:</b> Dipartimento Protezione Civile (DPC) &bull; Mappa OpenStreetMap</div>
    <div>Scansione radar: <span id="radar-timestamp" class="cml-radar-time">Caricamento frame in corso...</span></div>
  </div>
</div>

<div class="cml-section-title">
  <div>
    <span>ORIZZONTE PREVISIONALE</span>
    <h2>📅 I prossimi tre giorni</h2>
    <p>Condizione prevalente diurna, nuvolosità media, temperature, precipitazioni, vento e ciclo lunare.</p>
  </div>
  <div class="cml-pill">72 ore</div>
</div>
<div class="cml-days-grid">{''.join(carte_html)}</div>
<div class="cml-note">
  ℹ️ Le schede giornaliere riportano la <b>condizione meteorologica prevalente e la nuvolosità media delle ore diurne</b> (dall'alba al tramonto). I valori di temperatura, vento e pioggia rappresentano gli estremi e i cumulati delle 24 ore.
</div>

<div class="cml-hour-header">
  <span>DETTAGLIO ORARIO</span>
  <h2>🕒 Previsione ora per ora</h2>
  <p>Seleziona uno dei giorni sottostanti per visualizzare l'evoluzione oraria dettagliata.</p>
</div>

<div class="cml-tabs-bar">
  {''.join(pulsanti_tab_html)}
</div>

{''.join(sezioni_tabelle_html)}

<div class="cml-note">
  ℹ️ La precipitazione oraria è espressa in millimetri. 🧭 «Da SO» indica vento proveniente da sud-ovest. Le ore notturne sono riconoscibili esclusivamente dallo sfondo blu.
</div>

<script>
var lat = {lat};
var lon = {lon};

var map = L.map('radar-map', {{
  center: [lat, lon],
  zoom: 8,
  minZoom: 5,
  maxZoom: 18,
  zoomControl: true
}});

L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '&copy; OpenStreetMap contributors',
  maxZoom: 18
}}).addTo(map);

var redPinIcon = L.divIcon({{
  className: 'cml-pin-wrapper',
  html: '<div class="cml-map-pin"></div>',
  iconSize: [18, 18],
  iconAnchor: [9, 9]
}});
L.marker([lat, lon], {{icon: redPinIcon, title: '{html.escape(luogo)}'}}).addTo(map);

var timestamps = [];
var radarLayers = {{}};
var currentFrame = 0;
var isPlaying = true;
var animationTimer = null;

fetch('https://api.rainviewer.com/public/weather-maps.json')
  .then(res => res.json())
  .then(apiData => {{
    var frames = apiData.radar.past;
    timestamps = frames.map(f => f.time);

    frames.forEach(f => {{
      var layer = L.tileLayer('https://tilecache.rainviewer.com' + f.path + '/256/{{z}}/{{x}}/{{y}}/2/1_1.png', {{
        opacity: 0,
        zIndex: 100,
        maxNativeZoom: 6,
        maxZoom: 18
      }});
      layer.addTo(map);
      radarLayers[f.time] = layer;
    }});

    currentFrame = timestamps.length - 1;
    showFrame(currentFrame);
    startAnimation();
  }});

function showFrame(index) {{
  if (timestamps.length === 0) return;
  
  if (radarLayers[timestamps[currentFrame]]) {{
    radarLayers[timestamps[currentFrame]].setOpacity(0);
  }}

  currentFrame = index;
  var time = timestamps[currentFrame];
  
  if (radarLayers[time]) {{
    radarLayers[time].setOpacity(0.75);
  }}

  var date = new Date(time * 1000);
  var ore = ('0' + date.getHours()).slice(-2);
  var min = ('0' + date.getMinutes()).slice(-2);
  document.getElementById('radar-timestamp').innerText = ore + ':' + min + ' (Ora Locale)';
}}

function startAnimation() {{
  if (animationTimer) clearInterval(animationTimer);
  animationTimer = setInterval(() => {{
    var next = (currentFrame + 1) % timestamps.length;
    showFrame(next);
  }}, 750);
}}

function togglePlay() {{
  var btn = document.getElementById('btn-play');
  if (isPlaying) {{
    clearInterval(animationTimer);
    btn.innerText = '▶️ Play';
    isPlaying = false;
  }} else {{
    startAnimation();
    btn.innerText = '⏸️ Pausa';
    isPlaying = true;
  }}
}}
</script>

</body>
</html>"""

# =====================================================================
# INTERFACCIA STREAMLIT
# =====================================================================
st.markdown("### 🔍 Seleziona Località Calabrese")

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
    with st.spinner(f"Elaborazione modello ICON-2I e Radar Live per {luogo}..."):
        dati_meteo = scarica_previsione(lat, lon)
        df_ore, df_giorni = prepara(dati_meteo)

    doc_html = genera_app_completa(luogo, lat, lon, dati_meteo, df_ore, df_giorni)
    components.html(doc_html, height=2700, scrolling=True)

except Exception as errore:
    st.error(f"{errore}")
