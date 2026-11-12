# =============================================================================
# Calabria Meteo Lab - Riquadro "Adesso", riga delle fonti e menu rapido
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import html
import json

import pandas as pd

from meteo.formato import direzione, icona_meteo_html, meteo, numero, ora_it, valore_finito

CODICI_TEMPORALE = {95, 96, 99}
CODICI_NEVE = {71, 73, 75, 77, 85, 86}
CODICI_NEBBIA = {45, 48}
SOGLIA_PIOGGIA_MM = 0.2  # mm nell'ora: sotto questa soglia l'ora è considerata asciutta

ORE_STRISCIA = 12


# -----------------------------------------------------------------------------
# Dati di supporto
# -----------------------------------------------------------------------------

def codice_attuale(corrente):
    """Codice meteo attuale; senza fenomeni, coerente con la nuvolosità."""
    codice = corrente.get("weather_code")
    nuvole = corrente.get("cloud_cover")
    if codice in (0, 1, 2, 3) and nuvole is not None and not pd.isna(nuvole):
        nuvole = float(nuvole)
        if nuvole <= 15:
            return 0
        if nuvole <= 45:
            return 1
        if nuvole <= 75:
            return 2
        return 3
    return codice


def riga_di_oggi(giorni, istante):
    """Riga giornaliera del giorno di 'istante' (o None)."""
    if giorni is None or giorni.empty or istante is None:
        return None
    data = pd.Timestamp(istante).date()
    righe = giorni.loc[giorni["time"].dt.date == data]
    return None if righe.empty else righe.iloc[0]


def _codice(valore):
    numero_intero = valore_finito(valore, None)
    return None if numero_intero is None else int(numero_intero)


def _ora(istante):
    return pd.Timestamp(istante).strftime("%H")


# -----------------------------------------------------------------------------
# Frase riassuntiva
# -----------------------------------------------------------------------------

def _tipo_fenomeno(righe):
    codici = {c for c in (_codice(v) for v in righe["weather_code"]) if c is not None}
    if codici & CODICI_TEMPORALE:
        return "temporale"
    if codici & CODICI_NEVE:
        return "neve"
    return "pioggia"


def _intensita(millimetri):
    if millimetri < 1:
        return "debole"
    if millimetri < 4:
        return "moderata"
    return "forte"


def frase_riassuntiva(ore, ore_totali=ORE_STRISCIA):
    """Una o due frasi semplici sulle prossime ore (pioggia, poi vento o temperatura)."""
    prossime = ore.head(ore_totali).reset_index(drop=True)
    if prossime.empty:
        return "Previsione oraria non disponibile."

    pioggia = pd.to_numeric(prossime["precipitation"], errors="coerce").fillna(0.0)
    codici = prossime["weather_code"].map(_codice)
    bagnata = (pioggia >= SOGLIA_PIOGGIA_MM) | codici.isin(CODICI_TEMPORALE)

    frasi = []

    # 1) Precipitazioni
    if bagnata.iloc[0]:
        asciutte = [i for i in range(1, len(prossime)) if not bagnata.iloc[i]]
        fine = asciutte[0] if asciutte else len(prossime)
        tipo = _tipo_fenomeno(prossime.iloc[:fine])
        inizio = {"temporale": "Temporale in corso", "neve": "Neve in corso", "pioggia": "Pioggia in corso"}[tipo]
        if asciutte:
            frasi.append(f"{inizio}, in attenuazione verso le {_ora(prossime.loc[fine, 'time'])}.")
        else:
            frasi.append(f"{inizio} per tutte le prossime {len(prossime)} ore.")
    elif bagnata.any():
        inizio = int(bagnata.idxmax())
        fine = inizio
        while fine + 1 < len(prossime) and bagnata.iloc[fine + 1]:
            fine += 1
        tratto = prossime.iloc[inizio:fine + 1]
        tipo = _tipo_fenomeno(tratto)
        ora_inizio = _ora(prossime.loc[inizio, "time"])
        if tipo == "temporale":
            frasi.append(f"Possibili temporali dalle {ora_inizio}.")
        else:
            massimo = float(pioggia.iloc[inizio:fine + 1].max())
            nome = "Neve" if tipo == "neve" else "Pioggia"
            frasi.append(f"{nome} {_intensita(massimo)} dalle {ora_inizio}.")
    else:
        nebbia = [i for i in range(len(prossime)) if codici.iloc[i] in CODICI_NEBBIA]
        if nebbia:
            frasi.append(f"Niente pioggia; possibile nebbia dalle {_ora(prossime.loc[nebbia[0], 'time'])}.")
        else:
            frasi.append(f"Niente pioggia nelle prossime {len(prossime)} ore.")

    # 2) Vento, altrimenti temperatura
    raffiche = pd.to_numeric(prossime["wind_gusts_10m"], errors="coerce")
    vento = pd.to_numeric(prossime["wind_speed_10m"], errors="coerce")
    temperatura = pd.to_numeric(prossime["temperature_2m"], errors="coerce")

    if raffiche.notna().any() and raffiche.max() >= 50:
        i = int(raffiche.idxmax())
        frasi.append(f"Raffiche fino a {raffiche.max():.0f} km/h verso le {_ora(prossime.loc[i, 'time'])}.")
    elif vento.notna().all() and vento.max() - vento.iloc[0] >= 15:
        i = int(vento.idxmax())
        frasi.append(f"Vento in aumento verso le {_ora(prossime.loc[i, 'time'])}.")
    elif temperatura.notna().all():
        t0 = temperatura.iloc[0]
        if temperatura.max() - t0 >= 3:
            i = int(temperatura.idxmax())
            frasi.append(f"Temperatura in salita fino a {temperatura.max():.0f}° verso le {_ora(prossime.loc[i, 'time'])}.")
        elif t0 - temperatura.min() >= 3:
            i = int(temperatura.idxmin())
            frasi.append(f"Temperatura in calo fino a {temperatura.min():.0f}° verso le {_ora(prossime.loc[i, 'time'])}.")

    return " ".join(frasi)


# -----------------------------------------------------------------------------
# Elementi HTML
# -----------------------------------------------------------------------------

def freccia_vento_html(gradi):
    """Freccia che indica dove va il vento (la provenienza è scritta accanto)."""
    gradi = valore_finito(gradi, None)
    if gradi is None:
        return ""
    verso = (gradi + 180) % 360
    return (
        '<svg class="cml-freccia-vento" viewBox="0 0 24 24" aria-hidden="true" '
        f'style="transform:rotate({verso:.0f}deg)">'
        '<path d="M12 2 L18 14 L13 12 L13 22 L11 22 L11 12 L6 14 Z" fill="currentColor"/>'
        "</svg>"
    )


def striscia_ore_html(ore, numero_ore=ORE_STRISCIA):
    elementi = []
    for indice, riga in ore.head(numero_ore).iterrows():
        pioggia = valore_finito(riga.get("precipitation"), 0.0)
        testo_pioggia = f"{pioggia:.1f} mm" if pioggia >= 0.1 else "—"
        etichetta = "Ora" if indice == ore.index[0] else riga["time"].strftime("%H:%M")
        descrizione = meteo(riga.get("weather_code"))[1]
        elementi.append(f"""
        <li class="cml-ora{' cml-ora-bagnata' if pioggia >= SOGLIA_PIOGGIA_MM else ''}"
            aria-label="{html.escape(etichetta, quote=True)}: {html.escape(descrizione, quote=True)}, {numero(riga.get('temperature_2m'), 0, ' gradi')}, pioggia {html.escape(testo_pioggia, quote=True)}">
          <span class="cml-ora-quando">{html.escape(etichetta)}</span>
          <span class="cml-ora-icona">{icona_meteo_html(riga.get("weather_code"), bool(riga.get("Notte", False)))}</span>
          <strong>{numero(riga.get("temperature_2m"), 0, "°")}</strong>
          <span class="cml-ora-pioggia">{html.escape(testo_pioggia)}</span>
        </li>""")
    return "".join(elementi)


def dati_cielo(corrente, ore, giorni):
    """Dati reali per disegnare il cielo animato (ora, sole, luna, nubi, pioggia, vento)."""
    istante = corrente.get("time")
    oggi = riga_di_oggi(giorni, istante)

    def testo(valore):
        return None if valore is None or pd.isna(valore) else str(pd.Timestamp(valore).strftime("%Y-%m-%dT%H:%M"))

    pioggia_ora = valore_finito(ore.iloc[0].get("precipitation"), 0.0) if not ore.empty else 0.0
    return {
        "ora": testo(istante),
        "alba": testo(oggi.get("sunrise")) if oggi is not None else None,
        "tramonto": testo(oggi.get("sunset")) if oggi is not None else None,
        "sorgeLuna": testo(oggi.get("moonrise")) if oggi is not None else None,
        "tramontaLuna": testo(oggi.get("moonset")) if oggi is not None else None,
        "faseLuna": valore_finito(oggi.get("moon_phase"), 0.5) if oggi is not None else 0.5,
        "nuvole": valore_finito(corrente.get("cloud_cover"), 0.0),
        "pioggia": max(pioggia_ora, valore_finito(corrente.get("precipitation"), 0.0)),
        "codice": _codice(corrente.get("weather_code")),
        "vento": valore_finito(corrente.get("wind_speed_10m"), 0.0),
        "direzioneVento": valore_finito(corrente.get("wind_direction_10m"), 270.0),
    }


def riquadro_adesso_html(luogo, corrente, ore, giorni):
    codice = codice_attuale(corrente)
    descrizione = meteo(codice)[1]
    istante = corrente.get("time")
    oggi = riga_di_oggi(giorni, istante)
    notte = bool(ore.iloc[0].get("Notte", False)) if not ore.empty else False

    minima = numero(oggi.get("temperature_2m_min"), 0, "°") if oggi is not None else "—"
    massima = numero(oggi.get("temperature_2m_max"), 0, "°") if oggi is not None else "—"
    alba = ora_it(oggi.get("sunrise")) if oggi is not None else "—"
    tramonto = ora_it(oggi.get("sunset")) if oggi is not None else "—"

    cielo_json = json.dumps(dati_cielo(corrente, ore, giorni), ensure_ascii=False).replace("<", "\\u003c")

    return f"""
<section id="cml-adesso" class="cml-adesso cml-sezione" aria-labelledby="cml-adesso-titolo">
  <canvas class="cml-cielo" id="cml-cielo" aria-hidden="true"></canvas>
  <button type="button" class="cml-cielo-pausa" id="cml-cielo-pausa" aria-pressed="false"
          aria-label="Metti in pausa l'animazione del cielo">⏸</button>

  <div class="cml-adesso-contenuto">
    <div class="cml-adesso-testa">
      <span class="cml-adesso-etichetta">ADESSO · {html.escape(ora_it(istante))}</span>
      <h1 id="cml-adesso-titolo">{html.escape(luogo)}</h1>
    </div>

    <div class="cml-adesso-principale">
      <div class="cml-adesso-temp">{numero(corrente.get("temperature_2m"), 0, "")}<span>°C</span></div>
      <div class="cml-adesso-condizione">
        <span class="cml-adesso-icona">{icona_meteo_html(codice, notte)}</span>
        <div>
          <strong>{html.escape(descrizione)}</strong>
          <span>Percepita {numero(corrente.get("apparent_temperature"), 0, "°")} · Min {minima} · Max {massima}</span>
        </div>
      </div>
    </div>

    <p class="cml-adesso-frase">{html.escape(frase_riassuntiva(ore))}</p>

    <div class="cml-adesso-dati">
      <div class="cml-dato">
        <span class="cml-dato-titolo">Vento</span>
        <span class="cml-dato-valore">{freccia_vento_html(corrente.get("wind_direction_10m"))}
          {numero(corrente.get("wind_speed_10m"), 0, " km/h")}
          <small>da {html.escape(direzione(corrente.get("wind_direction_10m")))}</small></span>
        <span class="cml-dato-nota">Raffiche {numero(corrente.get("wind_gusts_10m"), 0, " km/h")}</span>
      </div>
      <div class="cml-dato">
        <span class="cml-dato-titolo">Sole</span>
        <span class="cml-dato-valore">🌅 {html.escape(alba)} <small>alba</small></span>
        <span class="cml-dato-nota">🌇 {html.escape(tramonto)} tramonto</span>
      </div>
      <div class="cml-dato">
        <span class="cml-dato-titolo">Aria</span>
        <span class="cml-dato-valore">💧 {numero(corrente.get("relative_humidity_2m"), 0, "%")} <small>umidità</small></span>
        <span class="cml-dato-nota">☁️ Nubi {numero(corrente.get("cloud_cover"), 0, "%")} · {numero(corrente.get("pressure_msl"), 0, " hPa")}</span>
      </div>
    </div>

    <ol class="cml-ore" aria-label="Prossime {ORE_STRISCIA} ore">{striscia_ore_html(ore)}</ol>
  </div>
</section>
<script>window.CML_CIELO = {cielo_json};</script>
"""


def riga_fonti_html(dati_terrestri, correzione, dati_mare, is_costiero):
    """Fonte, ora di aggiornamento e stato dei servizi (verde = attivo, grigio = no)."""
    fonte = dati_terrestri.get("_fonte", "ICON-2I")
    ore_riserva = dati_terrestri.get("_ore_riserva") or []
    scaricato = dati_terrestri.get("_scaricato_alle")
    orario = f" · aggiornati alle {pd.Timestamp(scaricato).strftime('%H:%M')}" if scaricato else ""

    servizi = []
    if fonte != "ICON-2I":
        servizi.append(("parziale", "Previsione", "ICON-EU (ICON-2I non disponibile)"))
    elif ore_riserva:
        servizi.append(("parziale", "Previsione", f"ICON-2I + ICON-EU per {len(ore_riserva)} ore"))
    else:
        servizi.append(("attivo", "Previsione", "ICON-2I"))

    if correzione:
        servizi.append(("attivo", "Correzione", f"stazione {correzione.get('stazione', '')}"))
    else:
        servizi.append(("spento", "Correzione", "nessuna stazione vicina a quota simile"))

    if dati_mare:
        servizi.append(("attivo", "Mare", "previsione marina"))
    elif is_costiero:
        servizi.append(("spento", "Mare", "non disponibile"))
    else:
        servizi.append(("spento", "Mare", "località non costiera"))

    servizi.append(("attesa", "Radar", "caricamento…"))

    voci = "".join(
        f'<li class="cml-servizio cml-servizio-{stato}" id="cml-stato-{nome.lower()}">'
        f'<span class="cml-pallino" aria-hidden="true"></span>'
        f"<b>{html.escape(nome)}</b> <span>{html.escape(testo)}</span></li>"
        for stato, nome, testo in servizi
    )
    return f"""
<div class="cml-fonti">
  <p>Dati {html.escape(fonte)} (ItaliaMeteo–ARPAE) via Open-Meteo{html.escape(orario)}</p>
  <ul aria-label="Stato dei servizi">{voci}</ul>
</div>
"""


def menu_rapido_html(ha_mare):
    voci = [("cml-adesso", "Adesso"), ("cml-giorni", "Giorni"), ("cml-ora-per-ora", "Ora per ora")]
    if ha_mare:
        voci.append(("cml-mare", "Mare"))
    voci += [("cml-radar", "Radar"), ("cml-attivita", "Attività")]
    collegamenti = "".join(f'<a href="#{ancora}" data-vai="{ancora}">{testo}</a>' for ancora, testo in voci)
    return f'<nav class="cml-menu-rapido" id="cml-menu-rapido" aria-label="Sezioni della pagina">{collegamenti}</nav>'
