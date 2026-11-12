# =============================================================================
# Calabria Meteo Lab - Costruzione della pagina HTML completa.
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import html
import json
from datetime import datetime

import pandas as pd

from meteo.attivita import tabella_attivita_luogo_html
from meteo.config import FUSO_ORARIO, GIORNI_PREVISIONE, leggi_static
from meteo.dati import stato_mare_da_onda, valuta_rischio_locale
from meteo.formato import data_it, direzione, e_notte, icona_meteo_html, meteo, numero, ora_it, sintesi_oraria_html, valore_finito


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

    return (
        f'<span class="cml-risk-badge" style="background:{colore};">'
        f"<span>{icona}</span>"
        f"<span>{html.escape(testo)} · {html.escape(rischio.title())}</span>"
        f"</span>"
    )


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
):
    corrente = dati_terrestri["current"]

    # Condizione attuale: icona coerente con la nuvolosità
    # quando non sono previsti fenomeni significativi.
    codice_corrente = corrente.get("weather_code")
    nuvolosita_corrente = corrente.get("cloud_cover")

    if (
        codice_corrente in (0, 1, 2, 3)
        and nuvolosita_corrente is not None
        and not pd.isna(nuvolosita_corrente)
    ):
        nuvolosita = float(nuvolosita_corrente)
        if nuvolosita <= 15: codice_corrente = 0
        elif nuvolosita <= 45: codice_corrente = 1
        elif nuvolosita <= 75: codice_corrente = 2
        else: codice_corrente = 3

    icona_corrente, descrizione_corrente = meteo(codice_corrente)
    sintesi_html = sintesi_oraria_html(ore)
    ora_corrente = corrente.get("time")
    alba_corrente = None
    tramonto_corrente = None

    if ora_corrente is not None and not giorni.empty:
        giorno_corrente = giorni.loc[
            giorni["time"].dt.date == pd.Timestamp(ora_corrente).date()
        ]
        if not giorno_corrente.empty:
            alba_corrente = giorno_corrente.iloc[0].get("sunrise")
            tramonto_corrente = giorno_corrente.iloc[0].get("sunset")

    icona_corrente_html = icona_meteo_html(
        corrente.get("weather_code"),
        e_notte(ora_corrente, alba_corrente, tramonto_corrente),
    )

    metriche = [
        (
            "🌡️",
            "Percepita",
            numero(
                corrente.get("apparent_temperature"),
                1,
                " °C",
            ),
        ),
        (
            "💧",
            "Umidità",
            numero(
                corrente.get("relative_humidity_2m"),
                0,
                " %",
            ),
        ),
        (
            "☁️",
            "Nuvolosità",
            numero(
                corrente.get("cloud_cover"),
                0,
                " %",
            ),
        ),
        (
            "💨",
            "Vento",
            numero(
                corrente.get("wind_speed_10m"),
                0,
                " km/h",
            ),
        ),
        (
            "🧭",
            "Provenienza",
            direzione(
                corrente.get("wind_direction_10m")
            ),
        ),
        (
            "🌬️",
            "Raffica",
            numero(
                corrente.get("wind_gusts_10m"),
                0,
                " km/h",
            ),
        ),
        (
            "🌀",
            "Pressione",
            numero(
                corrente.get("pressure_msl"),
                1,
                " hPa",
            ),
        ),
    ]

    metriche_html = "".join(
        f"""
        <div class="cml-metric-card">
          <div class="cml-metric-icon">{icona}</div>

          <div>
            <div class="cml-metric-label">
              {html.escape(etichetta)}
            </div>

            <div class="cml-metric-value">
              {html.escape(valore)}
            </div>
          </div>
        </div>
        """
        for icona, etichetta, valore in metriche
    )

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
                        <td>{ora_it(riga_mare.get("time"))}</td>
                        <td><span class="cml-marine-forecast-status {classe_prev}" style="margin:0;">
                          {icona_prev} {html.escape(stato_prev)}</span></td>
                        <td>{numero(riga_mare.get("wave_height"), 2)}</td>
                        <td>{direzione(riga_mare.get("wave_direction"))} · {numero(riga_mare.get("wave_direction"), 0, "°")}</td>
                        <td>{numero(riga_mare.get("sea_surface_temperature"), 1)}</td>
                      </tr>
                    """)
                sezioni_mare.append(f"""
                  <div class="cml-marine-forecast-date" style="margin-top:18px;">
                    {html.escape(data_it(data_mare).title())}
                  </div>
                  <div class="cml-table-wrap">
                    <table class="cml-table" style="min-width:680px;">
                      <thead><tr>
                        <th>Ora</th><th>Stazione del mare</th><th>Altezza onda m</th>
                        <th>Direzione onda</th><th>Temp. mare °C</th>
                      </tr></thead>
                      <tbody>{''.join(righe_mare)}</tbody>
                    </table>
                  </div>
                """)
            previsioni_mare_html = f"""
              <div class="cml-marine-forecast-title">🌊 Previsioni mare ogni 3 ore · prossimi {GIORNI_PREVISIONE} giorni</div>
              <p style="color:#607987;font-size:12px;">
                Orari locali Europe/Rome. Valori alle ore indicate, non medie su tre ore.
                Per oggi sono mostrate solo le scadenze dall’ora corrente in avanti.
              </p>
              {''.join(sezioni_mare) if sezioni_mare else '<p>Nessuna scadenza trioraria disponibile.</p>'}
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
              role="button" tabindex="0" aria-expanded="false"
              aria-controls="dettaglio-{riga['time'].date()}"
              aria-label="Mostra la previsione oraria per {html.escape(data_it(riga['time']), quote=True)}"
              onclick="mostraGiorno('{riga['time'].date()}', this, event)"
              onkeydown="if (event.target === this && (event.key === 'Enter' || event.key === ' ')) {{ event.preventDefault(); mostraGiorno('{riga['time'].date()}', this, event); }}">
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
              <!--DETTAGLIO-{riga['time'].date()}-->
            </article>
            """
        )

    # ---------------------------------------------------------
    # DETTAGLI ORARI (TABELLA PRIMA, GRAFICO DOPO)
    # ---------------------------------------------------------

    date_disponibili = sorted(ore["time"].dt.date.unique())

    if not date_disponibili:
        raise RuntimeError(
            "Non sono disponibili dati orari futuri per la località selezionata."
        )

    dati_grafici = {}
    tabelle_html = []

    for indice, data_giorno in enumerate(date_disponibili):
        chiave = str(data_giorno)

        ore_giorno = ore.loc[
            ore["time"].dt.date == data_giorno
        ].copy()

        dati_grafici[chiave] = {
            "ore": ore_giorno["time"].dt.strftime("%H:%M").tolist(),

            "temperatura": [
                round(float(valore), 1)
                if pd.notna(valore)
                else None
                for valore in ore_giorno["temperature_2m"].tolist()
            ],

            "nuvolosita": [
                round(float(valore), 0)
                if pd.notna(valore)
                else None
                for valore in ore_giorno["cloud_cover"].tolist()
            ],

            "precipitazione": [
                round(float(valore), 1)
                if pd.notna(valore)
                else None
                for valore in ore_giorno["precipitation"].tolist()
            ],

            "vento": [
                round(float(valore), 1)
                if pd.notna(valore)
                else None
                for valore in ore_giorno["wind_speed_10m"].tolist()
            ],

            "raffiche": [
                round(float(valore), 1)
                if pd.notna(valore)
                else None
                for valore in ore_giorno["wind_gusts_10m"].tolist()
            ],
        }

        righe_tabella = []

        for _, riga in ore_giorno.iterrows():
            classe_notte = (
                "cml-night-row"
                if bool(riga.get("Notte", False))
                else ""
            )
            icona_ora_html = icona_meteo_html(
                riga.get("weather_code"),
                bool(riga.get("Notte", False)),
            )

            righe_tabella.append(
                f"""
                <tr class="{classe_notte}">
                  <td>{riga["time"].strftime("%H:%M")}</td>

                  <td class="cml-scenario-cell">
                    <span class="cml-table-icon">
                      {icona_ora_html}
                    </span>

                    <span>
                      {html.escape(str(riga["Scenario"]))}
                    </span>
                  </td>

                  <td>{numero(riga["temperature_2m"], 1)}</td>
                  <td>{numero(riga["apparent_temperature"], 1)}</td>
                  <td>{numero(riga["precipitation"], 1)}</td>
                  <td>{numero(riga["wind_speed_10m"], 0)}</td>
                  <td>{html.escape(str(riga["Da"]))}</td>
                  <td>{numero(riga["wind_gusts_10m"], 0)}</td>
                  <td>{numero(riga["cloud_cover"], 0)}</td>
                  <td>{numero(riga["relative_humidity_2m"], 0)}</td>
                </tr>
                """
            )

        tabelle_html.append(
            f"""
            <div id="dettaglio-{chiave}" class="cml-day-inline-detail" hidden
                 onclick="event.stopPropagation()">

              <h3>
                🕒 Previsione oraria ·
                {html.escape(data_it(data_giorno).title())}
              </h3>

              <div class="cml-table-wrap">
                <table class="cml-table">
                  <thead>
                    <tr>
                      <th>Ora</th>
                      <th>Scenario</th>
                      <th>Temp. °C</th>
                      <th>Percepita °C</th>
                      <th>Pioggia mm</th>
                      <th>Vento km/h</th>
                      <th>Da</th>
                      <th>Raffica km/h</th>
                      <th>Nubi %</th>
                      <th>Umidità %</th>
                    </tr>
                  </thead>

                  <tbody>
                    {''.join(righe_tabella)}
                  </tbody>
                </table>
              </div>

              <div class="cml-chart-box">
              <div class="cml-chart-title">
                🌡️ Andamento della temperatura
              </div>

              <div class="cml-chart-subtitle">
                Temperatura prevista nelle diverse ore della giornata.
              </div>

              <div class="cml-chart-canvas-wrap">
                <canvas id="temperaturaChart-{chiave}"></canvas>
              </div>
            </div>

            <div class="cml-chart-box">
              <div class="cml-chart-title">
                ☁️ Nuvolosità e precipitazioni
              </div>

              <div class="cml-chart-subtitle">
                Nuvolosità prevista e precipitazione oraria.
              </div>

              <div class="cml-chart-canvas-wrap">
                <canvas id="nuvolositaPrecipitazioniChart-{chiave}"></canvas>
              </div>
            </div>

            <div class="cml-chart-box">
              <div class="cml-chart-title">
                💨 Andamento del vento
              </div>

              <div class="cml-chart-subtitle">
                Vento medio e raffiche previste.
              </div>

              <div class="cml-chart-canvas-wrap">
                <canvas id="ventoChart-{chiave}"></canvas>
              </div>
            </div>

            </div>
            """
        )

    dettagli_per_data = {
        str(data): dettaglio
        for data, dettaglio in zip(date_disponibili, tabelle_html)
    }

    carte_html = [
        carta.replace(
            f"<!--DETTAGLIO-{riga['time'].date()}-->",
            dettagli_per_data.get(
                str(riga['time'].date()),
                '<div class="cml-day-inline-empty">Nessuna ora futura disponibile per questo giorno.</div>',
            ),
        )
        for carta, (_, riga) in zip(carte_html, giorni.iterrows())
    ]

    dati_grafici_json = json.dumps(dati_grafici, ensure_ascii=False)

    # ---------------------------------------------------------
    # HTML COMPLETO CON HOME / PREVISIONI / RADAR
    # ---------------------------------------------------------

    riquadro_correzione = riquadro_correzione_html(
        correzione_osservativa
    )

    if "precipitation" not in corrente or corrente.get("precipitation") is None:
        try:
            ora_corrente = pd.Timestamp(
                corrente.get("time")
            ).floor("h")
    
            pioggia_ora = ore.loc[
                ore["time"] == ora_corrente,
                "precipitation",
            ]
    
            corrente["precipitation"] = (
                float(pioggia_ora.iloc[0])
                if not pioggia_ora.empty
                and pd.notna(pioggia_ora.iloc[0])
                else 0.0
            )
        except Exception:
            corrente["precipitation"] = 0.0
    
    tabella_attivita_luogo = tabella_attivita_luogo_html(
        luogo,
        corrente,
        is_costiero,
    )

    codice_sfondo = int(
        valore_finito(
            corrente.get("weather_code"),
            -1,
        )
    )

    ora_sfondo = pd.to_datetime(
        corrente.get("time"),
        errors="coerce",
    )

    notte_sfondo = False

    if pd.notna(ora_sfondo) and not giorni.empty:
        giorno_sfondo = giorni.loc[
            giorni["time"].dt.date == ora_sfondo.date()
        ]

        if not giorno_sfondo.empty:
            notte_sfondo = e_notte(
                ora_sfondo,
                giorno_sfondo.iloc[0].get("sunrise"),
                giorno_sfondo.iloc[0].get("sunset"),
            )

    if codice_sfondo in (95, 96, 99):
        classe_sfondo_meteo = "cml-bg-thunder"

    elif codice_sfondo in (71, 73, 75, 77, 85, 86):
        classe_sfondo_meteo = "cml-bg-snow"

    elif codice_sfondo in (
        51, 53, 55, 56, 57,
        61, 63, 65, 66, 67,
        80, 81, 82,
    ):
        classe_sfondo_meteo = "cml-bg-rain"

    elif codice_sfondo in (45, 48):
        classe_sfondo_meteo = "cml-bg-fog"

    elif codice_sfondo in (2, 3):
        classe_sfondo_meteo = "cml-bg-cloud"

    elif notte_sfondo:
        classe_sfondo_meteo = "cml-bg-night"

    else:
        classe_sfondo_meteo = "cml-bg-clear"
        
    script_app = (
        leggi_static("app.js")
        .replace("__CML_DATI_GRAFICI__", dati_grafici_json)
        .replace("__CML_LAT__", str(latitudine))
        .replace("__CML_LON__", str(longitudine))
        .replace(
            "__CML_LUOGO_JSON__",
            # Stringa JavaScript sicura (apostrofi, virgolette, "</script>")
            json.dumps(str(luogo), ensure_ascii=False).replace("<", "\\u003c"),
        )
    )

    documento_html = f"""
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
{STILE_CSS}
</style>
</head>

<body>

<!-- ===================== HOME ===================== -->
<section id="cml-home" class="cml-view">

  <section class="cml-home-hero">
    <div class="cml-hero-backdrop" aria-hidden="true">
      <div class="cml-hero-glow"></div>
      <div class="cml-hero-grid"></div>
    </div>

    <div class="cml-hero-content">
      <div class="cml-brand">
        <span class="cml-brand-mark"></span>
        CALABRIA · METEOROLOGIA LOCALE
      </div>

      <h1>
        <span class="cml-hero-title-line">Calabria</span>
        <span class="cml-hero-title-accent">Meteo Lab</span>
      </h1>

      <p class="cml-hero-lead">
        Previsioni locali, radar delle precipitazioni, satellite e fulminazioni
        per scegliere la località e leggere il tempo in Calabria.
      </p>

      <div class="cml-hero-badges">
        <span class="cml-hero-badge">🌦️ ICON-2I</span>
        <span class="cml-hero-badge">📡 Radar live</span>
        <span class="cml-hero-badge">🛰️ Satellite</span>
        <span class="cml-hero-badge">⚡ Fulmini</span>
      </div>
    </div>

    <div class="cml-hero-visual" aria-hidden="true">
      <svg class="cml-hero-scene" viewBox="0 0 420 260" role="img" aria-label="Illustrazione meteorologica della Calabria">
        <defs>
          <linearGradient id="cmlSky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#0b3f5c"/>
            <stop offset="55%" stop-color="#12708c"/>
            <stop offset="100%" stop-color="#22a3ad"/>
          </linearGradient>
          <linearGradient id="cmlSea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#0d6d86"/>
            <stop offset="100%" stop-color="#063a4d"/>
          </linearGradient>
          <linearGradient id="cmlLand" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#2f7a5b"/>
            <stop offset="100%" stop-color="#14453a"/>
          </linearGradient>
          <radialGradient id="cmlSun" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#ffe89a"/>
            <stop offset="70%" stop-color="#ffc247"/>
            <stop offset="100%" stop-color="#ff9d2e"/>
          </radialGradient>
        </defs>

        <rect width="420" height="260" fill="url(#cmlSky)"/>
        <!-- Radar meteorologico in lontananza -->
        <g class="cml-radar-sweep" opacity=".30">
          <circle cx="345" cy="155" r="72" fill="none"
                  stroke="#9ee8ed" stroke-width="1.4"/>
          <circle cx="345" cy="155" r="48" fill="none"
                  stroke="#9ee8ed" stroke-width="1.1"/>
          <circle cx="345" cy="155" r="24" fill="none"
                  stroke="#9ee8ed" stroke-width="1"/>
          <line x1="345" y1="155" x2="409" y2="155"
                stroke="#d7ffff" stroke-width="1.5"/>
        </g>
        
        <!-- Particelle atmosferiche -->
        <g class="cml-hero-particles" fill="#d8fbff">
          <circle cx="44" cy="52" r="2"/>
          <circle cx="68" cy="178" r="1.6"/>
          <circle cx="244" cy="31" r="1.5"/>
          <circle cx="386" cy="126" r="2"/>
          <circle cx="256" cy="175" r="1.4"/>
          <circle cx="29" cy="213" r="1.3"/>
        </g>
        
        <!-- Fulmine discreto -->
        <path
          class="cml-hero-lightning"
          d="M252 104 L234 142 L251 142 L239 172 L274 126 L256 126 Z"
          fill="#fff1a3"
          opacity="0"
        />
        <g class="cml-hero-sun">
          <circle cx="318" cy="72" r="34" fill="url(#cmlSun)"/>
          <g class="cml-hero-rays" stroke="#ffd166" stroke-width="4" stroke-linecap="round">
            <line x1="318" y1="16" x2="318" y2="28"/>
            <line x1="318" y1="116" x2="318" y2="128"/>
            <line x1="262" y1="72" x2="274" y2="72"/>
            <line x1="362" y1="72" x2="374" y2="72"/>
            <line x1="279" y1="33" x2="288" y2="42"/>
            <line x1="348" y1="102" x2="357" y2="111"/>
            <line x1="357" y1="33" x2="348" y2="42"/>
            <line x1="288" y1="102" x2="279" y2="111"/>
          </g>
        </g>

        <g class="cml-hero-cloud">
          <path d="M116 96c0-16 13-29 29-29 8 0 15 3 20 9 5-12 17-20 31-20 19 0 34 15 34 34 0 2 0 4-1 6h-113z" fill="#eaf4f8" opacity=".94"/>
          <path d="M70 122c0-12 10-22 22-22 6 0 11 2 15 7 4-9 13-15 24-15 14 0 26 12 26 26 0 2 0 3-1 4H70z" fill="#dcebf1" opacity=".82"/>
        </g>

        <g class="cml-hero-rain" stroke="#8ed8f2" stroke-width="4" stroke-linecap="round">
          <line x1="112" y1="140" x2="104" y2="162"/>
          <line x1="140" y1="140" x2="132" y2="162"/>
          <line x1="168" y1="140" x2="160" y2="162"/>
          <line x1="196" y1="140" x2="188" y2="162"/>
        </g>

        <path d="M0 197c48-38 92-58 141-52 40 5 69 24 110 18 49-7 89-33 169-24v121H0z" fill="url(#cmlLand)"/>
        <path d="M0 226c58-25 111-34 168-22 55 12 96 7 138-11 43-18 78-20 114-10v87H0z" fill="url(#cmlSea)"/>
        <g class="cml-hero-waves" stroke="#9be3ef" stroke-width="3" stroke-linecap="round" opacity=".7">
          <path d="M35 236c14-7 28-7 42 0"/>
          <path d="M112 247c14-7 28-7 42 0"/>
          <path d="M208 238c14-7 28-7 42 0"/>
          <path d="M292 250c14-7 28-7 42 0"/>
        </g>
      </svg>
    </div>
  </section>

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

  <!-- ===================== FULMINAZIONI ===================== -->
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

</section>



  <section class="cml-home-actions">

    <button
      class="cml-home-choice"
      type="button"
      onclick="mostraVista('previsioni')"
    >
      <div class="cml-home-choice-icon">📅</div>

      <h2>Previsioni orarie</h2>

      <p>
        Consulta condizioni attuali, temperatura, vento, precipitazioni,
        tabelle ora per ora e grafici per i prossimi tre giorni.
      </p>

      <span>Apri previsioni →</span>
    </button>

    <button
      class="cml-home-choice activities"
      type="button"
      onclick="apriVistaAttivita()"
    >
      <div class="cml-home-choice-icon">🏃</div>

      <h2>Attività</h2>

      <p>
        Scopri quali attività sono più adatte alle condizioni meteorologiche
        previste nelle diverse zone della Calabria.
      </p>

      <span>Apri attività →</span>
    </button>

  </section>

</section>


<!-- ===================== PREVISIONI ===================== -->
<section
  id="cml-previsioni"
  class="cml-view {classe_sfondo_meteo}"
  hidden
>

  <div class="cml-nav-bar">
    <button
      class="cml-back-btn"
      type="button"
      onclick="mostraVista('home')"
    >
      ← Torna alla home
    </button>

    <span class="cml-nav-title">
      📅 Previsioni orarie · {html.escape(luogo)}
    </span>
  </div>

  <section class="cml-hero">
    <div class="cml-brand">
      <span class="cml-brand-mark"></span>
      CALABRIA · METEOROLOGIA LOCALE
    </div>

    <h1>Previsioni per {html.escape(luogo)}</h1>

    <p>
      Previsioni ad alta risoluzione per la località selezionata:
      temperatura, cielo, vento, precipitazioni e sviluppo delle
      prossime 72 ore.
    </p>
  </section>

  <section class="cml-current">
    <div class="cml-current-main">
      <div class="cml-place-block">

        <div class="cml-kicker">
          <span class="cml-live-dot"></span>
          ICON-2I · PREVISIONE LOCALE
        </div>

        <h2>📍 {html.escape(luogo)}</h2>

        <div class="cml-condition">
          <span class="cml-current-weather-icon">
            {icona_corrente_html}
          </span>

          {html.escape(descrizione_corrente)}
        </div>

      </div>

      <div class="cml-temperature">
        <span>{numero(corrente.get("temperature_2m"), 1, "")}</span>
        <small>°C</small>
      </div>
    </div>

    <div class="cml-metrics">
      {metriche_html}
    </div>

    <div class="cml-current-footer">
      <span>
        ◷ Valido alle
        <b>{html.escape(str(corrente.get("time", "—")))}</b>
      </span>

      <span>
        ◉ Fuso
        <b>Europe/Rome</b>
      </span>

      <span>
        ◌ Fonte
        <b>ItaliaMeteo–ARPAE</b>
      </span>
    </div>
  </section>

  {mare_html}
  {riquadro_correzione}
  {sintesi_html}

  <section class="cml-three-days">
    <div class="cml-section-title">
      <div>
        <span>ORIZZONTE PREVISIONALE</span>

        <h2>📅 I prossimi tre giorni</h2>

        <p>
          Premi sul giorno che ti interessa per visualizzare prima
          la previsione oraria e poi il grafico.
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

  <div class="cml-note">
    ℹ️ <b>ICON-2I:</b> modello deterministico ad alta risoluzione
    di ItaliaMeteo–ARPAE. I dati terrestri sono forniti attraverso
    Open-Meteo.
  </div>

</section>


<!-- ===================== RADAR ===================== -->



<!-- ===================== ATTIVITÀ ===================== -->
<section id="cml-attivita" class="cml-view" hidden>

  <div class="cml-nav-bar">
    <button
      class="cml-back-btn"
      type="button"
      onclick="mostraVista('home')"
    >
      ← Torna alla home
    </button>

    <span class="cml-nav-title">
      🏃 Attività consigliate · {html.escape(luogo)}
    </span>
  </div>

  {tabella_attivita_luogo}

</section>

<!-- ===================== SCRIPT ===================== -->
<script>
{script_app}
</script>

<!-- ===================== COPYRIGHT ===================== -->
<footer class="cml-copyright">
  <div><strong>Calabria Meteo Lab</strong> · © 2026 Saverio Campanella · Tutti i diritti riservati</div>
  <div>Codice, interfaccia e contenuti dell’applicazione sono protetti da copyright.</div>
</footer>

</body>
</html>
"""

    return aggiungi_dashboard_interattiva(documento_html, ore, luogo)


def aggiungi_dashboard_interattiva(documento_html, ore, luogo):
    campi = ["time", "temperature_2m", "apparent_temperature", "precipitation",
             "wind_speed_10m", "wind_gusts_10m", "cloud_cover", "relative_humidity_2m", "Scenario", "Notte"]
    tabella = ore.reindex(columns=campi).copy()
    tabella["time"] = pd.to_datetime(tabella["time"]).dt.strftime("%Y-%m-%dT%H:%M")
    dati_json = tabella.to_json(orient="records", force_ascii=False).replace("<", "\\u003c")
    interfaccia = leggi_static("esploratore.html")
    interfaccia = interfaccia.replace("__EX_DATA__", dati_json).replace(
        "__EX_PLACE__", json.dumps(str(luogo), ensure_ascii=False).replace("<", "\\u003c")
    )
    return documento_html.replace("</body>", interfaccia + "\n</body>")


def aggiungi_altezza_automatica(documento_html):
    """Aggiunge lo script che adatta l'altezza del riquadro Streamlit alla pagina."""
    script = leggi_static("altezza_automatica.html")
    if "</body>" not in documento_html:
        return documento_html + script
    return documento_html.replace("</body>", script + "\n</body>", 1)
