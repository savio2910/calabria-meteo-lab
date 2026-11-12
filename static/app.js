let radarMap = null;

/* ---------- STATO DEI SERVIZI (riga sotto "Adesso") ---------- */

function statoServizio(nome, stato, testo) {
  const voce = document.getElementById("cml-stato-" + nome);
  if (!voce) return;
  voce.className = "cml-servizio cml-servizio-" + stato;
  const descrizione = voce.querySelector("span:last-child");
  if (descrizione) descrizione.textContent = testo;
}


/* ---------- MAPPA RADAR ---------- */

radarMap = L.map("radar-map", {
  center: [__CML_LAT__, __CML_LON__],
  zoom: 8,
  minZoom: 5,
  maxZoom: 18,
  zoomControl: true
});

L.tileLayer(
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 18
  }
).addTo(radarMap);

const pinIcon = L.divIcon({
  className: "cml-radar-pin-wrapper",

  html:
    '<div style="width:20px;height:20px;background:#e63b45;border:3px solid #ffffff;border-radius:50%;box-shadow:0 0 0 3px rgba(230,59,69,0.40),0 4px 10px rgba(0,0,0,0.25);"></div>',

  iconSize: [20, 20],
  iconAnchor: [10, 10]
});

L.marker([__CML_LAT__, __CML_LON__], {
  icon: pinIcon,
  title: __CML_LUOGO_JSON__
}).addTo(radarMap);

let radarTimes = [];
let radarLayers = {};
let radarFrameIndex = 0;
let radarPlaying = true;
let radarTimer = null;

function visualizzaFrameRadar(indice) {
  if (radarTimes.length === 0) {
    return;
  }

  const tempoPrecedente = radarTimes[radarFrameIndex];

  if (radarLayers[tempoPrecedente]) {
    radarLayers[tempoPrecedente].setOpacity(0);
  }

  radarFrameIndex = indice;

  const tempo = radarTimes[radarFrameIndex];

  if (radarLayers[tempo]) {
    radarLayers[tempo].setOpacity(0.72);
  }

  const data = new Date(tempo * 1000);

  const ore = String(data.getHours()).padStart(2, "0");
  const minuti = String(data.getMinutes()).padStart(2, "0");

  const timestamp = document.getElementById("radar-timestamp");

  if (timestamp) {
    timestamp.textContent = ore + ":" + minuti + " (ora locale)";
  }
}

function avviaRadar() {
  if (radarTimer) {
    clearInterval(radarTimer);
  }

  radarTimer = setInterval(function() {
    if (radarTimes.length === 0) {
      return;
    }

    const prossimo = (radarFrameIndex + 1) % radarTimes.length;
    visualizzaFrameRadar(prossimo);
  }, 800);
}

function togglePlayRadar() {
  const bottone = document.getElementById("btn-play");

  if (radarPlaying) {
    clearInterval(radarTimer);
    radarPlaying = false;
    bottone.textContent = "▶ Play";
  } else {
    avviaRadar();
    radarPlaying = true;
    bottone.textContent = "⏸ Pausa";
  }
}

// ---------- MAPPA ATTIVITÀ: DATI REALI ICON-2I ----------

fetch(
  "https://api.rainviewer.com/public/weather-maps.json"
)
  .then(function(response) {
    return response.json();
  })
  .then(function(payload) {
    const frames = (
      payload
      && payload.radar
      && payload.radar.past
    ) ? payload.radar.past : [];

    radarTimes = frames.map(function(frame) {
      return frame.time;
    });

    frames.forEach(function(frame) {
      const layer = L.tileLayer(
        "https://tilecache.rainviewer.com"
          + frame.path
          + "/256/{z}/{x}/{y}/2/1_1.png",
        {
          opacity: 0,
          zIndex: 100,
          maxNativeZoom: 6,
          maxZoom: 18
        }
      );

      layer.addTo(radarMap);
      radarLayers[frame.time] = layer;
    });

    if (radarTimes.length > 0) {
      radarFrameIndex = radarTimes.length - 1;
      visualizzaFrameRadar(radarFrameIndex);
      avviaRadar();
      const ultimo = new Date(radarTimes[radarTimes.length - 1] * 1000);
      statoServizio("radar", "attivo", "ultima immagine " + ultimo.toLocaleTimeString("it-IT", {
        hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome"
      }));
    } else {
      statoServizio("radar", "spento", "nessuna immagine disponibile");
      const timestamp = document.getElementById("radar-timestamp");

      if (timestamp) {
        timestamp.textContent = "frame non disponibile";
      }
    }
  })
  .catch(function() {
    statoServizio("radar", "spento", "temporaneamente non disponibile");
    const timestamp = document.getElementById("radar-timestamp");

    if (timestamp) {
      timestamp.textContent = "radar temporaneamente non disponibile";
    }
  });
