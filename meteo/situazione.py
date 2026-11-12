# =============================================================================
# Calabria Meteo Lab - Situazione generale (pressione, aria in quota, correnti)
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Traduce in frasi le grandezze che guardano i previsori:
# - pressione al livello del mare nelle prossime 24 ore (tendenza);
# - temperatura a 850 hPa (circa 1500 m): aria fredda o calda in arrivo;
# - vento a 850 hPa: correnti con il nome del vento ed effetto sui versanti;
# - zero termico.

import html
import math

import numpy as np
import pandas as pd
import requests
import streamlit as st

from meteo.api import HTTP_FACOLTATIVO as HTTP
from meteo.config import API_METEO_URL

SOGLIE_SITUAZIONE = {
    "pressione_hpa": (-6, -3, 3),        # forte calo, calo, aumento (in 24 ore)
    "t850": (-4, 0, 16, 20),             # neve a bassa quota, neve in montagna, aria calda, ondata di calore
    "correnti_kmh": 20,                  # vento a 850 hPa oltre cui si parla di correnti
}

# Rosa dei venti (da dove soffia) e effetto sui versanti calabresi
VENTI = [
    ("Tramontana", "aria fredda da nord: più nubi e precipitazioni sui rilievi settentrionali, più sereno sul Tirreno meridionale"),
    ("Grecale", "più nubi e pioggia sul versante ionico, tempo migliore sul Tirreno"),
    ("Levante", "più nubi e pioggia sul versante ionico, tempo migliore sul Tirreno"),
    ("Scirocco", "aria umida da sud-est: più pioggia sul versante ionico e sui rilievi esposti; sul Tirreno caldo e secco"),
    ("Ostro", "aria calda da sud: possibile sabbia del Sahara, più nubi sui rilievi meridionali"),
    ("Libeccio", "più pioggia sul versante tirrenico e mare mosso sul Tirreno, più asciutto sullo Ionio"),
    ("Ponente", "più pioggia sul versante tirrenico, più asciutto sullo Ionio"),
    ("Maestrale", "aria più fresca da nord-ovest: rovesci sul Tirreno, cielo più sereno e vento sullo Ionio"),
]


def nome_vento(gradi):
    """Nome del vento dalla direzione di provenienza (8 settori)."""
    return VENTI[int(((gradi % 360) + 22.5) // 45) % 8]


@st.cache_data(ttl=1800, show_spinner=False)
def scarica_quota(latitudine, longitudine):
    """Temperatura e vento a 850 hPa (ECMWF; se non disponibile, il modello scelto da Open-Meteo)."""
    for modello in ("ecmwf_ifs025", None):
        parametri = {
            "latitude": latitudine, "longitude": longitudine, "timezone": "Europe/Rome",
            "forecast_days": 3, "wind_speed_unit": "kmh",
            "hourly": "temperature_850hPa,wind_speed_850hPa,wind_direction_850hPa",
        }
        if modello:
            parametri["models"] = modello
        try:
            risposta = HTTP.get(API_METEO_URL, params=parametri, timeout=10)
            risposta.raise_for_status()
            orario = risposta.json().get("hourly") or {}
        except (requests.RequestException, ValueError):
            continue
        if not orario.get("time"):
            continue
        tabella = pd.DataFrame({k: v for k, v in orario.items() if k != "time"},
                               index=pd.to_datetime(orario["time"])).apply(pd.to_numeric, errors="coerce")
        if tabella.notna().any().any():
            return tabella
    return None


def _metri(valore):
    """1645 -> "1.650 m" (arrotondato a 50 m, separatore delle migliaia italiano)."""
    return f"{int(round(valore / 50.0) * 50):,} m".replace(",", ".")


def _ora(istante):
    return f"{pd.Timestamp(istante):%H}"


def _quando(istante, adesso):
    giorni = (pd.Timestamp(istante).normalize() - pd.Timestamp(adesso).normalize()).days
    return {0: "oggi", 1: "domani", 2: "dopodomani"}.get(giorni, f"tra {giorni} giorni") + f" verso le {_ora(istante)}"


def frasi_situazione(ore, quota, indicatori, adesso):
    """Elenco di (icona, titolo, testo) sulla situazione generale delle prossime ore."""
    frasi = []
    adesso = pd.Timestamp(adesso).floor("h")

    # 1) Pressione: tendenza nelle prossime 24 ore
    if "pressure_msl" in ore and ore["pressure_msl"].notna().sum() > 12:
        serie = pd.Series(ore["pressure_msl"].to_numpy(dtype=float), index=pd.to_datetime(ore["time"])).dropna()
        ora0 = serie.index[0]
        dopo = serie.loc[serie.index <= ora0 + pd.Timedelta(hours=24)]
        variazione = dopo.iloc[-1] - dopo.iloc[0]
        forte, calo, aumento = SOGLIE_SITUAZIONE["pressione_hpa"]
        if variazione <= forte:
            testo = f"in forte calo ({variazione:+.0f} hPa in 24 ore): peggioramento in arrivo"
        elif variazione <= calo:
            testo = f"in calo ({variazione:+.0f} hPa in 24 ore): tempo in peggioramento"
        elif variazione >= aumento:
            testo = f"in aumento ({variazione:+.0f} hPa in 24 ore): tempo in miglioramento"
        else:
            testo = "stabile nelle prossime 24 ore"
        frasi.append(("🧭", "Pressione", f"{dopo.iloc[0]:.0f} hPa, {testo}."))

    # 2) Temperatura a circa 1500 m (850 hPa)
    if quota is not None and "temperature_850hPa" in quota and quota["temperature_850hPa"].notna().any():
        futuro = quota.loc[quota.index >= adesso, "temperature_850hPa"].dropna()
        if not futuro.empty:
            minima, quando_min = futuro.min(), futuro.idxmin()
            massima, quando_max = futuro.max(), futuro.idxmax()
            bassa, montagna, calda, calore = SOGLIE_SITUAZIONE["t850"]
            if minima <= bassa:
                testo = f"aria fredda: {minima:.0f}° {_quando(quando_min, adesso)}, neve possibile anche a bassa quota"
            elif minima <= montagna:
                testo = f"aria fredda in quota: {minima:.0f}° {_quando(quando_min, adesso)}, neve in montagna"
            elif massima >= calore:
                testo = f"aria molto calda: {massima:.0f}° {_quando(quando_max, adesso)}, ondata di calore"
            elif massima >= calda:
                testo = f"aria calda: fino a {massima:.0f}° {_quando(quando_max, adesso)}"
            else:
                testo = f"tra {minima:.0f}° e {massima:.0f}° nei prossimi giorni, nella norma"
            frasi.append(("🌡️", "Aria a 1.500 m", testo[0].upper() + testo[1:] + "."))

    # 3) Correnti in quota nelle prossime 24 ore (media dei vettori)
    if quota is not None and {"wind_speed_850hPa", "wind_direction_850hPa"} <= set(quota.columns):
        tratto = quota.loc[(quota.index >= adesso) & (quota.index < adesso + pd.Timedelta(hours=24))].dropna(
            subset=["wind_speed_850hPa", "wind_direction_850hPa"])
        if not tratto.empty:
            angoli = np.radians(tratto["wind_direction_850hPa"].to_numpy(dtype=float))
            forza = tratto["wind_speed_850hPa"].to_numpy(dtype=float)
            u, v = (forza * np.sin(angoli)).mean(), (forza * np.cos(angoli)).mean()
            velocita = math.hypot(u, v)
            if velocita >= SOGLIE_SITUAZIONE["correnti_kmh"]:
                nome, effetto = nome_vento(math.degrees(math.atan2(u, v)))
                frasi.append(("🌬️", "Correnti in quota",
                              f"Correnti di {nome} ({velocita:.0f} km/h a 1.500 m). {effetto[0].upper() + effetto[1:]}."))
            else:
                frasi.append(("🌬️", "Correnti in quota", "Deboli: niente flussi prevalenti, tempo guidato dai fenomeni locali."))

    # 4) Zero termico
    if indicatori is not None and "zero_termico" in indicatori and indicatori["zero_termico"].notna().any():
        futuro = indicatori.loc[indicatori.index >= adesso, "zero_termico"].dropna()
        if not futuro.empty:
            attuale, minimo, quando = futuro.iloc[0], futuro.min(), futuro.idxmin()
            testo = f"Ora intorno ai {_metri(attuale)}"
            if minimo < attuale - 300:
                testo += f", in discesa fino a circa {_metri(minimo)} {_quando(quando, adesso)}"
            frasi.append(("❄️", "Zero termico", testo + "."))
    return frasi


def situazione_html(frasi):
    if not frasi:
        return ""
    righe = "".join(
        f'<li><span class="sit-icona" aria-hidden="true">{icona}</span>'
        f'<div><b>{html.escape(titolo)}</b><span>{html.escape(testo)}</span></div></li>'
        for icona, titolo, testo in frasi
    )
    return f"""
<section class="cml-radar-box cml-situazione" aria-labelledby="sit-titolo">
  <span class="cml-eyebrow">COME I PREVISORI</span>
  <h2 id="sit-titolo">🌍 Situazione generale</h2>
  <ul>{righe}</ul>
  <p class="sit-nota">Dai modelli del Centro Europeo (ECMWF): pressione, aria e vento a circa 1.500 m, zero termico.</p>
</section>"""
