# =============================================================================
# Calabria Meteo Lab - Formattazione di numeri, date, direzioni e icone meteo.
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import math

import pandas as pd

from meteo.config import CODICI_METEO, GIORNI_IT, MESI_IT
from meteo.icone import icona_svg


def valore_finito(valore, default=0.0):
    """Converte uno scalare senza propagare NaN o infinito."""
    try:
        risultato = float(valore)
    except (TypeError, ValueError, OverflowError):
        return default
    return risultato if math.isfinite(risultato) else default


def numero(valore, decimali=1, unita=""):
    try:
        if valore is None or pd.isna(valore):
            return "—"

        return f"{float(valore):.{decimali}f}{unita}"

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
            return "", "Non disponibile"

        codice = int(float(codice))
    except (TypeError, ValueError):
        return "", "Non disponibile"

    return CODICI_METEO.get(
        codice,
        ("", "Non disponibile"),
    )


def data_it(valore):
    try:
        data = pd.Timestamp(valore)

        return (
            f"{GIORNI_IT[data.weekday()]} "
            f"{data.day} "
            f"{MESI_IT[data.month - 1]}"
        )

    except (TypeError, ValueError):
        return "Data non disponibile"


def ora_it(valore):
    try:
        if valore is None or pd.isna(valore):
            return "—"

        return pd.Timestamp(valore).strftime("%H:%M")

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


def e_notte(ora, alba, tramonto):
    try:
        if any(
            valore is None or pd.isna(valore)
            for valore in (ora, alba, tramonto)
        ):
            return False

        istante = pd.Timestamp(ora)

        return (
            istante < pd.Timestamp(alba)
            or istante >= pd.Timestamp(tramonto)
        )

    except (TypeError, ValueError):
        return False


def icona_meteo_html(codice, notte=False, animata=False):
    """Icona meteo disegnata (SVG): richiede lo sprite di meteo.icone nella pagina."""
    return icona_svg(codice, notte, meteo(codice)[1], animata)
