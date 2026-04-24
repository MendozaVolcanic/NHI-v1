"""
Configuracion NHI (Normalized Hotspot Indices)
Analisis de anomalias termales volcanicas usando indices SWIR/NIR
para 43 volcanes activos de Chile.

Fuentes de datos:
  - Sentinel-2 L2A (Planetary Computer): B8A (NIR), B11 (SWIR1), B12 (SWIR2)
  - Landsat 8/9 C2 L2 (Planetary Computer): B5 (NIR), B6 (SWIR1), B7 (SWIR2)

Algoritmo basado en: Marchese et al. 2019 (doi:10.3390/rs11232876)
"""

import os
from math import cos, radians

# ============================================
# CONFIGURACION GENERAL
# ============================================
MAX_CLOUD_COVER = 50        # Mas estricto que descarga visual
DIAS_ATRAS = 60             # Ventana de busqueda por defecto
IMAGE_SIZE = 400            # Pixeles (no necesitamos resolucion visual alta)
HOTSPOT_IMAGE_SIZE = 200    # Pixeles para mapas PNG de hotspots
DIAS_RETENCION = 365        # Mantener datos NHI por 1 anio

# STAC
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
SENTINEL2_COLLECTION = "sentinel-2-l2a"
LANDSAT_COLLECTION = "landsat-c2-l2"

# ============================================
# BANDAS PARA NHI
# ============================================
# NHI usa radiancia TOA, pero Planetary Computer sirve L2A (reflectancia).
# Para Sentinel-2 L2A usamos reflectancia de superficie (SR) como proxy:
#   - La relacion NHISWIR > 0 se mantiene porque el indice es normalizado
#   - La magnitud absoluta cambia, pero el signo (positivo = anomalia) se conserva
#
# Sentinel-2 L2A: factor_escala = 0.0001 (valor digital → reflectancia)
# Landsat C2 L2:  factor_escala = 0.0000275, offset = -0.2

SENTINEL2_BANDS = {
    "nir":   "B8A",     # ~0.865 um, 20m
    "swir1": "B11",     # ~1.610 um, 20m
    "swir2": "B12",     # ~2.190 um, 20m
}
SENTINEL2_SCALE = 0.0001
SENTINEL2_OFFSET = 0.0

LANDSAT_BANDS = {
    "nir":   "nir08",   # B5, ~0.865 um, 30m
    "swir1": "swir16",  # B6, ~1.610 um, 30m
    "swir2": "swir22",  # B7, ~2.190 um, 30m
}
LANDSAT_SCALE = 0.0000275
LANDSAT_OFFSET = -0.2

# ============================================
# UMBRALES NHI (Marchese et al. 2019 — NHI Tool GEE)
# ============================================
# Usamos el criterio puro del paper / NHI Tool:
#   hot = NHI_SWIR > 0 AND NHI_SWNIR > 0
#
# Motivo: comparabilidad con el historico generado por el NHI Tool en
# Google Earth Engine (https://nicogenzano.users.earthengine.app/view/nhi-tool).
# Los filtros estadisticos previos (mediana+Nsigma, MAX_HOT_FRACTION) se
# removieron porque producian escalas de area incompatibles con el historico.
#
# Nota: el paper usa radiancia TOA; nosotros usamos L2A (Planetary Computer
# no sirve TOA). El signo del indice se conserva, la magnitud absoluta puede
# diferir ligeramente pero el patron temporal debe coincidir.

# ============================================
# 43 VOLCANES ACTIVOS DE CHILE
# ============================================
VOLCANES = {
    # ZONA NORTE (8 volcanes)
    "Taapaca": {
        "lat": -18.10922, "lon": -69.50584, "buffer_km": 5.0,
        "zona": "Norte", "activo": True
    },
    "Parinacota": {
        "lat": -18.17126, "lon": -69.14534, "buffer_km": 2.5,
        "zona": "Norte", "activo": True
    },
    "Guallatiri": {
        "lat": -18.42781, "lon": -69.08500, "buffer_km": 2.5,
        "zona": "Norte", "activo": True
    },
    "Isluga": {
        "lat": -19.16737, "lon": -68.82225, "buffer_km": 3.5,
        "zona": "Norte", "activo": True
    },
    "Irruputuncu": {
        "lat": -20.73329, "lon": -68.56041, "buffer_km": 1.4,
        "zona": "Norte", "activo": True
    },
    "Ollague": {
        "lat": -21.30685, "lon": -68.17941, "buffer_km": 3.5,
        "zona": "Norte", "activo": True
    },
    "San Pedro": {
        "lat": -21.88485, "lon": -68.40706, "buffer_km": 4.5,
        "zona": "Norte", "activo": True
    },
    "Lascar": {
        "lat": -23.36726, "lon": -67.73611, "buffer_km": 2.8,
        "zona": "Norte", "activo": True
    },

    # ZONA CENTRO (9 volcanes)
    "Tupungatito": {
        "lat": -33.40849, "lon": -69.82181, "buffer_km": 3.5,
        "zona": "Centro", "activo": True
    },
    "San Jose": {
        "lat": -33.78682, "lon": -69.89732, "buffer_km": 2.5,
        "zona": "Centro", "activo": True
    },
    "Tinguiririca": {
        "lat": -34.80794, "lon": -70.34917, "buffer_km": 2.8,
        "zona": "Centro", "activo": True
    },
    "Planchon-Peteroa": {
        "lat": -35.24212, "lon": -70.57189, "buffer_km": 1.3,
        "zona": "Centro", "activo": True
    },
    "Descabezado Grande": {
        "lat": -35.60431, "lon": -70.74830, "buffer_km": 7.0,
        "zona": "Centro", "activo": True
    },
    "Tatara-San Pedro": {
        "lat": -35.99755, "lon": -70.84533, "buffer_km": 3.5,
        "zona": "Centro", "activo": True
    },
    "Laguna del Maule": {
        "lat": -36.07100, "lon": -70.49828, "buffer_km": 9.0,
        "zona": "Centro", "activo": True
    },
    "Nevado de Longavi": {
        "lat": -36.20001, "lon": -71.17010, "buffer_km": 5.0,
        "zona": "Centro", "activo": True
    },
    "Nevados de Chillan": {
        "lat": -37.41096, "lon": -71.35231, "buffer_km": 3.3,
        "zona": "Centro", "activo": True
    },

    # ZONA SUR (13 volcanes)
    "Antuco": {
        "lat": -37.41859, "lon": -71.34097, "buffer_km": 3.0,
        "zona": "Sur", "activo": True
    },
    "Copahue": {
        "lat": -37.85715, "lon": -71.16836, "buffer_km": 2.0,
        "zona": "Sur", "activo": True
    },
    "Callaqui": {
        "lat": -37.92554, "lon": -71.46113, "buffer_km": 5.0,
        "zona": "Sur", "activo": True
    },
    "Lonquimay": {
        "lat": -38.38216, "lon": -71.58530, "buffer_km": 3.0,
        "zona": "Sur", "activo": True
    },
    "Llaima": {
        "lat": -38.71238, "lon": -71.73447, "buffer_km": 4.0,
        "zona": "Sur", "activo": True
    },
    "Sollipulli": {
        "lat": -38.98103, "lon": -71.51557, "buffer_km": 5.0,
        "zona": "Sur", "activo": True
    },
    "Villarrica": {
        "lat": -39.42052, "lon": -71.93939, "buffer_km": 1.5,
        "zona": "Sur", "activo": True
    },
    "Quetrupillan": {
        "lat": -39.53150, "lon": -71.70337, "buffer_km": 5.5,
        "zona": "Sur", "activo": True
    },
    "Lanin": {
        "lat": -39.62762, "lon": -71.47923, "buffer_km": 4.5,
        "zona": "Sur", "activo": True
    },
    "Mocho-Choshuenco": {
        "lat": -39.93439, "lon": -72.00281, "buffer_km": 5.0,
        "zona": "Sur", "activo": True
    },
    "Carran - Los Venados": {
        "lat": -40.37922, "lon": -72.10509, "buffer_km": 6.5,
        "zona": "Sur", "activo": True
    },
    "Puyehue - Cordon Caulle": {
        "lat": -40.54783, "lon": -72.14826, "buffer_km": 10.0,
        "zona": "Sur", "activo": True
    },
    "Antillanca - Casablanca": {
        "lat": -40.76716, "lon": -72.15114, "buffer_km": 5.5,
        "zona": "Sur", "activo": True
    },

    # ZONA AUSTRAL (13 volcanes)
    "Osorno": {
        "lat": -41.10453, "lon": -72.49271, "buffer_km": 4.0,
        "zona": "Austral", "activo": True
    },
    "Calbuco": {
        "lat": -41.33035, "lon": -72.60399, "buffer_km": 2.5,
        "zona": "Austral", "activo": True
    },
    "Yate": {
        "lat": -41.77750, "lon": -72.38678, "buffer_km": 4.5,
        "zona": "Austral", "activo": True
    },
    "Hornopiren": {
        "lat": -41.88132, "lon": -72.43178, "buffer_km": 2.5,
        "zona": "Austral", "activo": True
    },
    "Huequi": {
        "lat": -42.38094, "lon": -72.58103, "buffer_km": 1.5,
        "zona": "Austral", "activo": True
    },
    "Michinmahuida": {
        "lat": -42.83733, "lon": -72.43927, "buffer_km": 9.5,
        "zona": "Austral", "activo": True
    },
    "Chaiten": {
        "lat": -42.83276, "lon": -72.65155, "buffer_km": 2.7,
        "zona": "Austral", "activo": True
    },
    "Corcovado": {
        "lat": -43.19300, "lon": -72.78979, "buffer_km": 2.5,
        "zona": "Austral", "activo": True
    },
    "Melimoyu": {
        "lat": -44.07612, "lon": -72.85073, "buffer_km": 7.0,
        "zona": "Austral", "activo": True
    },
    "Mentolat": {
        "lat": -44.69272, "lon": -73.07507, "buffer_km": 3.0,
        "zona": "Austral", "activo": True
    },
    "Cay": {
        "lat": -45.07068, "lon": -72.96318, "buffer_km": 3.5,
        "zona": "Austral", "activo": True
    },
    "Maca": {
        "lat": -45.11210, "lon": -73.16908, "buffer_km": 3.5,
        "zona": "Austral", "activo": True
    },
    "Hudson": {
        "lat": -45.90915, "lon": -72.96508, "buffer_km": 8.0,
        "zona": "Austral", "activo": True
    },
}


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def get_active_volcanoes():
    return {k: v for k, v in VOLCANES.items() if v.get("activo", False)}


def get_bbox(lat, lon, buffer_km):
    delta_lat = buffer_km / 111.0
    delta_lon = buffer_km / (111.0 * abs(cos(radians(lat))))
    return [lon - delta_lon, lat - delta_lat, lon + delta_lon, lat + delta_lat]


def get_nhi_data_dir(volcano_name):
    base = os.path.join("docs", "nhi_data", volcano_name)
    os.makedirs(base, exist_ok=True)
    return base
