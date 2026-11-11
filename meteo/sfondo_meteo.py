# Calabria Meteo Lab - sfondo artistico guidato dai dati modellistici
import json
import pandas as pd

from meteo.config import CARTELLA_STATIC

_FRAGMENT = (CARTELLA_STATIC / "sfondo_meteo.html").read_text(encoding="utf-8")

def aggiungi_sfondo_meteo(documento, luogo, dati_terrestri, dati_orari,
                         dati_giornalieri, is_costiero=False):
    def records(frame):
        frame = frame.copy()
        for col in ("time", "sunrise", "sunset"):
            if col in frame.columns:
                frame[col] = pd.to_datetime(frame[col], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
        return json.loads(frame.to_json(orient="records", force_ascii=False))
    current = json.loads(pd.DataFrame([dati_terrestri.get("current", {})]).to_json(orient="records"))[0]
    payload = {"place": str(luogo), "current": current,
               "hourly": records(dati_orari), "daily": records(dati_giornalieri),
               "coastal": bool(is_costiero)}
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    fragment = _FRAGMENT.replace("__ATMO_DATA__", encoded)
    if "</body>" not in documento:
        return documento + fragment
    return documento.replace("</body>", fragment + "\n</body>", 1)
