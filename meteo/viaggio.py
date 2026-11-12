# =============================================================================
# Calabria Meteo Lab - Viaggio: percorso, meteo lungo la strada, orario migliore
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# 1. Percorso stradale (OSRM su routing.openstreetmap.de, poi OSRM pubblico,
#    infine stima in linea d'aria).
# 2. Punti di controllo circa ogni 15 minuti di viaggio (al massimo 24).
# 3. Previsione ICON-2I in tutti i punti con una sola richiesta.
# 4. Per ogni partenza possibile (ogni 30 minuti) si calcola l'ora di
#    passaggio in ogni punto e il giudizio; il viaggio vale quanto il punto
#    peggiore. Consigliata la partenza migliore; a parità, la più presto.
# Soglie applicative, non criteri ufficiali di sicurezza stradale.

import math
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

from meteo.api import HTTP, _completa_con_riserva
from meteo.config import API_GEOCODING_URL, API_METEO_URL, FUSO_ORARIO, MODELLO_RISERVA, MODELLO_TERRESTRE
from meteo.localita import in_calabria, normalizza_comune

OTTIMO, BUONO, DISCRETO, SCONSIGLIATO = 0, 1, 2, 3
LIVELLI = {
    OTTIMO: ("🟢", "Ottimo"),
    BUONO: ("🟡", "Buono"),
    DISCRETO: ("🟠", "Discreto"),
    SCONSIGLIATO: ("🔴", "Sconsigliato"),
}

CODICI_TEMPORALE = {95, 96, 99}
CODICI_NEVE = {71, 73, 75, 77, 85, 86}
CODICI_NEBBIA = {45, 48}

MEZZI = {
    # chiave: (nome, icona, servizi OSRM da provare, velocità media in linea d'aria km/h)
    "auto": ("Auto", "🚗", ["https://routing.openstreetmap.de/routed-car/route/v1/driving",
                           "https://router.project-osrm.org/route/v1/driving"], 60),
    "moto": ("Moto", "🏍️", ["https://routing.openstreetmap.de/routed-car/route/v1/driving",
                           "https://router.project-osrm.org/route/v1/driving"], 60),
    "bici": ("Bici", "🚴", ["https://routing.openstreetmap.de/routed-bike/route/v1/driving"], 16),
}
FATTORE_DEVIAZIONE = 1.3      # strada reale ≈ 1,3 volte la linea d'aria
INTERVALLO_PUNTI_MIN = 15
MASSIMO_PUNTI = 24
PASSO_PARTENZE_MIN = 30

# Soglie (pioggia in mm/h, vento e raffiche in km/h, temperature in °C)
SOGLIE_VIAGGIO = {
    "comuni": {"ghiaccio_temperatura": 1.0, "ghiaccio_pioggia": 0.2},
    "auto": {"raffiche_sconsigliato": 90, "pioggia_discreto": 4.0, "raffiche_discreto": 70,
             "pioggia_buono": 1.0, "freddo_buono": 1.0},
    "moto": {"pioggia_sconsigliato": 2.0, "raffiche_sconsigliato": 60, "pioggia_discreto": 0.2,
             "vento_discreto": 35, "raffiche_discreto": 45, "freddo_discreto": 3.0, "freddo_buono": 8.0},
    "bici": {"pioggia_sconsigliato": 1.0, "raffiche_sconsigliato": 50, "caldo_sconsigliato": 35,
             "pioggia_discreto": 0.2, "vento_discreto": 25, "raffiche_discreto": 40,
             "percepita_discreto": (3, 32), "vento_buono": 15},
}

VARIABILI_VIAGGIO = [
    "temperature_2m", "apparent_temperature", "precipitation", "weather_code",
    "wind_speed_10m", "wind_gusts_10m", "is_day",
]


# -----------------------------------------------------------------------------
# Località (tutta Italia)
# -----------------------------------------------------------------------------

@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def geocodifica_italia(nome):
    """(nome, lat, lon, regione) di una località italiana, o errore se non trovata."""
    try:
        risposta = HTTP.get(
            API_GEOCODING_URL,
            params={"name": nome, "count": 10, "language": "it", "countryCode": "IT", "format": "json"},
            timeout=15,
        )
        risposta.raise_for_status()
        risultati = risposta.json().get("results", []) or []
    except requests.RequestException as exc:
        raise RuntimeError("Ricerca delle località non disponibile al momento. Riprova tra poco.") from exc

    if not risultati:
        raise ValueError(f"Località «{nome}» non trovata in Italia.")
    cercato = normalizza_comune(nome)
    migliore = next((r for r in risultati if normalizza_comune(r.get("name")) == cercato), risultati[0])
    return migliore["name"], float(migliore["latitude"]), float(migliore["longitude"]), migliore.get("admin1", "")


def e_in_calabria(regione, latitudine, longitudine):
    return "calabria" in str(regione).casefold() or in_calabria(latitudine, longitudine)


# -----------------------------------------------------------------------------
# Percorso
# -----------------------------------------------------------------------------

def distanza_km(a, b):
    raggio = 6371.0088
    phi1, phi2 = math.radians(a[0]), math.radians(b[0])
    dphi, dlam = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * raggio * math.asin(math.sqrt(h))


def _percorso_osrm(url_base, partenza, arrivo):
    url = f"{url_base}/{partenza[1]:.5f},{partenza[0]:.5f};{arrivo[1]:.5f},{arrivo[0]:.5f}"
    risposta = HTTP.get(url, params={"overview": "full", "geometries": "geojson", "steps": "true"}, timeout=20)
    risposta.raise_for_status()
    dati = risposta.json()
    if dati.get("code") != "Ok" or not dati.get("routes"):
        raise ValueError(dati.get("message", "percorso non trovato"))
    rotta = dati["routes"][0]
    passi, percorsi = [], 0.0
    for tratto in rotta.get("legs", []):
        for passo in tratto.get("steps", []):
            nome = " · ".join(x for x in (passo.get("ref"), passo.get("name")) if x)
            passi.append((percorsi, percorsi + float(passo.get("distance", 0)), nome))
            percorsi += float(passo.get("distance", 0))
    return {
        "coordinate": [(lat, lon) for lon, lat in rotta["geometry"]["coordinates"]],
        "distanza_km": float(rotta["distance"]) / 1000,
        "durata_min": float(rotta["duration"]) / 60,
        "passi": passi,
    }


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def calcola_percorso(partenza, arrivo, mezzo):
    """Percorso stradale; se i servizi non rispondono, stima in linea d'aria."""
    for url in MEZZI[mezzo][2]:
        try:
            percorso = _percorso_osrm(url, partenza, arrivo)
            percorso["fonte"] = "OpenStreetMap (OSRM)"
            percorso["stimato"] = False
            return percorso
        except (requests.RequestException, ValueError, KeyError, IndexError):
            continue

    km = distanza_km(partenza, arrivo) * FATTORE_DEVIAZIONE
    passi = 50
    return {
        "coordinate": [
            (partenza[0] + (arrivo[0] - partenza[0]) * i / passi, partenza[1] + (arrivo[1] - partenza[1]) * i / passi)
            for i in range(passi + 1)
        ],
        "distanza_km": km,
        "durata_min": km / MEZZI[mezzo][3] * 60,
        "passi": [],
        "fonte": "stima in linea d'aria (servizio percorsi non disponibile)",
        "stimato": True,
    }


def punti_di_controllo(percorso, intervallo_min=INTERVALLO_PUNTI_MIN, massimo=MASSIMO_PUNTI):
    """Punti lungo il percorso circa ogni 'intervallo_min' minuti di viaggio (partenza e arrivo inclusi)."""
    coordinate = percorso["coordinate"]
    cumulata = [0.0]
    for a, b in zip(coordinate, coordinate[1:]):
        cumulata.append(cumulata[-1] + distanza_km(a, b))
    lunghezza = cumulata[-1] or 1e-9
    durata = max(percorso["durata_min"], 1.0)

    numero = max(2, min(massimo, int(durata // intervallo_min) + 2))
    punti = []
    indice = 0
    for k in range(numero):
        frazione = k / (numero - 1)
        obiettivo = frazione * lunghezza
        while indice < len(cumulata) - 2 and cumulata[indice + 1] < obiettivo:
            indice += 1
        tratto = (cumulata[indice + 1] - cumulata[indice]) or 1e-9
        t = min(1.0, max(0.0, (obiettivo - cumulata[indice]) / tratto))
        a, b = coordinate[indice], coordinate[min(indice + 1, len(coordinate) - 1)]
        km = frazione * percorso["distanza_km"]
        punti.append({
            "lat": a[0] + (b[0] - a[0]) * t,
            "lon": a[1] + (b[1] - a[1]) * t,
            "km": km,
            "minuti": frazione * durata,
            "strada": _strada_al_km(percorso["passi"], km * 1000),
        })
    return punti


def _strada_al_km(passi, metri):
    for inizio, fine, nome in passi:
        if inizio <= metri <= fine and nome:
            return nome
    return ""


# -----------------------------------------------------------------------------
# Meteo nei punti
# -----------------------------------------------------------------------------

def _scarica_punti(parametri, modello):
    risposta = HTTP.get(API_METEO_URL, params={**parametri, "models": modello}, timeout=25)
    risposta.raise_for_status()
    dati = risposta.json()
    return dati if isinstance(dati, list) else [dati]


@st.cache_data(ttl=1800, show_spinner=False)
def meteo_nei_punti(coordinate):
    """Previsione oraria per ogni punto (tuple di (lat, lon) arrotondate)."""
    parametri = {
        "latitude": ",".join(f"{lat:.3f}" for lat, _ in coordinate),
        "longitude": ",".join(f"{lon:.3f}" for _, lon in coordinate),
        "timezone": "Europe/Rome",
        "forecast_days": 3,
        "wind_speed_unit": "kmh",
        "hourly": ",".join(VARIABILI_VIAGGIO),
    }
    try:
        principale = _scarica_punti(parametri, MODELLO_TERRESTRE)
    except requests.RequestException:
        principale = None

    mancano = principale is None or any(
        v is None for p in principale for k, valori in (p.get("hourly") or {}).items() if k != "time" for v in valori
    )
    if mancano:
        try:
            riserva = _scarica_punti(parametri, MODELLO_RISERVA)
        except requests.RequestException as exc:
            if principale is None:
                raise RuntimeError("Previsioni lungo il percorso non disponibili al momento. Riprova tra poco.") from exc
            riserva = None
        if principale is None:
            principale = riserva
        elif riserva:
            for p, r in zip(principale, riserva):
                _completa_con_riserva(p, r)

    tabelle = []
    for punto in principale:
        tabella = pd.DataFrame(punto["hourly"])
        tabella["time"] = pd.to_datetime(tabella["time"])
        tabelle.append({"quota": punto.get("elevation"), "orario": tabella.set_index("time")})
    return tabelle


# -----------------------------------------------------------------------------
# Giudizio
# -----------------------------------------------------------------------------

def _valore(riga, campo):
    try:
        v = float(riga.get(campo))
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def giudica_punto(mezzo, riga):
    """(livello, motivi) per il meteo di un'ora in un punto del percorso."""
    s, c = SOGLIE_VIAGGIO[mezzo], SOGLIE_VIAGGIO["comuni"]
    livello, motivi = OTTIMO, {}

    def abbassa(nuovo, motivo):
        nonlocal livello
        livello = max(livello, nuovo)
        motivi.setdefault(nuovo, [])
        if motivo not in motivi[nuovo]:
            motivi[nuovo].append(motivo)

    codice = _valore(riga, "weather_code")
    codice = int(codice) if codice is not None else None
    pioggia = _valore(riga, "precipitation") or 0.0
    vento = _valore(riga, "wind_speed_10m") or 0.0
    raffiche = _valore(riga, "wind_gusts_10m") or 0.0
    temperatura = _valore(riga, "temperature_2m")
    percepita = _valore(riga, "apparent_temperature")
    giorno = _valore(riga, "is_day")
    neve = codice in CODICI_NEVE
    nebbia = codice in CODICI_NEBBIA

    if codice in CODICI_TEMPORALE:
        abbassa(SCONSIGLIATO, "temporali")
    if neve:
        abbassa(SCONSIGLIATO, "neve")
    elif temperatura is not None and temperatura <= c["ghiaccio_temperatura"] and pioggia >= c["ghiaccio_pioggia"]:
        abbassa(SCONSIGLIATO, "rischio ghiaccio")

    if mezzo == "auto":
        if raffiche >= s["raffiche_sconsigliato"]:
            abbassa(SCONSIGLIATO, "raffiche fortissime")
        elif raffiche >= s["raffiche_discreto"]:
            abbassa(DISCRETO, "raffiche forti")
        if pioggia >= s["pioggia_discreto"]:
            abbassa(DISCRETO, "pioggia forte")
        elif pioggia >= s["pioggia_buono"]:
            abbassa(BUONO, "pioggia")
        if nebbia:
            abbassa(DISCRETO, "nebbia")
        if temperatura is not None and temperatura <= s["freddo_buono"] and pioggia < c["ghiaccio_pioggia"]:
            abbassa(BUONO, "possibile ghiaccio")

    elif mezzo == "moto":
        if pioggia >= s["pioggia_sconsigliato"]:
            abbassa(SCONSIGLIATO, "pioggia")
        elif pioggia >= s["pioggia_discreto"]:
            abbassa(DISCRETO, "pioggia")
        if raffiche >= s["raffiche_sconsigliato"]:
            abbassa(SCONSIGLIATO, "raffiche forti")
        elif raffiche >= s["raffiche_discreto"] or vento >= s["vento_discreto"]:
            abbassa(DISCRETO, "vento forte")
        if nebbia:
            abbassa(DISCRETO, "nebbia")
        if temperatura is not None:
            if temperatura <= s["freddo_discreto"]:
                abbassa(DISCRETO, "freddo")
            elif temperatura <= s["freddo_buono"]:
                abbassa(BUONO, "fresco")
        if giorno == 0:
            abbassa(BUONO, "buio")

    elif mezzo == "bici":
        if pioggia >= s["pioggia_sconsigliato"]:
            abbassa(SCONSIGLIATO, "pioggia")
        elif pioggia >= s["pioggia_discreto"]:
            abbassa(DISCRETO, "pioggia")
        if raffiche >= s["raffiche_sconsigliato"]:
            abbassa(SCONSIGLIATO, "raffiche forti")
        elif raffiche >= s["raffiche_discreto"] or vento >= s["vento_discreto"]:
            abbassa(DISCRETO, "vento forte")
        elif vento >= s["vento_buono"]:
            abbassa(BUONO, "vento")
        if percepita is not None:
            if percepita > s["caldo_sconsigliato"]:
                abbassa(SCONSIGLIATO, "caldo intenso")
            elif percepita < s["percepita_discreto"][0]:
                abbassa(DISCRETO, "freddo")
            elif percepita > s["percepita_discreto"][1]:
                abbassa(DISCRETO, "caldo")
        if nebbia:
            abbassa(DISCRETO, "nebbia")
        if giorno == 0:
            abbassa(BUONO, "buio")

    return livello, ", ".join(motivi.get(livello, [])) or "nessun problema"


def _riga_all_ora(orario, istante):
    """Riga oraria più vicina all'istante (None se fuori dalla previsione)."""
    ora = pd.Timestamp(istante).round("h")
    if ora not in orario.index:
        return None
    return orario.loc[ora]


def valuta_partenza(partenza, punti, meteo, mezzo):
    """Giudizio di ogni punto per una partenza; il viaggio vale quanto il punto peggiore."""
    tappe = []
    for punto, dati in zip(punti, meteo):
        passaggio = partenza + pd.Timedelta(minutes=punto["minuti"])
        riga = _riga_all_ora(dati["orario"], passaggio)
        if riga is None:
            tappe.append({**punto, "passaggio": passaggio, "quota": dati["quota"], "meteo": None,
                          "livello": None, "motivo": "previsione non disponibile"})
            continue
        livello, motivo = giudica_punto(mezzo, riga)
        tappe.append({**punto, "passaggio": passaggio, "quota": dati["quota"], "meteo": riga,
                      "livello": livello, "motivo": motivo})

    noti = [t for t in tappe if t["livello"] is not None]
    if not noti:
        return {"partenza": partenza, "arrivo": tappe[-1]["passaggio"], "livello": None, "tappe": tappe,
                "motivo": "previsione non disponibile", "dove": "", "completo": False}
    peggiore = max(noti, key=lambda t: t["livello"])
    return {
        "partenza": partenza,
        "arrivo": tappe[-1]["passaggio"],
        "livello": peggiore["livello"],
        "motivo": peggiore["motivo"],
        "dove": peggiore["strada"] or f"km {peggiore['km']:.0f}",
        "tappe": tappe,
        "completo": len(noti) == len(tappe),
    }


def partenze_possibili(giorno, ora_da, ora_a, adesso=None):
    """Orari di partenza ogni 30 minuti nella fascia scelta (per oggi solo da adesso in poi)."""
    adesso = adesso or pd.Timestamp(datetime.now(FUSO_ORARIO).replace(tzinfo=None))
    inizio = pd.Timestamp(giorno) + pd.Timedelta(hours=ora_da)
    fine = pd.Timestamp(giorno) + pd.Timedelta(hours=ora_a)
    if inizio < adesso:
        inizio = adesso.ceil(f"{PASSO_PARTENZE_MIN}min")
    if inizio > fine:
        return []
    return list(pd.date_range(inizio, fine, freq=f"{PASSO_PARTENZE_MIN}min"))


def consiglia(valutazioni):
    """Partenza consigliata: giudizio migliore; a parità la più presto. Solo previsioni complete."""
    candidate = [v for v in valutazioni if v["livello"] is not None and v["completo"]]
    if not candidate:
        return None
    return min(candidate, key=lambda v: (v["livello"], v["partenza"]))


def fasce_da_evitare(valutazioni):
    """Intervalli di partenze consecutive Sconsigliate, con il motivo prevalente."""
    fasce, corrente = [], []
    for v in valutazioni + [None]:
        if v is not None and v["livello"] == SCONSIGLIATO:
            corrente.append(v)
            continue
        if corrente:
            motivi = pd.Series([c["motivo"] for c in corrente]).mode()
            fasce.append((corrente[0]["partenza"], corrente[-1]["partenza"], motivi.iloc[0], corrente[0]["dove"]))
            corrente = []
    return fasce
