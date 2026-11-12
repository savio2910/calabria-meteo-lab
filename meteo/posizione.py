# =============================================================================
# Calabria Meteo Lab - Pulsante "Usa la mia posizione"
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import streamlit.components.v1 as components

from meteo.config import CARTELLA_APP

_componente = components.declare_component(
    "posizione_utente",
    path=str(CARTELLA_APP / "componenti" / "posizione"),
)


def pulsante_posizione(key=None):
    """Mostra il pulsante e restituisce {lat, lon, accuratezza, istante} o None."""
    return _componente(key=key, default=None)
