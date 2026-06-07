"""
Algoritmo NHI para Landsat 8/9 OLI (replica EXACTA del NHI Tool de Genzano).

Decifrado de nhi_tool_source.js (lineas 135-170). El algoritmo OLI DIFIERE del
de Sentinel-2 en cuatro puntos criticos (no es copiar los mismos umbrales):

  1. Banda de "test brillante": OLI usa b400nm (B1 coastal aerosol);
     S2 usa b703nm (B5 red-edge). Sirve para rechazar nieve/nube brillante.
  2. Umbral EXTREME: OLI b1600 >= 74; S2 b1600 >= 70.
  3. OLI NO aplica el TEST_miss_reg (que en S2 filtra mis-registracion de bandas).
  4. OLI NO exige b800 > 10 en la condicion SWNIR (S2 si).

Conversion DN -> radiancia: el NHI Tool usa ee.Algorithms.Landsat.calibratedRadiance,
que es lineal:  L = RADIANCE_MULT_BAND_x * DN + RADIANCE_ADD_BAND_x
(coeficientes del MTL de cada escena). El resultado es radiancia espectral en
W/(m^2 sr um), MISMA escala que la conversion S2 -> por eso los umbrales (2, 74)
son cross-sensor y el algoritmo NHI funciona igual en ambos.

Este modulo es PURO (sin red): recibe arrays de DN + coeficientes, devuelve stats.
El lector de escenas (AWS COG / M2M) se conecta aparte.
"""
from __future__ import annotations
import numpy as np


# Mapeo banda OLI -> nombre fisico del NHI Tool
# B1=coastal(~443nm), B5=NIR(~865nm), B6=SWIR1(~1609nm), B7=SWIR2(~2201nm)
LANDSAT_BANDS = {
    "b400": "B1",    # coastal aerosol  -> test brillante (nieve/nube)
    "b800": "B5",    # NIR
    "b1600": "B6",   # SWIR1
    "b2200": "B7",   # SWIR2
}


def landsat_dn_to_radiance(dn, mult, add):
    """
    DN -> radiancia espectral TOA (replica calibratedRadiance de GEE).

    L = mult * DN + add   (coeficientes RADIANCE_MULT/ADD_BAND_x del MTL)

    Se clipea a 0 los negativos (DN de relleno / borde de swath) para evitar
    artefactos en los indices normalizados.
    """
    rad = dn.astype(np.float64) * mult + add
    return np.maximum(rad, 0.0)


def calcular_nhi_landsat(b400, b800, b1600, b2200, circular_mask):
    """
    Aplica el algoritmo NHI Tool OLI sobre radiancias ya convertidas.

    Parametros: arrays 2D de radiancia (W/m^2/sr/um) de las 4 bandas, ya
    recortados al AOI, mas la mascara circular del buffer.

    Retorna dict con el MISMO schema que calcular_nhi_toa (S2) para que el
    merge S2+OLI en el timeseries sea homogeneo. Incluye masks para PNG.
    """
    eps = 1e-10
    nhi_swir  = (b2200 - b1600) / (b2200 + b1600 + eps)   # normalizedDifference(2200,1600)
    nhi_swnir = (b1600 - b800)  / (b1600 + b800  + eps)    # normalizedDifference(1600,800)

    valid = (b800 > 0) & (b1600 > 0) & (b2200 > 0) & circular_mask
    total = int(valid.sum())
    if total < 100:
        return _empty_landsat()

    # --- Algoritmo OLI (orden del source GEE; SWNIR tiene prioridad sobre SWIR) ---
    # NHI_SWNIR_L8 = (b2200 > 2) AND (NHI_SWNIR > 0)
    swnir_l8 = valid & (b2200 > 2) & (nhi_swnir > 0)
    # NHI_SWIR_L8 = (b2200 > 2) AND (NHI_SWNIR_L8 == 0) AND (NHI_SWIR > 0)
    swir_l8 = valid & (b2200 > 2) & (~swnir_l8) & (nhi_swir > 0)
    # EXTREME = NOT swir_l8 AND NOT swnir_l8 AND b1600 >= 74 AND b400 < 70
    extreme = valid & (~swir_l8) & (~swnir_l8) & (b1600 >= 74) & (b400 < 70)

    hot_mask = swir_l8 | swnir_l8 | extreme
    hot = int(hot_mask.sum())

    if hot > 0:
        max_swir  = float(nhi_swir[hot_mask].max())
        max_swnir = float(nhi_swnir[hot_mask].max())
        max_b2200 = float(b2200[hot_mask].max())
        sum_b1600 = float(b1600[hot_mask].sum())
        sum_b2200 = float(b2200[hot_mask].sum())
    else:
        max_swir = max_swnir = max_b2200 = 0.0
        sum_b1600 = sum_b2200 = 0.0

    return {
        "pixeles_validos": total,
        "pixeles_calientes": hot,
        # Para OLI: cond_a = SWIR_L8, cond_b = SWNIR_L8 (mapeo al schema S2).
        "pixeles_cond_a": int(swir_l8.sum()),
        "pixeles_cond_b": int(swnir_l8.sum()),
        "pixeles_extreme": int(extreme.sum()),
        "max_nhiswir": round(max_swir, 6),
        "max_nhiswnir": round(max_swnir, 6),
        "max_b2200_radiance": round(max_b2200, 4),
        "sum_b1600_radiance": round(sum_b1600, 4),
        "sum_b2200_radiance": round(sum_b2200, 4),
        "alerta": hot > 0,
        "_mask_a": swir_l8,
        "_mask_b": swnir_l8,
        "_mask_extreme": extreme,
        "_b2200_radiance": b2200,
    }


def _empty_landsat():
    return {
        "pixeles_validos": 0, "pixeles_calientes": 0,
        "pixeles_cond_a": 0, "pixeles_cond_b": 0, "pixeles_extreme": 0,
        "max_nhiswir": 0, "max_nhiswnir": 0, "max_b2200_radiance": 0,
        "sum_b1600_radiance": 0, "sum_b2200_radiance": 0,
        "alerta": False,
    }
