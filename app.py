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
            placeholder=(
                "Scrivi es. Cosenza, Tropea, Scilla, "
                "Camigliatello Silano, Serra San Bruno..."
            ),
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

    documento = genera_app_completa(
        luogo,
        latitudine,
        longitudine,
        dati_terrestri,
        dati_orari,
        dati_giornalieri,
        dati_mare,
        distanza_mare_km,
    )

    components.html(
        documento,
        height=4300,
        scrolling=True,
    )

except Exception as errore:
    st.error(str(errore))
