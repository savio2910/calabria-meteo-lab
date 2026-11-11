# =============================================================================
# Calabria Meteo Lab - Preparazione dei dati orari e giornalieri, stato del mare, indice meteo.
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import math
from datetime import datetime

import pandas as pd

from meteo.config import FUSO_ORARIO
from meteo.formato import direzione, e_notte, fase_lunare, meteo, valore_finito


def calcola_dati_diurni(
    ore_giorno,
    alba,
    tramonto,
    ora_riferimento=None,
):
    if ore_giorno.empty:
        return 0, 0

    alba_ts = pd.to_datetime(alba, errors="coerce")
    tramonto_ts = pd.to_datetime(tramonto, errors="coerce")

    if pd.notna(alba_ts) and pd.notna(tramonto_ts):
        ore_diurne = ore_giorno.loc[
            (ore_giorno["time"] >= alba_ts)
            & (ore_giorno["time"] < tramonto_ts)
        ].copy()
    else:
        ore_diurne = ore_giorno.loc[
            (ore_giorno["time"].dt.hour >= 7)
            & (ore_giorno["time"].dt.hour <= 18)
        ].copy()

    if ore_diurne.empty:
        return 0, 0

    # Solo per oggi: conserva esclusivamente le ore diurne ancora future.
    if ora_riferimento is not None:
        ore_rimanenti = ore_diurne.loc[
            ore_diurne["time"] >= pd.Timestamp(ora_riferimento)
        ].copy()

        if not ore_rimanenti.empty:
            ore_diurne = ore_rimanenti

    nuvole = pd.to_numeric(
        ore_diurne["cloud_cover"],
        errors="coerce",
    ).fillna(0.0)

    nuvolosita_media = round(float(nuvole.mean()))

    if nuvolosita_media <= 25:
        return 0, nuvolosita_media

    if nuvolosita_media <= 40:
        return 1, nuvolosita_media

    if nuvolosita_media <= 70:
        return 2, nuvolosita_media

    return 3, nuvolosita_media


def calcola_codice_giornaliero(
    ore_giorno,
    codice_cielo,
    codice_daily=None,
    precipitazione_daily=None,
):
    """
    Sintesi delle 24 ore: i fenomeni significativi hanno priorità
    rispetto al cielo medio diurno. Gestisce anche valori NaN.
    """
    pioggia = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
    neve = {71, 73, 75, 77, 85, 86}
    temporali = {95, 96, 99}

    def numero_valido(valore):
        try:
            valore = float(valore)
        except (TypeError, ValueError):
            return None
        if pd.isna(valore) or not math.isfinite(valore):
            return None
        return valore

    def codice_valido(valore):
        valore = numero_valido(valore)
        return int(valore) if valore is not None else None

    daily = codice_valido(codice_daily)
    totale_daily = numero_valido(precipitazione_daily)
    totale_daily = totale_daily if totale_daily is not None else 0.0

    if ore_giorno is None or ore_giorno.empty:
        return daily if daily is not None else codice_cielo

    if "weather_code" in ore_giorno.columns:
        codici = pd.to_numeric(
            ore_giorno["weather_code"],
            errors="coerce",
        )
    else:
        codici = pd.Series(
            [pd.NA] * len(ore_giorno),
            index=ore_giorno.index,
        )

    if "precipitation" in ore_giorno.columns:
        precip = pd.to_numeric(
            ore_giorno["precipitation"],
            errors="coerce",
        ).clip(lower=0)
    else:
        precip = pd.Series(
            0.0,
            index=ore_giorno.index,
        )

    validi = codici.replace([float("inf"), float("-inf")], float("nan")).dropna().astype(int)
    totale_orario = float(precip.fillna(0.0).sum())
    totale = max(totale_orario, totale_daily)

    presenti_temporali = set(validi) & temporali
    if presenti_temporali:
        return max(presenti_temporali)

    if daily in temporali:
        return daily

    ore_bagnate = int((precip.fillna(0.0) >= 0.1).sum())
    ore_fenomeni = int(codici.isin(pioggia | neve).sum())
    significativo = (
        totale >= 0.5
        or ore_bagnate >= 2
        or ore_fenomeni >= 2
    )

    if significativo:
        fenomeni = validi[validi.isin(pioggia | neve)]

        if not fenomeni.empty:
            mask_neve = codici.isin(neve)
            mask_pioggia = codici.isin(pioggia)

            peso_neve = (
                int(mask_neve.sum()),
                float(precip[mask_neve].fillna(0.0).sum()),
            )
            peso_pioggia = (
                int(mask_pioggia.sum()),
                float(precip[mask_pioggia].fillna(0.0).sum()),
            )

            famiglia = neve if peso_neve > peso_pioggia else pioggia
            candidati = fenomeni[fenomeni.isin(famiglia)]

            if candidati.empty:
                candidati = fenomeni

            frequenze = candidati.value_counts()
            pari = frequenze[frequenze == frequenze.max()].index

            ordine = [
                51, 53, 55, 61, 63, 65, 80, 81, 82,
                56, 57, 66, 67, 77, 71, 73, 75, 85, 86,
            ]

            return int(
                max(
                    pari,
                    key=lambda c: ordine.index(c)
                    if c in ordine
                    else -1,
                )
            )

        if daily in pioggia | neve:
            return daily

        return 61

    if validi.empty and daily is not None:
        return daily

    return codice_cielo


def prepara_dati_terrestri(dati):
    ore_raw = pd.DataFrame(dati["hourly"])
    giorni = pd.DataFrame(dati["daily"])

    ore_raw["time"] = pd.to_datetime(
        ore_raw["time"]
    )

    giorni["time"] = pd.to_datetime(
        giorni["time"]
    )

    codici_prevalenti = []
    nuvolosita_giornaliera = []

    for _, riga_giorno in giorni.iterrows():
        data_giorno = riga_giorno["time"].date()

        ore_giorno = ore_raw.loc[
            ore_raw["time"].dt.date == data_giorno
        ]

        ora_locale = pd.Timestamp(
            datetime.now(FUSO_ORARIO).replace(tzinfo=None)
        ).floor("h")

        riferimento_giorno = (
            ora_locale
            if data_giorno == ora_locale.date()
            else None
        )

        codice, nubi = calcola_dati_diurni(
            ore_giorno,
            riga_giorno.get("sunrise"),
            riga_giorno.get("sunset"),
            riferimento_giorno,
        )

        codice = calcola_codice_giornaliero(
            ore_giorno,
            codice,
            riga_giorno.get("weather_code"),
            riga_giorno.get("precipitation_sum"),
        )
        codici_prevalenti.append(codice)
        nuvolosita_giornaliera.append(nubi)

    giorni["weather_code_prevalente"] = (
        codici_prevalenti
    )

    giorni["cloud_cover_diurno"] = (
        nuvolosita_giornaliera
    )

    giorni["Da"] = giorni[
        "wind_direction_10m_dominant"
    ].map(direzione)

    giorni["Fase lunare"] = giorni[
        "moon_phase"
    ].map(fase_lunare)

    ora_locale = datetime.now(
        FUSO_ORARIO
    ).replace(tzinfo=None)

    ore = ore_raw.loc[
        ore_raw["time"] >= pd.Timestamp(ora_locale).floor("h")
    ].copy()

    # Icone e scenari orari: codice weather_code orario di ICON-2I,
    # senza ricalcolare la classe del cielo dalla copertura nuvolosa.
    ore["Icona"] = ore["weather_code"].map(
        lambda codice: meteo(codice)[0]
    )

    ore["Scenario"] = ore["weather_code"].map(
        lambda codice: meteo(codice)[1]
    )

    ore["Da"] = ore["wind_direction_10m"].map(
        direzione
    )

    valori_notte = []

    for _, riga_ora in ore.iterrows():
        data_ora = riga_ora["time"].date()

        righe_giorno = giorni.loc[
            giorni["time"].dt.date == data_ora
        ]

        if righe_giorno.empty:
            valori_notte.append(False)
            continue

        giorno_corrente = righe_giorno.iloc[0]

        valori_notte.append(
            e_notte(
                riga_ora["time"],
                giorno_corrente.get("sunrise"),
                giorno_corrente.get("sunset"),
            )
        )

    ore["Notte"] = valori_notte

    return (
        ore.reset_index(drop=True),
        giorni.reset_index(drop=True),
    )


def stato_mare_da_onda(altezza_onda):
    try:
        if altezza_onda is None or pd.isna(altezza_onda):
            return (
                "Non disponibile",
                "⚪",
                "cml-mare-nd",
            )

        altezza = float(altezza_onda)

        if altezza < 0.10:
            return "Calmo", "🟦", "cml-mare-calmo"

        if altezza < 0.50:
            return (
                "Quasi calmo",
                "🟦",
                "cml-mare-quasi-calmo",
            )

        if altezza < 1.25:
            return (
                "Poco mosso",
                "🟩",
                "cml-mare-poco-mosso",
            )

        if altezza < 2.50:
            return "Mosso", "🟨", "cml-mare-mosso"

        if altezza < 4.00:
            return (
                "Molto mosso",
                "🟧",
                "cml-mare-molto-mosso",
            )

        if altezza < 6.00:
            return (
                "Agitato",
                "🟥",
                "cml-mare-agitato",
            )

        return (
            "Molto agitato",
            "🟥",
            "cml-mare-molto-agitato",
        )

    except (TypeError, ValueError):
        return (
            "Non disponibile",
            "⚪",
            "cml-mare-nd",
        )


def valuta_rischio_locale(riga):
    precipitazione = float(
        riga.get("precipitation_sum", 0) or 0
    )

    raffica = float(
        riga.get("wind_gusts_10m_max", 0) or 0
    )

    # La nuvolosità media serve soltanto per l'icona della scheda giornaliera.
    # Per i rischi usa il codice giornaliero restituito da ICON-2I.
    codice_meteo = int(valore_finito(riga.get("weather_code"), -1))

    if (
        precipitazione >= 100
        or raffica >= 100
        or codice_meteo in [96, 99]
    ):
        if codice_meteo in [95, 96, 99]:
            return "rosso", "temporali"

        if raffica >= 100:
            return "rosso", "vento"

        return "rosso", "precipitazioni"

    if (
        precipitazione >= 50
        or raffica >= 70
        or codice_meteo in [95, 96, 99]
    ):
        if codice_meteo in [95, 96, 99]:
            return "arancione", "temporali"

        if raffica >= 70:
            return "arancione", "vento"

        return "arancione", "precipitazioni"

    if (
        precipitazione >= 20
        or raffica >= 50
        or codice_meteo in [80, 81, 82]
    ):
        if codice_meteo in [80, 81, 82]:
            return "giallo", "rovesci"

        if raffica >= 50:
            return "giallo", "vento"

        return "giallo", "precipitazioni"

    return "verde", "nessuna criticità"
