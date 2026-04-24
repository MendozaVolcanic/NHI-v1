"""
NHI Analyzer TOA — Replica del NHI Tool de Genzano (GEE) para Sentinel-2 L1C.

Implementa el algoritmo EXACTO del NHI Tool, decifrado del source GEE
(asset users/nicogenzano/default:vulcani/nhi-v1.5).

Pasos:
  1. Lee bandas B5 (705nm), B8A (865nm), B11 (1610nm), B12 (2186nm) como DN
  2. Convierte DN -> radiancia TOA: b = DN * ESUN * cos(SZA) / d
     donde d = pi * 10000 / reflectance_conversion_factor
  3. Calcula 3 indices sobre radiancia:
       NHI_SWIR     = (b2200 - b1600) / (b2200 + b1600)
       NHI_SWNIR    = (b1600 - b800)  / (b1600 + b800)
       TEST_missreg = (b2200 - b800)  / (b2200 + b800)
  4. Pixel HOT si CUALQUIERA de:
       A) NHI_SWIR  > 0 AND b2200 > 2  AND b703 < 90 AND TEST_missreg > -0.6
       B) NHI_SWNIR > 0 AND b800 > 10  AND b2200 > 2 AND b703 < 70 AND TEST_missreg > -0.3
       C) EXTREME (saturados): NOT(A) AND NOT(B) AND b1600 >= 70 AND b703 < 70

Mascara circular adicional (no en NHI Tool original, pero NHI Tool usa area
dibujada por el usuario): aplicamos circulo de buffer_km del centro del volcan
para descartar las esquinas del bbox cuadrado.

Datos: Sentinel-2 L1C via Element84 STAC (anonymous AWS).
Landsat L1 TOA pendiente (bucket usgs-landsat es requester-pays).

Uso: python nhi_analyzer_toa.py --volcan Lascar --dias 60
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pystac_client
import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform_bounds

from config_nhi import (
    VOLCANES, MAX_CLOUD_COVER, IMAGE_SIZE, get_bbox, get_active_volcanoes,
)

# AWS sin firmar para s3://sentinel-s2-l1c (Element84 anonymous access)
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("AWS_REGION", "eu-central-1")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")

EARTHSEARCH_URL = "https://earth-search.aws.element84.com/v1"
S2_L1C_COLLECTION = "sentinel-2-l1c"

# Element84 nombres de assets para S2 L1C
S2_ASSETS = {
    "b703": "rededge1",  # B5  ~705 nm
    "b800": "nir08",     # B8A ~865 nm
    "b1600": "swir16",   # B11 ~1610 nm
    "b2200": "swir22",   # B12 ~2186 nm
}

# Solar Exoatmospheric Irradiance (W/m^2/um) — valores ESA
# Variacion S2A/S2B/S2C es ~1%, usamos S2B como nominal.
ESUN = {
    "b703":  1287.69,  # B5
    "b800":   956.52,  # B8A
    "b1600":  247.15,  # B11
    "b2200":   87.83,  # B12
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def leer_banda(href, lat, lon, buffer_km, size=IMAGE_SIZE):
    """Lee un window de la banda dado bbox WGS84 y tamano final cuadrado."""
    bbox_wgs84 = get_bbox(lat, lon, buffer_km)
    with rasterio.open(href) as src:
        bbox_crs = transform_bounds(CRS.from_epsg(4326), src.crs, *bbox_wgs84)
        window = src.window(*bbox_crs)
        data = src.read(1, window=window, out_shape=(size, size),
                        resampling=rasterio.enums.Resampling.bilinear)
    return data.astype(np.float32)


def _circular_mask(size):
    """Mascara circular inscrita en raster cuadrado."""
    yy, xx = np.ogrid[:size, :size]
    cy, cx = (size - 1) / 2.0, (size - 1) / 2.0
    return ((yy - cy) ** 2 + (xx - cx) ** 2) <= (size / 2.0) ** 2


def to_radiance(dn, esun_band, cos_sza, sun_earth_dist_factor):
    """
    Convierte DN -> radiancia TOA (W/m2/sr/um) replicando el calculo del NHI Tool.

    Formula GEE: b = DN_harmonized * ESUN * cos(SZA) / d
    donde d = pi * 10000 / REFLECTANCE_CONVERSION_CORRECTION,
    y DN_harmonized = DN - 1000 para processing baseline >= 04.00.

    El NHI Tool usa COPERNICUS/S2_HARMONIZED que resta 1000 automaticamente.
    Element84 sirve los DN crudos con baseline 05.12, asi que aplicamos
    el offset manualmente. Clipeamos negativos a 0 para evitar artefactos.
    """
    dn_harmonized = np.maximum(dn - 1000.0, 0.0)
    return dn_harmonized * esun_band * cos_sza / sun_earth_dist_factor


def calcular_nhi_toa(b703, b800, b1600, b2200, sun_elevation_deg, refl_conv_factor, circular):
    """
    Aplica el algoritmo EXACTO del NHI Tool sobre radiancias.

    Retorna dict con: pixeles_validos, pixeles_calientes, mascaras y stats.
    """
    sza_rad = np.radians(90.0 - sun_elevation_deg)
    cos_sza = np.cos(sza_rad)
    d_factor = np.pi * 10000.0 / refl_conv_factor  # divisor en formula radiancia

    # Conversion DN -> radiancia para las 4 bandas
    b703_r  = to_radiance(b703,  ESUN["b703"],  cos_sza, d_factor)
    b800_r  = to_radiance(b800,  ESUN["b800"],  cos_sza, d_factor)
    b1600_r = to_radiance(b1600, ESUN["b1600"], cos_sza, d_factor)
    b2200_r = to_radiance(b2200, ESUN["b2200"], cos_sza, d_factor)

    eps = 1e-10
    nhi_swir  = (b2200_r - b1600_r) / (b2200_r + b1600_r + eps)
    nhi_swnir = (b1600_r - b800_r)  / (b1600_r + b800_r  + eps)
    test_miss_reg = (b2200_r - b800_r) / (b2200_r + b800_r + eps)

    # Validez basica + mascara circular
    valid = (b800_r > 0) & (b1600_r > 0) & (b2200_r > 0) & circular

    total = int(valid.sum())
    if total < 100:
        return _empty_result()

    # Criterios NHI Tool S2 (linea por linea del source GEE)
    cond_a = (
        valid
        & (nhi_swir > 0)
        & (b2200_r > 2)
        & (b703_r < 90)
        & (test_miss_reg > -0.6)
    )
    cond_b = (
        valid
        & (nhi_swnir > 0)
        & (b800_r > 10)
        & (b2200_r > 2)
        & (b703_r < 70)
        & (test_miss_reg > -0.3)
    )
    cond_extreme = (
        valid
        & ~cond_a
        & ~cond_b
        & (b1600_r >= 70)
        & (b703_r < 70)
    )

    hot_mask = cond_a | cond_b | cond_extreme
    hot = int(hot_mask.sum())

    if hot > 0:
        max_swir  = float(nhi_swir[hot_mask].max())
        max_swnir = float(nhi_swnir[hot_mask].max())
        max_b2200 = float(b2200_r[hot_mask].max())
    else:
        max_swir = max_swnir = max_b2200 = 0.0

    return {
        "pixeles_validos": total,
        "pixeles_calientes": hot,
        "pixeles_cond_a": int(cond_a.sum()),
        "pixeles_cond_b": int(cond_b.sum()),
        "pixeles_extreme": int(cond_extreme.sum()),
        "max_nhiswir": round(max_swir, 6),
        "max_nhiswnir": round(max_swnir, 6),
        "max_b2200_radiance": round(max_b2200, 4),
        "alerta": hot > 0,
    }


def _empty_result():
    return {
        "pixeles_validos": 0, "pixeles_calientes": 0,
        "pixeles_cond_a": 0, "pixeles_cond_b": 0, "pixeles_extreme": 0,
        "max_nhiswir": 0, "max_nhiswnir": 0, "max_b2200_radiance": 0,
        "alerta": False,
    }


def procesar_volcan_toa(catalog, nombre, datos, fi, ff):
    lat, lon = datos["lat"], datos["lon"]
    buffer_km = datos.get("buffer_km", 3.0)
    bbox = get_bbox(lat, lon, buffer_km)
    circular = _circular_mask(IMAGE_SIZE)

    search = catalog.search(
        collections=[S2_L1C_COLLECTION], bbox=bbox,
        datetime=f"{fi.strftime('%Y-%m-%d')}/{ff.strftime('%Y-%m-%d')}",
        query={"eo:cloud_cover": {"lte": MAX_CLOUD_COVER}},
        sortby="-properties.datetime",
    )
    items = list(search.items())
    log.info(f"  {len(items)} escenas S2 L1C")

    resultados = []
    fechas_procesadas = set()
    for item in items:
        fecha = datetime.fromisoformat(item.properties["datetime"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
        if fecha in fechas_procesadas:
            continue

        sun_elev = item.properties.get("view:sun_elevation")
        refl_conv = item.properties.get("s2:reflectance_conversion_factor")
        if sun_elev is None or refl_conv is None:
            log.warning(f"  {fecha}: falta metadata SZA o reflectance_conversion_factor")
            continue

        try:
            b703  = leer_banda(item.assets[S2_ASSETS["b703"]].href,  lat, lon, buffer_km)
            b800  = leer_banda(item.assets[S2_ASSETS["b800"]].href,  lat, lon, buffer_km)
            b1600 = leer_banda(item.assets[S2_ASSETS["b1600"]].href, lat, lon, buffer_km)
            b2200 = leer_banda(item.assets[S2_ASSETS["b2200"]].href, lat, lon, buffer_km)
        except Exception as e:
            log.warning(f"  {fecha}: error leyendo bandas: {e}")
            continue

        stats = calcular_nhi_toa(b703, b800, b1600, b2200, sun_elev, refl_conv, circular)
        stats["fecha"] = fecha
        stats["sensor"] = "Sentinel-2"
        stats["fuente"] = "S2 L1C TOA radiance (Element84) — algoritmo NHI Tool exacto"
        stats["cloud_cover"] = item.properties.get("eo:cloud_cover")
        stats["sun_elevation"] = sun_elev
        resultados.append(stats)
        fechas_procesadas.add(fecha)
        if stats["alerta"]:
            area = stats["pixeles_calientes"] * 400
            log.info(f"    {fecha}: {stats['pixeles_calientes']} px ({stats['pixeles_cond_a']}A + {stats['pixeles_cond_b']}B + {stats['pixeles_extreme']}X) -> {area} m2")

    resultados.sort(key=lambda x: x["fecha"], reverse=True)
    return resultados


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--volcan", required=True)
    parser.add_argument("--dias", type=int, default=60)
    args = parser.parse_args()

    volcanes = get_active_volcanoes()
    if args.volcan not in volcanes:
        log.error(f"Volcan '{args.volcan}' no existe")
        sys.exit(1)

    datos = volcanes[args.volcan]
    ff = datetime.now()
    fi = ff - timedelta(days=args.dias)

    log.info(f"=== TOA NHI Tool replica: {args.volcan} ({args.dias} dias) ===")
    catalog = pystac_client.Client.open(EARTHSEARCH_URL)
    resultados = procesar_volcan_toa(catalog, args.volcan, datos, fi, ff)

    out_dir = os.path.join("docs", "nhi_data_toa", args.volcan)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "nhi_timeseries.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    alertas = sum(1 for r in resultados if r["alerta"])
    log.info(f"Guardado: {out_path} ({len(resultados)} obs, {alertas} con anomalias)")


if __name__ == "__main__":
    main()
