# =============================================================================
# Calabria Meteo Lab - Storico: osservazioni delle stazioni e previsioni passate
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Raccoglie, ora per ora e nei punti delle stazioni:
#   - osservazioni della rete della Protezione Civile in Calabria (MeteoHub,
#     ultimi 10 giorni pubblici, licenza CC BY 4.0) e, una tantum, l'archivio
#     orario delle stazioni sinottiche (Meteostat, solo misure; CC BY-NC 4.0):
#     temperatura, vento e raffiche (la pioggia oraria non è disponibile);
#   - previsioni passate di ICON-2I, ECMWF IFS, ICON-EU e AIFS (Open-Meteo,
#     "previous runs"): la corsa più recente (giorno 0), quella di 1 e di 2
#     giorni prima, per confrontare le previsioni alle varie scadenze.
#
# Cartella (nel ramo "dati"):
#   storico/stazioni.csv                 id, nome, rete, lat, lon, quota
#   storico/osservazioni/AAAA-MM.csv.gz  id, time (UTC), temperatura, pioggia, vento, raffica, umidita
#   storico/previsioni/AAAA-MM.csv.gz    id, time (UTC), modello, giorno, temperatura, pioggia, vento, raffica
#
# Uso:
#   python elaborazione/storico_calabria.py CARTELLA_STORICO               (giornaliero: ultimi 3 giorni)
#   python elaborazione/storico_calabria.py CARTELLA_STORICO --giorni 10   (recupero)
#   python elaborazione/storico_calabria.py CARTELLA_STORICO --meteostat --dal 2025-08-01

import argparse
import gzip
import io
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

METEOHUB = "https://meteohub.agenziaitaliameteo.it/api/observations"
RETE_DPC = "dpcn-calabria"
METEOSTAT_BULK = "https://bulk.meteostat.net/v2/hourly/obs/{}.csv.gz"   # solo misure, niente dati di modello
PREVIOUS_RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"

# Stazioni sinottiche in Calabria (e Messina, utile per lo Stretto)
STAZIONI_METEOSTAT = {
    "16337": ("Bonifati", 39.58, 15.88, 484),
    "16344": ("Monte Scuro", 39.33, 16.40, 1710),
    "16350": ("Crotone", 39.00, 17.07, 155),
    "16362": ("Lamezia Terme", 38.90, 16.25, 15),
    "16364": ("Serralta di San Vito", 38.76, 16.37, 996),
    "16420": ("Messina", 38.20, 15.55, 59),
    "16422": ("Reggio Calabria", 38.07, 15.65, 11),
}

# Modelli di Open-Meteo confrontati con le stazioni (nome nell'app -> nome API)
MODELLI = {
    "ICON-2I": "italia_meteo_arpae_icon_2i",
    "ECMWF IFS": "ecmwf_ifs025",
    "ICON-EU": "icon_eu",
    "AIFS": "ecmwf_aifs025_single",
}
VARIABILI = {"temperatura": "temperature_2m", "pioggia": "precipitation",
             "vento": "wind_speed_10m", "raffica": "wind_gusts_10m"}
GIORNI_PRECEDENTI = (0, 1, 2)
PUNTI_PER_RICHIESTA = 40

COLONNE_OSS = ["id", "time", "temperatura", "pioggia", "vento", "raffica", "umidita"]
COLONNE_PREV = ["id", "time", "modello", "giorno", "temperatura", "pioggia", "vento", "raffica"]
LIMITI = {"temperatura": (-30, 50), "pioggia": (0, 200), "vento": (0, 250), "raffica": (0, 300), "umidita": (1, 100)}


def _get(url, tentativi=4, **opzioni):
    ultimo = None
    for tentativo in range(tentativi):
        try:
            risposta = requests.get(url, timeout=(20, 300), **opzioni)
            if risposta.status_code == 429:
                raise requests.HTTPError("429: limite di richieste")
            risposta.raise_for_status()
            return risposta
        except requests.RequestException as errore:
            ultimo = errore
            time.sleep(10 * (tentativo + 1))
    raise RuntimeError(f"{url}: {ultimo}")


def id_stazione(nome, rete):
    pulito = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    return f"{'dpc' if rete == RETE_DPC else rete}-{pulito}"


# -----------------------------------------------------------------------------
# Archivio su file (un file compresso per mese, aggiornato senza duplicati)
# -----------------------------------------------------------------------------

def leggi_mesi(cartella, colonne):
    file = sorted(Path(cartella).glob("*.csv.gz"))
    if not file:
        return pd.DataFrame(columns=colonne)
    return pd.concat([pd.read_csv(f, parse_dates=["time"]) for f in file], ignore_index=True)


def aggiorna_mesi(cartella, nuovi, chiavi):
    """Unisce i nuovi dati a quelli dei mesi interessati (i nuovi vincono) e riscrive i file."""
    if nuovi.empty:
        return 0
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    nuovi = nuovi.copy()
    nuovi["time"] = pd.to_datetime(nuovi["time"])
    for mese, parte in nuovi.groupby(nuovi["time"].dt.strftime("%Y-%m")):
        percorso = cartella / f"{mese}.csv.gz"
        if percorso.exists():
            vecchi = pd.read_csv(percorso, parse_dates=["time"])
            parte = pd.concat([vecchi, parte], ignore_index=True)
        parte = parte.drop_duplicates(subset=chiavi, keep="last").sort_values(chiavi)
        with gzip.open(percorso, "wt", compresslevel=9) as f:
            parte.to_csv(f, index=False, float_format="%.1f", date_format="%Y-%m-%dT%H:%M")
    return len(nuovi)


def leggi_stazioni(cartella):
    percorso = Path(cartella) / "stazioni.csv"
    if percorso.exists():
        return pd.read_csv(percorso, dtype={"id": str})
    return pd.DataFrame(columns=["id", "nome", "rete", "lat", "lon", "quota"])


def scrivi_stazioni(cartella, stazioni):
    Path(cartella).mkdir(parents=True, exist_ok=True)
    stazioni.drop_duplicates("id", keep="last").sort_values("id").to_csv(Path(cartella) / "stazioni.csv", index=False)


# -----------------------------------------------------------------------------
# Osservazioni della Protezione Civile (MeteoHub)
# -----------------------------------------------------------------------------

def _richiesta_dpc(inizio, fine, prodotti=None, **altro):
    q = f"reftime: >={inizio:%Y-%m-%d %H:%M},<={fine:%Y-%m-%d %H:%M};license:CCBY_COMPLIANT"
    if prodotti:
        q += ";product:" + " or ".join(prodotti)
    return _get(METEOHUB, params={"networks": RETE_DPC, "q": q, **altro}).json()


def quota_stazione_dpc(lat, lon, giorno):
    """Quota della stazione (una richiesta per stazione, fatta una sola volta)."""
    try:
        dati = _richiesta_dpc(giorno, giorno + timedelta(hours=1), ["B12101", "B13011"], lat=lat, lon=lon,
                              allStationProducts="true", stationDetails="true")
        for voce in dati["data"][0]["stat"].get("details", []):
            if voce["var"] == "B07030":
                return float(voce["val"])
    except (RuntimeError, KeyError, IndexError, TypeError, ValueError):
        pass
    return np.nan


def _serie(prodotto):
    valori = [v for v in prodotto.get("val", []) if v.get("rel", 1) == 1 and v.get("val") is not None]
    if not valori:
        return pd.Series(dtype=float)
    serie = pd.Series([float(v["val"]) for v in valori], index=pd.to_datetime([v["ref"] for v in valori]))
    return serie[~serie.index.duplicated()].sort_index()


def orarie_da_prodotti(prodotti):
    """Valori orari (UTC) da tutti i prodotti di una stazione.

    - temperatura e umidità: media dei valori tra 10 minuti prima e 10 minuti dopo l'ora;
    - vento: media tra mezz'ora prima e mezz'ora dopo;
    - raffica: massimo dell'ora precedente;
    - pioggia: somma dell'ora precedente (almeno l'80% dell'ora coperto da misure).
    """
    colonne = {}
    for p in prodotti:
        serie = _serie(p)
        if serie.empty:
            continue
        var, trange = p["var"], p.get("trange", "")
        if var == "B12101":
            serie = serie - 273.15
            colonne["temperatura"] = serie.resample("20min", origin="epoch", offset="-10min").mean()
        elif var == "B13003":
            colonne["umidita"] = serie.resample("20min", origin="epoch", offset="-10min").mean()
        elif var == "B11002":
            colonne["vento"] = serie.resample("1h", origin="epoch", offset="-30min").mean() * 3.6
        elif var == "B11041":
            colonne["raffica"] = serie.resample("1h", closed="right", label="right").max() * 3.6
        elif var == "B13011" and trange.startswith("1,"):
            durata_s = float(trange.split(",")[2] or 0)
            if durata_s <= 0 or durata_s > 3600:
                continue
            somma = serie.resample("1h", closed="right", label="right").sum()
            copertura = serie.resample("1h", closed="right", label="right").count() * durata_s / 3600
            colonne["pioggia"] = somma.where(copertura >= 0.8)
    if not colonne:
        return pd.DataFrame()
    tabella = {}
    for nome, serie in colonne.items():
        if nome in ("temperatura", "umidita"):
            # finestre di 20 minuti centrate sull'ora: si tengono quelle che iniziano a hh:50
            serie = serie[(serie.index + pd.Timedelta(minutes=10)).minute == 0]
            serie.index = serie.index + pd.Timedelta(minutes=10)
        elif nome == "vento":
            serie.index = serie.index + pd.Timedelta(minutes=30)
        tabella[nome] = serie
    risultato = pd.DataFrame(tabella)
    risultato = risultato[risultato.index.minute == 0]
    for nome, (minimo, massimo) in LIMITI.items():
        if nome in risultato:
            risultato.loc[(risultato[nome] < minimo) | (risultato[nome] > massimo), nome] = np.nan
    return risultato.dropna(how="all")


def osservazioni_dpc(cartella, giorni):
    """Osservazioni orarie della rete della Protezione Civile degli ultimi 'giorni' giorni."""
    stazioni = leggi_stazioni(cartella)
    oggi = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    righe, nuove_stazioni = [], []
    for k in range(giorni, -1, -1):
        inizio = (oggi - timedelta(days=k)).replace(hour=0) - timedelta(hours=1)
        fine = min(inizio + timedelta(hours=24, minutes=59), oggi)
        if inizio >= fine:
            continue
        try:
            dati = _richiesta_dpc(inizio, fine, ["B12101", "B13011", "B11002", "B11041", "B13003"])
        except RuntimeError as errore:
            print(f"  osservazioni {inizio:%d/%m}: {errore}", file=sys.stderr)
            continue
        if not isinstance(dati, dict):
            print(f"  osservazioni {inizio:%d/%m}: {dati}", file=sys.stderr)
            continue
        for voce in dati.get("data", []):
            stat = voce["stat"]
            nome = next((d["val"] for d in stat.get("details", []) if d["var"] == "B01019"), None)
            if not nome:
                continue
            ident = id_stazione(nome, RETE_DPC)
            nuove_stazioni.append({"id": ident, "nome": nome, "rete": RETE_DPC, "lat": stat["lat"], "lon": stat["lon"]})
            orarie = orarie_da_prodotti(voce.get("prod", []))
            orarie = orarie[(orarie.index > inizio) & (orarie.index <= inizio + timedelta(hours=24))]
            if not orarie.empty:
                orarie.insert(0, "id", ident)
                righe.append(orarie.rename_axis("time").reset_index())
        print(f"  osservazioni del {inizio + timedelta(hours=1):%d/%m}: {len(dati.get('data', []))} stazioni")

    # Nuove stazioni: quota (una volta sola)
    nuove = pd.DataFrame(nuove_stazioni).drop_duplicates("id") if nuove_stazioni else pd.DataFrame()
    if not nuove.empty:
        note = set(stazioni["id"])
        da_aggiungere = nuove[~nuove["id"].isin(note)].copy()
        if not da_aggiungere.empty:
            giorno = oggi - timedelta(days=1)
            da_aggiungere["quota"] = [quota_stazione_dpc(r.lat, r.lon, giorno) for r in da_aggiungere.itertuples()]
            stazioni = pd.concat([stazioni, da_aggiungere], ignore_index=True)
            scrivi_stazioni(cartella, stazioni)
            print(f"  {len(da_aggiungere)} nuove stazioni")
    osservazioni = pd.concat(righe, ignore_index=True) if righe else pd.DataFrame(columns=COLONNE_OSS)
    return osservazioni.reindex(columns=COLONNE_OSS)


# -----------------------------------------------------------------------------
# Osservazioni Meteostat (archivio orario delle stazioni sinottiche)
# -----------------------------------------------------------------------------

def osservazioni_meteostat(cartella, dal):
    stazioni = leggi_stazioni(cartella)
    righe = []
    for codice, (nome, lat, lon, quota) in STAZIONI_METEOSTAT.items():
        try:
            grezzo = _get(METEOSTAT_BULK.format(codice)).content
        except RuntimeError as errore:
            print(f"  Meteostat {nome}: {errore}", file=sys.stderr)
            continue
        d = pd.read_csv(io.BytesIO(gzip.decompress(grezzo)), header=None,
                        names="date hour temp dwpt rhum prcp snow wdir wspd wpgt pres tsun coco".split())
        d["time"] = pd.to_datetime(d["date"]) + pd.to_timedelta(d["hour"], unit="h")
        d = d[d["time"] >= pd.Timestamp(dal)]
        if d.empty:
            continue
        ident = f"meteostat-{codice}"
        righe.append(pd.DataFrame({"id": ident, "time": d["time"], "temperatura": d["temp"], "pioggia": np.nan,
                                   "vento": d["wspd"], "raffica": d["wpgt"], "umidita": d["rhum"]}))
        stazioni = pd.concat([stazioni, pd.DataFrame([{"id": ident, "nome": nome, "rete": "meteostat",
                                                       "lat": lat, "lon": lon, "quota": quota}])], ignore_index=True)
        print(f"  Meteostat {nome}: {len(d)} ore ({d['time'].min():%d/%m/%Y} - {d['time'].max():%d/%m/%Y})")
    scrivi_stazioni(cartella, stazioni)
    return pd.concat(righe, ignore_index=True) if righe else pd.DataFrame(columns=COLONNE_OSS)


# -----------------------------------------------------------------------------
# Previsioni passate (Open-Meteo, previous runs)
# -----------------------------------------------------------------------------

def previsioni_passate(stazioni, inizio, fine):
    """Previsioni orarie dei 4 modelli nei punti delle stazioni, per i giorni da 'inizio' a 'fine'."""
    orarie = [f"{v}{'' if g == 0 else f'_previous_day{g}'}" for v in VARIABILI.values() for g in GIORNI_PRECEDENTI]
    righe = []
    for modello, nome_api in MODELLI.items():
        for k in range(0, len(stazioni), PUNTI_PER_RICHIESTA):
            gruppo = stazioni.iloc[k:k + PUNTI_PER_RICHIESTA]
            try:
                dati = _get(PREVIOUS_RUNS, params={
                    "latitude": ",".join(f"{x:.4f}" for x in gruppo["lat"]),
                    "longitude": ",".join(f"{x:.4f}" for x in gruppo["lon"]),
                    "models": nome_api, "hourly": ",".join(orarie), "timezone": "GMT",
                    "start_date": f"{inizio:%Y-%m-%d}", "end_date": f"{fine:%Y-%m-%d}",
                    "wind_speed_unit": "kmh",
                }).json()
            except RuntimeError as errore:
                print(f"  previsioni {modello}: {errore}", file=sys.stderr)
                continue
            dati = dati if isinstance(dati, list) else [dati]
            for stazione, punto in zip(gruppo.itertuples(), dati):
                h = punto.get("hourly") or {}
                if not h.get("time"):
                    continue
                tempi = pd.to_datetime(h["time"])
                for g in GIORNI_PRECEDENTI:
                    suffisso = "" if g == 0 else f"_previous_day{g}"
                    tabella = pd.DataFrame({nome: pd.to_numeric(pd.Series(h.get(v + suffisso)), errors="coerce")
                                            for nome, v in VARIABILI.items()})
                    tabella.insert(0, "time", tempi)
                    tabella = tabella.dropna(subset=list(VARIABILI), how="all")
                    if tabella.empty:
                        continue
                    tabella.insert(0, "giorno", g)
                    tabella.insert(0, "modello", modello)
                    tabella.insert(0, "id", stazione.id)
                    righe.append(tabella)
            time.sleep(1)
        print(f"  previsioni {modello}: fatto")
    if not righe:
        return pd.DataFrame(columns=COLONNE_PREV)
    return pd.concat(righe, ignore_index=True).reindex(columns=COLONNE_PREV)


def main():
    argomenti = argparse.ArgumentParser()
    argomenti.add_argument("cartella")
    argomenti.add_argument("--giorni", type=int, default=3, help="giorni di osservazioni della Protezione Civile")
    argomenti.add_argument("--meteostat", action="store_true", help="importa l'archivio Meteostat")
    argomenti.add_argument("--dal", default="2025-08-01", help="inizio dell'archivio Meteostat")
    a = argomenti.parse_args()
    cartella = Path(a.cartella)
    oggi = datetime.now(timezone.utc).date()

    print("Osservazioni della Protezione Civile")
    dpc = osservazioni_dpc(cartella, a.giorni)
    print(f"  {aggiorna_mesi(cartella / 'osservazioni', dpc, ['id', 'time'])} ore-stazione scritte")

    stazioni = leggi_stazioni(cartella)
    if a.meteostat:
        print("Archivio Meteostat")
        ms = osservazioni_meteostat(cartella, a.dal)
        aggiorna_mesi(cartella / "osservazioni", ms, ["id", "time"])
        stazioni = leggi_stazioni(cartella)
        print("Previsioni passate per le stazioni Meteostat")
        sinottiche = stazioni[stazioni["rete"] == "meteostat"]
        fine_ms = ms["time"].max().date() if not ms.empty else oggi
        for inizio in pd.date_range(a.dal, fine_ms, freq="30D"):
            fine = min(inizio + pd.Timedelta(days=29), pd.Timestamp(fine_ms))
            prev = previsioni_passate(sinottiche, inizio, fine)
            aggiorna_mesi(cartella / "previsioni", prev, ["id", "time", "modello", "giorno"])

    print("Previsioni passate per le stazioni della Protezione Civile")
    dpc_stazioni = stazioni[stazioni["rete"] == RETE_DPC]
    prev = previsioni_passate(dpc_stazioni, oggi - timedelta(days=a.giorni), oggi)
    print(f"  {aggiorna_mesi(cartella / 'previsioni', prev, ['id', 'time', 'modello', 'giorno'])} righe scritte")
    return 0


if __name__ == "__main__":
    sys.exit(main())
