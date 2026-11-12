# =============================================================================
# Calabria Meteo Lab - Costruzione della pagina HTML completa.
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import html
import json
from datetime import timedelta

from meteo.adesso import menu_rapido_html, riga_breve_fonti_html, riga_fonti_html, riquadro_adesso_html
from meteo.allerta import LIVELLI_ALLERTA, URL_CFD_CALABRIA, descrivi_livelli
from meteo.attivita import sezione_attivita_html
from meteo.config import leggi_static
from meteo.formato import data_it, ora_it
from meteo.giorni import giorni_html
from meteo.indicatori import riassunto_giorno, testi_indicatori
from meteo.mare import mare_html
from meteo.oraperora import sezione_ora_per_ora_html
from meteo.probabilita import PROBABILITA_MINIMA_MOSTRATA, SOGLIE_RAFFICHE, testo_affidabilita
from meteo.situazione import situazione_html


STILE_CSS = leggi_static("stile.css")


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


def correzione_breve_html(correzione):
    """Ritocco con l'ultima osservazione Meteostat, in una riga."""
    if not correzione:
        return ""
    distanza = f", {correzione['distanza_km']:.0f} km" if correzione.get("distanza_km") is not None else ""
    vento = (correzione["rapporto_vento"] - 1) * 100
    return (f'<p class="cml-info-correzione">🔎 <b>Ritocco con l\'ultima osservazione</b> della stazione '
            f'{html.escape(correzione["stazione"])}{distanza} (ore {ora_it(correzione["ultima_osservazione"])}): '
            f'temperatura {correzione["bias_temp"]:+.1f} °C, umidità {correzione["bias_umidita"]:+.0f} %, '
            f'vento {vento:+.0f} %, attenuato nelle 6 ore successive.</p>')


def informazioni_html(fonti_html, correzione, ha_mare):
    """Riquadro unico, chiuso, con stato dei servizi, correzioni, avvertenze e fonti."""
    note = [
        "<b>Prossimi giorni</b>: l'icona riassume i fenomeni importanti delle 24 ore (se non ce ne sono, il cielo "
        "medio di giorno); la barra va dalla minima alla massima, con la stessa scala per tutti i giorni; 💧 è la "
        "probabilità di pioggia calcolata dagli scenari degli ensemble.",
        "L'<b>indice meteo dell'app</b> è una stima automatica, <b>non un'allerta ufficiale</b>: per le allerte consulta "
        f'il <a href="{URL_CFD_CALABRIA}" target="_blank" rel="noopener">Centro Funzionale Multirischi – ARPACAL</a>.',
        "<b>Radar</b>: pioggia osservata, non una previsione. <b>Satellite</b>: mostra le nubi, non la pioggia al suolo. "
        "<b>Fulmini</b>: scariche rilevate dalla rete Blitzortung; se non ce ne sono il rischio di temporali non è escluso.",
    ]
    if ha_mare:
        note.append("<b>Mare</b>: la freccia indica dove vanno le onde, la direzione scritta da dove arrivano. Valori "
                    "stimati su una griglia marina, meno precisi in baie, porti e promontori: per la navigazione "
                    "consulta sempre fonti nautiche e avvisi ufficiali.")
    note.append("<b>Attività e viaggio</b>: giudizi automatici basati sulla previsione, non garanzie di sicurezza.")
    return f"""
<details class="cml-info cml-sezione" id="cml-info">
  <summary>ℹ️ Fonti, taratura e affidabilità</summary>
  <div class="cml-info-corpo">
    {fonti_html}
    {correzione_breve_html(correzione)}
    <h3>Come leggere la pagina</h3>
    <ul class="cml-info-note">{''.join(f'<li>{n}</li>' for n in note)}</ul>
    <h3>Fonti dei dati</h3>
    <p class="cml-info-fonti">
      Modelli: ICON-2I (ItaliaMeteo–ARPAE), ECMWF IFS e AIFS (Centro Europeo), ICON-EU (DWD) attraverso Open-Meteo;
      MOLOCH e BOLAM (CNR-ISAC), WRF (ItaliaMeteo, Fondazione CIMA, LaMMA) dai dati aperti di MeteoHub – Agenzia
      ItaliaMeteo. Stazioni: rete della Protezione Civile in Calabria (MeteoHub) e Meteostat. Allerte: Dipartimento
      della Protezione Civile. Radar: RainViewer. Satellite: Windy. Fulmini: Blitzortung.org. Mappe: OpenStreetMap.
      Licenze CC BY / CC BY-SA.
    </p>
  </div>
</details>"""


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

    if ore.empty:
        raise RuntimeError(
            "Non sono disponibili dati orari futuri per la località selezionata."
        )

    sezione_giorni = giorni_html(
        giorni, ore, corrente, probabilita, allerta, indicatori,
        allerta_giorno_html, probabilita_giorno_html, indicatori_giorno_html,
    )
    ora_per_ora_html = sezione_ora_per_ora_html(ore, probabilita, indicatori, giorni)
    mare_sezione = mare_html(dati_mare, distanza_mare_km)
    sezione_attivita = sezione_attivita_html(
        luogo, ore, giorni, dati_mare, is_costiero, dati_terrestri.get("elevation"), indicatori, probabilita
    )

    # Riquadro "Adesso", riga breve delle fonti, menu e riquadro unico delle informazioni
    adesso_html = riquadro_adesso_html(luogo, corrente, ore, giorni, probabilita, indicatori)
    fonti_breve = riga_breve_fonti_html(dati_terrestri)
    informazioni = informazioni_html(
        riga_fonti_html(dati_terrestri, correzione_osservativa, dati_mare, is_costiero, probabilita, allerta),
        correzione_osservativa,
        bool(mare_sezione),
    )
    banner_allerta = banner_allerta_html(allerta, giorni)
    menu_html = menu_rapido_html(bool(mare_sezione))
    situazione = situazione_html(situazione)

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
{fonti_breve}

<!-- ===================== PROSSIMI GIORNI ===================== -->
{sezione_giorni}

<!-- ===================== ORA PER ORA ===================== -->
<div id="cml-ora-per-ora" class="cml-sezione">
{ora_per_ora_html}
</div>

<!-- ===================== SITUAZIONE GENERALE ===================== -->
{situazione}

<!-- ===================== MARE ===================== -->
{mare_sezione}

<!-- ===================== RADAR, SATELLITE, FULMINI ===================== -->
<div id="cml-radar" class="cml-sezione">
  <section class="cml-radar-box">
    <div class="cml-radar-head">
      <h2 class="cml-titolo-sezione">📡 Radar</h2>
      <button class="cml-radar-btn" id="btn-play" type="button" onclick="togglePlayRadar()">⏸ Pausa</button>
    </div>
    <div id="radar-map"></div>
    <div class="cml-radar-footer">
      <span>Pioggia osservata · RainViewer</span>
      <span id="radar-timestamp" class="cml-radar-time">caricamento...</span>
    </div>
  </section>

  <!-- ===================== SATELLITE NUVOLOSITÀ ===================== -->
  <details class="cml-fisarmonica cml-fisarmonica-mappa">
  <summary class="cml-fisarmonica-titolo">🛰️ Satellite · nuvole</summary>
  <section class="cml-radar-box">
    <iframe
      title="Satellite della nuvolosità"
      loading="lazy"
      src="https://embed.windy.com/embed2.html?lat={latitudine}&amp;lon={longitudine}&amp;zoom=7&amp;level=surface&amp;overlay=satellite&amp;product=satellite&amp;menu=&amp;message=&amp;marker=true&amp;calendar=now&amp;pressure=&amp;type=map&amp;location=coordinates&amp;detail=&amp;metricWind=km%2Fh&amp;metricTemp=%C2%B0C"
      class="cml-mappa-esterna"
      allowfullscreen
    ></iframe>
    <div class="cml-radar-footer">
      <span>Windy</span>
      <a href="https://www.windy.com/-Satellite-satellite?satellite,{latitudine},{longitudine},7" target="_blank" rel="noopener noreferrer">Apri su Windy ↗</a>
    </div>
  </section>
  </details>

  <!-- ===================== FULMINAZIONI ===================== -->
  <details class="cml-fisarmonica cml-fisarmonica-mappa">
  <summary class="cml-fisarmonica-titolo">⚡ Fulmini in tempo reale</summary>
  <section class="cml-radar-box">
    <iframe
      title="Mappa delle fulminazioni Blitzortung"
      loading="lazy"
      src="https://map.blitzortung.org/index.php?interactive=1&amp;NavigationControl=1&amp;FullScreenControl=1&amp;Cookies=0&amp;InfoDiv=1&amp;MenuButtonDiv=1&amp;ScaleControl=1#7/{latitudine}/{longitudine}"
      class="cml-mappa-esterna"
      allowfullscreen
    ></iframe>
    <div class="cml-radar-footer">
      <span>Blitzortung.org e collaboratori</span>
      <a href="https://map.blitzortung.org/#7/{latitudine}/{longitudine}" target="_blank" rel="noopener noreferrer">Apri la mappa ↗</a>
    </div>
  </section>
  </details>
</div>

<!-- ===================== ATTIVITÀ ===================== -->
<div id="cml-attivita" class="cml-sezione">
  {sezione_attivita}
</div>

<!-- ===================== FONTI E AFFIDABILITÀ ===================== -->
{informazioni}

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
