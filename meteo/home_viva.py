# Calabria Meteo Lab - estensione visiva della home
# Scena artistica interattiva, non simulazione meteorologica.

from meteo.config import CARTELLA_STATIC

HOME_VIVA = (CARTELLA_STATIC / "home_viva.html").read_text(encoding="utf-8")

def aggiungi_home_viva(documento):
    if '</body>' not in documento:
        return documento + HOME_VIVA
    return documento.replace('</body>', HOME_VIVA + '\n</body>', 1)
