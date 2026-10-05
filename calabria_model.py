# =============================================================================
# CALABRIA MODEL - Sistema di correzione territoriale per ICON-2I
# Copyright (c) 2026 Saverio Campanella
# =============================================================================

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    import xarray as xr
    XARRAY_DISPONIBILE = True
except ImportError:
    XARRAY_DISPONIBILE = False

FUSO_ORARIO = ZoneInfo("Europe/Rome")

# =============================================================================
# DESCRITTORI TERRITORIALI
# =============================================================================

class DescrittoriTerritorio:
    """Calcola descrittori orografici per una località."""
    
    def __init__(self):
        # Dataset DEM Copernicus GLO-30 (da scaricare separatamente)
        self.dem = None
        self.caricato = False
    
    def carica_dem(self, percorso_dem):
        """Carica il DEM Copernicus GLO-30."""
        if not XARRAY_DISPONIBILE:
            return False
        
        try:
            self.dem = xr.open_dataset(percorso_dem)
            self.caricato = True
            return True
        except Exception:
            return False
    
    def calcola_per_punto(self, latitudine, longitudine, quota_locale=None):
        """Calcola descrittori territoriali per un punto."""
        descrittori = {
            'latitudine': latitudine,
            'longitudine': longitudine,
            'quota_locale': quota_locale,
            'pendenza': None,
            'esposizione': None,
            'curvatura': None,
            'distanza_costa': None,
            'tipo_posizione': None,
        }
        
        if not self.caricato or quota_locale is None:
            return descrittori
        
        try:
            # Estrai valori DEM intorno al punto
            raggio = 0.05  # ~5 km
            
            lat_min = latitudine - raggio
            lat_max = latitudine + raggio
            lon_min = longitudine - raggio
            lon_max = longitudine + raggio
            
            dem_locale = self.dem.sel(
                lat=slice(lat_min, lat_max),
                lon=slice(lon_min, lon_max)
            )
            
            if dem_locale.sizes['lat'] < 3 or dem_locale.sizes['lon'] < 3:
                return descrittori
            
            # Calcola pendenza ed esposizione
            gradiente = np.gradient(dem_locale['dem'].values)
            pendenza = np.arctan(np.sqrt(gradiente[0]**2 + gradiente[1]**2))
            esposizione = np.arctan2(gradiente[1], gradiente[0])
            
            # Valori medi nel intorno
            descrittori['pendenza'] = float(np.mean(pendenza))
            descrittori['esposizione'] = float(np.mean(esposizione))
            
            # Classifica tipo di posizione
            quota_dem = float(dem_locale['dem'].mean())
            delta_quota = quota_locale - quota_dem
            
            if delta_quota < -50:
                descrittori['tipo_posizione'] = 'fondovalle'
            elif delta_quota > 50:
                descrittori['tipo_posizione'] = 'crinale'
            elif pendenza.mean() > 0.15:
                descrittori['tipo_posizione'] = 'pendio'
            else:
                descrittori['tipo_posizione'] = 'pianura'
            
            # Curvatura (semplificata)
            h = dem_locale['dem'].values
            if h.shape[0] >= 3 and h.shape[1] >= 3:
                centro = h[h.shape[0]//2, h.shape[1]//2]
                media_intorno = np.mean(h)
                descrittori['curvatura'] = float(centro - media_intorno)
            
        except Exception:
            pass
        
        return descrittori


# =============================================================================
# IDENTIFICAZIONE REGIME METEOROLOGICO
# =============================================================================

class IdentificatoreRegime:
    """Identifica il regime meteorologico da ICON-2I."""
    
    @staticmethod
    def identifica(dati_orari, indice_ora=0):
        """Identifica regime per una data ora di previsione."""
        if isinstance(dati_orari, dict):
            dati_orari = pd.DataFrame(dati_orari)
        
        if indice_ora >= len(dati_orari):
            return 'non_disponibile'
        
        riga = dati_orari.iloc[indice_ora]
        
        # Estrai variabili
        vento = float(riga.get('wind_speed_10m', 0) or 0)
        nuvole = float(riga.get('cloud_cover', 0) or 0)
        pioggia = float(riga.get('precipitation', 0) or 0)
        codice = int(riga.get('weather_code', 0) or 0)
        
        # Regimi principali
        if vento < 3 and nuvole < 20 and codice in (0, 1):
            return 'notte_sere_ventilata' if riga.get('Notte', False) else 'giorno_sere_ventilato'
        
        if vento >= 8 and nuvole > 60:
            return 'flusso_intenso_nuvoloso'
        
        if codice in (95, 96, 99) or pioggia > 2:
            return 'temporale'
        
        if 0.5 < pioggia <= 2 and codice in (61, 63, 80, 81):
            return 'pioggia_moderata'
        
        if vento >= 5 and nuvole < 30:
            return 'flusso_moderato_poco_nuvoloso'
        
        return 'condizioni_miste'


# =============================================================================
# CORREZIONE TERRITORIALE
# =============================================================================

class CorrettoreTerritoriale:
    """Applica correzioni basate su territorio e regime."""
    
    def __init__(self):
        # Coefficienti da calibrare con dati storici
        self.coefficienti = {
            'temperatura': {
                'fondovalle_notte': -1.5,
                'fondovalle_giorno': 0.5,
                'crinale': -0.8,
                'pendio': 0.0,
                'pianura': 0.0,
            },
            'vento': {
                'crinale': 1.2,
                'pendio': 1.1,
                'fondovalle': 0.7,
                'pianura': 1.0,
            }
        }
    
    def correggi_temperatura(self, temperatura_icon, tipo_posizione, regime, ora_locale):
        """Corregge temperatura in base a posizione e regime."""
        correzione = 0.0
        
        # Effetto tipo posizione
        if tipo_posizione in self.coefficienti['temperatura']:
            if regime in ('notte_sere_ventilata', 'giorno_sere_ventilato'):
                correzione += self.coefficienti['temperatura'][tipo_posizione]
        
        # Effetto ora (semplificato)
        if 4 <= ora_locale <= 6:
            if tipo_posizione == 'fondovalle':
                correzione -= 0.5
        
        return temperatura_icon + correzione
    
    def correggi_vento(self, vento_icon, tipo_posizione):
        """Corregge vento in base alla posizione."""
        fattore = self.coefficienti['vento'].get(tipo_posizione, 1.0)
        return vento_icon * fattore


# =============================================================================
# CORREZIONE OSSERVATIVA
# =============================================================================

class CorrettoreOsservativo:
    """Corregge previsioni usando osservazioni recenti."""
    
    @staticmethod
    def calcola_bias(osservazioni, previsioni, variabile='temperature_2m'):
        """Calcola bias medio tra osservazioni e previsioni."""
        if osservazioni is None or osservazioni.empty:
            return 0.0
        
        try:
            ultime_3 = osservazioni.last('3h')
            if ultime_3.empty:
                return 0.0
            
            bias = []
            for istante, riga_oss in ultime_3.iterrows():
                ora_prev = istante.floor('h')
                if ora_prev not in previsioni.index:
                    continue
                
                val_oss = riga_oss.get(variabile)
                val_prev = previsioni.loc[ora_prev, variabile]
                
                if pd.notna(val_oss) and pd.notna(val_prev):
                    bias.append(float(val_oss) - float(val_prev))
            
            if not bias:
                return 0.0
            
            return float(np.mean(bias))
        
        except Exception:
            return 0.0
    
    @staticmethod
    def applica_correzione(dati_orari, bias, peso_iniziale=0.8, ore_decadimento=6):
        """Applica correzione con peso decrescente nel tempo."""
        if bias == 0.0:
            return dati_orari
        
        dati = dati_orari.copy()
        adesso = pd.Timestamp.utcnow().tz_localize(None).floor('h')
        
        for indice, riga in dati.iterrows():
            if riga['time'] < adesso:
                continue
            
            ore_trascorse = (riga['time'] - adesso).total_seconds() / 3600
            peso = max(0.0, peso_iniziale * (1 - ore_trascorse / ore_decadimento))
            
            if 'temperature_2m' in dati.columns:
                dati.at[indice, 'temperature_2m'] += bias * peso
        
        return dati


# =============================================================================
# SISTEMA INTEGRATO
# =============================================================================

class SistemaCalabria:
    """Sistema integrato di correzione per la Calabria."""
    
    def __init__(self, percorso_dem=None):
        self.descrittori = DescrittoriTerritorio()
        self.identificatore = IdentificatoreRegime()
        self.correttore_ter = CorrettoreTerritoriale()
        self.correttore_obs = CorrettoreOsservativo()
        
        if percorso_dem:
            self.descrittori.carica_dem(percorso_dem)
    
    def elabora_previsione(self, dati_icon, latitudine, longitudine, 
                          quota_locale=None, osservazioni=None):
        """Elabora previsione ICON-2I con correzioni Calabria."""
        
        # 1. Calcola descrittori territoriali
        descr = self.descrittori.calcola_per_punto(
            latitudine, longitudine, quota_locale
        )
        
        # 2. Prepara dati orari
        dati_orari = pd.DataFrame(dati_icon['hourly'])
        dati_orari['time'] = pd.to_datetime(dati_orari['time'])
        dati_orari = dati_orari.set_index('time')
        
        # 3. Per ogni ora di previsione
        dati_corretti = dati_orari.copy()
        
        for indice in range(len(dati_orari)):
            # Identifica regime
            regime = self.identificatore.identifica(dati_orari, indice)
            
            # Correggi temperatura
            if 'temperature_2m' in dati_orari.columns:
                temp_icon = dati_orari.iloc[indice]['temperature_2m']
                ora_locale = dati_orari.index[indice].hour
                
                temp_corr = self.correttore_ter.correggi_temperatura(
                    temp_icon,
                    descr['tipo_posizione'] or 'pianura',
                    regime,
                    ora_locale
                )
                
                dati_corretti.at[dati_orari.index[indice], 'temperature_2m'] = temp_corr
            
            # Correggi vento
            if 'wind_speed_10m' in dati_orari.columns:
                vento_icon = dati_orari.iloc[indice]['wind_speed_10m']
                vento_corr = self.correttore_ter.correggi_vento(
                    vento_icon,
                    descr['tipo_posizione'] or 'pianura'
                )
                dati_corretti.at[dati_orari.index[indice], 'wind_speed_10m'] = vento_corr
        
        # 4. Correzione osservativa (se disponibile)
        if osservazioni is not None and not osservazioni.empty:
            bias = self.correttore_obs.calcola_bias(
                osservazioni, dati_orari, 'temperature_2m'
            )
            if abs(bias) > 0.3:
                dati_corretti = self.correttore_obs.applica_correzione(
                    dati_corretti, bias
                )
        
        # 5. Aggiorna dizionario
        dati_icon['hourly'] = {
            col: dati_corretti[col].tolist()
            for col in dati_corretti.columns
        }
        
        return dati_icon, descr, regime


# =============================================================================
# UTILITÀ PER L'APP
# =============================================================================

def prepara_info_correzione(descrittori, regime, bias=None):
    """Prepara informazioni sulla correzione per l'interfaccia."""
    info = {
        'tipo_posizione': descrittori.get('tipo_posizione', 'non disponibile'),
        'regime': regime.replace('_', ' ').title(),
        'bias_temperatura': bias if bias is not None else 0.0,
    }
    
    return info
