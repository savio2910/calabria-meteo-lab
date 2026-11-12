# =============================================================================
# Calabria Meteo Lab - Allenamento delle correzioni con le stazioni (livello 1: MOS)
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Confronta le previsioni passate di ogni modello con le osservazioni delle
# stazioni e calcola, per ogni stazione e ogni modello:
#   - temperatura: errore sistematico per scadenza (giorno 0/1/2) e fascia di
#     3 ore (UTC), con "restringimento" verso la media della stazione quando i
#     dati sono pochi (così una fascia con poche ore non dà correzioni strane);
#   - pioggia: fattore moltiplicativo dai totali giornalieri dei giorni piovosi;
#   - vento medio e raffiche: fattore moltiplicativo (posizione dell'anemometro,
#     rugosità, incanalamenti che i modelli non vedono).
# Calcola anche i pesi dei modelli per variabile e scadenza (inverso dell'errore
# quadratico medio delle previsioni già corrette).
#
# Ogni correzione viene verificata su dati NON usati per calcolarla (gli ultimi
# giorni di ogni stazione): una correzione viene attivata solo se riduce l'errore.
# Poi viene ricalcolata con tutti i dati.
#
# I dati recenti contano di più (dimezzamento in 45 giorni); quelli dello
# stesso periodo dell'anno precedente contano comunque (stagionalità).
#
# Uso: python elaborazione/allena_correzioni.py CARTELLA_STORICO CARTELLA_USCITA

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

GIORNI = (0, 1, 2)
FASCE = 8                      # fasce di 3 ore
K_STAZIONE = 24.0              # ore "virtuali" che tirano la media della stazione verso 0
K_FASCIA = 12.0                # ore "virtuali" che tirano la fascia verso la media della stazione
MAX_CORREZIONE_C = 6.0
PIOGGIA_GIORNO_BAGNATO_MM = 0.5
K_PIOGGIA_GIORNI = 8.0
LIMITI_PIOGGIA = (0.5, 2.0)
VENTO_MINIMO_KMH = 3.0
K_VENTO_ORE = 48.0
LIMITI_VENTO = (0.4, 2.5)
GIORNI_VERIFICA = 7
MIN_ORE_VERIFICA = 24
DIMEZZAMENTO_GIORNI = 45.0
STAGIONE_GIORNI = 30.0


# -----------------------------------------------------------------------------
# Dati
# -----------------------------------------------------------------------------

def leggi(cartella):
    cartella = Path(cartella)
    stazioni = pd.read_csv(cartella / "stazioni.csv", dtype={"id": str})
    oss = pd.concat([pd.read_csv(f, parse_dates=["time"]) for f in sorted((cartella / "osservazioni").glob("*.csv.gz"))])
    prev = pd.concat([pd.read_csv(f, parse_dates=["time"]) for f in sorted((cartella / "previsioni").glob("*.csv.gz"))])
    coppie = prev.merge(oss, on=["id", "time"], suffixes=("_p", "_o"))
    return stazioni, coppie


def pesi_temporali(tempi, riferimento):
    """Peso di ogni dato: recente (dimezzamento 45 giorni) o della stessa stagione dell'anno prima (metà)."""
    eta = (riferimento - tempi).dt.total_seconds().to_numpy() / 86400
    recenti = np.exp(-np.log(2) * np.clip(eta, 0, None) / DIMEZZAMENTO_GIORNI)
    distanza = np.abs(((tempi.dt.dayofyear.to_numpy() - riferimento.dayofyear) + 182) % 365 - 182)
    stagione = 0.5 * np.exp(-0.5 * (distanza / STAGIONE_GIORNI) ** 2)
    return np.maximum(recenti, stagione)


def dividi_verifica(coppie):
    """(allenamento, verifica): per ogni stazione gli ultimi giorni (al massimo il 30% del periodo)."""
    fine = coppie.groupby("id")["time"].transform("max")
    inizio = coppie.groupby("id")["time"].transform("min")
    giorni = np.minimum(GIORNI_VERIFICA, (fine - inizio).dt.total_seconds() / 86400 * 0.3)
    soglia = fine - pd.to_timedelta(giorni, unit="D")
    verifica = coppie["time"] > soglia
    return coppie[~verifica], coppie[verifica]


# -----------------------------------------------------------------------------
# Stima delle correzioni
# -----------------------------------------------------------------------------

def stima_temperatura(dati, riferimento):
    """{(id, modello, giorno): [8 correzioni per fascia]} (°C da aggiungere alla previsione)."""
    d = dati.dropna(subset=["temperatura_p", "temperatura_o"]).copy()
    d["errore"] = d["temperatura_o"] - d["temperatura_p"]
    d["w"] = pesi_temporali(d["time"], riferimento)
    d["fascia"] = d["time"].dt.hour // 3
    d["we"] = d["w"] * d["errore"]
    risultato = {}
    for chiave, gruppo in d.groupby(["id", "modello", "giorno"]):
        media = gruppo["we"].sum() / (gruppo["w"].sum() + K_STAZIONE)
        fasce = gruppo.groupby("fascia")[["we", "w"]].sum().reindex(range(FASCE), fill_value=0.0)
        correzioni = (fasce["we"] + K_FASCIA * media) / (fasce["w"] + K_FASCIA)
        risultato[chiave] = np.clip(correzioni.to_numpy(), -MAX_CORREZIONE_C, MAX_CORREZIONE_C)
    return risultato


def applica_temperatura(dati, correzioni):
    chiavi = list(zip(dati["id"], dati["modello"], dati["giorno"]))
    fasce = (dati["time"].dt.hour // 3).to_numpy()
    return dati["temperatura_p"].to_numpy() + np.array(
        [correzioni[k][f] if k in correzioni else 0.0 for k, f in zip(chiavi, fasce)])


def _giornalieri_pioggia(dati):
    d = dati.dropna(subset=["pioggia_p", "pioggia_o"]).copy()
    d["data"] = d["time"].dt.floor("D")
    g = d.groupby(["id", "modello", "giorno", "data"]).agg(p=("pioggia_p", "sum"), o=("pioggia_o", "sum"),
                                                         n=("pioggia_o", "size"))
    return g[g["n"] >= 20].reset_index()


def stima_pioggia(dati, riferimento):
    """{(id, modello): fattore} dai giorni piovosi (osservati o previsti)."""
    g = _giornalieri_pioggia(dati)
    g = g[(g["o"] >= PIOGGIA_GIORNO_BAGNATO_MM) | (g["p"] >= PIOGGIA_GIORNO_BAGNATO_MM)]
    g["w"] = pesi_temporali(g["data"], riferimento)
    risultato = {}
    for chiave, gruppo in g.groupby(["id", "modello"]):
        fattore = ((gruppo["w"] * gruppo["o"]).sum() + 1) / ((gruppo["w"] * gruppo["p"]).sum() + 1)
        fattore = float(np.clip(fattore, *LIMITI_PIOGGIA))
        n = gruppo["data"].nunique()
        risultato[chiave] = 1 + (fattore - 1) * n / (n + K_PIOGGIA_GIORNI)
    return risultato


def stima_fattore(dati, colonna, riferimento):
    """{(id, modello): fattore} per vento medio o raffiche."""
    d = dati.dropna(subset=[f"{colonna}_p", f"{colonna}_o"])
    d = d[d[f"{colonna}_p"] >= VENTO_MINIMO_KMH].copy()
    d["w"] = pesi_temporali(d["time"], riferimento)
    risultato = {}
    for chiave, gruppo in d.groupby(["id", "modello"]):
        fattore = (gruppo["w"] * gruppo[f"{colonna}_o"]).sum() / max((gruppo["w"] * gruppo[f"{colonna}_p"]).sum(), 1e-6)
        fattore = float(np.clip(fattore, *LIMITI_VENTO))
        n = gruppo["w"].sum()
        risultato[chiave] = 1 + (fattore - 1) * n / (n + K_VENTO_ORE)
    return risultato


def applica_fattore(dati, colonna, fattori):
    return dati[f"{colonna}_p"].to_numpy() * np.array(
        [fattori.get(k, 1.0) for k in zip(dati["id"], dati["modello"])])


# -----------------------------------------------------------------------------
# Verifica e pesi
# -----------------------------------------------------------------------------

def _mae(errori):
    errori = np.asarray(errori, dtype=float)
    errori = errori[~np.isnan(errori)]
    return float(np.mean(np.abs(errori))) if len(errori) else None


def verifica(allenamento, prova, riferimento):
    """Errori prima/dopo su dati non usati; stazioni in cui ogni correzione migliora."""
    esito = {"temperatura": {}, "pioggia": {}, "vento": {}, "raffica": {}}
    attive = {k: set() for k in esito}
    p = prova.copy()

    c_temp = stima_temperatura(allenamento, riferimento)
    t = p.dropna(subset=["temperatura_p", "temperatura_o"]).copy()
    t["corretta"] = applica_temperatura(t, c_temp)
    t["e0"] = (t["temperatura_o"] - t["temperatura_p"]).abs()
    t["e1"] = (t["temperatura_o"] - t["corretta"]).abs()
    for ident, g in t.groupby("id"):
        if len(g) >= MIN_ORE_VERIFICA and g["e1"].mean() < g["e0"].mean():
            attive["temperatura"].add(ident)
    for (modello, giorno), g in t.groupby(["modello", "giorno"]):
        esito["temperatura"][f"{modello}|{giorno}"] = {"prima": round(g["e0"].mean(), 2),
                                                       "dopo": round(g["e1"].mean(), 2), "ore": int(len(g))}

    c_pioggia = stima_pioggia(allenamento, riferimento)
    g = _giornalieri_pioggia(p)
    if not g.empty:
        g["corretta"] = g["p"] * np.array([c_pioggia.get(k, 1.0) for k in zip(g["id"], g["modello"])])
        g["e0"], g["e1"] = (g["o"] - g["p"]).abs(), (g["o"] - g["corretta"]).abs()
        for ident, gg in g.groupby("id"):
            if len(gg) >= 3 and gg["e1"].mean() <= gg["e0"].mean() and (gg["o"] >= PIOGGIA_GIORNO_BAGNATO_MM).any():
                attive["pioggia"].add(ident)
        for modello, gg in g.groupby("modello"):
            esito["pioggia"][modello] = {"prima": round(gg["e0"].mean(), 2), "dopo": round(gg["e1"].mean(), 2),
                                         "giorni": int(len(gg))}

    for colonna in ("vento", "raffica"):
        fattori = stima_fattore(allenamento, colonna, riferimento)
        v = p.dropna(subset=[f"{colonna}_p", f"{colonna}_o"]).copy()
        if v.empty:
            continue
        v["corretta"] = applica_fattore(v, colonna, fattori)
        v["e0"] = (v[f"{colonna}_o"] - v[f"{colonna}_p"]).abs()
        v["e1"] = (v[f"{colonna}_o"] - v["corretta"]).abs()
        for ident, gg in v.groupby("id"):
            if len(gg) >= MIN_ORE_VERIFICA and gg["e1"].mean() < gg["e0"].mean():
                attive[colonna].add(ident)
        for modello, gg in v.groupby("modello"):
            esito[colonna][modello] = {"prima": round(gg["e0"].mean(), 2), "dopo": round(gg["e1"].mean(), 2),
                                       "ore": int(len(gg))}
    return esito, attive, c_temp, c_pioggia


def pesi_modelli(allenamento, prova, c_temp, c_pioggia, riferimento):
    """{gruppo: {giorno: {modello: peso}}, "campioni": {...}} dall'inverso dell'errore quadratico medio."""
    pesi, campioni = {}, {}
    p = prova.copy()
    p["temperatura_c"] = applica_temperatura(p, c_temp)
    p["pioggia_c"] = applica_fattore(p, "pioggia", c_pioggia)
    fattori_vento = stima_fattore(allenamento, "vento", riferimento)
    p["vento_c"] = applica_fattore(p, "vento", fattori_vento)
    for gruppo, (prevista, osservata) in {"temperatura": ("temperatura_c", "temperatura_o"),
                                          "pioggia": ("pioggia_c", "pioggia_o"),
                                          "vento": ("vento_c", "vento_o")}.items():
        pesi[gruppo], campioni[gruppo] = {}, {}
        for giorno in GIORNI:
            d = p[(p["giorno"] == giorno)].dropna(subset=[prevista, osservata])
            tabella = d.pivot_table(index=["id", "time"], columns="modello", values=prevista)
            tabella = tabella.dropna()           # solo ore in cui ci sono tutti i modelli
            if len(tabella) < 48 or tabella.shape[1] < 2:
                continue
            oss = d.drop_duplicates(["id", "time"]).set_index(["id", "time"])[osservata].reindex(tabella.index)
            mse = ((tabella.sub(oss, axis=0)) ** 2).mean()
            inverso = 1 / mse.clip(lower=1e-3)
            pesi[gruppo][str(giorno)] = {m: round(float(v), 4) for m, v in (inverso / inverso.sum()).items()}
            campioni[gruppo][str(giorno)] = int(len(tabella))
    return pesi, campioni


# -----------------------------------------------------------------------------
# Uscita
# -----------------------------------------------------------------------------

def rapporto_md(risultato):
    righe = ["# Taratura delle previsioni con le stazioni\n",
             f"Aggiornata il {risultato['creato'][:16].replace('T', ' ')} UTC · "
             f"{risultato['stazioni_totali']} stazioni con dati · periodo {risultato['periodo'][0]} → {risultato['periodo'][1]}\n",
             "Errore medio assoluto sui giorni di verifica (non usati per calcolare le correzioni).\n",
             "## Temperatura (°C)\n", "| Modello | Scadenza | Prima | Dopo | Ore |", "|---|---|---|---|---|"]
    for chiave, v in sorted(risultato["verifica"]["temperatura"].items()):
        modello, giorno = chiave.split("|")
        righe.append(f"| {modello} | giorno {giorno} | {v['prima']} | {v['dopo']} | {v['ore']} |")
    for nome, unita, misura in (("pioggia", "mm/giorno", "giorni"), ("vento", "km/h", "ore"), ("raffica", "km/h", "ore")):
        if risultato["verifica"].get(nome):
            righe += [f"\n## {nome.capitalize()} ({unita})\n", f"| Modello | Prima | Dopo | {misura.capitalize()} |", "|---|---|---|---|"]
            for modello, v in sorted(risultato["verifica"][nome].items()):
                righe.append(f"| {modello} | {v['prima']} | {v['dopo']} | {v[misura]} |")
    righe += ["\n## Stazioni con correzione attiva\n"]
    for nome, elenco in risultato["attive"].items():
        righe.append(f"- {nome}: {elenco}")
    righe += ["\n## Pesi dei modelli appresi\n"]
    for gruppo, per_giorno in risultato["pesi"].items():
        for giorno, pesi in per_giorno.items():
            righe.append(f"- {gruppo}, giorno {giorno}: " + ", ".join(f"{m} {p * 100:.0f}%" for m, p in pesi.items())
                         + f" ({risultato['campioni_pesi'][gruppo][giorno]} ore)")
    return "\n".join(righe) + "\n"


def main(cartella_storico, cartella_uscita):
    stazioni, coppie = leggi(cartella_storico)
    if coppie.empty:
        print("Nessuna coppia previsione-osservazione", file=sys.stderr)
        return 1
    riferimento = coppie["time"].max()
    allenamento, prova = dividi_verifica(coppie)
    esito, attive, c_temp_a, c_pioggia_a = verifica(allenamento, prova, riferimento)
    pesi, campioni = pesi_modelli(allenamento, prova, c_temp_a, c_pioggia_a, riferimento)

    # Correzioni finali con tutti i dati
    c_temp = stima_temperatura(coppie, riferimento)
    c_pioggia = stima_pioggia(coppie, riferimento)
    c_vento = stima_fattore(coppie, "vento", riferimento)
    c_raffica = stima_fattore(coppie, "raffica", riferimento)

    # Variabili misurate da ogni stazione (con abbastanza dati): una stazione che
    # misura una variabile ma non ha una correzione attiva conta come "nessuna correzione".
    misure = {}
    for colonna in ("temperatura", "pioggia", "vento", "raffica"):
        conteggi = coppie.dropna(subset=[f"{colonna}_o"]).groupby("id")["time"].nunique()
        for ident in conteggi[conteggi >= MIN_ORE_VERIFICA].index:
            misure.setdefault(ident, []).append(colonna)

    elenco = []
    for s in stazioni.itertuples():
        if s.id not in misure:
            continue
        voce = {"id": s.id, "nome": s.nome, "rete": s.rete, "lat": round(float(s.lat), 5), "lon": round(float(s.lon), 5),
                "quota": None if pd.isna(s.quota) else round(float(s.quota)), "misure": misure[s.id]}
        if s.id in attive["temperatura"]:
            voce["temperatura"] = {m: {str(g): [round(float(x), 2) for x in c_temp[(s.id, m, g)]]
                                       for g in GIORNI if (s.id, m, g) in c_temp}
                                   for m in sorted({k[1] for k in c_temp if k[0] == s.id})}
        for nome, valori in (("pioggia", c_pioggia), ("vento", c_vento), ("raffica", c_raffica)):
            if s.id in attive[nome]:
                voce[nome] = {m: round(float(f), 3) for (i, m), f in valori.items() if i == s.id}
        elenco.append(voce)

    risultato = {
        "creato": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metodo": "MOS livello 1: errore sistematico per stazione, modello, scadenza e fascia oraria (UTC)",
        "periodo": [str(coppie["time"].min())[:10], str(coppie["time"].max())[:10]],
        "stazioni_totali": int(coppie["id"].nunique()),
        "verifica": esito,
        "attive": {k: len(v) for k, v in attive.items()},
        "pesi": pesi,
        "campioni_pesi": campioni,
        "stazioni": elenco,
    }
    uscita = Path(cartella_uscita)
    uscita.mkdir(parents=True, exist_ok=True)
    (uscita / "correzioni.json").write_text(json.dumps(risultato, ensure_ascii=False, separators=(",", ":")))
    (uscita / "rapporto.md").write_text(rapporto_md(risultato))
    print(rapporto_md(risultato))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "dati/storico",
                  sys.argv[2] if len(sys.argv) > 2 else "dati/correzioni"))
