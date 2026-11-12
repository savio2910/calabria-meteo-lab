# =============================================================================
# Calabria Meteo Lab - Costruzione della pagina HTML completa.
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import html
import json
from datetime import datetime, timedelta

import pandas as pd

from meteo.adesso import menu_rapido_html, riga_fonti_html, riquadro_adesso_html
from meteo.allerta import LIVELLI_ALLERTA, URL_CFD_CALABRIA, descrivi_livelli
from meteo.attivita import sezione_attivita_html
from meteo.config import FUSO_ORARIO, GIORNI_PREVISIONE, leggi_static
from meteo.dati import stato_mare_da_onda, valuta_rischio_locale
from meteo.formato import data_it, direzione, meteo, numero, ora_it
from meteo.indicatori import riassunto_giorno, testi_indicatori
from meteo.oraperora import sezione_ora_per_ora_html
from meteo.probabilita import PROBABILITA_MINIMA_MOSTRATA, SOGLIE_RAFFICHE, testo_affidabilita
from meteo.situazione import situazione_html


STILE_CSS = leggi_static("stile.css")


def badge_rischio_html(livello, rischio):
    palette = {
        "verde": ("#4f6d7a", "○", "Indice meteo: nessun segnale"),
        "giallo": ("#2f6db3", "◔", "Indice meteo: attenzione"),
        "arancione": ("#6a3fb5", "◑", "Indice meteo: attenzione alta"),
        "rosso": ("#3b1f73", "●", "Indice meteo: attenzione molto alta"),
    }

    colore, icona, testo = palette.get(
        livello,
        palette["verde"],
    )

    # Per il livello verde il tipo di rischio ("nessuna criticità") ripeterebbe il testo
    dettaglio = "" if livello == "verde" else f" · {html.escape(rischio.capitalize())}"
    return (
        f'<span class="cml-risk-badge" style="background:{colore};">'
        f"<span>{icona}</span>"
        f"<span>{html.escape(testo)}{dettaglio}</span>"
        "</span>"
    )


def _testo_emissione(allerta):
    emesso = allerta.get("emesso")
    return f"bollettino del {emesso:%d/%m} ore {emesso:%H:%M}" if emesso is not None else "bollettino"


def banner_allerta_html(allerta, giorni):
    """Riquadro con l'allerta ufficiale, mostrato solo se oggi o domani c'è almeno un'allerta gialla."""
    if not allerta or not allerta.get("giorni"):
        return ""
    righe, massimo = [], 0
    for indice, (data, livelli) in enumerate(sorted(allerta["giorni"].items())):
        livello, testo = descrivi_livelli(livelli)
        if livello == 0:
            continue
        massimo = max(massimo, livello)
        quando = "Oggi" if indice == 0 else "Domani"
        righe.append(f"<li><b>{quando}</b> ({html.escape(data_it(data))}): {LIVELLI_ALLERTA[livello][0]} {html.escape(testo)}</li>")
    if not righe:
        return ""
    return f"""
<section class="cml-allerta cml-allerta-{massimo}" role="alert">
  <strong>⚠️ Allerta ufficiale della Protezione Civile</strong>
  <ul>{''.join(righe)}</ul>
  <p>Zona {html.escape(allerta['zona'])} «{html.escape(allerta['nome_zona'])}» · {html.escape(_testo_emissione(allerta))} ·
     <a href="{URL_CFD_CALABRIA}" target="_blank" rel="noopener">dettagli e indicazioni sul sito del Centro Funzionale Calabria</a></p>
</section>"""


def allerta_giorno_html(data, allerta):
    """Badge dell'allerta ufficiale nella scheda del giorno."""
    if not allerta or not allerta.get("disponibile"):
        return ""
    livelli = allerta["giorni"].get(data)
    if livelli is None:
        # Il bollettino copre oggi e domani: se c'è solo oggi, quello di domani esce entro le 16
        if len(allerta["giorni"]) == 1 and data == min(allerta["giorni"]) + timedelta(days=1):
            return '<div class="cml-allerta-giorno cml-allerta-giorno-nd">Allerta ufficiale: bollettino in arrivo (entro le 16)</div>'
        return ""
    livello, testo = descrivi_livelli(livelli)
    return (f'<div class="cml-allerta-giorno cml-allerta-giorno-{livello}" title="Protezione Civile · zona {html.escape(allerta["zona"])}">'
            f'{LIVELLI_ALLERTA[livello][0]} Protezione Civile: {html.escape(testo)}</div>')


def indicatori_giorno_html(data, ore, indicatori):
    """Quota neve, potenziale temporalesco, UV e polveri del giorno (solo quelli che contano)."""
    if indicatori is None:
        return ""
    testi = testi_indicatori(riassunto_giorno(indicatori, ore.loc[ore["time"].dt.date == data]))
    if not testi:
        return ""
    return '<div class="cml-giorno-extra">' + "".join(f"<span>{html.escape(t)}</span>" for t in testi) + "</div>"


def probabilita_giorno_html(data, probabilita):
    """Probabilità di pioggia, forchette delle temperature e affidabilità di un giorno."""
    giorno = ((probabilita or {}).get("giornaliere") or {}).get(data)
    if not giorno:
        return ""
    massima, minima = giorno["massima"], giorno["minima"]
    motivi = ", ".join(giorno.get("motivi") or [])
    vento = ""
    if giorno.get("raffica"):
        if giorno.get("vento"):
            vento += f'<span>💨 Vento <b>{giorno["vento"][0]:.0f}–{giorno["vento"][1]:.0f}</b> · '
        else:
            vento += "<span>💨 "
        vento += f'raffiche <b>{giorno["raffica"][0]:.0f}–{giorno["raffica"][1]:.0f} km/h</b></span>'
        for chiave, testo in (("burrasca", f"Raffiche ≥ {SOGLIE_RAFFICHE['burrasca']}"),
                              ("raffiche_forti", f"Raffiche ≥ {SOGLIE_RAFFICHE['forti']}")):
            if (giorno.get(chiave) or 0) >= PROBABILITA_MINIMA_MOSTRATA:
                vento += f'<span class="cml-prob-vento">🌬️ {testo} km/h: <b>{giorno[chiave] * 100:.0f}%</b></span>'
                break
    return f"""
              <div class="cml-giorno-prob" title="{html.escape(motivi, quote=True)}">
                <span>🎲 Pioggia <b>{giorno['pioggia'] * 100:.0f}%</b></span>
                <span>Max <b>{massima[0]:.0f}–{massima[1]:.0f}°</b></span>
                <span>Min <b>{minima[0]:.0f}–{minima[1]:.0f}°</b></span>
                {vento}
                <span class="cml-affidabilita-{giorno['affidabilita']}">{html.escape(testo_affidabilita(giorno['affidabilita']))}</span>
              </div>"""


def riquadro_correzione_html(correzione):
    if not correzione:
        return ""

    distanza = (
        f"{correzione['distanza_km']:.1f} km"
        if correzione.get("distanza_km") is not None
        else "non disponibile"
    )

    bias_temp = correzione["bias_temp"]
    segno_temp = "+" if bias_temp >= 0 else ""

    bias_umidita = correzione["bias_umidita"]
    segno_umidita = "+" if bias_umidita >= 0 else ""

    rapporto = correzione["rapporto_vento"]
    variazione_vento = (rapporto - 1) * 100
    segno_vento = "+" if variazione_vento >= 0 else ""

    return f"""
    <section class="cml-nowcast-box">
      <div class="cml-nowcast-head">
        <span class="cml-eyebrow">CORREZIONE CON OSSERVAZIONI</span>
        <h2>🔎 Previsione adattata alle osservazioni</h2>
        <p>
          Le prossime 6 ore sono corrette usando le osservazioni recenti della stazione
          Meteostat più vicina e affidabile.
        </p>
      </div>

      <div class="cml-marine-grid">
        <div class="cml-marine-card">
          <span>📍 Stazione</span>
          <strong style="font-size:16px;">{html.escape(correzione['stazione'])}</strong>
          <small>Distanza: {html.escape(distanza)}</small>
        </div>

        <div class="cml-marine-card">
          <span>🕒 Ultima osservazione</span>
          <strong>{ora_it(correzione['ultima_osservazione'])}</strong>
          <small>{correzione['numero_osservazioni']} osservazioni nelle ultime 3 ore</small>
        </div>

        <div class="cml-marine-card">
          <span>🌡️ Correzione temperatura</span>
          <strong>{segno_temp}{bias_temp:.1f} °C</strong>
          <small>Bias medio osservato</small>
        </div>

        <div class="cml-marine-card">
          <span>💧 Correzione umidità</span>
          <strong>{segno_umidita}{bias_umidita:.0f} %</strong>
          <small>Bias medio osservato</small>
        </div>

        <div class="cml-marine-card">
          <span>💨 Correzione vento</span>
          <strong>{segno_vento}{variazione_vento:.0f} %</strong>
          <small>Rapporto osservazione/modello</small>
        </div>
      </div>

      <div class="cml-nowcast-note">
        ℹ️ La correzione è più forte nelle prossime ore e si attenua progressivamente entro 6 ore.
        È una stima automatica e non sostituisce avvisi ufficiali o valutazioni di sicurezza.
      </div>
    </section>
    """


def genera_app_completa(
    luogo,
    latitudine,
    longitudine,
    dati_terrestri,
    ore,
    giorni,
    dati_mare=None,
    distanza_mare_km=None,
    correzione_osservativa=None,
    is_costiero=False,
    probabilita=None,
    allerta=None,
    indicatori=None,
    situazione=None,
):
    corrente = dati_terrestri["current"]

    mare_html = ""

    if (
        dati_mare is not None
        and isinstance(dati_mare, dict)
        and dati_mare.get("current")
    ):
        corrente_mare = dati_mare["current"]
        orarie_mare = pd.DataFrame(dati_mare.get("hourly", {}))
        giornaliere_mare = pd.DataFrame(dati_mare.get("daily", {}))

        if not orarie_mare.empty and "time" in orarie_mare:
            orarie_mare["time"] = pd.to_datetime(orarie_mare["time"])

        altezza_onda = corrente_mare.get("wave_height")
        direzione_onda = corrente_mare.get("wave_direction")
        periodo_onda = corrente_mare.get("wave_period")
        altezza_mare_vento = corrente_mare.get("wind_wave_height")
        altezza_swell = corrente_mare.get("swell_wave_height")
        temperatura_mare = corrente_mare.get("sea_surface_temperature")

        stato_mare, icona_mare, classe_mare = stato_mare_da_onda(altezza_onda)

        previsioni_mare_html = ""
        if not orarie_mare.empty and "time" in orarie_mare:
            adesso_mare = pd.Timestamp(datetime.now(FUSO_ORARIO).replace(tzinfo=None))
            triorarie = orarie_mare.loc[
                (orarie_mare["time"].dt.hour % 3 == 0)
                & (orarie_mare["time"].dt.minute == 0)
                & (orarie_mare["time"] >= adesso_mare.floor("h"))
            ].sort_values("time").copy()
            sezioni_mare = []
            for data_mare, gruppo_mare in triorarie.groupby(triorarie["time"].dt.date):
                righe_mare = []
                for _, riga_mare in gruppo_mare.iterrows():
                    stato_prev, icona_prev, classe_prev = stato_mare_da_onda(riga_mare.get("wave_height"))
                    righe_mare.append(f"""
                      <tr>
                        <td class="c-ora">{ora_it(riga_mare.get("time"))}</td>
                        <td class="c-scenario"><span class="cml-marine-forecast-status {classe_prev}" style="margin:0;">
                          {icona_prev} {html.escape(stato_prev)}</span></td>
                        <td class="c-temp" data-unita=" m">{numero(riga_mare.get("wave_height"), 2)}</td>
                        <td class="c-dato" data-etichetta="Onda da">{direzione(riga_mare.get("wave_direction"))} · {numero(riga_mare.get("wave_direction"), 0, "°")}</td>
                        <td class="c-dato" data-etichetta="Mare" data-unita=" °C">{numero(riga_mare.get("sea_surface_temperature"), 1)}</td>
                      </tr>
                    """)
                sezioni_mare.append(f"""
                  <div class="cml-marine-forecast-date" style="margin-top:18px;">
                    {html.escape(data_it(data_mare).title())}
                  </div>
                  <div class="cml-table-wrap">
                    <table class="cml-table cml-tabella-mare">
                      <thead><tr>
                        <th>Ora</th><th>Stato del mare</th><th>Altezza onda m</th>
                        <th>Direzione onda</th><th>Temp. mare °C</th>
                      </tr></thead>
                      <tbody>{''.join(righe_mare)}</tbody>
                    </table>
                  </div>
                """)
            previsioni_mare_html = f"""
              <details class="cml-fisarmonica" open data-chiudi-su-telefono>
              <summary class="cml-marine-forecast-title">🌊 Previsioni mare ogni 3 ore · prossimi {GIORNI_PREVISIONE} giorni</summary>
              <p style="color:#607987;font-size:12px;">
                Orari locali Europe/Rome. Valori alle ore indicate, non medie su tre ore.
                Per oggi sono mostrate solo le scadenze dall’ora corrente in avanti.
              </p>
              {''.join(sezioni_mare) if sezioni_mare else '<p>Nessuna scadenza trioraria disponibile.</p>'}
              </details>
            """
        else:
            previsioni_mare_html = '<p>Previsioni marine orarie non disponibili.</p>'

        mare_html = f"""
        <section class="cml-marine-box">
          <div class="cml-marine-head">
            <div>
              <span class="cml-eyebrow">BOLLETTINO COSTIERO</span>
              <h2>🌊 Vento e stato del mare</h2>
              <p>Stato attuale e previsione marina per il comune costiero di riferimento. La cella modellistica più vicina è a circa {numero(distanza_mare_km, 1, " km")} dal punto selezionato.</p>
            </div>
            <div class="cml-sea-status {classe_mare}">
              <span>{icona_mare}</span>
              <div><small>STATO DEL MARE</small><strong>{html.escape(stato_mare)}</strong></div>
            </div>
          </div>

          <div class="cml-marine-grid">
            <div class="cml-marine-card"><span>🌊 Altezza onda</span><strong>{numero(altezza_onda, 2, " m")}</strong><small>Onda significativa</small></div>
            <div class="cml-marine-card"><span>🧭 Provenienza onda</span><strong>{direzione(direzione_onda)}</strong><small>{numero(direzione_onda, 0, "°")}</small></div>
            <div class="cml-marine-card"><span>〰️ Periodo medio</span><strong>{numero(periodo_onda, 1, " s")}</strong><small>Intervallo medio d'onda</small></div>
            <div class="cml-marine-card"><span>💨 Mare del vento</span><strong>{numero(altezza_mare_vento, 2, " m")}</strong><small>Componente wind sea</small></div>
            <div class="cml-marine-card"><span>🌐 Mare di fondo</span><strong>{numero(altezza_swell, 2, " m")}</strong><small>Componente swell</small></div>
            <div class="cml-marine-card"><span>🌡️ Temperatura mare</span><strong>{numero(temperatura_mare, 1, " °C")}</strong><small>Temperatura superficiale</small></div>
          </div>

          {previsioni_mare_html}
          <div class="cml-marine-note">ℹ️ La direzione indica <b>da dove proviene</b> il moto ondoso. I valori sono stimati su griglia marina e possono essere meno rappresentativi presso baie, porti, promontori e costa molto frastagliata. Per navigazione e sicurezza consulta sempre fonti nautiche e avvisi ufficiali.</div>
        </section>
        """

    # ---------------------------------------------------------
    # SCHEDE GIORNALIERE
    # ---------------------------------------------------------

    etichette_giorni = ["OGGI", "DOMANI", "DOPODOMANI"]
    carte_html = []

    for indice, (_, riga) in enumerate(giorni.iterrows()):
        tag = (
            etichette_giorni[indice]
            if indice < len(etichette_giorni)
            else "PROSSIMAMENTE"
        )

        # La scheda sintetizza i fenomeni sulle 24 ore e il cielo medio diurno.
        codice_effettivo = riga.get(
            "weather_code_prevalente",
            riga.get("weather_code"),
        )

        try:
            if codice_effettivo is None or pd.isna(codice_effettivo):
                codice_effettivo = 3
            else:
                codice_effettivo = int(float(codice_effettivo))
        except (TypeError, ValueError):
            codice_effettivo = 3

        icona, descrizione = meteo(codice_effettivo)
        fase = html.escape(str(riga.get("Fase lunare", "🌙 Luna")))
        livello, rischio = valuta_rischio_locale(riga)
        badge_rischio = badge_rischio_html(livello, rischio)

        if codice_effettivo in [95, 96, 99]:
            classe_icona = "cml-icon-thunder"
        elif codice_effettivo in [71, 73, 75, 77, 85, 86]:
            classe_icona = "cml-icon-snow"
        elif (
            codice_effettivo in range(51, 68)
            or codice_effettivo in range(80, 83)
        ):
            classe_icona = "cml-icon-rain"
        elif codice_effettivo in [2, 3, 45, 48]:
            classe_icona = "cml-icon-cloud"
        else:
            classe_icona = "cml-icon-sun"

        carte_html.append(
            f"""
            <article class="cml-day-card" id="scheda-{riga['time'].date()}"
              role="button" tabindex="0"
              aria-label="Mostra {html.escape(data_it(riga['time']), quote=True)} ora per ora"
              onclick="window.vaiAlGiorno && vaiAlGiorno('{riga['time'].date()}')"
              onkeydown="if (event.key === 'Enter' || event.key === ' ') {{ event.preventDefault(); window.vaiAlGiorno && vaiAlGiorno('{riga['time'].date()}'); }}">
              <div class="cml-day-head">
                <span class="cml-day-tag">{tag}</span>

                <span class="cml-day-date">
                  {html.escape(data_it(riga["time"]))}
                </span>
              </div>

              <div class="cml-risk-row">
                {badge_rischio}
              </div>

              <div class="cml-day-weather">
                <div class="cml-day-icon {classe_icona}">
                  {icona}
                </div>

                <div>
                  <div class="cml-day-description">
                    {html.escape(descrizione)}
                  </div>

                  <div class="cml-day-moon">
                    {fase}
                  </div>
                </div>
              </div>

              <div class="cml-temperature-grid">
                <div class="cml-temp-box">
                  <span>MINIMA</span>

                  <strong class="cml-temp-min">
                    ↓ {numero(riga["temperature_2m_min"], 1, "°")}
                  </strong>
                </div>

                <div class="cml-temp-box">
                  <span>MASSIMA</span>

                  <strong class="cml-temp-max">
                    ↑ {numero(riga["temperature_2m_max"], 1, "°")}
                  </strong>
                </div>
              </div>

              {allerta_giorno_html(riga["time"].date(), allerta)}
              {probabilita_giorno_html(riga["time"].date(), probabilita)}
              {indicatori_giorno_html(riga["time"].date(), ore, indicatori)}

              <div class="cml-day-details">
                <div>
                  <span>☁️ Nuvolosità diurna</span>
                  <b>{numero(riga.get("cloud_cover_diurno"), 0, " %")}</b>
                </div>

                <div>
                  <span>🌧️ Precipitazione</span>
                  <b>{numero(riga.get("precipitation_sum"), 1, " mm")}</b>
                </div>

                <div>
                  <span>💨 Vento massimo</span>
                  <b>{numero(riga.get("wind_speed_10m_max"), 0, " km/h")}</b>
                </div>

                <div>
                  <span>🌬️ Raffica massima</span>
                  <b>{numero(riga.get("wind_gusts_10m_max"), 0, " km/h")}</b>
                </div>

                <div>
                  <span>🧭 Direzione dominante</span>
                  <b>{html.escape(str(riga.get("Da", "—")))}</b>
                </div>
              </div>

              <div class="cml-astro-grid">
                <div>
                  <span>☀️ Alba</span>
                  <b>{ora_it(riga.get("sunrise"))}</b>
                </div>

                <div>
                  <span>🌇 Tramonto</span>
                  <b>{ora_it(riga.get("sunset"))}</b>
                </div>

                <div>
                  <span>🌙 Sorge</span>
                  <b>{ora_it(riga.get("moonrise"))}</b>
                </div>

                <div>
                  <span>🌘 Tramonta</span>
                  <b>{ora_it(riga.get("moonset"))}</b>
                </div>
              </div>
              <span class="cml-day-vai">Vedi ora per ora →</span>
            </article>
            """
        )

    if ore.empty:
        raise RuntimeError(
            "Non sono disponibili dati orari futuri per la località selezionata."
        )

    ora_per_ora_html = sezione_ora_per_ora_html(ore, probabilita, indicatori, giorni)

    # ---------------------------------------------------------
    # HTML COMPLETO CON HOME / PREVISIONI / RADAR
    # ---------------------------------------------------------

    riquadro_correzione = riquadro_correzione_html(
        correzione_osservativa
    )

    sezione_attivita = sezione_attivita_html(
        luogo, ore, giorni, dati_mare, is_costiero, dati_terrestri.get("elevation"), indicatori, probabilita
    )

    # Riquadro "Adesso", fonti dei dati e menu rapido
    adesso_html = riquadro_adesso_html(luogo, corrente, ore, giorni, probabilita, indicatori)
    fonti_html = riga_fonti_html(dati_terrestri, correzione_osservativa, dati_mare, is_costiero, probabilita, allerta)
    banner_allerta = banner_allerta_html(allerta, giorni)
    menu_html = menu_rapido_html(bool(mare_html))
    mare_sezione = f'<div id="cml-mare" class="cml-sezione">{mare_html}</div>' if mare_html else ""

    script_app = (
        leggi_static("app.js")
        .replace("__CML_LAT__", str(latitudine))
        .replace("__CML_LON__", str(longitudine))
        .replace(
            "__CML_LUOGO_JSON__",
            # Stringa JavaScript sicura (apostrofi, virgolette, "</script>")
            json.dumps(str(luogo), ensure_ascii=False).replace("<", "\\u003c"),
        )
    )

    script_adesso = leggi_static("adesso.js")
    script_oraperora = leggi_static("oraperora.js")

    documento_html = f"""
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
{STILE_CSS}
</style>
</head>

<body>

<main id="cml-pagina">

{menu_html}

{banner_allerta}

<!-- ===================== ADESSO ===================== -->
{adesso_html}
{fonti_html}
{situazione_html(situazione)}
{riquadro_correzione}

<!-- ===================== PROSSIMI GIORNI ===================== -->
  <section class="cml-three-days cml-sezione" id="cml-giorni">
    <div class="cml-section-title">
      <div>
        <span>ORIZZONTE PREVISIONALE</span>

        <h2>📅 I prossimi tre giorni</h2>

        <p>
          Il riassunto di ogni giorno: toccalo per vederlo ora per ora.
        </p>
      </div>

      <div class="cml-pill">72 ore</div>
    </div>

    <div class="cml-days-grid">
      {''.join(carte_html)}
    </div>
    <div class="cml-note">
      ℹ️ L'«indice meteo» è una stima automatica di questa app, <b>non un'allerta ufficiale</b>.
      Per le allerte consulta il
      <a href="https://www.cfd.calabria.it/" target="_blank" rel="noopener">Centro Funzionale Multirischi – ARPACAL</a>.
    </div>

    <div class="cml-note">
      ℹ️ Le icone sintetizzano i fenomeni significativi sulle 24 ore;
      in assenza di fenomeni mostrano il cielo medio diurno.
      La nuvolosità riportata è la media diurna. Temperature, precipitazioni e vento
      rappresentano estremi o cumulati sulle 24 ore.
    </div>
  </section>

<!-- ===================== ORA PER ORA ===================== -->
<div id="cml-ora-per-ora" class="cml-sezione">
{ora_per_ora_html}
</div>

<!-- ===================== MARE ===================== -->
{mare_sezione}

<!-- ===================== RADAR, SATELLITE, FULMINI ===================== -->
<div id="cml-radar" class="cml-sezione">
  <section class="cml-radar-box">
    <div class="cml-radar-head">
      <div>
        <h2>📡 Radar precipitazioni live</h2>

        <p>
          Sequenza radar RainViewer centrata sulla località selezionata:
          {html.escape(luogo)}.
        </p>
      </div>

      <button
        class="cml-radar-btn"
        id="btn-play"
        type="button"
        onclick="togglePlayRadar()"
      >
        ⏸ Pausa
      </button>
    </div>

    <div id="radar-map"></div>

    <div class="cml-radar-footer">
      <span>
        🛰️ Base cartografica OpenStreetMap · Overlay radar RainViewer
      </span>

      <span>
        Frame:
        <span id="radar-timestamp" class="cml-radar-time">
          caricamento...
        </span>
      </span>
    </div>
  </section>

  <div class="cml-note">
    ℹ️ Il radar mostra le precipitazioni osservate dai frame disponibili.
    Non costituisce un bollettino di allerta né una previsione ufficiale.
  </div>

  <!-- ===================== SATELLITE NUVOLOSITÀ ===================== -->
  <details class="cml-fisarmonica cml-fisarmonica-mappa" open data-chiudi-su-telefono>
  <summary class="cml-fisarmonica-titolo">🛰️ Satellite · Nuvolosità</summary>
  <section class="cml-radar-box">
    <div class="cml-radar-head">
      <div>
        <h2>🛰️ Satellite · Nuvolosità</h2>
        <p>
          Immagini satellitari delle nubi, centrate sulla località
          selezionata: {html.escape(luogo)}.
          Controlla l’orario dell’immagine nella mappa.
        </p>
      </div>
    </div>

    <iframe
      title="Satellite della nuvolosità"
      loading="lazy"
      src="https://embed.windy.com/embed2.html?lat={latitudine}&amp;lon={longitudine}&amp;zoom=7&amp;level=surface&amp;overlay=satellite&amp;product=satellite&amp;menu=&amp;message=&amp;marker=true&amp;calendar=now&amp;pressure=&amp;type=map&amp;location=coordinates&amp;detail=&amp;metricWind=km%2Fh&amp;metricTemp=%C2%B0C"
      style="display:block;width:100%;height:520px;border:1px solid #d8e7eb;border-radius:16px;"
      allowfullscreen
    ></iframe>

    <div class="cml-radar-footer">
      <span>🛰️ Visualizzazione satellitare · Windy</span>
      <a
        href="https://www.windy.com/-Satellite-satellite?satellite,{latitudine},{longitudine},7"
        target="_blank"
        rel="noopener noreferrer"
      >
        Apri il satellite su Windy ↗
      </a>
    </div>

    <div class="cml-marine-note">
      ℹ️ Le immagini satellitari mostrano le nubi:
      non sono una misura diretta della pioggia al suolo.
      Se il widget non mostra il satellite, usa il collegamento
      oppure configura il riquadro dal generatore ufficiale Windy.
    </div>
  </section>
  </details>

  <!-- ===================== FULMINAZIONI ===================== -->
  <details class="cml-fisarmonica cml-fisarmonica-mappa" open data-chiudi-su-telefono>
  <summary class="cml-fisarmonica-titolo">⚡ Fulminazioni osservate</summary>
  <section class="cml-radar-box">
    <div class="cml-radar-head">
      <div>
        <h2>⚡ Fulminazioni osservate</h2>
        <p>
          Scariche rilevate dalla rete Blitzortung,
          con mappa centrata su {html.escape(luogo)}.
        </p>
      </div>
    </div>

    <iframe
      title="Mappa delle fulminazioni Blitzortung"
      loading="lazy"
      src="https://map.blitzortung.org/index.php?interactive=1&amp;NavigationControl=1&amp;FullScreenControl=1&amp;Cookies=0&amp;InfoDiv=1&amp;MenuButtonDiv=1&amp;ScaleControl=1#7/{latitudine}/{longitudine}"
      style="display:block;width:100%;height:520px;border:1px solid #d8e7eb;border-radius:16px;"
      allowfullscreen
    ></iframe>

    <div class="cml-radar-footer">
      <span>⚡ Dati: Blitzortung.org e collaboratori</span>
      <a
        href="https://map.blitzortung.org/#7/{latitudine}/{longitudine}"
        target="_blank"
        rel="noopener noreferrer"
      >
        Apri la mappa dei fulmini ↗
      </a>
    </div>

    <div class="cml-marine-note">
      ℹ️ La mappa mostra le scariche rilevate dalla rete,
      non una previsione dei fulmini.
      L’assenza di scariche visualizzate non garantisce
      l’assenza di rischio temporalesco.
      Consulta gli avvisi ufficiali.
    </div>
  </section>
  </details>
</div>

<!-- ===================== ATTIVITÀ ===================== -->
<div id="cml-attivita" class="cml-sezione">
  {sezione_attivita}
</div>

  <div class="cml-note">
    ℹ️ <b>Fonti dei modelli:</b> ICON-2I (ItaliaMeteo–ARPAE), ECMWF IFS e AIFS
    (Centro Europeo), ICON-EU (DWD) attraverso Open-Meteo; MOLOCH e BOLAM
    (CNR-ISAC), WRF (ItaliaMeteo, Fondazione CIMA, LaMMA) dai dati aperti di
    MeteoHub – Agenzia ItaliaMeteo (licenze CC BY / CC BY-SA).
  </div>

</main>

<!-- ===================== SCRIPT ===================== -->
<script>
{script_app}
</script>
<script>
{script_adesso}
</script>
<script>
{script_oraperora}
</script>

<!-- ===================== COPYRIGHT ===================== -->
<footer class="cml-copyright">
  <div><strong>Calabria Meteo Lab</strong> · © 2026 Saverio Campanella · Tutti i diritti riservati</div>
  <div>Codice, interfaccia e contenuti dell’applicazione sono protetti da copyright.</div>
</footer>

</body>
</html>
"""

    return documento_html


def aggiungi_altezza_automatica(documento_html):
    """Aggiunge lo script che adatta l'altezza del riquadro Streamlit alla pagina."""
    script = leggi_static("altezza_automatica.html")
    if "</body>" not in documento_html:
        return documento_html + script
    return documento_html.replace("</body>", script + "\n</body>", 1)
