# =============================================================================
# Calabria Meteo Lab - Attività: giudizio ora per ora e fasce migliori
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Ogni ora parte da "Ottimo"; ogni condizione sfavorevole può abbassarla a
# "Buono", "Discreto" o "Sconsigliato". Il giudizio è la condizione peggiore,
# e il motivo mostrato è quello che la determina.
# Soglie applicative, non criteri ufficiali di sicurezza.

import html
import math

import pandas as pd

from meteo.formato import data_it, valore_finito
from meteo.indicatori import SOGLIE_INDICATORI, valore_ora
from meteo.probabilita import PROBABILITA_AVVISO_RAFFICHE, SOGLIE_RAFFICHE_ORARIE

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

ORE_MINIME_FASCIA = 2
MASSIMO_FASCE_GIORNO = 3
QUOTA_MINIMA_NEVE_M = 1000

# Tutte le soglie in un unico posto (vento e raffiche in km/h, onde in m).
SOGLIE = {
    "comuni": {"raffiche_sconsigliato": 70},
    "escursionismo": {"pioggia_sconsigliato": 1.0, "pioggia_discreto": 0.2, "vento_discreto": 30,
                      "raffiche_discreto": 40, "percepita_min": (-5, 0, 5), "percepita_max": (36, 32, 28)},
    "ciclismo": {"pioggia_sconsigliato": 1.0, "pioggia_discreto": 0.2, "vento_sconsigliato": 40,
                 "vento_discreto": 25, "vento_buono": 15, "raffiche_discreto": 45, "percepita": (3, 32)},
    "corsa": {"percepita_sconsigliato": 34, "pioggia_discreto": 2.0, "percepita": (0, 30),
              "afa": (26, 80), "vento_discreto": 35},
    "fotografia": {"pioggia_sconsigliato": 2.0, "pioggia_discreto": 0.5, "raffiche_discreto": 50,
                   "nubi_luce_piatta": 95, "ora_dorata_min": 75},
    "astronomia": {"nubi": (15, 40, 70), "umidita_discreto": 90, "luna_buono": 0.6, "margine_buio_min": 60},
    "spiaggia": {"aria": (20, 24), "nubi_discreto": 70, "vento_discreto": 30, "onde": (1.25, 2.5), "mare_discreto": 18},
    "surf": {"onde_min": 0.5, "onde_buone": 0.8, "onde_max": 3.0, "periodo_minimo": 7},
    "kite": {"vento": (10, 15, 35, 45), "raffiche_sconsigliato": 60},
    "pesca": {"onde": (0.5, 1.25, 2.5), "vento_discreto": 30, "pioggia_discreto": 1.0},
    "neve": {"temperatura_max": 6, "vento_discreto": 30},
}

ATTIVITA = [
    # chiave, nome, icona, quando, solo costa, solo montagna
    ("escursionismo", "Escursionismo", "🥾", "luce", False, False),
    ("ciclismo", "Ciclismo", "🚴", "luce", False, False),
    ("corsa", "Corsa", "🏃", "sempre", False, False),
    ("fotografia", "Fotografia", "📸", "luce", False, False),
    ("astronomia", "Astronomia", "🔭", "buio", False, False),
    ("spiaggia", "Spiaggia", "🏖️", "luce", True, False),
    ("surf", "Surf", "🏄", "luce", True, False),
    ("kite", "Kite e vela", "🪁", "luce", True, False),
    ("pesca", "Pesca", "🎣", "sempre", True, False),
    ("neve", "Neve", "⛷️", "luce", False, True),
]

ORARI = {
    "luce": "ore di luce",
    "sempre": "tutte le ore",
    "buio": "da 1 ora dopo il tramonto a 1 ora prima dell'alba",
}


def criteri_testo(chiave):
    """Criteri leggibili, generati dalle stesse soglie usate nel calcolo.

    Ogni voce è una funzione: legge solo le soglie della propria attività.
    """
    s = SOGLIE[chiave]
    c = SOGLIE["comuni"]["raffiche_sconsigliato"]
    comuni = f"Sempre 🔴 con temporali o raffiche ≥ {c} km/h."
    testi = {
        "escursionismo": lambda s: [
            f"🔴 pioggia ≥ {s['pioggia_sconsigliato']} mm/h; percepita < {s['percepita_min'][0]}° o > {s['percepita_max'][0]}°",
            f"🟠 pioviggine, neve o nebbia; vento ≥ {s['vento_discreto']} o raffiche ≥ {s['raffiche_discreto']} km/h; "
            f"percepita < {s['percepita_min'][1]}° o > {s['percepita_max'][1]}°",
            f"🟡 percepita {s['percepita_min'][1]}–{s['percepita_min'][2]}° o {s['percepita_max'][2]}–{s['percepita_max'][1]}°",
        ],
        "ciclismo": lambda s: [
            f"🔴 pioggia ≥ {s['pioggia_sconsigliato']} mm/h; vento ≥ {s['vento_sconsigliato']} km/h",
            f"🟠 pioviggine o nebbia; vento ≥ {s['vento_discreto']} o raffiche ≥ {s['raffiche_discreto']} km/h; "
            f"percepita < {s['percepita'][0]}° o > {s['percepita'][1]}°",
            f"🟡 vento {s['vento_buono']}–{s['vento_discreto']} km/h",
        ],
        "corsa": lambda s: [
            f"🔴 percepita > {s['percepita_sconsigliato']}°",
            f"🟠 pioggia ≥ {s['pioggia_discreto']} mm/h; percepita < {s['percepita'][0]}° o > {s['percepita'][1]}°; "
            f"afa (≥ {s['afa'][0]}° con umidità ≥ {s['afa'][1]}%); vento ≥ {s['vento_discreto']} km/h",
        ],
        "fotografia": lambda s: [
            f"🔴 pioggia ≥ {s['pioggia_sconsigliato']} mm/h",
            f"🟠 pioggia ≥ {s['pioggia_discreto']} mm/h; raffiche ≥ {s['raffiche_discreto']} km/h; "
            f"cielo coperto ≥ {s['nubi_luce_piatta']}% (luce piatta)",
            f"✨ segnalata l'ora dorata ({s['ora_dorata_min']} minuti dopo l'alba e prima del tramonto)",
        ],
        "astronomia": lambda s: [
            f"🔴 nubi > {s['nubi'][2]}% o pioggia",
            f"🟠 nubi {s['nubi'][1]}–{s['nubi'][2]}%; umidità ≥ {s['umidita_discreto']}%",
            f"🟡 nubi {s['nubi'][0]}–{s['nubi'][1]}%; luna illuminata ≥ {s['luna_buono']:.0%}",
        ],
        "spiaggia": lambda s: [
            f"🔴 aria < {s['aria'][0]}°; pioggia; onde ≥ {s['onde'][1]} m",
            f"🟠 aria {s['aria'][0]}–{s['aria'][1]}°; nubi > {s['nubi_discreto']}%; vento ≥ {s['vento_discreto']} km/h; "
            f"onde ≥ {s['onde'][0]} m; mare < {s['mare_discreto']}°",
        ],
        "surf": lambda s: [
            f"🔴 onde < {s['onde_min']} m o > {s['onde_max']} m",
            f"🟠 onde {s['onde_min']}–{s['onde_buone']} m; periodo < {s['periodo_minimo']} s",
            f"🟢 onde {s['onde_buone']}–{s['onde_max']} m con periodo ≥ {s['periodo_minimo']} s",
        ],
        "kite": lambda s: [
            f"🔴 vento < {s['vento'][0]} o > {s['vento'][3]} km/h; raffiche ≥ {s['raffiche_sconsigliato']} km/h",
            f"🟠 vento {s['vento'][0]}–{s['vento'][1]} (debole) o {s['vento'][2]}–{s['vento'][3]} km/h (solo esperti)",
            f"🟢 vento {s['vento'][1]}–{s['vento'][2]} km/h",
        ],
        "pesca": lambda s: [
            f"🔴 onde > {s['onde'][2]} m",
            f"🟠 onde {s['onde'][1]}–{s['onde'][2]} m; vento ≥ {s['vento_discreto']} km/h; pioggia ≥ {s['pioggia_discreto']} mm/h",
            f"🟡 onde {s['onde'][0]}–{s['onde'][1]} m (in barca con prudenza)",
        ],
        "neve": lambda s: [
            f"🔴 pioggia (non neve); temperatura > {s['temperatura_max']}°",
            f"🟠 vento ≥ {s['vento_discreto']} km/h; nebbia",
            "🟡 sta nevicando",
            "ℹ️ Lo spessore della neve al suolo non è disponibile: verifica innevamento e apertura degli impianti.",
        ],
    }
    return testi[chiave](s) + [comuni]


# -----------------------------------------------------------------------------
# Giudizio di una singola ora
# -----------------------------------------------------------------------------

class _Giudizio:
    def __init__(self):
        self.livello = OTTIMO
        self.motivi = {}   # livello -> elenco motivi
        self.note = []

    def abbassa(self, livello, motivo):
        self.livello = max(self.livello, livello)
        self.motivi.setdefault(livello, [])
        if motivo not in self.motivi[livello]:
            self.motivi[livello].append(motivo)

    def motivo_principale(self):
        return ", ".join(self.motivi.get(self.livello, [])) or "nessun fattore limitante"


def _valore(riga, campo):
    return valore_finito(riga.get(campo), None) if riga is not None else None


def giudica_ora(chiave, riga, mare=None, luna=0.5):
    """Restituisce (livello, motivo, note) per un'ora, o None se l'ora non è valutabile."""
    g = _Giudizio()
    s = SOGLIE[chiave]
    codice = _valore(riga, "weather_code")
    codice = int(codice) if codice is not None else None
    pioggia = _valore(riga, "precipitation") or 0.0
    vento = _valore(riga, "wind_speed_10m")
    raffiche = _valore(riga, "wind_gusts_10m")
    percepita = _valore(riga, "apparent_temperature")
    temperatura = _valore(riga, "temperature_2m")
    nubi = _valore(riga, "cloud_cover")
    umidita = _valore(riga, "relative_humidity_2m")
    onde = _valore(mare, "wave_height")
    periodo = _valore(mare, "wave_period")
    temp_mare = _valore(mare, "sea_surface_temperature")
    neve = codice in CODICI_NEVE
    nebbia = codice in CODICI_NEBBIA
    precipitazione = "neve" if neve else "pioggia"

    # Pericoli comuni a tutte le attività
    if codice in CODICI_TEMPORALE:
        g.abbassa(SCONSIGLIATO, "temporali")
    if raffiche is not None and raffiche >= SOGLIE["comuni"]["raffiche_sconsigliato"]:
        g.abbassa(SCONSIGLIATO, "raffiche molto forti")

    if chiave == "escursionismo":
        if pioggia >= s["pioggia_sconsigliato"]:
            g.abbassa(SCONSIGLIATO, precipitazione)
        elif pioggia >= s["pioggia_discreto"]:
            g.abbassa(DISCRETO, "neve debole" if neve else "pioviggine")
        if neve:
            g.abbassa(DISCRETO, "neve")
        if nebbia:
            g.abbassa(DISCRETO, "nebbia")
        if (vento or 0) >= s["vento_discreto"] or (raffiche or 0) >= s["raffiche_discreto"]:
            g.abbassa(DISCRETO, "vento forte")
        if percepita is not None:
            minimi, massimi = s["percepita_min"], s["percepita_max"]
            if percepita < minimi[0] or percepita > massimi[0]:
                g.abbassa(SCONSIGLIATO, "freddo intenso" if percepita < minimi[0] else "caldo intenso")
            elif percepita < minimi[1] or percepita > massimi[1]:
                g.abbassa(DISCRETO, "freddo" if percepita < minimi[1] else "caldo")
            elif percepita < minimi[2] or percepita > massimi[2]:
                g.abbassa(BUONO, "fresco" if percepita < minimi[2] else "caldo")

    elif chiave == "ciclismo":
        if pioggia >= s["pioggia_sconsigliato"]:
            g.abbassa(SCONSIGLIATO, precipitazione)
        elif pioggia >= s["pioggia_discreto"]:
            g.abbassa(DISCRETO, "strade bagnate")
        if nebbia:
            g.abbassa(DISCRETO, "nebbia")
        if vento is not None:
            if vento >= s["vento_sconsigliato"]:
                g.abbassa(SCONSIGLIATO, "vento forte")
            elif vento >= s["vento_discreto"]:
                g.abbassa(DISCRETO, "vento sostenuto")
            elif vento >= s["vento_buono"]:
                g.abbassa(BUONO, "un po' di vento")
        if (raffiche or 0) >= s["raffiche_discreto"]:
            g.abbassa(DISCRETO, "raffiche")
        if percepita is not None and (percepita < s["percepita"][0] or percepita > s["percepita"][1]):
            g.abbassa(DISCRETO, "freddo" if percepita < s["percepita"][0] else "caldo")

    elif chiave == "corsa":
        if percepita is not None and percepita > s["percepita_sconsigliato"]:
            g.abbassa(SCONSIGLIATO, "caldo intenso")
        elif percepita is not None and (percepita < s["percepita"][0] or percepita > s["percepita"][1]):
            g.abbassa(DISCRETO, "freddo" if percepita < s["percepita"][0] else "caldo")
        if pioggia >= s["pioggia_discreto"]:
            g.abbassa(DISCRETO, precipitazione)
        if temperatura is not None and umidita is not None and temperatura >= s["afa"][0] and umidita >= s["afa"][1]:
            g.abbassa(DISCRETO, "afa")
        if (vento or 0) >= s["vento_discreto"]:
            g.abbassa(DISCRETO, "vento forte")

    elif chiave == "fotografia":
        if pioggia >= s["pioggia_sconsigliato"]:
            g.abbassa(SCONSIGLIATO, precipitazione)
        elif pioggia >= s["pioggia_discreto"]:
            g.abbassa(DISCRETO, precipitazione)
        if (raffiche or 0) >= s["raffiche_discreto"]:
            g.abbassa(DISCRETO, "raffiche")
        if nubi is not None and nubi >= s["nubi_luce_piatta"] and pioggia < s["pioggia_discreto"]:
            g.abbassa(DISCRETO, "luce piatta")

    elif chiave == "astronomia":
        primo, secondo, terzo = s["nubi"]
        if pioggia > 0 or (codice is not None and codice >= 51):
            g.abbassa(SCONSIGLIATO, "precipitazioni")
        if nubi is not None:
            if nubi > terzo:
                g.abbassa(SCONSIGLIATO, "cielo coperto")
            elif nubi > secondo:
                g.abbassa(DISCRETO, "molte nubi")
            elif nubi > primo:
                g.abbassa(BUONO, "qualche nube")
        if (umidita or 0) >= s["umidita_discreto"]:
            g.abbassa(DISCRETO, "umidità alta")
        if luna >= s["luna_buono"]:
            g.abbassa(BUONO, "luna luminosa")

    elif chiave == "spiaggia":
        if temperatura is not None:
            if temperatura < s["aria"][0]:
                g.abbassa(SCONSIGLIATO, "aria fresca")
            elif temperatura < s["aria"][1]:
                g.abbassa(DISCRETO, "aria fresca")
        if pioggia >= 0.2:
            g.abbassa(SCONSIGLIATO, "pioggia")
        if (nubi or 0) > s["nubi_discreto"]:
            g.abbassa(DISCRETO, "nuvoloso")
        if (vento or 0) >= s["vento_discreto"]:
            g.abbassa(DISCRETO, "vento forte")
        if onde is not None:
            if onde >= s["onde"][1]:
                g.abbassa(SCONSIGLIATO, "mare agitato")
            elif onde >= s["onde"][0]:
                g.abbassa(DISCRETO, "mare mosso")
        else:
            g.note.append("stato del mare non disponibile")
        if temp_mare is not None and temp_mare < s["mare_discreto"]:
            g.abbassa(DISCRETO, "acqua fredda")

    elif chiave == "surf":
        if onde is None:
            return None  # senza dati sulle onde il giudizio non avrebbe senso
        if onde < s["onde_min"]:
            g.abbassa(SCONSIGLIATO, "mare piatto")
        elif onde > s["onde_max"]:
            g.abbassa(SCONSIGLIATO, "onde troppo alte")
        elif onde < s["onde_buone"]:
            g.abbassa(DISCRETO, "onde piccole")
        if periodo is not None and periodo < s["periodo_minimo"]:
            g.abbassa(DISCRETO, "onde corte e disordinate")

    elif chiave == "kite":
        minimo, debole, forte, massimo = s["vento"]
        if vento is None:
            return None
        if vento < minimo:
            g.abbassa(SCONSIGLIATO, "poco vento")
        elif vento > massimo:
            g.abbassa(SCONSIGLIATO, "vento troppo forte")
        elif vento < debole:
            g.abbassa(DISCRETO, "vento debole")
        elif vento > forte:
            g.abbassa(DISCRETO, "vento forte, solo esperti")
        if (raffiche or 0) >= s["raffiche_sconsigliato"]:
            g.abbassa(SCONSIGLIATO, "raffiche forti")

    elif chiave == "pesca":
        if onde is not None:
            calmo, mosso, agitato = s["onde"]
            if onde > agitato:
                g.abbassa(SCONSIGLIATO, "mare agitato")
            elif onde > mosso:
                g.abbassa(DISCRETO, "mare mosso")
            elif onde > calmo:
                g.abbassa(BUONO, "mare poco mosso")
        else:
            g.note.append("stato del mare non disponibile")
        if (vento or 0) >= s["vento_discreto"]:
            g.abbassa(DISCRETO, "vento forte")
        if pioggia >= s["pioggia_discreto"]:
            g.abbassa(DISCRETO, "pioggia")

    elif chiave == "neve":
        if pioggia >= 0.2 and not neve:
            g.abbassa(SCONSIGLIATO, "pioggia")
        if temperatura is not None and temperatura > s["temperatura_max"]:
            g.abbassa(SCONSIGLIATO, "troppo caldo per la neve")
        if (vento or 0) >= s["vento_discreto"]:
            g.abbassa(DISCRETO, "vento forte")
        if nebbia:
            g.abbassa(DISCRETO, "nebbia")
        if neve:
            g.abbassa(BUONO, "sta nevicando")

    return g.livello, g.motivo_principale(), g.note


# -----------------------------------------------------------------------------
# Contesto: luce, buio, luna, dati marini
# -----------------------------------------------------------------------------

def _riga_giorno(giorni, istante):
    righe = giorni.loc[giorni["time"].dt.date == istante.date()]
    return None if righe.empty else righe.iloc[0]


def _ora_applicabile(quando, istante, riga, giorno):
    if quando == "sempre":
        return True
    if quando == "luce":
        return not bool(riga.get("Notte", False))
    # buio astronomico approssimato: un'ora di margine dopo il tramonto e prima dell'alba
    if giorno is None:
        return bool(riga.get("Notte", False))
    alba = pd.to_datetime(giorno.get("sunrise"), errors="coerce")
    tramonto = pd.to_datetime(giorno.get("sunset"), errors="coerce")
    if pd.isna(alba) or pd.isna(tramonto):
        return bool(riga.get("Notte", False))
    margine = pd.Timedelta(minutes=SOGLIE["astronomia"]["margine_buio_min"])
    return istante >= tramonto + margine or istante + pd.Timedelta(hours=1) <= alba - margine


def _luna_illuminata(giorno):
    fase = valore_finito(giorno.get("moon_phase"), None) if giorno is not None else None
    if fase is None:
        return 0.5
    return (1 - math.cos(2 * math.pi * fase)) / 2


def _ora_dorata(istante, giorno):
    if giorno is None:
        return False
    alba = pd.to_datetime(giorno.get("sunrise"), errors="coerce")
    tramonto = pd.to_datetime(giorno.get("sunset"), errors="coerce")
    finestra = pd.Timedelta(minutes=SOGLIE["fotografia"]["ora_dorata_min"])
    fine_ora = istante + pd.Timedelta(hours=1)
    return (pd.notna(alba) and istante < alba + finestra and fine_ora > alba) or (
        pd.notna(tramonto) and fine_ora > tramonto - finestra and istante < tramonto
    )


def _mare_per_ora(dati_mare):
    if not dati_mare or not isinstance(dati_mare, dict) or not dati_mare.get("hourly"):
        return {}
    orarie = pd.DataFrame(dati_mare["hourly"])
    if "time" not in orarie:
        return {}
    orarie["time"] = pd.to_datetime(orarie["time"])
    return {riga["time"]: riga for _, riga in orarie.iterrows()}


def attivita_disponibili(is_costiero, quota):
    quota = valore_finito(quota, 0.0)
    return [
        a for a in ATTIVITA
        if (not a[4] or is_costiero) and (not a[5] or quota >= QUOTA_MINIMA_NEVE_M)
    ]


NOTA_RAFFICHE = "possibili raffiche forti"


def soglia_raffiche(chiave):
    """Soglia delle raffiche che peggiora il giudizio dell'attività (tra quelle calcolate dagli ensemble)."""
    s = SOGLIE.get(chiave, {})
    soglia = s.get("raffiche_discreto") or s.get("raffiche_sconsigliato") or SOGLIE["comuni"]["raffiche_sconsigliato"]
    return max((x for x in SOGLIE_RAFFICHE_ORARIE if x <= soglia), default=SOGLIE_RAFFICHE_ORARIE[0])


def avviso_raffiche(probabilita, istante, soglia, raffiche_previste):
    """'possibili raffiche forti (40%)' se gli scenari lo indicano ma la previsione resta sotto soglia."""
    if not probabilita or (raffiche_previste is not None and raffiche_previste >= soglia):
        return None
    quota = ((probabilita.get("orarie") or {}).get(pd.Timestamp(istante)) or {}).get("raffiche", {}).get(soglia)
    if quota is None or quota < PROBABILITA_AVVISO_RAFFICHE:
        return None
    return f"{NOTA_RAFFICHE} ({quota * 100:.0f}%)"


def valuta_attivita(ore, giorni, dati_mare=None, is_costiero=False, quota=None, indicatori=None, probabilita=None):
    """Per ogni attività disponibile, il giudizio di ogni ora (None = fuori orario)."""
    mare = _mare_per_ora(dati_mare)
    risultati = {}
    for chiave, nome, icona, quando, _, _ in attivita_disponibili(is_costiero, quota):
        ore_valutate = []
        for _, riga in ore.iterrows():
            istante = pd.Timestamp(riga["time"])
            giorno = _riga_giorno(giorni, istante)
            giudizio = None
            if _ora_applicabile(quando, istante, riga, giorno):
                giudizio = giudica_ora(chiave, riga, mare.get(istante), _luna_illuminata(giorno))
                if giudizio and chiave == "fotografia" and _ora_dorata(istante, giorno):
                    giudizio[2].append("ora dorata")
                uv = valore_ora(indicatori, istante, "uv")
                if giudizio and chiave == "spiaggia" and uv is not None and uv >= SOGLIE_INDICATORI["uv"][2]:
                    giudizio[2].append("UV molto alto: proteggiti dal sole")
                avviso = avviso_raffiche(probabilita, istante, soglia_raffiche(chiave), _valore(riga, "wind_gusts_10m"))
                if giudizio and avviso and giudizio[0] < SCONSIGLIATO:
                    giudizio[2].append(avviso)
            ore_valutate.append((istante, giudizio))
        risultati[chiave] = {"nome": nome, "icona": icona, "quando": quando, "ore": ore_valutate}
    return risultati


def fasce_migliori(ore_valutate, ore_minime=ORE_MINIME_FASCIA):
    """Fasce di ore consecutive Ottimo/Buono, raggruppate per giorno."""
    per_giorno = {}
    corrente = []

    def chiudi():
        if len(corrente) >= ore_minime:
            inizio, fine = corrente[0][0], corrente[-1][0] + pd.Timedelta(hours=1)
            livello = max(g[0] for _, g in corrente)
            note = sorted({n for _, g in corrente for n in g[2]})
            per_giorno.setdefault(inizio.date(), []).append((inizio, fine, livello, note))

    for istante, giudizio in ore_valutate:
        buona = giudizio is not None and giudizio[0] <= BUONO
        stesso_giorno = not corrente or corrente[-1][0].date() == istante.date()
        if buona and stesso_giorno and (not corrente or istante - corrente[-1][0] == pd.Timedelta(hours=1)):
            corrente.append((istante, giudizio))
        else:
            chiudi()
            corrente = [(istante, giudizio)] if buona else []
    chiudi()
    return per_giorno


def _motivo_prevalente(ore_valutate, data):
    conteggio = {}
    for istante, giudizio in ore_valutate:
        if istante.date() == data and giudizio is not None and giudizio[0] >= DISCRETO:
            for motivo in giudizio[1].split(", "):
                conteggio[motivo] = conteggio.get(motivo, 0) + 1
    return max(conteggio, key=conteggio.get) if conteggio else None


# -----------------------------------------------------------------------------
# HTML
# -----------------------------------------------------------------------------

def _etichetta(livello):
    simbolo, testo = LIVELLI[livello]
    return f'<span class="cml-liv cml-liv-{livello}">{simbolo} {testo}</span>'


def _ora_fine(fine):
    """Ora di fine di una fascia: la mezzanotte si scrive 24."""
    return "24" if fine.hour == 0 else f"{fine:%H}"


def _nome_giorno(data, oggi):
    differenza = (data - oggi).days
    if differenza == 0:
        return "Oggi"
    if differenza == 1:
        return "Domani"
    return data_it(data).split(" ")[0].capitalize()


def _scheda_attivita(chiave, dati, oggi):
    ore_valutate = dati["ore"]
    adesso = ore_valutate[0][1] if ore_valutate else None
    if adesso is None:
        testo_adesso = '<span class="cml-liv cml-liv-nd">⚪ Fuori orario</span>'
        motivo = {"luce": "Valutata nelle ore di luce.", "buio": "Valutata solo con il buio.",
                  "sempre": "Dati non disponibili."}[dati["quando"]]
    else:
        testo_adesso = _etichetta(adesso[0])
        motivo = f"Adesso: {adesso[1]}." + "".join(
            f" {'✨ ' if nota == 'ora dorata' else '💨 ' if nota.startswith(NOTA_RAFFICHE) else ''}"
            f"{nota[:1].upper() + nota[1:]}." for nota in adesso[2]
        )

    fasce = fasce_migliori(ore_valutate)
    giorni_presenti = sorted({i.date() for i, _ in ore_valutate})
    righe = []
    for data in giorni_presenti:
        if not any(g is not None and i.date() == data for i, g in ore_valutate):
            continue
        elenco = fasce.get(data, [])
        # al massimo 3 fasce, le più lunghe, in ordine di orario
        elenco = sorted(sorted(elenco, key=lambda f: f[1] - f[0], reverse=True)[:MASSIMO_FASCE_GIORNO])
        if elenco:
            testo = " · ".join(
                f"{inizio:%H}–{_ora_fine(fine)} {LIVELLI[livello][0]}" + (" ✨" if "ora dorata" in note else "")
                + (" 💨" if any(n.startswith(NOTA_RAFFICHE) for n in note) else "")
                for inizio, fine, livello, note in elenco
            )
        else:
            prevalente = _motivo_prevalente(ore_valutate, data)
            testo = "nessuna fascia adatta" + (f" ({html.escape(prevalente)})" if prevalente else "")
        righe.append(f"<li><b>{_nome_giorno(data, oggi)}</b> <span>{testo}</span></li>")

    celle = []
    for istante, giudizio in ore_valutate:
        classe = "nd" if giudizio is None else giudizio[0]
        titolo = f"{data_it(istante)} {istante:%H}:00 · " + (
            "fuori orario" if giudizio is None else f"{LIVELLI[giudizio[0]][1]} – {giudizio[1]}"
        )
        separatore = " cml-linea-giorno" if istante.hour == 0 else ""
        celle.append(f'<span class="cml-linea-ora cml-liv-{classe}{separatore}" title="{html.escape(titolo, quote=True)}"></span>')

    criteri = "".join(f"<li>{html.escape(c)}</li>" for c in criteri_testo(chiave))
    return f"""
    <article class="cml-att">
      <header>
        <span class="cml-att-icona" aria-hidden="true">{dati['icona']}</span>
        <h3>{html.escape(dati['nome'])}</h3>
        {testo_adesso}
      </header>
      <p class="cml-att-motivo">{html.escape(motivo)}</p>
      <ul class="cml-att-fasce" aria-label="Fasce migliori">{''.join(righe)}</ul>
      <div class="cml-linea" role="img" aria-label="Giudizio ora per ora sui prossimi giorni">{''.join(celle)}</div>
      <details>
        <summary>Come è calcolato ({html.escape(ORARI[dati['quando']])})</summary>
        <ul class="cml-att-criteri">{criteri}</ul>
      </details>
    </article>"""


def sezione_attivita_html(luogo, ore, giorni, dati_mare=None, is_costiero=False, quota=None, indicatori=None,
                          probabilita=None):
    risultati = valuta_attivita(ore, giorni, dati_mare, is_costiero, quota, indicatori, probabilita)
    oggi = pd.Timestamp(ore.iloc[0]["time"]).date() if not ore.empty else pd.Timestamp.now().date()
    schede = "".join(_scheda_attivita(chiave, dati, oggi) for chiave, dati in risultati.items())

    note = []
    if not is_costiero:
        note.append("Località non costiera: spiaggia, surf, kite e pesca non sono valutati.")
    if valore_finito(quota, 0.0) < QUOTA_MINIMA_NEVE_M:
        note.append(f"Neve valutata solo sopra {QUOTA_MINIMA_NEVE_M} m di quota.")
    if any(NOTA_RAFFICHE in "".join(g[2]) for d in risultati.values() for _, g in d["ore"] if g):
        note.append(f"💨 = {NOTA_RAFFICHE} secondo gli scenari degli ensemble (probabilità ≥ "
                    f"{PROBABILITA_AVVISO_RAFFICHE * 100:.0f}%), anche se la previsione resta sotto soglia.")
    legenda = " ".join(_etichetta(l) for l in LIVELLI) + ' <span class="cml-liv cml-liv-nd">⚪ Fuori orario</span>'

    return f"""
    <section class="cml-radar-box cml-attivita-box">
      <div class="cml-radar-head">
        <div>
          <h2>🏃 Attività per {html.escape(luogo)}</h2>
          <p>Giudizio ora per ora sui prossimi giorni e fasce migliori (almeno {ORE_MINIME_FASCIA} ore consecutive
          Ottime o Buone). Il motivo indica il fattore che limita di più.</p>
        </div>
      </div>
      <p class="cml-att-legenda">{legenda}</p>
      <div class="cml-attivita-griglia">{schede}</div>
      <div class="cml-marine-note">
        ℹ️ Criteri applicativi basati sulla previsione, non garanzie di sicurezza: verifica sempre
        le condizioni sul posto e gli avvisi ufficiali. {html.escape(' '.join(note))}
      </div>
    </section>
    """
