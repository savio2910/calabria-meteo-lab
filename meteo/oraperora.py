# =============================================================================
# Calabria Meteo Lab - Sezione "Ora per ora": elenco orario dei 3 giorni
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Una scheda per giorno (Oggi, Domani, ...) con una riga per ora: ora, icona,
# cielo, temperatura, pioggia con probabilità, vento con freccia. Toccando una
# riga si aprono i dettagli. Le righe si aprono senza JavaScript (<details>);
# static/oraperora.js gestisce solo il cambio di giorno.

import html

import pandas as pd

from meteo.adesso import freccia_vento_html
from meteo.formato import data_it, direzione, icona_meteo_html, meteo, numero, valore_finito
from meteo.indicatori import SOGLIE_INDICATORI, livello, quota_neve, valore_ora
from meteo.probabilita import PROBABILITA_MINIMA_MOSTRATA, SOGLIE_RAFFICHE


def _numero(valore, decimali=1):
    v = valore_finito(valore, None)
    return None if v is None else round(v, decimali)


def _neve_ora(riga, indicatori):
    pioggia = valore_finito(riga.get("precipitation"), 0.0)
    if pioggia < SOGLIE_INDICATORI["pioggia_mm"]:
        return None
    quota = quota_neve(valore_ora(indicatori, riga["time"], "zero_termico"))
    return quota if quota is not None and quota <= SOGLIE_INDICATORI["neve_quota_massima_m"] else None


def dati_ore(ore, probabilita=None, indicatori=None):
    """Una riga per ora con tutto ciò che serve al grafico e al dettaglio."""
    orarie = (probabilita or {}).get("orarie") or {}
    righe = []
    for _, riga in ore.iterrows():
        istante = pd.Timestamp(riga["time"])
        prob = orarie.get(istante) or {}
        icona, descrizione = meteo(riga.get("weather_code"))
        righe.append({
            "t": istante.strftime("%Y-%m-%dT%H:%M"),
            "data": istante.strftime("%Y-%m-%d"),
            "ora": istante.strftime("%H:%M"),
            "giorno": data_it(istante).capitalize(),
            "icona": icona,
            "cielo": descrizione,
            "notte": bool(riga.get("Notte", False)),
            "temp": _numero(riga.get("temperature_2m")),
            "percepita": _numero(riga.get("apparent_temperature")),
            "pioggia": _numero(riga.get("precipitation")),
            "prob": None if prob.get("pioggia") is None else round(prob["pioggia"] * 100),
            "temporali": None if prob.get("temporali") is None else round(prob["temporali"] * 100),
            "prob_raffiche": {s: round(p * 100) for s, p in (prob.get("raffiche") or {}).items()
                              if s in SOGLIE_RAFFICHE.values()},
            "vento": _numero(riga.get("wind_speed_10m"), 0),
            "raffiche": _numero(riga.get("wind_gusts_10m"), 0),
            "da": direzione(riga.get("wind_direction_10m")),
            "nubi": _numero(riga.get("cloud_cover"), 0),
            "umidita": _numero(riga.get("relative_humidity_2m"), 0),
            # quota neve solo se in quell'ora è prevista precipitazione (e sotto i 2000 m)
            "neve": _neve_ora(riga, indicatori),
            "cape": livello(valore_ora(indicatori, istante, "cape"), SOGLIE_INDICATORI["cape"]),
            "uv": _numero(valore_ora(indicatori, istante, "uv"), 0),
            "polveri": _numero(valore_ora(indicatori, istante, "polveri"), 0),
            "modelli": {
                chiave.replace("modello_temp_", ""): _numero(valore, 0)
                for chiave, valore in riga.items()
                if str(chiave).startswith("modello_temp_") and _numero(valore, 0) is not None
            },
        })
    return righe


LIVELLI_CAPE = ["basso", "moderato", "alto", "molto alto"]


def _fmt(valore, decimali=0, unita=""):
    if valore is None:
        return "—"
    return f"{valore:.{decimali}f}".replace(".", ",") + unita


def _riga_html(r, riga_originale, prima):
    pioggia_testo = ""
    if (r["pioggia"] or 0) >= 0.1:
        pioggia_testo = f"{_fmt(r['pioggia'], 1)} mm"
    if r["prob"] is not None and (r["prob"] >= 20 or pioggia_testo):
        pioggia_testo += (" · " if pioggia_testo else "") + f"{r['prob']}%"
    bagnata = (r["pioggia"] or 0) >= 0.2 or (r["prob"] or 0) >= 50

    dettagli = [
        f"🌡️ Percepita <b>{_fmt(r['percepita'], 0, '°')}</b>",
        f"💨 Raffiche <b>{_fmt(r['raffiche'], 0, ' km/h')}</b>",
        f"☁️ Nuvole <b>{_fmt(r['nubi'], 0, '%')}</b>",
        f"💧 Umidità <b>{_fmt(r['umidita'], 0, '%')}</b>",
    ]
    if r["prob"] is not None:
        dettagli.append(f"🎲 Probabilità di pioggia <b>{r['prob']}%</b>")
    for soglia in sorted(r["prob_raffiche"], reverse=True):     # la soglia più alta che conta
        if r["prob_raffiche"][soglia] >= PROBABILITA_MINIMA_MOSTRATA * 100:
            dettagli.append(f"🌬️ Probabilità di raffiche ≥ {soglia} km/h <b>{r['prob_raffiche'][soglia]}%</b>")
            break
    if r["temporali"] is not None and r["temporali"] >= 30:
        dettagli.append(f"⚡ Temporali nella zona <b>{r['temporali']}%</b>")
    if r["neve"] is not None:
        dettagli.append(f"❄️ Quota neve <b>circa {r['neve']:,} m</b>".replace(",", "."))
    if r["cape"]:
        dettagli.append(f"⛈️ Potenziale temporalesco <b>{LIVELLI_CAPE[r['cape']]}</b>")
    if r["uv"] is not None and r["uv"] >= 3:
        dettagli.append(f"☀️ Indice UV <b>{_fmt(r['uv'])}</b>")
    if r["polveri"] is not None and r["polveri"] >= 50:
        dettagli.append(f"🏜️ Polveri sahariane <b>{_fmt(r['polveri'])} µg/m³</b>")
    if len(r["modelli"]) > 1:
        dettagli.append("🧮 Temperatura nei modelli: " + " · ".join(
            f"{html.escape(nome)} <b>{_fmt(valore, 0, '°')}</b>" for nome, valore in r["modelli"].items()))

    etichetta_ora = "Ora" if prima else r["ora"]
    return f"""
      <details class="oo-ora{' oo-notte' if r['notte'] else ''}{' oo-bagnata' if bagnata else ''}">
        <summary aria-label="{html.escape(etichetta_ora, quote=True)}: {html.escape(r['cielo'], quote=True)}, {_fmt(r['temp'], 0)} gradi">
          <span class="oo-h">{html.escape(etichetta_ora)}</span>
          <span class="oo-ic">{icona_meteo_html(riga_originale.get('weather_code'), r['notte'])}</span>
          <span class="oo-cielo">{html.escape(r['cielo'])}</span>
          <strong class="oo-t">{_fmt(r['temp'], 0, '°')}</strong>
          <span class="oo-p">{html.escape(pioggia_testo) if pioggia_testo else '<span class="oo-nulla">—</span>'}</span>
          <span class="oo-v">{freccia_vento_html(riga_originale.get('wind_direction_10m'))}{_fmt(r['vento'])} <small>{html.escape(r['da'])}</small></span>
        </summary>
        <ul class="oo-extra"><li class="oo-extra-cielo">{html.escape(r['cielo'])}</li>{''.join(f'<li>{d}</li>' for d in dettagli)}</ul>
      </details>"""


def sezione_ora_per_ora_html(ore, probabilita=None, indicatori=None, giorni=None):
    righe = dati_ore(ore, probabilita, indicatori)
    originali = [r for _, r in ore.iterrows()]
    date = []
    for riga in righe:
        if riga["data"] not in date:
            date.append(riga["data"])

    riassunti = {}
    if giorni is not None and not giorni.empty:
        for _, g in giorni.iterrows():
            codice = g.get("weather_code_prevalente", g.get("weather_code"))
            riassunti[pd.Timestamp(g["time"]).strftime("%Y-%m-%d")] = (
                icona_meteo_html(codice), numero(g.get("temperature_2m_min"), 0, "°"), numero(g.get("temperature_2m_max"), 0, "°")
            )

    nomi = ["Oggi", "Domani"]
    schede, pannelli = [], []
    for indice, data in enumerate(date):
        etichetta = nomi[indice] if indice < len(nomi) else data_it(pd.Timestamp(data)).split(" ")[0].capitalize()
        icona, minima, massima = riassunti.get(data, ("", "—", "—"))
        attiva = indice == 0
        schede.append(f"""
        <button type="button" role="tab" class="oo-scheda" id="oo-scheda-{data}" data-data="{data}"
                aria-controls="oo-giorno-{data}" aria-selected="{'true' if attiva else 'false'}" tabindex="{0 if attiva else -1}">
          <span class="oo-scheda-nome">{html.escape(etichetta)}</span>
          <span class="oo-scheda-dati">{icona} {minima} / <b>{massima}</b></span>
        </button>""")
        righe_giorno = "".join(
            _riga_html(r, originali[k], k == 0) for k, r in enumerate(righe) if r["data"] == data
        )
        pannelli.append(f"""
      <div class="oo-elenco" role="tabpanel" id="oo-giorno-{data}" aria-labelledby="oo-scheda-{data}"{'' if attiva else ' hidden'}>
        <div class="oo-intestazione" aria-hidden="true"><span>Ora</span><span></span><span class="oo-cielo">Cielo</span><span>Temp.</span><span>Pioggia</span><span>Vento km/h</span></div>
        {righe_giorno}
      </div>""")

    return f"""
<section class="cml-radar-box oo" aria-labelledby="oo-titolo">
  <span class="cml-eyebrow">PROSSIMI 3 GIORNI</span>
  <h2 id="oo-titolo">🕒 Ora per ora</h2>
  <div class="oo-schede" role="tablist" aria-label="Scegli il giorno">{''.join(schede)}</div>
  {''.join(pannelli)}
  <p class="oo-piede">Tocca un'ora per i dettagli · pioggia in mm e probabilità · la freccia indica dove va il vento,
     la sigla da dove arriva · le righe scure sono le ore di buio</p>
</section>
"""
