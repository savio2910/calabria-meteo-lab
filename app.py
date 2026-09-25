# =====================================================================
# CALABRIA METEO LAB — SOLO CITTÀ
# VERSIONE STREAMLIT CLOUD
# ICON-2I VIA OPEN-METEO
# =====================================================================

import html
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
from streamlit.components.v1 import html as st_html

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim


# =====================================================================
# CONFIGURAZIONE
# =====================================================================

API_URL = "https://api.open-meteo.com/v1/forecast"
MODELLO = "italia_meteo_arpae_icon_2i"
FUSO = ZoneInfo("Europe/Rome")
GIORNI = 3


# =====================================================================
# LOCALITÀ CALABRESI
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
    "rossano": "Corigliano-Rossano",
    "isola capo rizzuto": "Isola di Capo Rizzuto",
}


# =====================================================================
# TESTI E CODICI METEOROLOGICI
# =====================================================================

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
# LOGICA ORARIA
# =====================================================================

def icona_oraria(riga, giorni):
    return meteo(riga.get("weather_code"))[0]


def scenario_orario(riga, giorni):
    return meteo(riga.get("weather_code"))[1]


# =====================================================================
# GEOCODIFICA
# =====================================================================

def risolvi_citta(testo):
    nome = testo.strip()

    if not nome:
        raise ValueError("Scrivi il nome di una località della Calabria.")

    indice = {
        nome_comune.casefold(): nome_comune
        for nome_comune in COMUNI
    }

    nome_alias = ALIASES.get(nome.casefold(), nome)
    chiave = nome_alias.casefold()

    if chiave in indice:
        citta = indice[chiave]
        lat, lon = COMUNI[citta]
        return citta, lat, lon

    try:
        geocoder = Nominatim(
            user_agent="calabria_meteo_lab_streamlit",
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
            "Ricerca della località non disponibile: riprova tra poco."
        ) from exc

    if risposta is None:
        raise ValueError(
            "Località non trovata in Calabria: controlla il nome."
        )

    indirizzo = risposta.raw.get("address", {})
    regione = (
        indirizzo.get("state")
        or indirizzo.get("region")
        or ""
    ).casefold()

    coordinate_valide = (
        37.8 <= risposta.latitude <= 40.2
        and 15.5 <= risposta.longitude <= 17.4
    )

    if "calabria" not in regione or not coordinate_valide:
        raise ValueError(
            "La ricerca non ha individuato una località calabrese con sicurezza."
        )

    return nome, float(risposta.latitude), float(risposta.longitude)


# =====================================================================
# DOWNLOAD DATI
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
        risposta = requests.get(
            API_URL,
            params=params,
            timeout=45,
        )

        risposta.raise_for_status()
        dati = risposta.json()

    except requests.HTTPError as exc:
        try:
            motivo = risposta.json().get(
                "reason",
                risposta.text[:250],
            )
        except (ValueError, AttributeError):
            motivo = risposta.text[:250]

        raise RuntimeError(
            f"Open-Meteo HTTP {risposta.status_code}: {motivo}"
        ) from exc

    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(
            f"Download della previsione non riuscito: {exc}"
        ) from exc

    if not isinstance(dati, dict):
        raise RuntimeError(
            "Risposta non valida ricevuta da Open-Meteo."
        )

    for sezione in ("current", "hourly", "daily"):
        if not isinstance(dati.get(sezione), dict):
            raise RuntimeError(
                f"Risposta incompleta: sezione {sezione} assente."
            )

    return dati


# =====================================================================
# DATAFRAME
# =====================================================================

def prepara(dati):
    ore = pd.DataFrame(dati["hourly"])
    giorni = pd.DataFrame(dati["daily"])

    if ore.empty or giorni.empty:
        raise RuntimeError(
            "Previsione oraria o giornaliera non disponibile."
        )

    ore["time"] = pd.to_datetime(ore["time"])
    giorni["time"] = pd.to_datetime(giorni["time"])

    ora_locale = datetime.now(FUSO).replace(tzinfo=None)

    ore = ore.loc[
        ore["time"] >= pd.Timestamp(ora_locale).floor("h")
    ].copy()

    if ore.empty:
        raise RuntimeError(
            "Nessuna ora futura disponibile nei tre giorni ricevuti."
        )

    giorni["Scenario"] = giorni["weather_code"].map(
        lambda codice: " ".join(meteo(codice))
    )

    giorni["Da"] = giorni[
        "wind_direction_10m_dominant"
    ].map(direzione)

    giorni["Fase lunare"] = giorni[
        "moon_phase"
    ].map(fase_lunare)

    ore["Icona"] = ore.apply(
        lambda riga: icona_oraria(riga, giorni),
        axis=1,
    )

    ore["Scenario"] = ore.apply(
        lambda riga: scenario_orario(riga, giorni),
        axis=1,
    )

    ore["Notte"] = ore.apply(
        lambda riga: (
            False
            if riga_giornaliera(
                riga["time"],
                giorni,
            ) is None
            else e_notte(
                riga["time"],
                riga_giornaliera(
                    riga["time"],
                    giorni,
                ).get("sunrise"),
                riga_giornaliera(
                    riga["time"],
                    giorni,
                ).get("sunset"),
            )
        ),
        axis=1,
    )

    ore["Da"] = ore[
        "wind_direction_10m"
    ].map(direzione)

    return (
        ore.reset_index(drop=True),
        giorni.reset_index(drop=True),
    )


# =====================================================================
# COMPONENTI HTML
# =====================================================================

def metric(icona, nome, dato):
    return (
        '<div class="cml-metric">'
        f'<div class="cml-metric-icon">{icona}</div>'
        '<div>'
        f'<div class="cml-metric-name">{html.escape(nome)}</div>'
        f'<div class="cml-metric-value">{html.escape(dato)}</div>'
        '</div>'
        '</div>'
    )


def pannello_attuale(luogo, dati):
    cur = dati["current"]
    icona, descrizione = meteo(cur.get("weather_code"))

    metriche = "".join([
        metric(
            "🌡️",
            "Percepita",
            numero(cur.get("apparent_temperature"), 1, " °C"),
        ),
        metric(
            "💧",
            "Umidità",
            numero(cur.get("relative_humidity_2m"), 0, " %"),
        ),
        metric(
            "☁️",
            "Nuvolosità",
            numero(cur.get("cloud_cover"), 0, " %"),
        ),
        metric(
            "💨",
            "Vento",
            numero(cur.get("wind_speed_10m"), 0, " km/h"),
        ),
        metric(
            "🧭",
            "Provenienza",
            direzione(cur.get("wind_direction_10m")),
        ),
        metric(
            "🌬️",
            "Raffica",
            numero(cur.get("wind_gusts_10m"), 0, " km/h"),
        ),
        metric(
            "🌀",
            "Pressione MSL",
            numero(cur.get("pressure_msl"), 1, " hPa"),
        ),
    ])

    return f'''
    <section class="cml-current">
      <div class="cml-current-main">
        <div class="cml-place-block">
          <div class="cml-kicker">
            <span class="cml-live-dot"></span>
            ICON-2I · PREVISIONE PUNTUALE
          </div>
          <h2>📍 {html.escape(luogo)}</h2>
          <div class="cml-condition">
            {icona} {html.escape(descrizione)}
          </div>
        </div>
        <div class="cml-temperature">
          <span>{numero(cur.get("temperature_2m"), 1, "")}</span>
          <small>°C</small>
        </div>
      </div>
      <div class="cml-metrics">{metriche}</div>
      <div class="cml-current-footer">
        <span>
          ◷ Valido alle
          <b>{html.escape(str(cur.get("time", "—")))}</b>
        </span>
        <span>◉ Fuso <b>Europe/Rome</b></span>
        <span>◌ Fonte <b>ItaliaMeteo–ARPAE</b></span>
      </div>
    </section>
    '''


def carte_giornaliere(giorni):
    carte = []
    etichette = ["OGGI", "DOMANI", "DOPODOMANI"]

    for i, (_, riga) in enumerate(giorni.iterrows()):
        etichetta = (
            etichette[i]
            if i < len(etichette)
            else "PREVISIONE"
        )

        icona, descrizione = meteo(
            riga["weather_code"]
        )

        fase = html.escape(
            str(riga.get("Fase lunare", "🌙 Luna"))
        )

        carte.append(f'''
        <article class="cml-day-card">
          <div class="cml-day-top">
            <span>{etichetta}</span>
            <span>{html.escape(data_it(riga["time"]))}</span>
          </div>

          <div class="cml-day-icon">
            <span class="cml-weather-symbol">
              {html.escape(icona)}
            </span>
            <div>
              <div class="cml-day-weather">
                {html.escape(descrizione)}
              </div>
              <div class="cml-moon-phase">
                {fase}
              </div>
            </div>
          </div>

          <div class="cml-day-temp-row">
            <div>
              <small>MINIMA</small>
              <strong class="cml-cold">
                ↓ {numero(riga["temperature_2m_min"], 1, "°")}
              </strong>
            </div>
            <div>
              <small>MASSIMA</small>
              <strong class="cml-warm">
                ↑ {numero(riga["temperature_2m_max"], 1, "°")}
              </strong>
            </div>
          </div>

          <div class="cml-day-data">
            <span>🌧️ Precipitazione</span>
            <b>{numero(riga["precipitation_sum"], 1, " mm")}</b>
          </div>

          <div class="cml-day-data">
            <span>💨 Vento massimo</span>
            <b>{numero(riga["wind_speed_10m_max"], 0, " km/h")}</b>
          </div>

          <div class="cml-day-data">
            <span>🌬️ Raffica massima</span>
            <b>{numero(riga["wind_gusts_10m_max"], 0, " km/h")}</b>
          </div>

          <div class="cml-day-data">
            <span>🧭 Direzione dominante</span>
            <b>{html.escape(riga["Da"])}</b>
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
        ''')

    return (
        '<div class="cml-section-title">'
        '<div>'
        '<span>ORIZZONTE PREVISIONALE</span>'
        '<h2>📅 I prossimi tre giorni</h2>'
        '<p>Temperature, precipitazioni, vento e ciclo lunare in una lettura immediata.</p>'
        '</div>'
        '<div class="cml-pill">72 ore</div>'
        '</div>'
        '<div class="cml-days-grid">'
        + "".join(carte)
        + '</div>'
        '<div class="cml-note">'
        'ℹ️ Le icone rappresentano la condizione meteorologica prevalente prevista dal modello. '
        'I valori sono riferiti alla località selezionata.'
        '</div>'
    )


def tabella_html(ore):
    intestazioni = [
        "Ora",
        "Scenario",
        "Temp. °C",
        "Percepita °C",
        "Pioggia mm",
        "Vento km/h",
        "Da",
        "Raffica km/h",
        "Nubi %",
        "Umidità %",
    ]

    righe_html = []

    for _, riga in ore.iterrows():
        classe = (
            "cml-night-row"
            if bool(riga.get("Notte", False))
            else "cml-day-row"
        )

        icona = html.escape(str(riga["Icona"]))
        scenario = html.escape(str(riga["Scenario"]))

        cielo = (
            '<span class="cml-table-condition">'
            f'<span class="cml-table-icon">{icona}</span>'
            f'<span class="cml-table-scenario">{scenario}</span>'
            '</span>'
        )

        celle = [
            html.escape(riga["time"].strftime("%H:%M")),
            cielo,
            html.escape(numero(riga["temperature_2m"])),
            html.escape(numero(riga["apparent_temperature"])),
            html.escape(numero(riga["precipitation"])),
            html.escape(numero(riga["wind_speed_10m"], 0)),
            html.escape(str(riga["Da"])),
            html.escape(numero(riga["wind_gusts_10m"], 0)),
            html.escape(numero(riga["cloud_cover"], 0)),
            html.escape(numero(riga["relative_humidity_2m"], 0)),
        ]

        righe_html.append(
            f'<tr class="{classe}">'
            + "".join(f"<td>{cella}</td>" for cella in celle)
            + "</tr>"
        )

    intestazioni_html = "".join(
        f"<th>{html.escape(titolo)}</th>"
        for titolo in intestazioni
    )

    return f'''
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
          <tr>{intestazioni_html}</tr>
        </thead>
        <tbody>{"".join(righe_html)}</tbody>
      </table>
    </div>
    '''


# =====================================================================
# CSS
# =====================================================================

CSS = """
<style>
:root{
  --cml-ink:#102b3b;
  --cml-muted:#607987;
  --cml-line:#dcebef;
  --cml-orange:#ed8750;
}


.cml-hero,.cml-current,.cml-day-card,.cml-note,
.cml-table-wrap,.cml-hour-header{
  box-sizing:border-box;
  font-family:Arial,sans-serif;
}


.cml-hero{
  position:relative;
  overflow:hidden;
  border-radius:28px;
  padding:38px 40px;
  margin:8px 0 18px;
  color:#fff;
  background:
    radial-gradient(circle at 83% 16%,rgba(117,241,244,.4),transparent 23%),
    radial-gradient(circle at 4% 115%,rgba(244,177,86,.22),transparent 30%),
    linear-gradient(125deg,#061b33 0%,#07566f 53%,#13aab2 100%);
  box-shadow:0 18px 44px rgba(5,57,78,.28);
}


.cml-hero:before{
  content:"";
  position:absolute;
  right:-74px;
  top:-122px;
  width:310px;
  height:310px;
  border:38px solid rgba(255,255,255,.09);
  border-radius:50%;
}


.cml-hero:after{
  content:"✦   ·   ✧";
  position:absolute;
  right:47px;
  top:58px;
  color:rgba(255,255,255,.63);
  font-size:21px;
  letter-spacing:10px;
}


.cml-brand{
  position:relative;
  display:flex;
  align-items:center;
  gap:10px;
  color:#bceff0;
  font-size:11px;
  font-weight:700;
  letter-spacing:2.3px;
}


.cml-brand-mark{
  width:10px;
  height:10px;
  border-radius:50%;
  background:#ffd06b;
  box-shadow:0 0 0 5px rgba(255,208,107,.18),0 0 17px rgba(255,208,107,.8);
}


.cml-hero h1{
  position:relative;
  margin:15px 0 9px;
  font-size:39px;
  letter-spacing:-1.2px;
}


.cml-hero p{
  position:relative;
  max-width:760px;
  margin:0;
  color:#e1f7f8;
  font-size:14px;
  line-height:1.7;
}


.cml-current{
  overflow:hidden;
  margin:18px 0 32px;
  border:1px solid var(--cml-line);
  border-radius:24px;
  background:#fff;
  box-shadow:0 12px 32px rgba(18,71,89,.11);
}


.cml-current-main{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:24px;
  padding:30px 32px 25px;
  background:
    radial-gradient(circle at 91% 29%,rgba(255,207,105,.27),transparent 23%),
    linear-gradient(110deg,#fff,#effbfd);
}


.cml-kicker{
  color:#078195;
  font-size:11px;
  font-weight:700;
  letter-spacing:1.5px;
}


.cml-live-dot{
  display:inline-block;
  width:7px;
  height:7px;
  margin-right:7px;
  border-radius:50%;
  background:#19b7a0;
  box-shadow:0 0 0 4px #d7f7ef,0 0 12px rgba(25,183,160,.7);
}


.cml-place-block h2{
  margin:10px 0 8px;
  color:var(--cml-ink);
  font-size:30px;
  letter-spacing:-.7px;
}


.cml-condition{color:#476572;font-size:18px}


.cml-temperature{
  display:flex;
  align-items:flex-start;
  color:var(--cml-orange);
  font-weight:800;
  line-height:.9;
  white-space:nowrap;
  text-shadow:0 4px 15px rgba(235,135,81,.16);
}


.cml-temperature span{font-size:72px;letter-spacing:-6px}
.cml-temperature small{margin:9px 0 0 6px;font-size:24px}


.cml-metrics{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(155px,1fr));
  gap:10px;
  padding:19px 24px;
}


.cml-metric{
  display:flex;
  align-items:center;
  gap:10px;
  min-height:68px;
  padding:12px;
  border:1px solid #e1edf1;
  border-radius:14px;
  background:#f2f9fa;
}


.cml-metric-icon{width:27px;text-align:center;font-size:21px}
.cml-metric-name{margin-bottom:5px;color:var(--cml-muted);font-size:11px}
.cml-metric-value{color:var(--cml-ink);font-size:16px;font-weight:700}


.cml-current-footer{
  display:flex;
  flex-wrap:wrap;
  gap:8px 22px;
  padding:14px 27px;
  border-top:1px solid #e3edf1;
  color:#607985;
  font-size:12px;
}


.cml-current-footer b{color:#345967}


.cml-section-title{
  display:flex;
  align-items:flex-end;
  justify-content:space-between;
  gap:18px;
  margin:0 0 16px;
}


.cml-section-title span{color:#1592a2;font-size:10px;font-weight:700;letter-spacing:1.8px}
.cml-section-title h2{margin:7px 0 5px;color:var(--cml-ink);font-size:25px;letter-spacing:-.5px}
.cml-section-title p{margin:0;color:var(--cml-muted);font-size:13px}
.cml-pill{padding:8px 13px;border-radius:999px;background:#e7f6f8;color:#087a8c;font-size:12px;font-weight:700;white-space:nowrap}


.cml-days-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:16px}


.cml-day-card{
  position:relative;
  overflow:hidden;
  padding:21px;
  border:1px solid var(--cml-line);
  border-radius:21px;
  background:linear-gradient(145deg,#fff 0%,#f5fbfc 58%,#e9f7fa 100%);
  color:var(--cml-ink);
  box-shadow:0 8px 23px rgba(22,68,86,.08);
}


.cml-day-card:before{
  content:"";
  position:absolute;
  right:-48px;
  top:-48px;
  width:150px;
  height:150px;
  border-radius:50%;
  background:radial-gradient(circle,rgba(255,202,102,.34),rgba(255,202,102,.08) 43%,transparent 70%);
}


.cml-day-card:after{
  content:"✦  ·  ✧";
  position:absolute;
  right:18px;
  top:22px;
  color:rgba(13,92,111,.25);
  font-size:14px;
  letter-spacing:7px;
}


.cml-day-top{position:relative;display:flex;justify-content:space-between;gap:7px;color:#5e7884;font-size:11px;font-weight:700}
.cml-day-top span:first-child{color:#078195;letter-spacing:1px}
.cml-day-icon{position:relative;display:flex;align-items:center;gap:13px;min-height:66px;margin:15px 0 8px}
.cml-weather-symbol{display:flex;align-items:center;justify-content:center;width:58px;height:58px;border-radius:18px;background:linear-gradient(145deg,#fff2c9,#ffe5a0);font-size:31px}
.cml-day-weather{font-size:17px;line-height:1.2}
.cml-moon-phase{display:inline-flex;margin-top:5px;padding:5px 8px;border-radius:999px;background:#edf4ff;color:#405777;font-size:11px;font-weight:700}
.cml-day-temp-row{position:relative;display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:14px;padding:13px 0;border-top:1px solid #e2edf0;border-bottom:1px solid #e2edf0}
.cml-day-temp-row div{display:flex;flex-direction:column;gap:5px}.cml-day-temp-row small{color:#71858e;font-size:10px;letter-spacing:1px}.cml-day-temp-row strong{font-size:22px}.cml-cold{color:#2c91b7}.cml-warm{color:var(--cml-orange)}
.cml-day-data{position:relative;display:flex;justify-content:space-between;gap:12px;margin:10px 0;font-size:13px}.cml-day-data b{white-space:nowrap;color:#16495b}
.cml-astro-grid{position:relative;display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:17px;padding-top:14px;border-top:1px solid #dcebef}.cml-astro-grid div{display:flex;justify-content:space-between;gap:5px;padding:7px 8px;border-radius:9px;background:rgba(255,255,255,.72);font-size:11px}.cml-astro-grid span{color:#718791}.cml-astro-grid b{color:#234c5b}


.cml-note{margin:16px 0 28px;padding:13px 16px;border:1px solid #f2e3bf;border-left:4px solid #e5ad4f;border-radius:11px;background:#fff9ea;color:#625237;font-size:13px;line-height:1.6}


.cml-hour-header{position:relative;overflow:hidden;margin-top:9px;padding:25px 27px;border-radius:20px;color:#fff;background:radial-gradient(circle at 87% 12%,rgba(116,210,255,.29),transparent 28%),linear-gradient(120deg,#0d1939,#24366b 55%,#3f5184);box-shadow:0 12px 29px rgba(21,38,79,.22)}
.cml-hour-header:after{content:"☾";position:absolute;right:34px;top:8px;color:rgba(255,255,255,.8);font-size:75px;line-height:1}.cml-hour-header span,.cml-hour-header h2,.cml-hour-header p{position:relative}.cml-hour-header span{color:#9aeaf1;font-size:10px;font-weight:700;letter-spacing:1.8px}.cml-hour-header h2{margin:8px 0 6px;color:#b98cff;font-size:25px;letter-spacing:-.4px}.cml-hour-header p{margin:0;color:#d9e9ff;font-size:13px}


/* ==================================================================
   TABELLA ORARIA — COLONNE STABILI E ALLINEAMENTO COERENTE
   ================================================================== */


.cml-table-wrap{
  width:100%;
  max-width:100%;
  overflow-x:auto;
  margin-top:12px;
  border:1px solid #d9e7ec;
  border-radius:17px;
  background:#fff;
  box-shadow:0 8px 23px rgba(22,68,86,.08);
}


.cml-table{
  width:100%;
  min-width:1120px;
  table-layout:fixed;
  border-collapse:separate;
  border-spacing:0;
  color:var(--cml-ink);
  font:13px Arial,sans-serif;
  white-space:nowrap;
}


.cml-table col.col-ora{width:7%}
.cml-table col.col-scenario{width:23%}
.cml-table col.col-temp{width:10%}
.cml-table col.col-percepita{width:10%}
.cml-table col.col-pioggia{width:10%}
.cml-table col.col-vento{width:10%}
.cml-table col.col-direzione{width:7%}
.cml-table col.col-raffica{width:11%}
.cml-table col.col-nubi{width:6%}
.cml-table col.col-umidita{width:6%}


.cml-table th{
  height:48px;
  padding:0 12px;
  background:#0b687c;
  color:#fff;
  text-align:center;
  vertical-align:middle;
  font-size:12px;
  font-weight:700;
  letter-spacing:.1px;
  line-height:1.15;
}


.cml-table th:first-child{border-top-left-radius:16px}
.cml-table th:last-child{border-top-right-radius:16px}


.cml-table td{
  height:46px;
  padding:0 12px;
  border-bottom:1px solid #e7eff2;
  text-align:center;
  vertical-align:middle;
  line-height:1.2;
  font-variant-numeric:tabular-nums;
}


.cml-table td:first-child{
  color:#087b8e;
  font-weight:700;
}


.cml-table th:nth-child(2),
.cml-table td:nth-child(2){
  text-align:left;
}


.cml-table td:nth-child(3),
.cml-table td:nth-child(4),
.cml-table td:nth-child(5),
.cml-table td:nth-child(6),
.cml-table td:nth-child(8),
.cml-table td:nth-child(9),
.cml-table td:nth-child(10){
  text-align:right;
}


.cml-table td:nth-child(7){
  text-align:center;
  color:#315b6a;
  font-weight:700;
}


.cml-table-condition{
  display:flex;
  align-items:center;
  justify-content:flex-start;
  gap:9px;
  width:100%;
  min-width:0;
}


.cml-table-icon{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  flex:0 0 30px;
  width:30px;
  min-width:30px;
  font-size:19px;
  line-height:1;
  text-align:center;
}


.cml-table-scenario{
  display:block;
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
  line-height:1.2;
}


.cml-table tbody tr:nth-child(even){background:#f4f9fa}
.cml-table tbody tr:hover{background:#e5f4f6}
.cml-table tbody tr:last-child td{border-bottom:0}


/* Solo differenza tra giorno e notte: il colore della riga. */
.cml-table tr.cml-night-row{
  background:linear-gradient(90deg,#111d42 0%,#1d2c59 100%) !important;
  color:#edf4ff;
}


.cml-table tr.cml-night-row .cml-table-icon{
  opacity:1;
  filter:none;
  font-size:20px;
}


.cml-table tr.cml-night-row .cml-table-scenario{
  color:#f4dda0;
  font-weight:700;
}


.cml-table tr.cml-night-row td:first-child{color:#a8e5ef}
.cml-table tr.cml-night-row td:nth-child(7){color:#d4e8f5}


.cml-table-wrap::-webkit-scrollbar{height:9px}
.cml-table-wrap::-webkit-scrollbar-track{background:#edf5f7;border-radius:20px}
.cml-table-wrap::-webkit-scrollbar-thumb{background:#8bbbc5;border-radius:20px}
.cml-table-wrap::-webkit-scrollbar-thumb:hover{background:#4d98a7}


@media(max-width:650px){
  .cml-hero{padding:28px 23px}
  .cml-hero h1{font-size:30px}
  .cml-current-main{align-items:flex-start;flex-direction:column}
  .cml-temperature span{font-size:57px}
  .cml-place-block h2{font-size:25px}
  .cml-section-title{align-items:flex-start;flex-direction:column}
  .cml-pill{align-self:flex-start}
  .cml-astro-grid{grid-template-columns:1fr}
}
</style>
"""


# =====================================================================
# INTERFACCIA PRINCIPALE
# =====================================================================

st.set_page_config(
    page_title="Calabria Meteo Lab",
    page_icon="🌤️",
    layout="wide",
)

# Inietta il CSS
st.markdown(CSS, unsafe_allow_html=True)

# Hero section
st.markdown("""
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
""", unsafe_allow_html=True)

# Form di input
with st.form("meteo_form", clear_on_submit=False):
    citta_input = st.text_input(
        "Località",
        value="Lamezia Terme",
        placeholder="Es. Cosenza, Tropea, Soverato…",
    )
    submitted = st.form_submit_button("Aggiorna", icon="🔄")

if submitted:
    try:
        luogo, lat, lon = risolvi_citta(citta_input)
        with st.spinner("⏳ Caricamento previsione…"):
            dati = scarica_previsione(lat, lon)
            ore, giorni = prepara(dati)

        # Pannello attuale
        st_html(pannello_attuale(luogo, dati), height=350)
        
        # Carte giornaliere
        st_html(carte_giornaliere(giorni), height=900)

        # Header tabella oraria
        st_html("""
        <div class="cml-hour-header">
          <span>DETTAGLIO ORARIO</span>
          <h2>🕒 Previsione ora per ora</h2>
        </div>
        """, height=150)

        # Selettore giorno
        date_disponibili = sorted(ore["time"].dt.date.unique())
        giorno_scelto = st.selectbox(
            "Giorno",
            options=date_disponibili,
            format_func=lambda x: data_it(x),
        )

        ore_giorno = ore.loc[ore["time"].dt.date == giorno_scelto]
        
        # Tabella oraria
        st_html(tabella_html(ore_giorno), height=850)

        # Nota finale
        st_html("""
        <div class="cml-note">
          ℹ️ La precipitazione oraria è espressa in millimetri.
          🧭 «Da SO» indica vento proveniente da sud-ovest.
          Le ore notturne sono riconoscibili esclusivamente
          dallo sfondo blu.
        </div>
        """, height=120)

    except Exception as exc:
        st.error(f"❌ {exc}")

else:
    st.info("✏️ Scrivi un comune o una località della Calabria e premi **Aggiorna**.")
    st.caption("Fonte dati: ItaliaMeteo–ARPAE ICON-2I tramite Open-Meteo.")
