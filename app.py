# =============================================================================
# Calabria Meteo Lab
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# Uso personale soltanto: vietate copia, modifica, redistribuzione
# o riutilizzo, anche parziale, senza autorizzazione scritta dell’autore.
# =============================================================================

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from meteo.api import scarica_previsione_mare, scarica_previsione_terrestre
from meteo.correzione import calcola_correzione_osservativa, scarica_osservazioni_meteostat
from meteo.dati import prepara_dati_terrestri
from meteo.home_viva import aggiungi_home_viva
from meteo.localita import carica_comuni_costieri, comune_e_costiero, risolvi_localita
from meteo.pagina import aggiungi_altezza_automatica, genera_app_completa
from meteo.sfondo_meteo import aggiungi_sfondo_meteo

# =============================================================================
# CONFIGURAZIONE STREAMLIT
# =============================================================================

st.set_page_config(
    page_title="Calabria Meteo Lab",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      #MainMenu {visibility: hidden;}
      header {visibility: hidden;}
      footer {visibility: hidden;}

      .block-container {
      max-width: none !important;
      width: 100% !important;
      padding: 0.5rem 1rem 2rem 1rem !important;
      }

      [data-testid="stAppViewContainer"] {
        background: #eef5f8;
      }

      [data-testid="stHeader"] {
        background: transparent;
      }

      iframe {
        background: #eef5f8 !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# INTERFACCIA STREAMLIT
# =============================================================================

try:
    COMUNI_COSTIERI = carica_comuni_costieri()

except (FileNotFoundError, ValueError) as errore_costieri:
    st.error(str(errore_costieri))
    st.stop()

st.markdown("## 🔎 Seleziona località calabrese")

with st.form("search_form", clear_on_submit=False):
    colonna_input, colonna_bottone = st.columns([4, 1])

    with colonna_input:
        testo_localita = st.text_input(
            "Località",
            value="",
            placeholder="",
            label_visibility="collapsed",
        )

    with colonna_bottone:
        cerca_localita = st.form_submit_button(
            "Aggiorna previsione",
            use_container_width=True,
            type="primary",
        )


# =============================================================================
# CONTROLLO INPUT
# =============================================================================

if not testo_localita.strip():
    st.info(
        "Inserisci una località calabrese e premi «Aggiorna previsione» "
        "per visualizzare le previsioni."
    )
    st.stop()


if not cerca_localita and "previsione_caricata" not in st.session_state:
    st.stop()


# =============================================================================
# ESECUZIONE
# =============================================================================

try:
    (
        luogo,
        latitudine,
        longitudine,
        comune_amministrativo,
    ) = risolvi_localita(testo_localita)

    with st.spinner(
        f"Elaborazione previsione ICON-2I e radar per {luogo}..."
    ):
        dati_terrestri = scarica_previsione_terrestre(
            latitudine,
            longitudine,
        )

        dati_orari, dati_giornalieri = (
            prepara_dati_terrestri(
                dati_terrestri
            )
        )

        osservazioni, stazione_oss, ultima_osservazione = (
            scarica_osservazioni_meteostat(
                latitudine,
                longitudine,
                dati_terrestri.get("elevation"),
            )
        )

        correzione_osservativa = calcola_correzione_osservativa(
            dati_terrestri,
            osservazioni,
            stazione_oss,
            ultima_osservazione,
        )

        # Ricalcola le serie dopo la correzione osservativa
        dati_orari, dati_giornalieri = (
            prepara_dati_terrestri(
                dati_terrestri
            )
        )

        dati_mare = None
        distanza_mare_km = None

        is_costiero = comune_e_costiero(
            comune_amministrativo,
            COMUNI_COSTIERI,
        )

        if is_costiero:
            try:
                (
                    dati_mare,
                    distanza_mare_km,
                ) = scarica_previsione_mare(
                    latitudine,
                    longitudine,
                )

            except RuntimeError:
                dati_mare = None
                distanza_mare_km = None

    st.session_state.previsione_caricata = True
    ore_riserva = dati_terrestri.get("_ore_riserva") or []
    if dati_terrestri.get("_fonte", "ICON-2I") != "ICON-2I":
        st.warning(f"⚠️ Fonte dei dati: {dati_terrestri['_fonte']}.")
    elif ore_riserva:
        st.info(
            f"ℹ️ {len(ore_riserva)} ore non coperte da ICON-2I sono state completate "
            f"con ICON-EU (a partire dalle {pd.Timestamp(ore_riserva[0]).strftime('%d/%m %H:%M')})."
        )
    documento = genera_app_completa(
        luogo,
        latitudine,
        longitudine,
        dati_terrestri,
        dati_orari,
        dati_giornalieri,
        dati_mare,
        distanza_mare_km,
        correzione_osservativa,
        is_costiero,
    )
    documento = aggiungi_home_viva(documento)

    documento = aggiungi_sfondo_meteo(
        documento,
        luogo,
        dati_terrestri,
        dati_orari,
        dati_giornalieri,
        is_costiero=is_costiero,
    )
    
    documento = aggiungi_altezza_automatica(documento)

    # L'altezza viene poi adattata dallo script; 1100 px è il valore iniziale
    # (e quello di riserva, con scorrimento interno, se lo script non può agire).
    components.html(
        documento,
        height=1100,
        scrolling=True,
    )
    

except Exception as errore:
    st.error(str(errore))
