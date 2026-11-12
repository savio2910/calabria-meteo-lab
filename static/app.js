const datiGraficiPerGiorno = __CML_DATI_GRAFICI__;

let meteoChartInstance = null;
let radarMap = null;

/* ---------- STATO DEI SERVIZI (riga sotto "Adesso") ---------- */

function statoServizio(nome, stato, testo) {
  const voce = document.getElementById("cml-stato-" + nome);
  if (!voce) return;
  voce.className = "cml-servizio cml-servizio-" + stato;
  const descrizione = voce.querySelector("span:last-child");
  if (descrizione) descrizione.textContent = testo;
}

/* ---------- GRAFICO METEO ---------- */

function creaGrafici(chiave) {
  const dati = datiGraficiPerGiorno[chiave];

  if (!dati) {
    return;
  }

  const canvasTemperatura = document.getElementById(
    "temperaturaChart-" + chiave
  );

  const canvasNuvolositaPrecipitazioni =
    document.getElementById(
      "nuvolositaPrecipitazioniChart-" + chiave
    );

  const canvasVento = document.getElementById(
    "ventoChart-" + chiave
  );

  if (
    !canvasTemperatura
    || !canvasNuvolositaPrecipitazioni
    || !canvasVento
  ) {
    return;
  }

  const opzioniComuni = {
    responsive: true,
    maintainAspectRatio: false,

    interaction: {
      mode: "index",
      intersect: false
    },

    plugins: {
      legend: {
        position: "top",

        labels: {
          usePointStyle: true,
          padding: 18,

          font: {
            size: 12,
            weight: "600"
          }
        }
      },

      tooltip: {
        backgroundColor: "rgba(15, 43, 59, 0.95)",
        padding: 11,
        cornerRadius: 9
      }
    },

    scales: {
      x: {
        grid: {
          color: "rgba(16, 43, 59, 0.06)"
        },

        ticks: {
          maxRotation: 0,
          autoSkip: true
        }
      }
    }
  };

  /*
   * 1. GRAFICO TEMPERATURA
   */

    const graficoTemperatura = new Chart(
    canvasTemperatura.getContext("2d"),
    {
      type: "line",

      data: {
        labels: dati.ore,

        datasets: [
          {
            label: "Temperatura °C",
            data: dati.temperatura,
            borderColor: "#ef6c16",
            backgroundColor: "rgba(239, 108, 22, 0.16)",
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 3,
            tension: 0.35,
            fill: true
          }
        ]
      },

      options: {
        responsive: true,
        maintainAspectRatio: false,

        interaction: {
          mode: "index",
          intersect: false
        },

        plugins: {
          legend: {
            position: "top",
            labels: {
              usePointStyle: true,
              padding: 18,
              font: {
                size: 12,
                weight: "600"
              }
            }
          },
          tooltip: {
            backgroundColor: "rgba(15, 43, 59, 0.95)",
            padding: 11,
            cornerRadius: 9
          }
        },

        scales: {
          x: {
            grid: {
              color: "rgba(16, 43, 59, 0.06)"
            },
            ticks: {
              maxRotation: 0,
              autoSkip: true
            }
          },
          y: {
            title: {
              display: true,
              text: "Temperatura °C"
            },
            grid: {
              color: "rgba(16, 43, 59, 0.08)"
            }
          }
        }
      }
    }
  );
  /*
   * 2. GRAFICO NUVOLOSITÀ E PRECIPITAZIONI
   */

  const graficoNuvolositaPrecipitazioni = new Chart(
    canvasNuvolositaPrecipitazioni.getContext("2d"),
    {
      data: {
        labels: dati.ore,

        datasets: [
          {
            type: "line",
            label: "Nuvolosità %",
            data: dati.nuvolosita,

            yAxisID: "nuvolosita",

            borderColor: "#687b88",
            backgroundColor: "rgba(104, 123, 136, 0.16)",

            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 3,
            tension: 0.35,
            fill: true
          },

          {
            type: "bar",
            label: "Precipitazione mm",
            data: dati.precipitazione,

            yAxisID: "precipitazione",

            backgroundColor: "rgba(47, 137, 202, 0.68)",
            borderColor: "#1679ba",
            borderWidth: 1,
            borderRadius: 4
          }
        ]
      },

      options: {
        ...opzioniComuni,

        scales: {
          ...opzioniComuni.scales,

          nuvolosita: {
            type: "linear",
            position: "left",
            min: 0,
            max: 100,

            title: {
              display: true,
              text: "Nuvolosità %"
            },

            grid: {
              color: "rgba(16, 43, 59, 0.08)"
            }
          },

          precipitazione: {
            type: "linear",
            position: "right",
            min: 0,

            title: {
              display: true,
              text: "Precipitazione mm"
            },

            grid: {
              drawOnChartArea: false
            }
          }
        }
      }
    }
  );

  /*
   * 3. GRAFICO VENTO
   */

    const graficoVento = new Chart(
    canvasVento.getContext("2d"),
    {
      type: "line",

      data: {
        labels: dati.ore,

        datasets: [
          {
            label: "Vento medio km/h",
            data: dati.vento,
            borderColor: "#0a8b72",
            backgroundColor: "rgba(10, 139, 114, 0.12)",
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 3,
            tension: 0.3,
            fill: true
          },
          {
            label: "Raffiche km/h",
            data: dati.raffiche,
            borderColor: "#9c3f84",
            backgroundColor: "rgba(156, 63, 132, 0.08)",
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 2.5,
            borderDash: [7, 4],
            tension: 0.3,
            fill: false
          }
        ]
      },

      options: {
        responsive: true,
        maintainAspectRatio: false,

        interaction: {
          mode: "index",
          intersect: false
        },

        plugins: {
          legend: {
            position: "top",
            labels: {
              usePointStyle: true,
              padding: 18,
              font: {
                size: 12,
                weight: "600"
              }
            }
          },
          tooltip: {
            backgroundColor: "rgba(15, 43, 59, 0.95)",
            padding: 11,
            cornerRadius: 9
          }
        },

        scales: {
          x: {
            grid: {
              color: "rgba(16, 43, 59, 0.06)"
            },
            ticks: {
              maxRotation: 0,
              autoSkip: true
            }
          },
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: "Velocità km/h"
            },
            grid: {
              color: "rgba(16, 43, 59, 0.08)"
            }
          }
        }
      }
    }
  );

  meteoChartInstance = {
    temperatura: graficoTemperatura,
    nuvolositaPrecipitazioni:
      graficoNuvolositaPrecipitazioni,
    vento: graficoVento,

    destroy: function() {
      this.temperatura.destroy();
      this.nuvolositaPrecipitazioni.destroy();
      this.vento.destroy();
    }
  };
}
/* ---------- APERTURA SCHEDA GIORNO ---------- */

function mostraGiorno(chiave, scheda, event) {
  if (event && event.target.closest(".cml-day-inline-detail")) return;

  const dettaglio = document.getElementById("dettaglio-" + chiave);

  if (!dettaglio) return;

  const eraAperta = !dettaglio.hidden;

  document.querySelectorAll(".cml-day-card").forEach(function(card) {
    card.classList.remove("active");
    card.setAttribute("aria-expanded", "false");
  });

  document.querySelectorAll(".cml-day-inline-detail").forEach(function(panel) {
    panel.hidden = true;
  });

  if (meteoChartInstance) {
    meteoChartInstance.destroy();
    meteoChartInstance = null;
  }

  if (eraAperta) return;

  dettaglio.hidden = false;
  scheda.classList.add("active");
  scheda.setAttribute("aria-expanded", "true");

  if (typeof Chart !== "undefined") {
    requestAnimationFrame(function() {
      creaGrafici(chiave);
    });
  }
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
