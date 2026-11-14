# Dati elaborati - Calabria Meteo Lab

Ramo generato automaticamente da `.github/workflows/meteohub.yml`: non modificarlo a mano.

- `meteohub/ultima.json`, `meteohub/ultima.bin`: ultima corsa di MOLOCH, WRF ItaliaMeteo,
  WRF CIMA e BOLAM sulla Calabria (griglia di 0,02°).
- `meteohub/storico/AAAA/AAAA-MM-GG.npz`: le stesse previsioni su griglia di 0,1°, ogni giorno.
- `storico/`: osservazioni orarie delle stazioni e previsioni passate dei modelli nei loro punti.
- `correzioni/`: taratura delle previsioni con le stazioni (correzioni.json, rapporto.md).

Dati: MOLOCH e BOLAM (CNR-ISAC), WRF (Agenzia ItaliaMeteo, Fondazione CIMA, LaMMA),
dai dati aperti di MeteoHub - Agenzia ItaliaMeteo. Licenze CC BY 4.0 / CC BY-SA 4.0:
questi dati derivati sono distribuiti con licenza CC BY-SA 4.0.
Stazioni: rete della Protezione Civile in Calabria (MeteoHub, CC BY 4.0) e Meteostat
(CC BY-NC 4.0). Previsioni passate: Open-Meteo (CC BY 4.0).
