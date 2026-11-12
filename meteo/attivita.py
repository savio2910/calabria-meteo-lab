# =============================================================================
# Calabria Meteo Lab - Punteggio di idoneità meteorologica per le attività.
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================

import html

from meteo.formato import valore_finito


# Pesi e soglie applicative: non sono criteri ufficiali di sicurezza.
CONFIG_ATTIVITA = {
    "escursionismo": {"pesi": {"pioggia":35,"raffiche":20,"temperatura":15,"vento":15,"neve":15}, "temp":(-5,8,26,34), "vento":(20,45), "raffiche":(35,70)},
    "ciclismo": {"pesi": {"pioggia":30,"vento":25,"raffiche":20,"temperatura":15,"nebbia":10}, "temp":(-2,10,27,34), "vento":(15,40), "raffiche":(30,60)},
    "spiaggia": {"pesi": {"temperatura":35,"pioggia":25,"nuvole":20,"vento":15,"raffiche":5}, "temp":(15,24,33,38), "nuvole":(45,90), "vento":(15,40), "raffiche":(30,55)},
    "fotografia": {"pesi": {"pioggia":30,"nuvole":30,"raffiche":20,"temperatura":10,"vento":10}, "temp":(-5,12,27,38), "nuvole":(70,95), "vento":(15,45), "raffiche":(25,55)},
    "corsa": {"pesi": {"percepita":35,"pioggia":25,"vento":20,"raffiche":20}, "temp":(-5,8,26,35), "vento":(15,40), "raffiche":(30,55)},
    "astronomia": {"pesi": {"nuvole":55,"pioggia":20,"vento":15,"raffiche":10}, "nuvole":(15,80), "vento":(10,35), "raffiche":(20,45)},
}


def valuta_attivita_pesata(dati, tipo):
    config = CONFIG_ATTIVITA[tipo]
    codice = valore_finito(dati.get("weather_code"), None)
    codice = int(codice) if codice is not None else None
    risultati = []
    limiti = []
    etichette = {"pioggia":"Precipitazione", "raffiche":"Raffiche", "vento":"Vento medio", "temperatura":"Temperatura", "percepita":"Temperatura percepita", "nuvole":"Nuvolosità", "neve":"Neve prevista", "nebbia":"Nebbia prevista"}
    campi = {"pioggia":"precipitation", "raffiche":"wind_gusts_10m", "vento":"wind_speed_10m", "temperatura":"temperature_2m", "percepita":"apparent_temperature", "nuvole":"cloud_cover"}
    unita = {"pioggia":"mm nell'ultimo intervallo", "raffiche":"km/h", "vento":"km/h", "temperatura":"°C", "percepita":"°C", "nuvole":"%"}

    def decrescente(x, ottimo, limite):
        return max(0.0, min(1.0, (limite-x)/(limite-ottimo)))

    for chiave, peso in config["pesi"].items():
        valore = codice if chiave in ("neve", "nebbia") else valore_finito(dati.get(campi[chiave]), None)
        indice = None
        soglia = ""
        testo = "Dato non disponibile"
        if chiave in ("neve", "nebbia"):
            soglia = "Codici nevosi 71, 73, 75, 77, 85, 86" if chiave == "neve" else "Codici nebbia 45, 48"
            if codice is not None:
                presente = codice in ({71,73,75,77,85,86} if chiave == "neve" else {45,48})
                indice = 0.0 if presente else 1.0
                testo = "Presente nel codice meteo" if presente else "Non indicata nel codice meteo"
        elif valore is not None:
            testo = f"{valore:.1f} {unita[chiave]}"
            if chiave == "pioggia":
                indice = decrescente(max(0.0,valore), 0.0, 2.0)
                soglia = "Indice 100 con 0 mm; indice 0 da 2 mm; variazione lineare"
                if codice in {51,53,55,56,57,61,63,65,66,67,80,81,82,71,73,75,77,85,86}:
                    indice = min(indice, 0.35)
                if codice in {95,96,99}: indice = 0.0
            elif chiave in ("vento", "raffiche", "nuvole"):
                ottimo, limite = config[chiave]
                indice = decrescente(valore, ottimo, limite)
                soglia = f"Indice 100 fino a {ottimo}; indice 0 da {limite}; variazione lineare"
            else:
                basso,ottimo_min,ottimo_max,alto = config["temp"]
                indice = 1.0 if ottimo_min <= valore <= ottimo_max else (max(0.0,(valore-basso)/(ottimo_min-basso)) if valore < ottimo_min else max(0.0,(alto-valore)/(alto-ottimo_max)))
                soglia = f"Ottimale {ottimo_min}–{ottimo_max} °C; indice 0 a {basso} / {alto} °C"
        risultati.append({"nome":etichette[chiave], "peso":peso, "indice":indice, "valore":testo, "soglia":soglia, "punti":None if indice is None else peso*indice, "persi":None if indice is None else peso*(1-indice)})

    # Vincoli cautelativi applicativi: il comfort non compensa eventi avversi.
    if codice in {95,96,99}: limiti.append((15,"Codice di temporale: punteggio massimo 15/100."))
    raffica = valore_finito(dati.get("wind_gusts_10m"), None)
    if raffica is not None and raffica >= config["raffiche"][1]:
        limiti.append((20,"Raffiche oltre il limite applicativo: punteggio massimo 20/100."))
    copertura = sum(r["peso"] for r in risultati if r["indice"] is not None)
    completo = copertura == 100 and codice is not None
    grezzo = sum(r["punti"] or 0.0 for r in risultati) if completo else None
    finale = None if grezzo is None else round(min([grezzo]+[l[0] for l in limiti]))
    return {"punteggio":finale,"grezzo":grezzo,"fattori":risultati,"limiti":limiti,"copertura":copertura,"codice_disponibile":codice is not None}


def punteggio_attivita_luogo(dati, tipo):
    return valuta_attivita_pesata(dati, tipo)["punteggio"]


def spiegazione_attivita_html(risultato):
    righe = []
    for r in risultato["fattori"]:
        indice = "N/D" if r["indice"] is None else f"{100*r['indice']:.0f}/100"
        punti = "N/D" if r["punti"] is None else f"{r['punti']:.1f} / {r['peso']}"
        persi = "N/D" if r["persi"] is None else f"{r['persi']:.1f}"
        righe.append(f"<tr><td>{html.escape(r['nome'])}</td><td>{html.escape(r['valore'])}</td><td>{r['peso']}%</td><td>{indice}</td><td>{punti}</td><td>{persi}</td></tr>")
    soglie = "".join(f"<li>{html.escape(r['nome'])}: {html.escape(r['soglia'] or 'Dato mancante: indice non calcolato')}</li>" for r in risultato["fattori"])
    if risultato["punteggio"] is None:
        motivo = "Dati incompleti: la percentuale non viene calcolata. I valori mancanti non sono interpretati come condizioni favorevoli."
    else:
        peggiori = sorted(risultato["fattori"], key=lambda r:r["persi"], reverse=True)
        peggiori = [r for r in peggiori if r["persi"]>0][:3]
        motivo = "Nessuna riduzione nei fattori considerati." if not peggiori else "I fattori che riducono maggiormente il punteggio sono: "+", ".join(f"{r['nome']} (−{r['persi']:.1f} punti)" for r in peggiori)+"."
        motivo += f" Media pesata prima dei vincoli: {risultato['grezzo']:.1f}/100."
    vincoli = " ".join(l[1] for l in risultato["limiti"])
    return f"<p>{html.escape(motivo)}</p><p>{html.escape(vincoli)}</p><div class='cml-table-wrap'><table class='cml-table'><thead><tr><th>Fattore</th><th>Dato</th><th>Peso</th><th>Indice</th><th>Punti ottenuti / massimi</th><th>Punti persi</th></tr></thead><tbody>{''.join(righe)}</tbody></table></div><details><summary>Soglie utilizzate</summary><ul>{soglie}</ul></details>"


def tabella_attivita_luogo_html(luogo, corrente, is_costiero=False):
    attivita = [
        ("escursionismo", "🥾 Escursionismo"),
        ("ciclismo", "🚴 Ciclismo"),
        ("fotografia", "📸 Fotografia"),
        ("corsa", "🏃 Corsa"),
        ("astronomia", "🔭 Astronomia"),
    ]

    if is_costiero:
        attivita.insert(2, ("spiaggia", "🏖️ Spiaggia"))

    righe = []
    spiegazioni = []
    for tipo, nome in attivita:
        risultato = valuta_attivita_pesata(corrente, tipo)
        punteggio = risultato["punteggio"]
        visualizzato = "N/D" if punteggio is None else f"{punteggio}%"
        spiegazioni.append(
            f"<details style='margin:12px 0;padding:12px;border:1px solid #d5e4e9;border-radius:12px'>"
            f"<summary>{html.escape(nome)} — Perché {visualizzato}?</summary>"
            + spiegazione_attivita_html(risultato) + "</details>"
        )
        colore = {
            4: "#16a34a", 3: "#84cc16", 2: "#eab308",
            1: "#f97316", 0: "#dc2626"
        }[min(4, (punteggio or 0) // 20)] if punteggio is not None else "#607987"
        righe.append(f"""
          <tr>
            <td>{html.escape(nome)}</td>
            <td>
              <div class="cml-activity-bar">
                <div class="cml-activity-bar-fill" style="width:{punteggio or 0}%;background:{colore};"></div>
              </div>
            </td>
            <td><b style="color:{colore};">{visualizzato}</b></td>
          </tr>
        """)

    nota_costa = (
        "La località risulta costiera: è inclusa anche la valutazione per la spiaggia."
        if is_costiero else
        "La località non risulta costiera: l’attività «Spiaggia» non è valutata."
    )

    return f"""
    <section class="cml-radar-box">
      <div class="cml-radar-head">
        <div>
          <h2>🏃 Attività per {html.escape(luogo)}</h2>
          <p>Indice di idoneità meteorologica sulle condizioni attuali previste dal modello, non probabilità di riuscita. Pesi e soglie sono criteri applicativi non validati; non certificano la sicurezza.</p>
        </div>
      </div>
      <div class="cml-table-wrap">
        <table class="cml-table cml-tabella-attivita">
          <thead><tr><th>Attività</th><th>Idoneità meteorologica</th><th>Valore</th></tr></thead>
          <tbody>{''.join(righe)}</tbody>
        </table>
      </div>
      <h3>Perché questa percentuale?</h3>
      <p>Somma dei contributi: peso × indice / 100. Gli indici variano da 0 a 100. I vincoli cautelativi possono limitare il risultato. N/D indica dati insufficienti, non condizioni ottimali.</p>
      {''.join(spiegazioni)}
      <div class="cml-marine-note">
        ℹ️ {nota_costa} Valori stimati su dati ICON-2I della località selezionata.
        Per la spiaggia non è valutata la balneabilità; per l’astronomia non sono considerati
        buio e inquinamento luminoso.
      </div>
    </section>
    """
