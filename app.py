# =============================================================================
# Calabria Meteo Lab
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# Uso personale soltanto: vietate copia, modifica, redistribuzione
# o riutilizzo, anche parziale, senza autorizzazione scritta dell’autore.
# =============================================================================

import streamlit as st
import streamlit.components.v1 as components

from meteo.api import scarica_previsione_mare, scarica_previsione_terrestre
from meteo.correzione import calcola_correzione_osservativa, scarica_osservazioni_meteostat
from meteo.dati import prepara_dati_terrestri
from meteo.localita import (
    carica_comuni_costieri,
    carica_elenco_comuni,
    comune_e_costiero,
    localita_da_posizione,
    risolvi_comune,
    risolvi_localita,
    trova_comune_scritto,
)
from meteo.pagina import aggiungi_altezza_automatica, genera_app_completa
from meteo.posizione import pulsante_posizione

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

      /* Pulsante "Usa la mia posizione": allineato al menu di ricerca */
      iframe[title="meteo.posizione.posizione_utente"] {
        display: block;
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

ELENCO_COMUNI = carica_elenco_comuni()

# Località arrivata da un link condiviso (?luogo=...): fissata per tutta la
# sessione, così le opzioni del menu restano stabili.
st.session_state.setdefault("luogo_da_link", st.query_params.get("luogo"))
luogo_da_link = st.session_state.luogo_da_link

opzioni = list(ELENCO_COMUNI)
indice_iniziale = None
if luogo_da_link:
    if luogo_da_link not in ELENCO_COMUNI:
        opzioni.insert(0, luogo_da_link)  # frazione o località fuori elenco
    indice_iniziale = opzioni.index(luogo_da_link)


def _nuova_scelta():
    # Una scelta nel menu ha la precedenza sulla posizione usata prima
    st.session_state.usa_posizione = False


colonna_ricerca, colonna_posizione = st.columns([4, 1.4], vertical_alignment="bottom")

with colonna_ricerca:
    scelta = st.selectbox(
        "Località",
        opzioni,
        index=indice_iniziale,
        key="localita",
        placeholder="Scrivi un comune o una frazione della Calabria…",
        accept_new_options=True,
        on_change=_nuova_scelta,
        label_visibility="collapsed",
    )

with colonna_posizione:
    posizione = pulsante_posizione(key="posizione")

if posizione and posizione.get("istante") != st.session_state.get("posizione_usata"):
    st.session_state.posizione_usata = posizione.get("istante")
    st.session_state.usa_posizione = True


# =============================================================================
# CONTROLLO INPUT
# =============================================================================

richiesta = None
if st.session_state.get("usa_posizione") and posizione:
    richiesta = ("posizione", float(posizione["lat"]), float(posizione["lon"]))
elif scelta:
    richiesta = ("scelta", scelta)
elif "lat" in st.query_params and "lon" in st.query_params:
    try:
        richiesta = ("posizione", float(st.query_params["lat"]), float(st.query_params["lon"]))
    except ValueError:
        richiesta = None

if richiesta is None:
    st.info(
        "Scrivi o scegli una località calabrese (comune o frazione), "
        "oppure premi «Usa la mia posizione»."
    )
    st.stop()


# =============================================================================
# ESECUZIONE
# =============================================================================

try:
    if richiesta[0] == "posizione":
        latitudine = round(richiesta[1], 3)
        longitudine = round(richiesta[2], 3)
        luogo, comune_amministrativo = localita_da_posizione(latitudine, longitudine)
        comune_amministrativo = comune_amministrativo or ""
        # Nel link le coordinate sono arrotondate (circa 1 km)
        st.query_params.from_dict({"lat": f"{latitudine:.2f}", "lon": f"{longitudine:.2f}"})
    else:
        # Testo scritto a mano che corrisponde a un solo comune -> quel comune
        scelta = scelta if scelta in ELENCO_COMUNI else (trova_comune_scritto(scelta, ELENCO_COMUNI) or scelta)
        if scelta in ELENCO_COMUNI:
            comune, provincia = ELENCO_COMUNI[scelta]
            luogo, latitudine, longitudine, comune_amministrativo = risolvi_comune(comune, provincia)
        else:
            luogo, latitudine, longitudine, comune_amministrativo = risolvi_localita(scelta)
        st.query_params.from_dict({"luogo": scelta})

    st.caption("🔗 Il link nella barra degli indirizzi riapre questa previsione: puoi copiarlo e condividerlo.")

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
