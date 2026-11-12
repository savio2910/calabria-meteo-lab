# =============================================================================
# Calabria Meteo Lab - Allerta ufficiale della Protezione Civile (DPC)
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Fonte: Dipartimento della Protezione Civile, bollettino nazionale di
# criticità/allerta (licenza CC BY 4.0), pubblicato ogni giorno entro le 16:
# https://github.com/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica
#
# Dall'archivio "latest_all.zip" (circa 4,6 MB) si leggono solo le due
# tabelle DBF di oggi e domani (pochi kB) con richieste HTTP parziali (Range).

import csv
import io
import re
import struct
import zipfile
from datetime import timedelta
from functools import lru_cache

import pandas as pd
import requests
import streamlit as st

from meteo.api import HTTP_FACOLTATIVO
from meteo.config import CARTELLA_APP
from meteo.localita import normalizza_comune

URL_BOLLETTINO = (
    "https://raw.githubusercontent.com/pcm-dpc/"
    "DPC-Bollettini-Criticita-Idrogeologica-Idraulica/master/files/all/latest_all.zip"
)
URL_CFD_CALABRIA = "https://www.cfd.calabria.it/"
FILE_ZONE = CARTELLA_APP / "risorse" / "zone_allerta_calabria.csv"

LIVELLI_ALLERTA = {
    0: ("🟢", "Nessuna allerta"),
    1: ("🟡", "Allerta gialla"),
    2: ("🟠", "Allerta arancione"),
    3: ("🔴", "Allerta rossa"),
}
RISCHI = {"Idrogeo": "idrogeologico", "Temporali": "temporali", "Idraulico": "idraulico"}


def livello_da_testo(testo):
    testo = str(testo).upper()
    if "ROSSA" in testo:
        return 3
    if "ARANCIONE" in testo:
        return 2
    if "GIALLA" in testo:
        return 1
    return 0


# -----------------------------------------------------------------------------
# Lettura parziale dello zip via HTTP Range
# -----------------------------------------------------------------------------

class _FileRemoto:
    """File remoto in sola lettura per zipfile: scarica solo i blocchi necessari (Range).

    I blocchi da 64 kB restano in memoria, così le piccole letture di zipfile
    non diventano tante richieste. Se il server non supporta le richieste
    parziali (risposta 200), il file intero viene tenuto in memoria.
    """

    BLOCCO = 64 * 1024

    def __init__(self, url, sessione, timeout=15):
        self.url, self.sessione, self.timeout = url, sessione, timeout
        self.posizione = 0
        self.blocchi = {}
        self.intero = None
        risposta = sessione.get(url, headers={"Range": "bytes=0-0"}, timeout=timeout)
        risposta.raise_for_status()
        if risposta.status_code == 206:
            self.dimensione = int(risposta.headers["Content-Range"].split("/")[-1])
        else:
            self.intero = risposta.content
            self.dimensione = len(self.intero)

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.posizione

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.posizione, io.SEEK_END: self.dimensione}[whence]
        self.posizione = max(0, base + offset)
        return self.posizione

    def _blocco(self, numero):
        if numero not in self.blocchi:
            inizio = numero * self.BLOCCO
            fine = min(self.dimensione, inizio + self.BLOCCO) - 1
            risposta = self.sessione.get(self.url, headers={"Range": f"bytes={inizio}-{fine}"}, timeout=self.timeout)
            risposta.raise_for_status()
            if risposta.status_code != 206:   # il server ha ignorato il Range
                self.intero = risposta.content
                return self.intero[inizio:fine + 1]
            self.blocchi[numero] = risposta.content
        return self.blocchi[numero]

    def read(self, quanti=-1):
        if self.posizione >= self.dimensione:
            return b""
        fine = self.dimensione if quanti is None or quanti < 0 else min(self.dimensione, self.posizione + quanti)
        if self.intero is not None:
            dati = self.intero[self.posizione:fine]
        else:
            parti = []
            for numero in range(self.posizione // self.BLOCCO, (fine - 1) // self.BLOCCO + 1):
                blocco = self._blocco(numero)
                if self.intero is not None:
                    parti = [self.intero[self.posizione:fine]]
                    break
                base = numero * self.BLOCCO
                parti.append(blocco[max(0, self.posizione - base):fine - base])
            dati = b"".join(parti)
        self.posizione += len(dati)
        return dati


def _leggi_dbf(contenuto):
    """Record di una tabella DBF (dBase III) come elenco di dizionari."""
    record, lunghezza_testa, lunghezza_record = struct.unpack("<IHH", contenuto[4:12])
    campi, posizione = [], 32
    while contenuto[posizione] != 0x0D:
        nome = contenuto[posizione:posizione + 11].split(b"\0")[0].decode("latin-1")
        campi.append((nome, contenuto[posizione + 16]))
        posizione += 32
    righe = []
    for i in range(record):
        inizio = lunghezza_testa + i * lunghezza_record
        if contenuto[inizio:inizio + 1] == b"*":   # record cancellato
            continue
        cursore, riga = inizio + 1, {}
        for nome, lunghezza in campi:
            riga[nome] = contenuto[cursore:cursore + lunghezza].decode("latin-1").strip()
            cursore += lunghezza
        righe.append(riga)
    return righe


@st.cache_data(ttl=1800, show_spinner=False)
def leggi_bollettino():
    """{"emesso": Timestamp, "giorni": {data: {zona: {rischio: livello}}}} dell'ultimo bollettino."""
    remoto = _FileRemoto(URL_BOLLETTINO, HTTP_FACOLTATIVO)
    archivio = zipfile.ZipFile(remoto)
    giorni, emesso = {}, None
    for nome in archivio.namelist():
        trovato = re.match(r"(\d{8})_(\d{4})_(today|tomorrow)\.dbf$", nome)
        if not trovato:
            continue
        emesso = pd.Timestamp(f"{trovato.group(1)} {trovato.group(2)}")
        data = emesso.date() + timedelta(days=1 if trovato.group(3) == "tomorrow" else 0)
        zone = {}
        for riga in _leggi_dbf(archivio.read(nome)):
            codice = riga.get("Zona_all", "")
            if codice.startswith("Cala-"):
                livelli = {nome_rischio: livello_da_testo(riga.get(campo, "")) for campo, nome_rischio in RISCHI.items()}
                livelli["complessiva"] = livello_da_testo(riga.get("Criticita", ""))
                zone[codice] = livelli
        giorni[data] = zone
    if not giorni:
        raise ValueError("bollettino senza dati per la Calabria")
    return {"emesso": emesso, "giorni": giorni}


# -----------------------------------------------------------------------------
# Comune -> zona di allerta
# -----------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _zone_comuni():
    with open(FILE_ZONE, encoding="utf-8") as file:
        return {normalizza_comune(r["comune"]): (r["zona"], r["nome_zona"]) for r in csv.DictReader(file)}


def zona_del_comune(comune):
    if not comune:
        return None
    chiave = normalizza_comune(comune)
    zone = _zone_comuni()
    if chiave in zone:
        return zone[chiave]
    # stesse regole dei suggerimenti: senza apostrofi né trattini
    semplice = " ".join(chiave.replace("'", " ").split())
    for nome, zona in zone.items():
        if " ".join(nome.replace("'", " ").split()) == semplice:
            return zona
    return None


def allerta_per_comune(comune, oggi):
    """Allerta ufficiale per oggi e domani nella zona del comune (None se non determinabile)."""
    zona = zona_del_comune(comune)
    if zona is None:
        return None
    try:
        bollettino = leggi_bollettino()
    except (requests.RequestException, zipfile.BadZipFile, ValueError, KeyError, struct.error):
        return {"zona": zona[0], "nome_zona": zona[1], "disponibile": False, "giorni": {}}

    giorni = {}
    for data in (oggi, oggi + timedelta(days=1)):
        livelli = bollettino["giorni"].get(data, {}).get(zona[0])
        if livelli is not None:
            giorni[data] = livelli
    return {
        "zona": zona[0],
        "nome_zona": zona[1],
        "disponibile": True,
        "emesso": bollettino["emesso"],
        "giorni": giorni,
    }


def descrivi_livelli(livelli):
    """Es. "Allerta gialla per temporali" (rischi al livello massimo) o "Nessuna allerta"."""
    if not livelli or livelli.get("complessiva", 0) == 0 and max(livelli.get(r, 0) for r in RISCHI.values()) == 0:
        return 0, LIVELLI_ALLERTA[0][1]
    massimo = max(livelli.get(r, 0) for r in RISCHI.values())
    massimo = max(massimo, livelli.get("complessiva", 0))
    rischi = [nome for nome in RISCHI.values() if livelli.get(nome, 0) == massimo]
    testo = LIVELLI_ALLERTA[massimo][1]
    if rischi:
        testo += " per rischio " + " e ".join(rischi)
    return massimo, testo
