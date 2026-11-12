# =============================================================================
# Calabria Meteo Lab - Icone meteo disegnate (SVG)
# Copyright (c) 2026 Saverio Campanella
# Tutti i diritti riservati.
# =============================================================================
#
# Un unico set di icone al posto delle emoji (che cambiano aspetto da telefono a
# telefono). Le icone sono composte da pochi pezzi (sole, luna, nuvole, gocce,
# fiocchi, fulmine, nebbia) e inserite una volta sola nella pagina come
# <symbol>; ogni icona è poi un <use> leggero. Nel riquadro "Adesso" l'icona è
# scritta per intero, così le animazioni CSS (lente) possono muoverne i pezzi.

import html

import pandas as pd

# ---------------------------------------------------------------------------
# Pezzi (viewBox 0 0 64 64)
# ---------------------------------------------------------------------------

_RAGGI = "".join(
    f'<line x1="{32 + 17 * c:.1f}" y1="{32 + 17 * s:.1f}" x2="{32 + 24 * c:.1f}" y2="{32 + 24 * s:.1f}"/>'
    for c, s in [(1, 0), (0.707, 0.707), (0, 1), (-0.707, 0.707), (-1, 0), (-0.707, -0.707), (0, -1), (0.707, -0.707)]
)


def _sole(x=0, y=0, scala=1.0):
    return (f'<g class="p-sole" transform="translate({x} {y}) scale({scala})">'
            f'<g class="p-raggi" stroke="#f5a623" stroke-width="4" stroke-linecap="round">{_RAGGI}</g>'
            f'<circle cx="32" cy="32" r="12" fill="#ffc83d" stroke="#f5a623" stroke-width="2"/></g>')


def _luna(x=0, y=0, scala=1.0):
    return (f'<g class="p-luna" transform="translate({x} {y}) scale({scala})">'
            f'<path d="M40 12A21 21 0 1 0 52 46A17 17 0 0 1 40 12Z" fill="#f9d674" stroke="#d4a942" stroke-width="2"/></g>')


def _nube(x=0, y=0, scala=1.0, scura=False):
    riempimento, bordo = ("#b7c6d1", "#6f8796") if scura else ("#f2f7fa", "#8ba6b7")
    return (f'<g class="p-nube" transform="translate({x} {y}) scale({scala})">'
            f'<path d="M16 48c-5.5 0-10-4.3-10-9.6 0-4.9 3.8-8.9 8.7-9.5C16.4 21.5 22.9 16 30.6 16c7 0 12.9 4.6 14.9 '
            f'11 .8-.1 1.5-.2 2.3-.2 6.7 0 12.2 5.3 12.2 11s-5.5 10.2-12.2 10.2Z" fill="{riempimento}" '
            f'stroke="{bordo}" stroke-width="2.5" stroke-linejoin="round"/></g>')


def _gocce(n=3, forte=False):
    posizioni = [22, 32, 42] if n == 3 else [18, 26, 34, 42, 50][:n] if n > 3 else [26, 38]
    lunghezza = 9 if forte else 6
    return ('<g class="p-gocce" stroke="#2f86d6" stroke-width="3.2" stroke-linecap="round">'
            + "".join(f'<line class="p-goccia" style="animation-delay:{i * 0.25:.2f}s" x1="{x}" y1="52" '
                      f'x2="{x - 3}" y2="{52 + lunghezza}"/>' for i, x in enumerate(posizioni))
            + "</g>")


def _fiocchi():
    return ('<g class="p-fiocchi" fill="#7fb6e0">'
            + "".join(f'<circle class="p-fiocco" style="animation-delay:{i * 0.4:.1f}s" cx="{x}" cy="{y}" r="2.8"/>'
                      for i, (x, y) in enumerate([(22, 55), (32, 59), (42, 55)]))
            + "</g>")


def _grandine():
    return ('<g class="p-gocce" fill="#d9ecf8" stroke="#5f9fcf" stroke-width="1.5">'
            + "".join(f'<circle class="p-goccia" style="animation-delay:{i * 0.3:.1f}s" cx="{x}" cy="56" r="3"/>'
                      for i, x in enumerate([20, 44]))
            + "</g>")


def _fulmine():
    return ('<path class="p-fulmine" d="M34 38 L26 52 L32 52 L28 62 L40 47 L34 47 L38 38 Z" '
            'fill="#ffcc33" stroke="#c48a00" stroke-width="1.5" stroke-linejoin="round"/>')


def _nebbia():
    return ('<g class="p-nebbia" stroke="#9fb3c0" stroke-width="3.5" stroke-linecap="round">'
            '<line x1="10" y1="50" x2="44" y2="50"/><line x1="18" y1="57" x2="54" y2="57"/>'
            '<line x1="8" y1="43" x2="30" y2="43"/></g>')


def _astro(notte, x, y, scala):
    return _luna(x, y, scala) if notte else _sole(x, y, scala)


# ---------------------------------------------------------------------------
# Icone (chiave -> funzione(notte) -> SVG interno)
# ---------------------------------------------------------------------------

ICONE = {
    "sereno": lambda n: _astro(n, 0, 0, 1.0),
    "poco-nuvoloso": lambda n: _astro(n, -4, -6, 0.85) + _nube(14, 16, 0.75),
    "nuvoloso": lambda n: _astro(n, -6, -8, 0.7) + _nube(4, 6, 0.95),
    "coperto": lambda n: _nube(-6, -4, 0.75, scura=True) + _nube(6, 6, 0.9),
    "nebbia": lambda n: _nube(2, -8, 0.85) + _nebbia(),
    "pioviggine": lambda n: _nube(2, -6, 0.9) + _gocce(2),
    "pioggia": lambda n: _nube(2, -8, 0.9) + _gocce(3),
    "pioggia-forte": lambda n: _nube(2, -8, 0.9, scura=True) + _gocce(5, forte=True),
    "rovesci": lambda n: _astro(n, -8, -12, 0.65) + _nube(6, -2, 0.85) + _gocce(3),
    "neve": lambda n: _nube(2, -8, 0.9) + _fiocchi(),
    "temporale": lambda n: _nube(2, -10, 0.9, scura=True) + _fulmine() + _gocce(2),
    "grandine": lambda n: _nube(2, -10, 0.9, scura=True) + _fulmine() + _grandine(),
}
CON_NOTTE = {"sereno", "poco-nuvoloso", "nuvoloso", "rovesci"}


def chiave_icona(codice):
    """Chiave dell'icona per un weather_code WMO (None se non valido)."""
    try:
        if codice is None or pd.isna(codice):
            return None
        codice = int(float(codice))
    except (TypeError, ValueError):
        return None
    if codice == 0:
        return "sereno"
    if codice == 1:
        return "poco-nuvoloso"
    if codice == 2:
        return "nuvoloso"
    if codice == 3:
        return "coperto"
    if codice in (45, 48):
        return "nebbia"
    if codice in (51, 53, 55, 56, 57):
        return "pioviggine"
    if codice in (61, 63):
        return "pioggia"
    if codice in (65, 66, 67):
        return "pioggia-forte"
    if codice in (80, 81, 82):
        return "rovesci"
    if codice in (71, 73, 75, 77, 85, 86):
        return "neve"
    if codice == 95:
        return "temporale"
    if codice in (96, 99):
        return "grandine"
    return "nuvoloso"


def _id_simbolo(chiave, notte):
    return f"cml-i-{chiave}{'-notte' if notte and chiave in CON_NOTTE else ''}"


def sprite_icone():
    """Tutte le icone come <symbol>, da inserire una volta all'inizio del <body>."""
    simboli = []
    for chiave, disegno in ICONE.items():
        for notte in ((False, True) if chiave in CON_NOTTE else (False,)):
            simboli.append(f'<symbol id="{_id_simbolo(chiave, notte)}" viewBox="0 0 64 64">{disegno(notte)}</symbol>')
    return f'<svg width="0" height="0" style="position:absolute" aria-hidden="true">{"".join(simboli)}</svg>'


def icona_svg(codice, notte=False, descrizione="", animata=False, classe=""):
    """Icona SVG per un weather_code. 'animata' la scrive per intero (per le animazioni)."""
    chiave = chiave_icona(codice)
    if chiave is None:
        return '<span class="cml-ico cml-ico-nd" aria-hidden="true">—</span>'
    etichetta = f' role="img" aria-label="{html.escape(descrizione, quote=True)}"' if descrizione else ' aria-hidden="true"'
    classi = f"cml-ico cml-ico-{chiave}{' cml-ico-animata' if animata else ''}{' ' + classe if classe else ''}"
    if animata:
        return f'<svg class="{classi}" viewBox="0 0 64 64"{etichetta}>{ICONE[chiave](notte)}</svg>'
    return f'<svg class="{classi}" viewBox="0 0 64 64"{etichetta}><use href="#{_id_simbolo(chiave, notte)}"/></svg>'
