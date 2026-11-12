# =============================================================================
# Calabria Meteo Lab
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# Uso personale soltanto: vietate copia, modifica, redistribuzione
# o riutilizzo, anche parziale, senza autorizzazione scritta dell’autore.
# =============================================================================

from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components

from meteo.allerta import allerta_per_comune
from meteo.api import scarica_previsione_mare, scarica_previsione_terrestre
from meteo.combinato import combina, scarica_modelli_aggiuntivi
from meteo.config import FUSO_ORARIO
from meteo.correzione import calcola_correzione_osservativa, scarica_osservazioni_meteostat
from meteo.dati import prepara_dati_terrestri
from meteo.indicatori import scarica_indicatori
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
from meteo.probabilita import calcola_probabilita, scarica_ensemble, temporali_nell_intorno
from meteo.situazione import frasi_situazione, scarica_quota
from meteo.viaggio import (
    MEZZI,
    calcola_percorso,
    consiglia,
    e_in_calabria,
    geocodifica_italia,
    meteo_nei_punti,
    partenze_possibili,
    punti_di_controllo,
    valuta_partenza,
)
from meteo.viaggio_pagina import documento_viaggio

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

      /* Schede principali "Meteo" e "Viaggio": grandi e ben visibili */
      [data-testid="stTabs"] [role="tablist"] {
        gap: 10px;
      }
      [data-testid="stTabs"] [role="tab"] {
        padding: 12px 26px;
        border-radius: 16px 16px 0 0;
      }
      [data-testid="stTabs"] [role="tab"] p {
        font-size: 1.7rem;
        font-weight: 800;
      }
      @media (max-width: 680px) {
        [data-testid="stTabs"] [role="tab"] { padding: 10px 14px; }
        [data-testid="stTabs"] [role="tab"] p { font-size: 1.35rem; }
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

ELENCO_COMUNI = carica_elenco_comuni()


def mostra_documento(documento):
    """Mostra una pagina HTML nel riquadro che si adatta alla sua altezza."""
    # 1100 px è l'altezza iniziale (e di riserva, con scorrimento interno,
    # se lo script dell'altezza automatica non può agire).
    components.html(aggiungi_altezza_automatica(documento), height=1100, scrolling=True)


# =============================================================================
# SCHEDA METEO
# =============================================================================

def _nuova_scelta():
    # Una scelta nel menu ha la precedenza sulla posizione usata prima
    st.session_state.usa_posizione = False


SERVIZI_METEO = """
- **🌤️ Adesso**: temperatura, cielo e vento in questo momento, con una frase che riassume
  le prossime 12 ore e un cielo animato che segue i dati reali (sole, luna, nuvole, pioggia, vento).
- **⚠️ Allerta ufficiale**: il livello di allerta della Protezione Civile (temporali,
  idrogeologico, idraulico) per la zona della località, oggi e domani.
- **📅 Prossimi 3 giorni** e **🕒 Ora per ora**: minime, massime, pioggia, vento e cielo
  per ogni giorno e per ogni ora.
- **🎲 Probabilità e affidabilità**: quanto è probabile la pioggia e quanto è sicura la
  previsione, confrontando 91 scenari dei modelli europei (ICON-EU ed ECMWF).
- **❄️ Neve, ⛈️ temporali, ☀️ UV, 🏜️ polveri**: quota neve, potenziale temporalesco,
  indice UV e sabbia del Sahara quando contano.
- **🌊 Mare** (località costiere): altezza e direzione delle onde, temperatura dell'acqua.
- **📡 Radar, satellite e fulmini**: le precipitazioni e i fulmini osservati in questo momento.
- **🏃 Attività**: le ore migliori per escursioni, bici, corsa, foto, stelle, spiaggia, surf,
  kite, pesca e neve.

- **🌍 Situazione generale**: pressione, aria e correnti a circa 1.500 m e zero termico, spiegati a parole.

La previsione è **combinata da quattro modelli**: **ICON-2I** (ItaliaMeteo–ARPAE, dettaglio di circa 2 km,
adatto alle montagne e alle coste calabresi), **ECMWF IFS** e **AIFS** del Centro Europeo e **ICON-EU**.
ICON-2I pesa di più nelle prime ore, ECMWF dal secondo giorno. Quando possibile la previsione è
corretta con le osservazioni delle stazioni vicine. Puoi condividere la previsione copiando
l'indirizzo della pagina.
"""

SERVIZI_VIAGGIO = """
1. Scegli **partenza** e **arrivo** (almeno uno in Calabria), il **mezzo** e il **giorno**.
2. L'app calcola il percorso stradale e controlla il meteo circa **ogni 15 minuti di strada**,
   all'ora in cui ci passerai.
3. Prova una partenza **ogni 30 minuti** nella fascia che indichi e ti consiglia quella con il
   tempo migliore lungo tutto il percorso, segnalando le partenze da evitare.
4. Vedi il viaggio **passo passo** (strada, quota, meteo, giudizio) e su una **mappa**.

Auto, moto e bici hanno soglie diverse: la moto e la bici risentono di più di pioggia, vento e freddo.
Sono indicazioni basate sulla previsione: segui sempre gli avvisi ufficiali e lo stato delle strade.
"""


def mostra_meteo():
    st.markdown("Le previsioni per tutta la Calabria: scegli un comune o una frazione, oppure usa la tua posizione.")
    with st.expander("ℹ️ Cosa trovi qui"):
        st.markdown(SERVIZI_METEO)
    st.markdown("### 🔎 Seleziona località calabrese")

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

    # ---------- Controllo input ----------
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
        return

    # ---------- Esecuzione ----------
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

        with st.spinner(f"Elaborazione previsione per {luogo}..."):
            dati_terrestri = scarica_previsione_terrestre(latitudine, longitudine)

            # Modello combinato: ICON-2I + ECMWF IFS + ICON-EU + AIFS (se rispondono)
            try:
                combina(
                    dati_terrestri,
                    scarica_modelli_aggiuntivi(latitudine, longitudine),
                    datetime.now(FUSO_ORARIO).replace(tzinfo=None),
                )
            except Exception:
                pass  # resta la previsione ICON-2I

            osservazioni, stazione_oss, ultima_osservazione = scarica_osservazioni_meteostat(
                latitudine,
                longitudine,
                dati_terrestri.get("elevation"),
            )
            correzione_osservativa = calcola_correzione_osservativa(
                dati_terrestri,
                osservazioni,
                stazione_oss,
                ultima_osservazione,
            )
            # Serie orarie e giornaliere dopo la correzione osservativa
            dati_orari, dati_giornalieri = prepara_dati_terrestri(dati_terrestri)

            # Probabilità dagli ensemble: se non disponibili la pagina funziona senza
            try:
                probabilita = calcola_probabilita(
                    scarica_ensemble(latitudine, longitudine),
                    temporali_nell_intorno(latitudine, longitudine),
                    dati_orari,
                    dati_giornalieri,
                )
            except Exception:
                probabilita = None

            dati_mare = None
            distanza_mare_km = None
            is_costiero = comune_e_costiero(comune_amministrativo, COMUNI_COSTIERI)
            # Quota neve, potenziale temporalesco, polveri e UV (facoltativi)
            try:
                indicatori = scarica_indicatori(latitudine, longitudine)
            except Exception:
                indicatori = None

            # Situazione generale: pressione, aria e vento a circa 1500 m, zero termico
            try:
                situazione = frasi_situazione(
                    dati_orari,
                    scarica_quota(latitudine, longitudine),
                    indicatori,
                    datetime.now(FUSO_ORARIO).replace(tzinfo=None),
                )
            except Exception:
                situazione = []

            # Allerta ufficiale della Protezione Civile per la zona del comune
            try:
                allerta = allerta_per_comune(comune_amministrativo, datetime.now(FUSO_ORARIO).date())
            except Exception:
                allerta = None
            if is_costiero:
                try:
                    dati_mare, distanza_mare_km = scarica_previsione_mare(latitudine, longitudine)
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
            probabilita,
            allerta,
            indicatori,
            situazione,
        )
        mostra_documento(documento)

    except Exception as errore:
        st.error(str(errore))


# =============================================================================
# SCHEDA VIAGGIO
# =============================================================================

GIORNI_VIAGGIO = {"Oggi": 0, "Domani": 1, "Dopodomani": 2}


def risolvi_tappa(testo):
    """(nome, lat, lon, regione) di partenza o arrivo: comuni calabresi o località italiane."""
    etichetta = testo if testo in ELENCO_COMUNI else trova_comune_scritto(testo, ELENCO_COMUNI)
    if etichetta:
        comune, provincia = ELENCO_COMUNI[etichetta]
        nome, latitudine, longitudine, _ = risolvi_comune(comune, provincia)
        return nome, latitudine, longitudine, "Calabria"
    return geocodifica_italia(testo)


def calcola_viaggio(testo_partenza, testo_arrivo, mezzo, giorno, ora_da, ora_a):
    origine = risolvi_tappa(testo_partenza)
    destinazione = risolvi_tappa(testo_arrivo)
    if not (e_in_calabria(origine[3], origine[1], origine[2]) or e_in_calabria(destinazione[3], destinazione[1], destinazione[2])):
        raise ValueError("La partenza o l'arrivo devono essere in Calabria.")

    percorso = calcola_percorso((origine[1], origine[2]), (destinazione[1], destinazione[2]), mezzo)
    punti = punti_di_controllo(percorso)
    meteo_punti = meteo_nei_punti(tuple((round(p["lat"], 3), round(p["lon"], 3)) for p in punti))

    partenze = partenze_possibili(giorno, ora_da, ora_a)
    if not partenze:
        raise ValueError("Nessuna partenza possibile nella fascia scelta: per oggi l'orario è già passato.")
    valutazioni = [valuta_partenza(p, punti, meteo_punti, mezzo) for p in partenze]
    return {
        "origine": origine[0],
        "destinazione": destinazione[0],
        "mezzo": mezzo,
        "percorso": percorso,
        "valutazioni": valutazioni,
        "consigliata": consiglia(valutazioni),
    }


def mostra_viaggio():
    st.markdown(
        "Il meteo che incontrerai lungo la strada, passo passo, e **l'orario di partenza migliore** "
        "in base alle condizioni."
    )
    with st.expander("ℹ️ Come funziona"):
        st.markdown(SERVIZI_VIAGGIO)
    st.markdown("### 🚗 Pianifica un viaggio")

    opzioni = list(ELENCO_COMUNI)
    with st.form("form_viaggio"):
        colonna_a, colonna_b = st.columns(2)
        testo_partenza = colonna_a.selectbox(
            "Partenza", opzioni, index=None, accept_new_options=True,
            placeholder="Comune calabrese o località italiana…",
        )
        testo_arrivo = colonna_b.selectbox(
            "Arrivo", opzioni, index=None, accept_new_options=True,
            placeholder="Comune calabrese o località italiana…",
        )
        colonna_c, colonna_d, colonna_e = st.columns([1.3, 1, 2])
        etichette_mezzi = {f"{MEZZI[m][1]} {MEZZI[m][0]}": m for m in MEZZI}
        mezzo = etichette_mezzi[colonna_c.radio("Mezzo", list(etichette_mezzi), horizontal=True)]
        nome_giorno = colonna_d.selectbox("Giorno", list(GIORNI_VIAGGIO))
        ora_da, ora_a = colonna_e.slider("Partenza tra le", 0, 23, (7, 20), format="%d:00")
        calcola = st.form_submit_button("Calcola il viaggio", type="primary", use_container_width=True)

    if calcola:
        if not testo_partenza or not testo_arrivo:
            st.warning("Inserisci sia la partenza sia l'arrivo.")
            return
        oggi = datetime.now(FUSO_ORARIO).date()
        giorno = oggi + timedelta(days=GIORNI_VIAGGIO[nome_giorno])
        try:
            with st.spinner("Calcolo del percorso e del meteo lungo la strada…"):
                st.session_state.viaggio = calcola_viaggio(testo_partenza, testo_arrivo, mezzo, giorno, ora_da, ora_a)
        except Exception as errore:
            st.session_state.pop("viaggio", None)
            st.error(str(errore))
            return

    viaggio = st.session_state.get("viaggio")
    if not viaggio:
        return

    valutazioni = viaggio["valutazioni"]
    consigliata = viaggio["consigliata"]
    orari = [v["partenza"].strftime("%H:%M") for v in valutazioni]
    predefinito = consigliata["partenza"].strftime("%H:%M") if consigliata else orari[0]
    scelta = st.select_slider(
        "Mostra il viaggio con partenza alle", options=orari, value=predefinito, key="partenza_mostrata"
    )
    selezionata = valutazioni[orari.index(scelta)]
    mostra_documento(documento_viaggio(
        viaggio["origine"], viaggio["destinazione"], viaggio["mezzo"], viaggio["percorso"],
        valutazioni, selezionata, consigliata,
    ))


# =============================================================================
# SCHEDE
# =============================================================================

scheda_meteo, scheda_viaggio = st.tabs(["🌤️ Meteo", "🚗 Viaggio"])
with scheda_meteo:
    mostra_meteo()
with scheda_viaggio:
    mostra_viaggio()
