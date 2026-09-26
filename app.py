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
    if ore_giorno.empty:
        return 0, 0
    
    if alba is not None and tramonto is not None:
        alba_t = pd.Timestamp(alba)
        tramonto_t = pd.Timestamp(tramonto)
        ore_diurne = ore_giorno.loc[(ore_giorno["time"] >= alba_t) & (ore_giorno["time"] <= tramonto_t)]
    else:
        ore_diurne = ore_giorno.loc[(ore_giorno["time"].dt.hour >= 7) & (ore_giorno["time"].dt.hour <= 20)]

    df_target = ore_diurne if not ore_diurne.empty else ore_giorno
    nubi_media = round(df_target["cloud_cover"].mean()) if "cloud_cover" in df_target else 0

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
        geocoder = Nominatim(user_agent="calabria_meteo_lab_v17", timeout=8)
        risposta = geocoder.geocode(
            f"{nome}, Calabria, Italia",
            exactly_one=True,
            addressdetails=True,
            timeout=8,
        )
    except (GeocoderServiceError, GeocoderTimedOut) as exc:
        raise RuntimeError(f"Località '{nome}' non trovata nei comuni calabresi. Usa uno dei comuni nella lista.") from exc

    if risposta is None:
        raise ValueError(f"Località «{nome}» non trovata. Prova con: Cosenza, Catanzaro, Reggio Calabria, Tropea, Soverato, etc.")

    indirizzo = risposta.raw.get("address", {})
    regione = str(indirizzo.get("state", "") or indirizzo.get("region", "")).casefold()
    lat, lon = float(risposta.latitude), float(risposta.longitude)

    is_calabria = "calabria" in regione
    in_bounds = (37.75 <= lat <= 40.15) and (15.60 <= lon <= 17.25)

    if not (is_calabria and in_bounds):
        reg_txt = f" ({regione.title()})" if regione else ""
        raise ValueError(f"❌ «{nome}»{reg_txt} non è in Calabria.")

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

def valuta_allerta_giornaliera(riga_giorno):
    precip = float(riga_giorno.get("precipitation_sum", 0) or 0)
    vento_max = float(riga_giorno.get("wind_speed_10m_max", 0) or 0)
    raffiche_max = float(riga_giorno.get("wind_gusts_10m_max", 0) or 0)
    weather_code = int(riga_giorno.get("weather_code_prevalente", riga_giorno.get("weather_code", 0)))
    
    if precip >= 100 or raffiche_max >= 100 or weather_code in [96, 99]:
        if weather_code in [95, 96, 99] or precip >= 80:
            return "rosso", "temporali"
        elif raffiche_max >= 100:
            return "rosso", "vento"
        else:
            return "rosso", "pioggia"
    
    if precip >= 50 or raffiche_max >= 70 or weather_code in [95, 96, 99]:
        if weather_code in [95, 96, 99] or precip >= 40:
            return "arancione", "temporali"
        elif raffiche_max >= 70:
            return "arancione", "vento"
        else:
            return "arancione", "pioggia"
    
    if precip >= 20 or raffiche_max >= 50 or weather_code in [80, 81, 82]:
        if weather_code in [80, 81, 82, 95, 96, 99]:
            return "giallo", "temporali"
        elif precip >= 20:
            return "giallo", "pioggia"
        else:
            return "giallo", "vento"
    
    return "verde", "nessuno"

def badge_allerta_html(livello, tipo):
    colori = {
        "verde": ("#10b981", "#059669", "Nessuna criticità"),
        "giallo": ("#fbbf24", "#d97706", "Allerta meteo"),
        "arancione": ("#f97316", "#ea580c", "Allerta moderata"),
        "rosso": ("#ef4444", "#dc2626", "Allerta critica"),
    }
    bg, border, label = colori.get(livello, colori["verde"])
    
    icone = {
        "temporali": "⛈️",
        "pioggia": "🌧️",
        "vento": "💨",
        "nessuno": "✅",
    }
    icona = icone.get(tipo, "✅")
    
    return f'<div class="cml-alert-badge" style="background: {bg}; border-color: {border}; color: white;"><span class="cml-alert-icon">{icona}</span><span class="cml-alert-text">{label} · {tipo.title()}</span></div>'
    
def genera_app_completa(luogo, lat, lon, dati, ore, giorni):
    cur = dati["current"]
    ico_cur, desc_cur = meteo(cur.get("weather_code"))

    metriche = [
        ("🌡️", "Percepita", numero(cur.get("apparent_temperature"), 1, " °C"), "Temperatura percepita dal corpo umano"),
        ("💧", "Umidità", numero(cur.get("relative_humidity_2m"), 0, " %"), "Contenuto di vapore acqueo nell'aria"),
        ("☁️", "Nuvolosità", numero(cur.get("cloud_cover"), 0, " %"), "Copertura nuvolosa totale"),
        ("💨", "Vento", numero(cur.get("wind_speed_10m"), 0, " km/h"), "Velocità media del vento"),
        ("🧭", "Provenienza", direzione(cur.get("wind_direction_10m")), "Direzione di provenienza"),
        ("🌬️", "Raffica", numero(cur.get("wind_gusts_10m"), 0, " km/h"), "Picchi istantanei di vento"),
        ("🌀", "Pressione", numero(cur.get("pressure_msl"), 1, " hPa"), "Pressione atmosferica al livello del mare"),
    ]
    metriche_html = "".join([
        f'<div class="cml-metric-card" title="{m[3]}"><div class="cml-metric-icon">{m[0]}</div><div class="cml-metric-content"><div class="cml-metric-lbl">{m[1]}</div><div class="cml-metric-val">{m[2]}</div></div></div>'
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
        
        livello_allerta, tipo_rischio = valuta_allerta_giornaliera(r)
        badge_allerta = badge_allerta_html(livello_allerta, tipo_rischio)
        
        badge_bg = "linear-gradient(135deg, #ffd700 0%, #ffb347 100%)"
        if cod_effettivo in [0, 1]:
            badge_bg = "linear-gradient(135deg, #ffd700 0%, #ffb347 100%)"
        elif cod_effettivo in [2, 3, 45, 48]:
            badge_bg = "linear-gradient(135deg, #b0c4de 0%, #87a3c9 100%)"
        elif cod_effettivo in range(51, 68):
            badge_bg = "linear-gradient(135deg, #4a90e2 0%, #357abd 100%)"
        elif cod_effettivo in range(71, 87):
            badge_bg = "linear-gradient(135deg, #6c7a89 0%, #5a6573 100%)"
        elif cod_effettivo in [95, 96, 99]:
            badge_bg = "linear-gradient(135deg, #8e44ad 0%, #6c3483 100%)"
        
        carte_html.append(f"""
        <div class="cml-day-card">
          <div class="cml-day-header">
            <span class="cml-day-tag">{tag}</span>
            <span class="cml-day-date">{html.escape(data_it(r["time"]))}</span>
          </div>
          <div class="cml-alert-container">{badge_allerta}</div>
          <div class="cml-day-body">
            <div class="cml-day-icon" style="background: {badge_bg}">{ico}</div>
            <div class="cml-day-info">
              <div class="cml-day-desc">{html.escape(desc)}</div>
              <div class="cml-day-moon">{fase}</div>
            </div>
          </div>
          <div class="cml-day-temps">
            <div class="cml-temp-box">
              <span class="cml-temp-label">MINIMA</span>
              <span class="cml-temp-val cml-cold">↓ {numero(r["temperature_2m_min"], 1, "°")}</span>
            </div>
            <div class="cml-temp-box">
              <span class="cml-temp-label">MASSIMA</span>
              <span class="cml-temp-val cml-warm">↑ {numero(r["temperature_2m_max"], 1, "°")}</span>
            </div>
          </div>
          <div class="cml-day-details">
            <div class="cml-detail-row">
              <span class="cml-detail-icon">☁️</span>
              <span class="cml-detail-label">Nuvolosità diurna</span>
              <span class="cml-detail-value">{nubi_effettive}%</span>
            </div>
            <div class="cml-detail-row">
              <span class="cml-detail-icon">🌧️</span>
              <span class="cml-detail-label">Precipitazione</span>
              <span class="cml-detail-value">{numero(r["precipitation_sum"], 1, " mm")}</span>
            </div>
            <div class="cml-detail-row">
              <span class="cml-detail-icon">💨</span>
              <span class="cml-detail-label">Vento max</span>
              <span class="cml-detail-value">{numero(r["wind_speed_10m_max"], 0, " km/h")}</span>
            </div>
            <div class="cml-detail-row">
              <span class="cml-detail-icon">🌬️</span>
              <span class="cml-detail-label">Raffica max</span>
              <span class="cml-detail-value">{numero(r["wind_gusts_10m_max"], 0, " km/h")}</span>
            </div>
            <div class="cml-detail-row">
              <span class="cml-detail-icon">🧭</span>
              <span class="cml-detail-label">Direzione dom.</span>
              <span class="cml-detail-value">{html.escape(str(r["Da"]))}</span>
            </div>
          </div>
          <div class="cml-day-astro">
            <div class="cml-astro-item">
              <span class="cml-astro-icon">☀️</span>
              <span class="cml-astro-label">Alba</span>
              <span class="cml-astro-time">{ora_it(r.get("sunrise"))}</span>
            </div>
            <div class="cml-astro-item">
              <span class="cml-astro-icon">🌇</span>
              <span class="cml-astro-label">Tramonto</span>
              <span class="cml-astro-time">{ora_it(r.get("sunset"))}</span>
            </div>
            <div class="cml-astro-item">
              <span class="cml-astro-icon">🌙</span>
              <span class="cml-astro-label">Sorge</span>
              <span class="cml-astro-time">{ora_it(r.get("moonrise"))}</span>
            </div>
            <div class="cml-astro-item">
              <span class="cml-astro-icon">🌘</span>
              <span class="cml-astro-label">Tramonta</span>
              <span class="cml-astro-time">{ora_it(r.get("moonset"))}</span>
            </div>
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
            
            riga_bg = ""
            if riga["weather_code"] in [0, 1]:
                riga_bg = "cml-row-sereno"
            elif riga["weather_code"] in [2, 3]:
                riga_bg = "cml-row-nuvoloso"
            elif riga["weather_code"] in range(51, 68):
                riga_bg = "cml-row-pioggia"
            elif riga["weather_code"] in range(71, 87):
                riga_bg = "cml-row-neve"
            elif riga["weather_code"] in [95, 96, 99]:
                riga_bg = "cml-row-temporale"
            
            righe_tabella.append(f"""
            <tr class="{classe_riga} {riga_bg}">
              <td class="col-ora">{riga["time"].strftime("%H:%M")}</td>
              <td class="col-scenario">
                <span class="cml-table-condition">
                  <span class="cml-table-icon">{riga["Icona"]}</span>
                  <span class="cml-table-scenario">{riga["Scenario"]}</span>
                </span>
              </td>
              <td class="col-temp">{numero(riga["temperature_2m"])}</td>
              <td class="col-percepita">{numero(riga["apparent_temperature"])}</td>
              <td class="col-pioggia">{numero(riga["precipitation"])}</td>
              <td class="col-vento">{numero(riga["wind_speed_10m"], 0)}</td>
              <td class="col-direzione">{riga["Da"]}</td>
              <td class="col-raffica">{numero(riga["wind_gusts_10m"], 0)}</td>
              <td class="col-nubi">{numero(riga["cloud_cover"], 0)}</td>
              <td class="col-umidita">{numero(riga["relative_humidity_2m"], 0)}</td>
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

    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
:root {{
  --cml-ink: #0f172a;
  --cml-muted: #64748b;
  --cml-line: #e2e8f0;
  --cml-primary: #0ea5e9;
  --cml-primary-dark: #0284c7;
  --cml-orange: #f97316;
  --cml-blue: #3b82f6;
  --cml-green: #10b981;
  --cml-purple: #8b5cf6;
  --cml-red: #ef4444;
  --cml-yellow: #f59e0b;
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  color: var(--cml-ink);
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 50%, #f0f9ff 100%);
  padding: 8px;
  line-height: 1.5;
  min-height: 100vh;
}}

.cml-hero {{
  position: relative;
  overflow: hidden;
  border-radius: 32px;
  padding: 48px 48px 40px;
  margin: 12px 0 24px;
  color: #fff;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.2);
}}
.cml-brand {{
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(8px);
  border-radius: 999px;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  border: 1px solid rgba(255, 255, 255, 0.3);
}}
.cml-brand-mark {{
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: linear-gradient(135deg, #fde047 0%, #fbbf24 100%);
  box-shadow: 0 0 0 6px rgba(253, 224, 71, 0.2), 0 0 24px rgba(253, 224, 71, 0.8);
}}
.cml-hero h1 {{
  margin: 20px 0 12px;
  font-size: 44px;
  font-weight: 800;
  letter-spacing: -1.5px;
  line-height: 1.1;
  background: linear-gradient(135deg, #ffffff 0%, #e0f2fe 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}
.cml-hero p {{
  max-width: 720px;
  margin: 0;
  color: rgba(255, 255, 255, 0.9);
  font-size: 15px;
  line-height: 1.7;
}}

.cml-current {{
  overflow: hidden;
  margin: 24px 0 32px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}}
.cml-current-main {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  padding: 36px 40px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(240, 249, 255, 0.8) 100%);
  border-bottom: 1px solid rgba(226, 232, 240, 0.5);
}}
.cml-kicker {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: rgba(14, 165, 233, 0.15);
  border-radius: 999px;
  color: var(--cml-primary-dark);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  margin-bottom: 14px;
}}
.cml-place-block h2 {{
  margin: 12px 0 10px;
  color: var(--cml-ink);
  font-size: 34px;
  font-weight: 800;
}}
.cml-condition {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 12px;
  color: var(--cml-muted);
  font-size: 17px;
  font-weight: 600;
}}
.cml-temperature {{
  display: flex;
  align-items: flex-start;
  color: var(--cml-orange);
  font-weight: 900;
  line-height: 0.9;
}}
.cml-temperature span {{
  font-size: 86px;
  letter-spacing: -8px;
}}
.cml-temperature small {{
  margin: 12px 0 0 8px;
  font-size: 28px;
  color: var(--cml-orange);
}}

.cml-metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  padding: 24px 32px;
}}
.cml-metric-card {{
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 72px;
  padding: 16px 18px;
  border: 1px solid rgba(241, 245, 249, 0.8);
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(248, 250, 252, 0.8) 100%);
  transition: all 0.25s ease;
}}
.cml-metric-card:hover {{
  background: linear-gradient(135deg, rgba(240, 249, 255, 0.95) 0%, rgba(224, 242, 254, 0.9) 100%);
  border-color: var(--cml-primary);
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(14, 165, 233, 0.2);
}}
.cml-metric-icon {{
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  font-size: 24px;
  flex-shrink: 0;
}}
.cml-metric-lbl {{
  color: var(--cml-muted);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}}
.cml-metric-val {{
  color: var(--cml-ink);
  font-size: 17px;
  font-weight: 800;
}}

.cml-current-footer {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px 28px;
  padding: 16px 32px;
  border-top: 1px solid rgba(226, 232, 240, 0.6);
  background: rgba(250, 250, 250, 0.6);
  color: var(--cml-muted);
  font-size: 12px;
}}
.cml-current-footer b {{
  color: var(--cml-ink);
  font-weight: 700;
}}

.cml-radar-box {{
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20px);
  padding: 28px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
  margin-bottom: 32px;
}}
.cml-radar-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
  flex-wrap: wrap;
  gap: 14px;
}}
.cml-radar-header h2 {{
  font-size: 22px;
  font-weight: 800;
  color: var(--cml-ink);
  margin: 0;
}}
.cml-radar-btn {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: linear-gradient(135deg, var(--cml-primary) 0%, var(--cml-primary-dark) 100%);
  border: none;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 700;
  color: #ffffff;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
}}
#radar-map {{
  width: 100%;
  height: 520px;
  border-radius: 16px;
  border: 2px solid rgba(226, 232, 240, 0.8);
}}
.cml-radar-legend {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding: 14px 18px;
  background: linear-gradient(135deg, rgba(240, 249, 255, 0.9) 0%, rgba(224, 242, 254, 0.8) 100%);
  border-radius: 12px;
  font-size: 12px;
  color: var(--cml-muted);
  gap: 12px;
  border: 1px solid rgba(186, 230, 253, 0.6);
}}

.cml-section-title {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin: 40px 0 20px;
}}
.cml-section-title span {{
  color: var(--cml-primary);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 2px;
  text-transform: uppercase;
}}
.cml-section-title h2 {{
  margin: 8px 0 6px;
  color: var(--cml-ink);
  font-size: 28px;
  font-weight: 800;
}}
.cml-section-title p {{
  margin: 0;
  color: var(--cml-muted);
  font-size: 14px;
}}
.cml-pill {{
  padding: 8px 16px;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(224, 242, 254, 0.9) 0%, rgba(186, 230, 253, 0.8) 100%);
  color: var(--cml-primary-dark);
  font-size: 12px;
  font-weight: 800;
  border: 1px solid rgba(186, 230, 253, 0.6);
}}

.cml-days-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
  margin-bottom: 28px;
}}
.cml-day-card {{
  position: relative;
  overflow: hidden;
  padding: 28px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  color: var(--cml-ink);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
}}
.cml-day-card:hover {{
  transform: translateY(-4px);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.15);
}}
.cml-day-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}}
.cml-day-tag {{
  padding: 6px 14px;
  background: linear-gradient(135deg, var(--cml-primary) 0%, var(--cml-primary-dark) 100%);
  border-radius: 999px;
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.2px;
  text-transform: uppercase;
}}
.cml-day-date {{
  color: var(--cml-muted);
  font-size: 12px;
  font-weight: 600;
}}

.cml-alert-container {{
  margin-bottom: 16px;
}}
.cml-alert-badge {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}}
.cml-alert-icon {{
  font-size: 18px;
  line-height: 1;
}}
.cml-alert-text {{
  letter-spacing: 0.3px;
}}

.cml-day-body {{
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
}}
.cml-day-icon {{
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 20px;
  font-size: 38px;
  flex-shrink: 0;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  transition: transform 0.3s ease;
}}
.cml-day-card:hover .cml-day-icon {{
  transform: scale(1.08) rotate(5deg);
}}
.cml-day-info {{
  display: flex;
  flex-direction: column;
  gap: 6px;
}}
.cml-day-desc {{
  font-size: 18px;
  font-weight: 800;
  line-height: 1.3;
}}
.cml-day-moon {{
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(224, 231, 255, 0.9) 0%, rgba(199, 210, 254, 0.8) 100%);
  color: #4338ca;
  font-size: 11px;
  font-weight: 700;
}}

.cml-day-temps {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 20px;
  padding: 16px;
  background: linear-gradient(135deg, rgba(248, 250, 252, 0.9) 0%, rgba(241, 245, 249, 0.8) 100%);
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.6);
}}
.cml-temp-box {{
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
}}
.cml-temp-label {{
  color: var(--cml-muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.cml-temp-val {{
  font-size: 24px;
  font-weight: 900;
}}
.cml-cold {{ color: #0284c7; }}
.cml-warm {{ color: var(--cml-orange); }}

.cml-day-details {{
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.6);
}}
.cml-detail-row {{
  display: flex;
  align-items: center;
  gap: 12px;
}}
.cml-detail-icon {{
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(240, 249, 255, 0.9) 0%, rgba(224, 242, 254, 0.8) 100%);
  border-radius: 8px;
  font-size: 16px;
  flex-shrink: 0;
  border: 1px solid rgba(186, 230, 253, 0.5);
}}
.cml-detail-label {{
  color: var(--cml-muted);
  font-size: 13px;
  font-weight: 600;
  flex: 1;
}}
.cml-detail-value {{
  color: var(--cml-ink);
  font-size: 14px;
  font-weight: 800;
  white-space: nowrap;
}}

.cml-day-astro {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}}
.cml-astro-item {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px;
  background: linear-gradient(135deg, rgba(250, 250, 250, 0.9) 0%, rgba(244, 246, 248, 0.8) 100%);
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.6);
  transition: all 0.25s ease;
}}
.cml-astro-item:hover {{
  background: linear-gradient(135deg, rgba(240, 249, 255, 0.95) 0%, rgba(224, 242, 254, 0.9) 100%);
  border-color: var(--cml-primary);
  transform: translateY(-2px);
}}
.cml-astro-icon {{ font-size: 20px; }}
.cml-astro-label {{
  color: var(--cml-muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}}
.cml-astro-time {{
  color: var(--cml-ink);
  font-size: 14px;
  font-weight: 800;
}}

.cml-hour-header {{
  position: relative;
  overflow: hidden;
  margin-top: 16px;
  padding: 32px 32px;
  border-radius: 24px;
  color: #fff;
  background: linear-gradient(135deg, rgba(30, 58, 95, 0.95) 0%, rgba(59, 89, 152, 0.9) 55%, rgba(74, 105, 168, 0.85));
  backdrop-filter: blur(10px);
  box-shadow: 0 12px 36px rgba(59, 89, 152, 0.3);
}}
.cml-hour-header span {{
  color: rgba(186, 230, 253, 0.9);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 2px;
  text-transform: uppercase;
}}
.cml-hour-header h2 {{
  margin: 10px 0 8px;
  color: #ffffff;
  font-size: 28px;
  font-weight: 800;
}}
.cml-hour-header p {{
  margin: 0;
  color: rgba(219, 234, 255, 0.9);
  font-size: 14px;
  line-height: 1.6;
}}

.cml-tabs-bar {{
  display: flex;
  gap: 12px;
  margin: 20px 0 16px;
  overflow-x: auto;
  padding-bottom: 6px;
}}
.cml-tab-btn {{
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.9);
  border: 2px solid rgba(226, 232, 240, 0.8);
  border-radius: 14px;
  font-size: 14px;
  font-weight: 700;
  color: var(--cml-muted);
  cursor: pointer;
  transition: all 0.25s ease;
  white-space: nowrap;
}}
.cml-tab-btn:hover {{
  background: rgba(240, 249, 255, 0.95);
  border-color: var(--cml-primary);
  color: var(--cml-primary-dark);
  transform: translateY(-2px);
}}
.cml-tab-btn.active {{
  background: linear-gradient(135deg, var(--cml-primary) 0%, var(--cml-primary-dark) 100%);
  color: #ffffff;
  border-color: var(--cml-primary);
  box-shadow: 0 6px 16px rgba(14, 165, 233, 0.35);
  transform: translateY(-2px);
}}

.cml-table-wrap {{
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  border: 2px solid rgba(226, 232, 240, 0.8);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
  margin-bottom: 16px;
}}
.cml-table {{
  width: 100%;
  min-width: 1100px;
  table-layout: fixed;
  border-collapse: separate;
  border-spacing: 0;
  color: var(--cml-ink);
  font: 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
  white-space: nowrap;
}}
.cml-table col.col-ora {{ width: 7%; }}
.cml-table col.col-scenario {{ width: 22%; }}
.cml-table col.col-temp {{ width: 9%; }}
.cml-table col.col-percepita {{ width: 9%; }}
.cml-table col.col-pioggia {{ width: 9%; }}
.cml-table col.col-vento {{ width: 9%; }}
.cml-table col.col-direzione {{ width: 7%; }}
.cml-table col.col-raffica {{ width: 10%; }}
.cml-table col.col-nubi {{ width: 7%; }}
.cml-table col.col-umidita {{ width: 7%; }}

.cml-table th {{
  height: 54px;
  padding: 0 12px;
  background: linear-gradient(135deg, var(--cml-primary) 0%, var(--cml-primary-dark) 100%);
  color: #ffffff;
  text-align: center;
  vertical-align: middle;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.5px;
  line-height: 1.2;
  text-transform: uppercase;
  position: sticky;
  top: 0;
  z-index: 10;
}}
.cml-table th:first-child {{ border-top-left-radius: 18px; }}
.cml-table th:last-child {{ border-top-right-radius: 18px; }}

.cml-table td {{
  height: 50px;
  padding: 0 12px;
  border-bottom: 1px solid rgba(241, 245, 249, 0.8);
  text-align: center;
  vertical-align: middle;
  line-height: 1.3;
  font-variant-numeric: tabular-nums;
  transition: all 0.15s ease;
}}
.cml-table td:first-child {{
  color: var(--cml-primary-dark);
  font-weight: 800;
  font-size: 14px;
}}
.cml-table th:nth-child(2), .cml-table td:nth-child(2) {{ text-align: left; }}
.cml-table td:nth-child(3), .cml-table td:nth-child(4), .cml-table td:nth-child(5), .cml-table td:nth-child(6), .cml-table td:nth-child(8), .cml-table td:nth-child(9), .cml-table td:nth-child(10) {{ text-align: right; }}
.cml-table td:nth-child(7) {{ text-align: center; color: var(--cml-muted); font-weight: 800; }}

.cml-table tbody tr:nth-child(even) {{ background: rgba(250, 250, 250, 0.6); }}
.cml-table tbody tr:hover {{
  background: linear-gradient(135deg, rgba(240, 249, 255, 0.95) 0%, rgba(224, 242, 254, 0.9) 100%);
  transform: scale(1.005);
}}
.cml-table tbody tr:last-child td {{ border-bottom: 0; }}

.cml-table tr.cml-row-sereno:hover {{ background: linear-gradient(135deg, rgba(254, 243, 199, 0.9) 0%, rgba(253, 230, 138, 0.85) 100%) !important; }}
.cml-table tr.cml-row-nuvoloso:hover {{ background: linear-gradient(135deg, rgba(224, 231, 255, 0.9) 0%, rgba(199, 210, 254, 0.85) 100%) !important; }}
.cml-table tr.cml-row-pioggia:hover {{ background: linear-gradient(135deg, rgba(219, 234, 255, 0.9) 0%, rgba(191, 219, 254, 0.85) 100%) !important; }}
.cml-table tr.cml-row-neve:hover {{ background: linear-gradient(135deg, rgba(241, 245, 249, 0.9) 0%, rgba(226, 232, 240, 0.85) 100%) !important; }}
.cml-table tr.cml-row-temporale:hover {{ background: linear-gradient(135deg, rgba(233, 213, 255, 0.9) 0%, rgba(216, 180, 254, 0.85) 100%) !important; }}

.cml-table tr.cml-night-row {{
  background: linear-gradient(90deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.9) 100%) !important;
}}
.cml-table tr.cml-night-row td {{
  color: rgba(226, 232, 240, 0.95) !important;
  border-bottom-color: rgba(51, 65, 85, 0.8) !important;
}}
.cml-table tr.cml-night-row .cml-table-icon {{
  background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%);
  color: #fde68a;
  font-size: 22px;
  box-shadow: 0 2px 8px rgba(253, 230, 138, 0.3);
}}
.cml-table tr.cml-night-row .cml-table-scenario {{ color: #fde68a !important; font-weight: 800; }}
.cml-table tr.cml-night-row td:first-child {{ color: rgba(125, 211, 252, 0.95) !important; }}
.cml-table tr.cml-night-row td:nth-child(7) {{ color: rgba(186, 230, 253, 0.95) !important; }}

.cml-table-condition {{
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  width: 100%;
}}
.cml-table-icon {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  font-size: 20px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}}
.cml-table-scenario {{
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
  font-weight: 600;
}}

.cml-note {{
  margin: 20px 0 24px;
  padding: 18px 22px;
  border: 2px solid rgba(253, 230, 138, 0.8);
  border-left: 5px solid var(--cml-yellow);
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(254, 243, 199, 0.9) 0%, rgba(253, 230, 138, 0.85) 100%);
  backdrop-filter: blur(10px);
  color: rgba(120, 52, 15, 0.9);
  font-size: 13px;
  line-height: 1.7;
}}
.cml-note b {{ color: rgba(146, 64, 14, 0.95); font-weight: 800; }}
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
        <span class="cml-live-dot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#10b981;margin-right:7px;"></span>
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

<div class="cml-radar-box">
  <div class="cml-radar-header">
    <div>
      <h2>📡 Radar Precipitazioni Live</h2>
      <div style="font-size:12px;color:var(--cml-muted);margin-top:2px;">Mosaico Nazionale DPC · Riflettività radar in tempo reale</div>
    </div>
    <div style="display:flex;gap:10px;align-items:center;">
      <button class="cml-radar-btn" id="btn-play" onclick="togglePlay()">⏸️ Pausa</button>
    </div>
  </div>
  <div id="radar-map"></div>
  <div class="cml-radar-legend">
    <div>⚡ <b>Rete Radar:</b> Dipartimento Protezione Civile (DPC)</div>
    <div>Scansione: <span id="radar-timestamp" style="font-weight:800;color:var(--cml-primary-dark);font-size:13px;">Caricamento...</span></div>
  </div>
</div>

<div class="cml-section-title">
  <div>
    <span>ORIZZONTE PREVISIONALE</span>
    <h2>📅 I prossimi tre giorni</h2>
    <p>Condizione prevalente diurna, nuvolosità, temperature, precipitazioni, vento e ciclo lunare.</p>
  </div>
  <div class="cml-pill">72 ore</div>
</div>
<div class="cml-days-grid">{''.join(carte_html)}</div>
<div class="cml-note">
  ℹ️ Le schede mostrano la <b>condizione prevalente e la nuvolosità media diurna</b> (alba-tramonto). Temperature, vento e pioggia sono valori estremi/cumulati sulle 24h. I livelli di allerta sono calcolati in base alle soglie della Protezione Civile.
</div>

<div class="cml-hour-header">
  <span>DETTAGLIO ORARIO</span>
  <h2>🕒 Previsione ora per ora</h2>
  <p>Seleziona un giorno per vedere l'evoluzione oraria del modello ICON-2I.</p>
</div>

<div class="cml-tabs-bar">
  {''.join(pulsanti_tab_html)}
</div>

{''.join(sezioni_tabelle_html)}

<div class="cml-note">
  ℹ️ <b>Modello ICON-2I:</b> Previsione deterministica ad alta risoluzione (2.2 km) di ItaliaMeteo–ARPAE. Aggiornata 2× al giorno (00/12 UTC), orizzonte 72h.
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
  html: '<div class="cml-map-pin" style="width:20px;height:20px;background:linear-gradient(135deg,#ef4444,#dc2626);border:3px solid #ffffff;border-radius:50%;box-shadow:0 0 0 3px rgba(239,68,68,0.4);"></div>',
  iconSize: [20, 20],
  iconAnchor: [10, 10]
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

    return html_content

st.markdown("### 🔍 Seleziona Località Calabrese")

with st.form("search_form", clear_on_submit=False):
    col_in, col_btn = st.columns([4, 1])
    with col_in:
        testo_citta = st.text_input(
            "Località",
            value="Cosenza",
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
    components.html(doc_html, height=2900, scrolling=True)

except Exception as errore:
    st.error(f"{errore}")
