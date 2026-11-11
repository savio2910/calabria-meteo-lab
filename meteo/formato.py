# =============================================================================
# Calabria Meteo Lab - Formattazione di numeri, date, direzioni e icone meteo.
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import html
import math

import pandas as pd

from meteo.config import CODICI_METEO, GIORNI_IT, MESI_IT


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


def icona_meteo_html(codice, notte=False):
    """Rende le icone notturne con livelli SVG realmente sovrapposti."""
    icona_fallback, descrizione = meteo(codice)

    if not notte:
        return html.escape(icona_fallback)

    try:
        if codice is None or pd.isna(codice):
            return html.escape(icona_fallback)
        codice = int(codice)
    except (TypeError, ValueError):
        return html.escape(icona_fallback)

    luna = (
        '<path d="M43 10A22 22 0 1 0 55 48A22 22 0 0 1 43 10Z" '
        'fill="#f9d674" stroke="#d4a942" stroke-width="2"/>'
    )
    nube_piccola = (
        '<path d="M32 43c0-3 2.2-5.3 5-5.3 1 0 1.8.2 2.5.6 '
        '1.2-3.5 4.3-5.8 8.1-5.8 4.2 0 7.5 2.9 8.2 6.6 '
        '3.4.1 6.2 2.8 6.2 6.2 0 3.6-3 6.5-6.7 6.5H38 '
        'c-3.5 0-6-2.9-6-6.5z" fill="#eaf2f6" '
        'stroke="#8ba6b7" stroke-width="2" stroke-linejoin="round"/>'
    )
    nube_grande = (
        '<path d="M14 43c0-4 3-7 7-7 1.1 0 2.1.2 3 .6 '
        '1.7-5.6 6.8-9.6 12.8-9.6 6.3 0 11.5 4.1 13 9.8 '
        '1.3-.5 2.7-.8 4.2-.8 6 0 10.8 4.8 10.8 10.8 '
        'S60 57.5 54 57.5H22c-4.5 0-8-3.5-8-8 0-2.5 1-4.7 3-6.5z" '
        'fill="#d9e4eb" stroke="#8499a8" stroke-width="2" '
        'stroke-linejoin="round"/>'
    )
    gocce = (
        '<g stroke="#4ea8e6" stroke-width="3.8" stroke-linecap="round">'
        '<path d="M24 60l-3 6M39 60l-3 6M54 60l-3 6"/>'
        '</g>'
    )
    gocce_deboli = (
        '<g stroke="#4ea8e6" stroke-width="3.8" stroke-linecap="round">'
        '<path d="M31 59l-3 6M48 59l-3 6"/>'
        '</g>'
    )
    fiocchi_neve = (
        '<g fill="#f5fbff" stroke="#8bbdd8" stroke-width="1.4" '
        'stroke-linecap="round">'
        '<path d="M24 60v12M18 66h12M19.5 61.5l9 9M28.5 61.5l-9 9"/>'
        '<path d="M39 60v12M33 66h12M34.5 61.5l9 9M43.5 61.5l-9 9"/>'
        '<path d="M54 60v12M48 66h12M49.5 61.5l9 9M58.5 61.5l-9 9"/>'
        '</g>'
    )

    fiocchi_neve_deboli = (
        '<g fill="none" stroke="#b9d9ea" stroke-width="1.4" '
        'stroke-linecap="round">'
        '<path d="M31 60v10M26 65h10M27.5 61.5l7 7M34.5 61.5l-7 7"/>'
        '<path d="M48 60v10M43 65h10M44.5 61.5l7 7M51.5 61.5l-7 7"/>'
        '</g>'
    )

    if codice == 0:
        elementi = luna

    elif codice == 1:
        elementi = luna + nube_piccola

    elif codice == 2:
        elementi = luna + nube_grande

    elif codice == 3:
        elementi = nube_grande

    elif codice in (51, 53, 80):
        elementi = luna + nube_grande + gocce_deboli

    elif codice in (55, 56, 57, 61, 63, 65, 66, 67, 81, 82):
        elementi = luna + nube_grande + gocce

    elif codice in (71, 85):
        elementi = luna + nube_grande + fiocchi_neve_deboli

    elif codice in (73, 75, 77, 86):
        elementi = luna + nube_grande + fiocchi_neve

    else:
        return html.escape(icona_fallback)

    return (
        '<svg class="cml-weather-svg" viewBox="0 0 76 76" '
        'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{html.escape(descrizione, quote=True)} di notte">'
        f'{elementi}</svg>'
    )


def sintesi_oraria_html(ore):
    """
    Genera tre righe di sintesi a partire dal DataFrame 'ore':
      - Prossimo cambiamento significativo
      - Fascia più piovosa (2 ore consecutive)
      - Raffica massima e orario
    """
    if ore.empty:
        return ""

    # Assumiamo che 'ore' abbia già le colonne:
    # time, temperature_2m, precipitation, wind_gusts_10m, Scenario, Icona, Da, Notte

    # Filtriamo alle prossime 24 ore
    ora_rif = ore["time"].min()
    ore_24 = ore.loc[
        (ore["time"] >= ora_rif)
        & (ore["time"] < ora_rif + pd.Timedelta(hours=24))
    ].copy()

    if ore_24.empty:
        return ""

    # 1) Prossimo cambiamento significativo
    # Definiamo cambiamento quando:
    #   - scenario cambia (es. da sereno a nuvoloso/pioggia) OPPURE
    #   - |ΔT| >= 2 °C in un'ora OPPURE
    #   - |Δvento| >= 15 km/h in un'ora
    scenario_prev = None
    cambio_idx = None

    temp_ora = ore_24["temperature_2m"].values
    vento_ora = ore_24["wind_gusts_10m"].values
    scenario_ora = ore_24["Scenario"].values
    time_ora = ore_24["time"].values

    for i in range(1, len(ore_24)):
        dT = abs(float(temp_ora[i]) - float(temp_ora[i - 1]))
        dV = abs(float(vento_ora[i]) - float(vento_ora[i - 1]))
        s_curr = scenario_ora[i]
        s_prev = scenario_ora[i - 1]

        if scenario_prev is not None and s_curr != s_prev:
            cambio_idx = i
            break
        if dT >= 2.0 or dV >= 15.0:
            cambio_idx = i
            break

        scenario_prev = s_prev

    if cambio_idx is not None:
        ora_cambio = pd.Timestamp(time_ora[cambio_idx]).strftime("%H:%M")
        testo_cambio = (
            f"Condizioni in evoluzione dalle {ora_cambio}: "
            f"{scenario_ora[cambio_idx]}."
        )
    else:
        testo_cambio = (
            "Nessun cambiamento significativo previsto nelle prossime 24 ore."
        )

    # 2) Fascia più piovosa (due ore consecutive)
    precip = ore_24["precipitation"].fillna(0.0).values
    best_start = 0
    best_sum = -1.0

    for i in range(len(precip) - 1):
        s = float(precip[i]) + float(precip[i + 1])
        if s > best_sum:
            best_sum = s
            best_start = i

    if best_sum > 0:
        t_start = pd.Timestamp(time_ora[best_start]).strftime("%H:%M")
        t_end = pd.Timestamp(time_ora[best_start + 1]).strftime("%H:%M")
        testo_pioggia = (
            f"Fascia più piovosa: {t_start}–{t_end}, "
            f"cumulo previsto {best_sum:.1f} mm."
        )
    else:
        testo_pioggia = "Precipitazione oraria nulla o trascurabile nelle prossime 24 ore."

    # 3) Raffica massima e orario
    raffiche_valide = pd.to_numeric(
        ore_24["wind_gusts_10m"], errors="coerce"
    ).replace([float("inf"), float("-inf")], float("nan")).dropna()
    if raffiche_valide.empty:
        testo_vento = "Raffica massima non disponibile: dati del vento mancanti."
    else:
        idx_max_gust = raffiche_valide.idxmax()
        max_gust = float(raffiche_valide.loc[idx_max_gust])
        ora_max_gust = pd.Timestamp(
            ore_24.loc[idx_max_gust, "time"]
        ).strftime("%H:%M")
        testo_vento = (
            f"Raffica massima prevista: {max_gust:.0f} km/h intorno alle {ora_max_gust}."
        )

    return f"""
    <section class="cml-nowcast-box">
      <div class="cml-nowcast-head">
        <span class="cml-eyebrow">PROSSIME ORE</span>
        <h2>🗣️ Le prossime ore, in parole chiare</h2>
        <p>
          Sintesi automatica basata sulla previsione ICON-2I
          per le prossime 24 ore.
        </p>
      </div>

      <ul class="cml-nowcast-list">
        <li>
          <span class="cml-nowcast-bullet">🔹</span>
          <span>{html.escape(testo_cambio)}</span>
        </li>
        <li>
          <span class="cml-nowcast-bullet">🔹</span>
          <span>{html.escape(testo_pioggia)}</span>
        </li>
        <li>
          <span class="cml-nowcast-bullet">🔹</span>
          <span>{html.escape(testo_vento)}</span>
        </li>
      </ul>

      <div class="cml-nowcast-note">
        ℹ️ Questa sintesi è generata in modo automatico dai dati orari
        e non sostituisce avvisi ufficiali o bollettini di protezione civile.
      </div>
    </section>
    """
