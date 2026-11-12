const datiGraficiPerGiorno = __CML_DATI_GRAFICI__;

let meteoChartInstance = null;
let radarMap = null;
let attivitaMap = null;
let attivitaLayer = null;
let datiCelleCache = null;
let cacheTimestamp = null;

// Griglia Calabria per attività
const CALABRIA_BOUNDS = {
  latMin: 37.75,
  latMax: 40.15,
  lonMin: 15.60,
  lonMax: 17.25,
};

const PASSO_GRIGLIA_KM = 15.0;
const PASSO_LAT = PASSO_GRIGLIA_KM / 111.0;
const PASSO_LON = PASSO_GRIGLIA_KM / 86.0;

let celleAttivita = [];
const CACHE_DURATION_MS = 15 * 60 * 1000;

/* ---------- NAVIGAZIONE HOME / PREVISIONI / RADAR ---------- */

function mostraVista(nome) {
  document.querySelectorAll(".cml-view").forEach(function(vista) {
    vista.setAttribute("hidden", "");
  });

  const vistaDaMostrare = document.getElementById("cml-" + nome);

  if (vistaDaMostrare) {
    vistaDaMostrare.removeAttribute("hidden");
  }

  if (
    nome === "radar"
    && typeof radarMap !== "undefined"
    && radarMap
  ) {
    setTimeout(function() {
      radarMap.invalidateSize();
    }, 200);
  }

  if (
    nome === "attivita"
    && typeof attivitaMap !== "undefined"
    && attivitaMap
  ) {
    setTimeout(function() {
      attivitaMap.invalidateSize();
    }, 200);
  }

  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });

  // Con l'altezza automatica scorre la pagina Streamlit, non il riquadro:
  // riporta in vista l'inizio del riquadro se è uscito dallo schermo.
  try {
    if (window.frameElement && window.frameElement.getBoundingClientRect().top < 0) {
      window.frameElement.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (errore) {
    /* riquadro non accessibile: nulla da fare */
  }
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

function generaCelleCalabria() {
  const celle = [];
  let lat = CALABRIA_BOUNDS.latMin;

  while (lat <= CALABRIA_BOUNDS.latMax) {
    let lon = CALABRIA_BOUNDS.lonMin;
    while (lon <= CALABRIA_BOUNDS.lonMax) {
      celle.push({
        latitudine: Number(lat.toFixed(4)),
        longitudine: Number(lon.toFixed(4)),
        id: celle.length + 1
      });
      lon += PASSO_LON;
    }
    lat += PASSO_LAT;
  }
  return celle;
}

function etichettaMeteo(codice) {
  const etichette = {
    0: 'Sereno', 1: 'Quasi sereno', 2: 'Parzialmente nuvoloso', 3: 'Coperto',
    45: 'Nebbia', 48: 'Nebbia con brina', 51: 'Pioviggine debole',
    53: 'Pioviggine moderata', 55: 'Pioviggine intensa', 61: 'Pioggia debole',
    63: 'Pioggia moderata', 65: 'Pioggia forte', 71: 'Neve debole',
    73: 'Neve moderata', 75: 'Neve forte', 80: 'Rovesci deboli',
    81: 'Rovesci moderati', 82: 'Rovesci forti', 95: 'Temporale',
    96: 'Temporale con grandine', 99: 'Temporale con forte grandine'
  };
  return etichette[codice] || 'Non disponibile';
}

function nomeAttivita(tipo) {
  const nomi = {
    escursionismo: '🥾 Escursionismo',
    ciclismo: '🚴 Ciclismo',
    spiaggia: '🏖️ Spiaggia',
    fotografia: '📸 Fotografia',
    corsa: '🏃 Corsa',
    astronomia: '🔭 Astronomia'
  };
  return nomi[tipo] || tipo;
}

function punteggioAttivitaReale(dati, tipo) {
  const temperatura = Number(dati.temperature_2m || 0);
  const percepita = Number(dati.apparent_temperature || temperatura);
  const pioggia = Number(dati.precipitation || 0);
  const vento = Number(dati.wind_speed_10m || 0);
  const raffica = Number(dati.wind_gusts_10m || 0);
  const nuvole = Number(dati.cloud_cover || 0);
  const codice = Number(dati.weather_code || 0);
  const temporale = [95, 96, 99].includes(codice);
  const rovesci = [80, 81, 82].includes(codice);
  const pioggiaMeteo = [51, 53, 55, 56, 57, 61, 63, 65, 66, 67].includes(codice);
  let punteggio = 100;

  if (temporale) punteggio -= 85;
  if (pioggia >= 2) punteggio -= Math.min(55, 20 + pioggia * 14);
  else if (pioggia > 0) punteggio -= Math.min(30, pioggia * 18);
  else if (rovesci || pioggiaMeteo) punteggio -= 25;
  if (raffica >= 70) punteggio -= 55;
  else if (raffica >= 50) punteggio -= 32;
  else if (raffica >= 35) punteggio -= 15;

  if (tipo === 'escursionismo') {
    if (temperatura < 4 || temperatura > 31) punteggio -= 20;
    if (vento >= 30) punteggio -= Math.min(25, (vento - 25) * 2);
    if (codice >= 71 && codice <= 77) punteggio -= 40;
  } else if (tipo === 'ciclismo') {
    if (temperatura < 6 || temperatura > 30) punteggio -= 22;
    if (vento >= 20) punteggio -= Math.min(40, (vento - 18) * 2.5);
    if (raffica >= 40) punteggio -= 18;
  } else if (tipo === 'spiaggia') {
    if (temperatura < 22) punteggio -= Math.min(55, (22 - temperatura) * 6);
    if (temperatura > 35) punteggio -= 18;
    if (nuvole > 75) punteggio -= 30;
    else if (nuvole > 50) punteggio -= 12;
    if (vento >= 30) punteggio -= 25;
  } else if (tipo === 'fotografia') {
    if (temporale || pioggia >= 3) punteggio -= 35;
    if (nuvole >= 95) punteggio -= 25;
    else if (nuvole >= 30 && nuvole <= 75) punteggio += 5;
    if (raffica >= 55) punteggio -= 20;
  } else if (tipo === 'corsa') {
    if (percepita < 4 || percepita > 29) punteggio -= 28;
    if (vento >= 28) punteggio -= Math.min(35, (vento - 22) * 2.5);
    if (raffica >= 45) punteggio -= 18;
  } else if (tipo === 'astronomia') {
    if (nuvole > 85) punteggio -= 75;
    else if (nuvole > 65) punteggio -= 50;
    else if (nuvole > 40) punteggio -= 28;
    else if (nuvole > 20) punteggio -= 10;
    if (pioggia > 0 || pioggiaMeteo || rovesci) punteggio -= 35;
    if (temporale) punteggio -= 30;
    if (raffica >= 45) punteggio -= 18;
  }

  return Math.max(0, Math.min(100, Math.round(punteggio)));
}

function coloreDaPunteggio(punteggio) {
  if (punteggio >= 80) return '#16a34a';
  if (punteggio >= 60) return '#84cc16';
  if (punteggio >= 40) return '#eab308';
  if (punteggio >= 20) return '#f97316';
  return '#dc2626';
}

function testoDaPunteggio(punteggio) {
  if (punteggio >= 80) return 'Molto favorevole';
  if (punteggio >= 60) return 'Favorevole';
  if (punteggio >= 40) return 'Possibile con attenzione';
  if (punteggio >= 20) return 'Poco favorevole';
  return 'Sconsigliata';
}

async function scaricaDatiRealiCelle() {
  const adesso = Date.now();
  if (datiCelleCache && cacheTimestamp && adesso - cacheTimestamp < CACHE_DURATION_MS) {
    return datiCelleCache;
  }

  const stato = document.getElementById('attivita-stato');
  if (stato) stato.textContent = '⏳ Download previsioni ICON-2I reali in corso…';

  const celle = generaCelleCalabria();
  const dimensioneBatch = 50;
  const risultati = [];

  for (let inizio = 0; inizio < celle.length; inizio += dimensioneBatch) {
    const batch = celle.slice(inizio, inizio + dimensioneBatch);
    const parametri = new URLSearchParams({
      latitude: batch.map(c => c.latitudine).join(','),
      longitude: batch.map(c => c.longitudine).join(','),
      models: 'italia_meteo_arpae_icon_2i',
      timezone: 'Europe/Rome',
      forecast_days: '1',
      current: 'temperature_2m,apparent_temperature,precipitation,weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m'
    });

    const risposta = await fetch('https://api.open-meteo.com/v1/forecast?' + parametri.toString());
    if (!risposta.ok) throw new Error('Errore Open-Meteo ' + risposta.status);

    const datiBatch = await risposta.json();
    const arrayDati = Array.isArray(datiBatch) ? datiBatch : [datiBatch];

    batch.forEach(function(cella, indice) {
      const dati = arrayDati[indice] || {};
      risultati.push({
        ...cella,
        meteo: dati.current || {}
      });
    });

    if (stato) {
      stato.textContent = `⏳ Previsioni reali: ${Math.min(inizio + batch.length, celle.length)}/${celle.length} celle…`;
    }
  }

  datiCelleCache = risultati;
  cacheTimestamp = Date.now();
  return risultati;
}

function inizializzaMappaAttivita() {
  if (attivitaMap) return;
  attivitaMap = L.map('attivita-map', {
    center: [39.0, 16.45], zoom: 8, minZoom: 7, maxZoom: 12
  });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
  }).addTo(attivitaMap);
}

async function aggiornaMappaAttivita() {
  if (!attivitaMap) return;
  const selettore = document.getElementById('attivita-selector');
  const tipo = selettore ? selettore.value : 'escursionismo';
  const stato = document.getElementById('attivita-stato');

  try {
    const datiCelle = await scaricaDatiRealiCelle();
    if (attivitaLayer) attivitaMap.removeLayer(attivitaLayer);
    attivitaLayer = L.layerGroup().addTo(attivitaMap);

    datiCelle.forEach(function(cella) {
      const meteo = cella.meteo || {};
      const punteggio = punteggioAttivitaReale(meteo, tipo);
      const colore = coloreDaPunteggio(punteggio);
      const livello = testoDaPunteggio(punteggio);
      const latSud = cella.latitudine - PASSO_LAT / 2;
      const latNord = cella.latitudine + PASSO_LAT / 2;
      const lonOvest = cella.longitudine - PASSO_LON / 2;
      const lonEst = cella.longitudine + PASSO_LON / 2;

      const rettangolo = L.rectangle([[latSud, lonOvest], [latNord, lonEst]], {
        color: colore, weight: 1, fillColor: colore, fillOpacity: 0.55
      });

      rettangolo.bindPopup(`
        <div style="min-width:220px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.55;">
          <strong style="font-size:15px;">${nomeAttivita(tipo)}</strong><br>
          <span style="color:${colore};font-weight:800;">${livello} · ${punteggio}/100</span>
          <hr style="border:0;border-top:1px solid #dbe8ec;margin:8px 0;">
          <b>Condizioni ICON-2I</b><br>
          🌡️ ${Number(meteo.temperature_2m || 0).toFixed(1)} °C, percepita ${Number(meteo.apparent_temperature || 0).toFixed(1)} °C<br>
          🌧️ ${Number(meteo.precipitation || 0).toFixed(1)} mm<br>
          💨 ${Number(meteo.wind_speed_10m || 0).toFixed(0)} km/h, raffiche ${Number(meteo.wind_gusts_10m || 0).toFixed(0)} km/h<br>
          ☁️ ${Number(meteo.cloud_cover || 0).toFixed(0)}% · ${etichettaMeteo(Number(meteo.weather_code || 0))}<br>
          <small style="color:#607987;">Centro: ${cella.latitudine.toFixed(3)}°, ${cella.longitudine.toFixed(3)}°</small>
        </div>
      `);
      attivitaLayer.addLayer(rettangolo);
    });

    if (stato) {
      const orario = new Date(cacheTimestamp).toLocaleTimeString('it-IT', {hour:'2-digit',minute:'2-digit'});
      stato.textContent = `✅ ${datiCelle.length} celle con dati ICON-2I reali · cache 15 min · ${orario}`;
    }
  } catch (errore) {
    console.error(errore);
    if (stato) stato.textContent = '❌ Errore nel download: ' + errore.message;
  }
}

function apriVistaAttivita() {
  mostraVista('attivita');
  inizializzaMappaAttivita();
  setTimeout(function() {
    if (attivitaMap) attivitaMap.invalidateSize();
    aggiornaMappaAttivita();
  }, 250);
}

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
    } else {
      const timestamp = document.getElementById("radar-timestamp");

      if (timestamp) {
        timestamp.textContent = "frame non disponibile";
      }
    }
  })
  .catch(function() {
    const timestamp = document.getElementById("radar-timestamp");

    if (timestamp) {
      timestamp.textContent = "radar temporaneamente non disponibile";
    }
  });

/* ---------- AVVIO INIZIALE ---------- */

document.addEventListener("DOMContentLoaded", function() {
  mostraVista("home");
});
