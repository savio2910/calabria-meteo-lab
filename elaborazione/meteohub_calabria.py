# =============================================================================
# Calabria Meteo Lab - Elaborazione giornaliera dei modelli MeteoHub
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Scarica le ultime corse di MOLOCH, WRF (ItaliaMeteo e CIMA) e BOLAM dai dati
# aperti di MeteoHub (Agenzia ItaliaMeteo), le legge mentre arrivano (i file
# sono di centinaia di MB e non vengono salvati) e tiene solo la Calabria:
#
#   ultima.bin   una griglia regolare di 0,02° (circa 2 km): per ogni punto,
#                tutti i modelli e tutte le ore, in interi a 16 bit. L'app
#                legge solo i byte del suo punto (richiesta HTTP "Range").
#   ultima.json  descrizione del file: griglia, modelli, corse, variabili.
#   storico/AAAA-MM-GG.npz  la stessa previsione su una griglia di 0,1°,
#                conservata ogni giorno per il confronto con le osservazioni.
#
# Uso:  python elaborazione/meteohub_calabria.py CARTELLA_DATI
#
# Dati: ItaliaMeteo, CNR-ISAC, Fondazione CIMA, LaMMA (licenze CC BY / CC BY-SA).

import json
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import eccodes
import numpy as np
import requests
from scipy.spatial import cKDTree

API = "https://meteohub.agenziaitaliameteo.it/api"

# nome mostrato nell'app -> dataset MeteoHub
MODELLI = {
    "MOLOCH": "MOLOCH",
    "WRF ItaliaMeteo": "WRF",
    "WRF CIMA": "WRF_OL",
    "BOLAM": "BOLAM",
}

# Griglia regolare sulla Calabria (un po' di margine sul mare)
LAT0, LON0, PASSO = 37.86, 15.56, 0.02
NY, NX = 118, 86                    # fino a 40,20 N e 17,26 E
PASSO_STORICO = 5                   # un punto ogni 5 = 0,1°

# Variabili in uscita: nome (come Open-Meteo), scala, scarto (valore = intero / scala + scarto)
VARIABILI = {
    "temperature_2m": (10, 0),
    "relative_humidity_2m": (1, 0),
    "wind_speed_10m": (10, 0),
    "wind_direction_10m": (1, 0),
    "precipitation": (10, 0),
    "cloud_cover": (1, 0),
    "pressure_msl": (10, 1000),
}
MANCANTE = -32768
CAMPI_LETTI = {"2t", "2d", "10u", "10v", "tp", "clct", "prmsl"}
ATTRIBUZIONE = ("Modelli MOLOCH e BOLAM (CNR-ISAC), WRF (ItaliaMeteo, Fondazione CIMA, LaMMA) "
                "dai dati aperti di MeteoHub - Agenzia ItaliaMeteo")


# -----------------------------------------------------------------------------
# Rete
# -----------------------------------------------------------------------------

def _get(url, **opzioni):
    ultimo = None
    for tentativo in range(4):
        try:
            risposta = requests.get(url, timeout=(20, 120), **opzioni)
            risposta.raise_for_status()
            return risposta
        except requests.RequestException as errore:
            ultimo = errore
            time.sleep(5 * (tentativo + 1))
    raise RuntimeError(f"{url}: {ultimo}")


def ultima_corsa(dataset):
    """(nome del file, istante della corsa in UTC) dell'ultima corsa pubblicata."""
    elenco = _get(f"{API}/datasets/{dataset}/opendata").json()
    if not elenco:
        raise RuntimeError(f"{dataset}: nessun file aperto")
    voce = max(elenco, key=lambda v: (v["date"], v["run"]))
    corsa = datetime.strptime(f"{voce['date']} {voce['run']}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    return voce["filename"], corsa


def messaggi_grib(url):
    """Messaggi GRIB uno alla volta mentre il file viene scaricato."""
    with requests.get(url, stream=True, timeout=(20, 300)) as risposta:
        risposta.raise_for_status()
        flusso = risposta.raw
        flusso.decode_content = True

        def leggi(n):
            parti, mancano = [], n
            while mancano:
                pezzo = flusso.read(mancano)
                if not pezzo:
                    break
                parti.append(pezzo)
                mancano -= len(pezzo)
            return b"".join(parti)

        while True:
            testa = leggi(16)
            if len(testa) < 16:
                return
            if testa[:4] != b"GRIB":
                raise RuntimeError("file GRIB non valido")
            lunghezza = int.from_bytes(testa[8:16], "big") if testa[7] == 2 else int.from_bytes(testa[4:7], "big")
            corpo = leggi(lunghezza - 16)
            if len(corpo) < lunghezza - 16:
                raise RuntimeError("file GRIB troncato")
            yield testa + corpo


# -----------------------------------------------------------------------------
# Griglie
# -----------------------------------------------------------------------------

def punti_griglia():
    lat = LAT0 + PASSO * np.arange(NY)
    lon = LON0 + PASSO * np.arange(NX)
    return np.meshgrid(lat, lon, indexing="ij")


class Interpolatore:
    """Punto del modello più vicino a ogni punto della griglia della Calabria, e rotazione del vento."""

    def __init__(self, h):
        lat = eccodes.codes_get_array(h, "latitudes")
        lon = eccodes.codes_get_array(h, "longitudes")
        lon = np.where(lon > 180, lon - 360, lon)
        ni = eccodes.codes_get(h, "Ni")
        coseno = math.cos(math.radians(39.0))
        vicini = np.where((lat > LAT0 - 0.3) & (lat < LAT0 + NY * PASSO + 0.3)
                          & (lon > LON0 - 0.3) & (lon < LON0 + NX * PASSO + 0.3))[0]
        if len(vicini) == 0:
            raise RuntimeError("la griglia del modello non copre la Calabria")
        albero = cKDTree(np.column_stack([lat[vicini], lon[vicini] * coseno]))
        glat, glon = punti_griglia()
        distanza, posizione = albero.query(np.column_stack([glat.ravel(), glon.ravel() * coseno]))
        self.indici = vicini[posizione]
        self.lontani = distanza > 0.15        # fuori dal dominio del modello

        # Angolo dell'asse x della griglia rispetto all'est (per il vento riferito alla griglia)
        self.ruota = eccodes.codes_get(h, "uvRelativeToGrid") == 1
        if self.ruota:
            accanto = np.where(self.indici % ni == ni - 1, self.indici - 1, self.indici + 1)
            segno = np.where(self.indici % ni == ni - 1, -1.0, 1.0)
            dlat = (lat[accanto] - lat[self.indici]) * segno
            dlon = (lon[accanto] - lon[self.indici]) * segno * np.cos(np.radians(lat[self.indici]))
            self.alfa = np.arctan2(dlat, dlon)

    def valori(self, h):
        valori = eccodes.codes_get_array(h, "values")[self.indici].astype(float)
        mancante = eccodes.codes_get(h, "missingValue") if eccodes.codes_is_defined(h, "missingValue") else None
        if mancante is not None and eccodes.codes_get(h, "bitmapPresent"):
            valori[valori == mancante] = np.nan
        valori[self.lontani] = np.nan
        return valori


# -----------------------------------------------------------------------------
# Lettura di un modello
# -----------------------------------------------------------------------------

def umidita_relativa(temperatura_c, rugiada_c):
    def pressione_vapore(t):
        return 6.112 * np.exp(17.62 * t / (243.12 + t))
    return np.clip(100 * pressione_vapore(rugiada_c) / pressione_vapore(temperatura_c), 0, 100)


def leggi_modello(dataset):
    """{"corsa": datetime, "file": nome, "ore": H, "campi": {variabile: array (H, NY*NX)}}."""
    nome_file, corsa = ultima_corsa(dataset)
    interpolatori = {}
    grezzi = {}         # (campo, ora) -> (dimensione griglia, valori)
    for messaggio in messaggi_grib(f"{API}/opendata/{nome_file}"):
        h = eccodes.codes_new_from_message(messaggio)
        try:
            campo = eccodes.codes_get(h, "shortName")
            if campo not in CAMPI_LETTI:
                continue
            eccodes.codes_set(h, "stepUnits", 1)
            ora = int(eccodes.codes_get(h, "endStep"))
            data = str(eccodes.codes_get(h, "dataDate"))
            ora_corsa = int(eccodes.codes_get(h, "dataTime"))
            inizio = datetime.strptime(data, "%Y%m%d").replace(
                hour=ora_corsa // 100, minute=ora_corsa % 100, tzinfo=timezone.utc)
            if inizio != corsa:     # corsa diversa da quella dichiarata: si usa quella del file
                corsa = inizio
            chiave_griglia = (eccodes.codes_get(h, "gridType"), eccodes.codes_get(h, "Ni"), eccodes.codes_get(h, "Nj"))
            if chiave_griglia not in interpolatori:
                interpolatori[chiave_griglia] = Interpolatore(h)
            dimensione = chiave_griglia[1] * chiave_griglia[2]
            precedente = grezzi.get((campo, ora))
            if precedente is None or dimensione > precedente[0]:   # si tiene la griglia più fine
                grezzi[(campo, ora)] = (dimensione, chiave_griglia, interpolatori[chiave_griglia].valori(h))
        finally:
            eccodes.codes_release(h)

    if not grezzi:
        raise RuntimeError(f"{dataset}: nessun campo utile")
    ore = max(ora for _, ora in grezzi) + 1
    punti = NY * NX

    def serie(campo):
        matrice = np.full((ore, punti), np.nan)
        presente = False
        for ora in range(ore):
            if (campo, ora) in grezzi:
                matrice[ora] = grezzi[(campo, ora)][2]
                presente = True
        return matrice if presente else None

    campi = {}
    t2 = serie("2t")
    if t2 is not None:
        campi["temperature_2m"] = t2 - 273.15
        d2 = serie("2d")
        if d2 is not None:
            campi["relative_humidity_2m"] = umidita_relativa(t2 - 273.15, d2 - 273.15)
    u, v = serie("10u"), serie("10v")
    if u is not None and v is not None:
        for ora in range(ore):
            voce = grezzi.get(("10u", ora))
            if voce is not None and interpolatori[voce[1]].ruota:
                alfa = interpolatori[voce[1]].alfa
                u[ora], v[ora] = (u[ora] * np.cos(alfa) - v[ora] * np.sin(alfa),
                                  u[ora] * np.sin(alfa) + v[ora] * np.cos(alfa))
        campi["wind_speed_10m"] = np.hypot(u, v) * 3.6
        campi["wind_direction_10m"] = (np.degrees(np.arctan2(-u, -v)) + 360) % 360
    tp = serie("tp")
    if tp is not None:
        campi["precipitation"] = np.clip(tp, 0, None)    # pioggia nell'ora che finisce all'ora indicata
    clct = serie("clct")
    if clct is not None:
        campi["cloud_cover"] = np.clip(clct * (100 if np.nanmax(clct) <= 1.01 else 1), 0, 100)
    prmsl = serie("prmsl")
    if prmsl is not None:
        campi["pressure_msl"] = prmsl / 100
    return {"corsa": corsa, "file": nome_file, "ore": ore, "campi": campi}


# -----------------------------------------------------------------------------
# Scrittura
# -----------------------------------------------------------------------------

def in_interi(valori, variabile):
    scala, scarto = VARIABILI[variabile]
    interi = np.round((valori - scarto) * scala)
    interi = np.where(np.isnan(interi), MANCANTE, np.clip(interi, -32767, 32767))
    return interi.astype("<i2")


def blocco_modello(modello):
    """Array (punti, variabili, ore) di interi e l'elenco delle variabili."""
    variabili = [v for v in VARIABILI if v in modello["campi"]]
    blocco = np.stack([in_interi(modello["campi"][v], v).T for v in variabili], axis=1)
    return blocco, variabili


def leggi_precedente(cartella):
    """Blocchi dei modelli dall'ultima elaborazione (per riusarli se un modello non risponde)."""
    try:
        indice = json.loads((cartella / "ultima.json").read_text())
        grezzo = np.fromfile(cartella / "ultima.bin", dtype="<i2")
    except (OSError, ValueError):
        return {}
    g = indice["griglia"]
    if (g["lat0"], g["lon0"], g["passo"], g["ny"], g["nx"]) != (LAT0, LON0, PASSO, NY, NX):
        return {}
    record = grezzo.reshape(NY * NX, indice["byte_per_punto"] // 2)
    blocchi = {}
    for m in indice["modelli"]:
        inizio = m["inizio_byte"] // 2
        n = len(m["variabili"]) * m["ore"]
        blocchi[m["nome"]] = (m, record[:, inizio:inizio + n].reshape(NY * NX, len(m["variabili"]), m["ore"]))
    return blocchi


def scrivi(cartella, risultati, oggi):
    cartella.mkdir(parents=True, exist_ok=True)
    versione = int(time.time() // 60) % 2_000_000_000
    blocchi, descrizioni, posizione = [], [], 4      # il record inizia con la versione (int32)
    for nome, dati in risultati.items():
        blocco, variabili = dati["blocco"], dati["variabili"]
        descrizioni.append({
            "nome": nome, "dataset": MODELLI[nome], "corsa": dati["corsa"],
            "ore": int(blocco.shape[2]), "variabili": variabili,
            "scale": {v: VARIABILI[v] for v in variabili},
            "inizio_byte": posizione, "elaborato": dati["elaborato"],
        })
        posizione += blocco.shape[1] * blocco.shape[2] * 2
        blocchi.append(blocco.reshape(NY * NX, -1))
    testa = np.full((NY * NX, 2), 0, dtype="<i2")
    testa.view("<i4")[:, 0] = versione
    record = np.concatenate([testa] + blocchi, axis=1).astype("<i2")
    (cartella / "ultima.bin.tmp").write_bytes(record.tobytes())
    (cartella / "ultima.bin.tmp").replace(cartella / "ultima.bin")
    indice = {
        "versione": versione,
        "creato": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "griglia": {"lat0": LAT0, "lon0": LON0, "passo": PASSO, "ny": NY, "nx": NX},
        "byte_per_punto": int(record.shape[1] * 2),
        "mancante": MANCANTE,
        "modelli": descrizioni,
        "attribuzione": ATTRIBUZIONE,
    }
    (cartella / "ultima.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1))

    # Storico su griglia di 0,1°
    righe = np.arange(0, NY, PASSO_STORICO)
    colonne = np.arange(0, NX, PASSO_STORICO)
    scelti = (righe[:, None] * NX + colonne[None, :]).ravel()
    archivio = {}
    for d, blocco in zip(descrizioni, (r["blocco"] for r in risultati.values())):
        for k, v in enumerate(d["variabili"]):
            archivio[f"{d['nome']}|{v}"] = blocco[scelti, k, :].T.reshape(d["ore"], len(righe), len(colonne))
    meta = {**indice, "griglia": {"lat0": LAT0, "lon0": LON0, "passo": PASSO * PASSO_STORICO,
                                  "ny": len(righe), "nx": len(colonne)}}
    meta.pop("byte_per_punto")
    cartella_storico = cartella / "storico" / oggi[:4]
    cartella_storico.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cartella_storico / f"{oggi}.npz", indice=np.array(json.dumps(meta)), **archivio)
    return indice


def previsioni_nelle_stazioni(cartella_storico, risultati):
    """Aggiunge allo storico le previsioni dei modelli MeteoHub nei punti delle stazioni
    (punto di griglia più vicino), per poterli tarare come gli altri modelli."""
    percorso = Path(cartella_storico) / "stazioni.csv"
    if not percorso.exists():
        return 0
    import pandas as pd
    sys.path.insert(0, str(Path(__file__).parent))
    from storico_calabria import COLONNE_PREV, aggiorna_mesi

    stazioni = pd.read_csv(percorso)
    righe_griglia = np.rint((stazioni["lat"].to_numpy() - LAT0) / PASSO).astype(int)
    colonne_griglia = np.rint((stazioni["lon"].to_numpy() - LON0) / PASSO).astype(int)
    dentro = (righe_griglia >= 0) & (righe_griglia < NY) & (colonne_griglia >= 0) & (colonne_griglia < NX)
    stazioni, punti = stazioni[dentro], (righe_griglia * NX + colonne_griglia)[dentro]
    nomi = {"temperature_2m": "temperatura", "precipitation": "pioggia", "wind_speed_10m": "vento"}
    tabelle = []
    for nome, dati in risultati.items():
        corsa = pd.Timestamp(dati["corsa"]).tz_convert("UTC").tz_localize(None)
        blocco, variabili = dati["blocco"], dati["variabili"]
        ore = blocco.shape[2]
        tempi = corsa + pd.to_timedelta(np.arange(ore), unit="h")
        for ident, punto in zip(stazioni["id"], punti):
            colonne = {}
            for k, variabile in enumerate(variabili):
                if variabile in nomi:
                    interi = blocco[punto, k, :].astype(float)
                    interi[interi == MANCANTE] = np.nan
                    scala, scarto = VARIABILI[variabile]
                    colonne[nomi[variabile]] = interi / scala + scarto
            t = pd.DataFrame({"id": ident, "time": tempi, "modello": nome,
                              "giorno": (np.arange(ore) // 24).clip(0, 2), **colonne})
            tabelle.append(t[t["time"] > corsa])
    if not tabelle:
        return 0
    nuove = pd.concat(tabelle, ignore_index=True).reindex(columns=COLONNE_PREV)
    return aggiorna_mesi(Path(cartella_storico) / "previsioni", nuove, ["id", "time", "modello", "giorno"])


def main(cartella):
    cartella = Path(cartella)
    precedenti = leggi_precedente(cartella)
    risultati, errori = {}, []
    for nome, dataset in MODELLI.items():
        try:
            nome_file, corsa = ultima_corsa(dataset)
            vecchio = precedenti.get(nome)
            if vecchio and vecchio[0]["corsa"] == corsa.isoformat():
                print(f"{nome}: corsa {corsa:%d/%m %H} UTC già elaborata")
                risultati[nome] = {"blocco": vecchio[1], "variabili": vecchio[0]["variabili"],
                                   "corsa": vecchio[0]["corsa"], "elaborato": vecchio[0]["elaborato"]}
                continue
            inizio = time.time()
            modello = leggi_modello(dataset)
            blocco, variabili = blocco_modello(modello)
            risultati[nome] = {"blocco": blocco, "variabili": variabili, "corsa": modello["corsa"].isoformat(),
                               "elaborato": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            print(f"{nome}: corsa {modello['corsa']:%d/%m %H} UTC, {modello['ore']} ore, "
                  f"{', '.join(variabili)} ({time.time() - inizio:.0f} s)")
        except Exception as errore:          # un modello che non risponde non ferma gli altri
            errori.append(f"{nome}: {errore}")
            print(f"{nome}: ERRORE {errore}", file=sys.stderr)
            vecchio = precedenti.get(nome)
            if vecchio and datetime.fromisoformat(vecchio[0]["corsa"]) > datetime.now(timezone.utc) - timedelta(hours=48):
                risultati[nome] = {"blocco": vecchio[1], "variabili": vecchio[0]["variabili"],
                                   "corsa": vecchio[0]["corsa"], "elaborato": vecchio[0]["elaborato"]}
    if not risultati:
        print("Nessun modello disponibile", file=sys.stderr)
        return 1
    indice = scrivi(cartella, risultati, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    try:
        righe = previsioni_nelle_stazioni(cartella.parent / "storico", risultati)
        print(f"Previsioni nei punti delle stazioni: {righe} righe")
    except Exception as errore:          # lo storico non deve mai bloccare l'elaborazione principale
        print(f"Previsioni nei punti delle stazioni: ERRORE {errore}", file=sys.stderr)
    print(f"Scritto: {len(indice['modelli'])} modelli, {indice['byte_per_punto']} byte per punto")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "dati/meteohub"))
