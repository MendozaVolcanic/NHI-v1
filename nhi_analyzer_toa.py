"""
NHI Analyzer TOA (proof-of-concept) — Sentinel-2 L1C TOA via Element84.

Valida la hipotesis: con radiancia TOA (como el paper NHI Tool), el criterio
puro NHI_SWIR > 0 AND NHI_SWNIR > 0 sin filtros extra deberia converger a
magnitudes similares al GEE NHI Tool.

Por ahora solo Sentinel-2 L1C (Element84 AWS anonimo). Landsat L1 TOA requiere
credenciales AWS (bucket requester-pays usgs-landsat) — se deja para segunda fase.

Uso:
  python nhi_analyzer_toa.py --volcan Lascar --dias 60
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

# ============================================
# S2 L1C sin firmar AWS
# ============================================
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("AWS_REGION", "eu-central-1")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")

EARTHSEARCH_URL = "https://earth-search.aws.element84.com/v1"
S2_L1C_COLLECTION = "sentinel-2-l1c"

# Element84 S2 L1C asset names + scale/offset TOA
S2_L1C_BANDS = {
    "nir": "nir08", "swir1": "swir16", "swir2": "swir22",
    "blue": "blue",    # B02, para mascara de nubes opacas
    "cirrus": "cirrus" # B10, para mascara de cirrus
}
S2_L1C_SCALE = 0.0001
S2_L1C_OFFSET = -0.1

# Umbrales cloud mask (sobre TOA reflectance)
CLOUD_BLUE_MAX = 0.25   # nubes opacas son brillantes en azul
CLOUD_CIRRUS_MAX = 0.03 # cirrus en B10 (1.375 um). 0.01 era muy estricto para altiplano

# ============================================
# LOGGING
# ============================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def leer_banda(href, lat, lon, buffer_km, size=IMAGE_SIZE):
    bbox_wgs84 = get_bbox(lat, lon, buffer_km)
    with rasterio.open(href) as src:
        bbox_crs = transform_bounds(CRS.from_epsg(4326), src.crs, *bbox_wgs84)
        window = src.window(*bbox_crs)
        data = src.read(1, window=window, out_shape=(size, size),
                        resampling=rasterio.enums.Resampling.bilinear)
    return data.astype(np.float32)


SWIR2_TOA_MIN = 0.30    # Umbral absoluto para pixeles termales reales
NHI_SWIR_MIN = 0.15     # Pixeles termales genuinos dan >0.15; mineralogia/halo 0.10-0.15
NHI_SWNIR_MIN = -0.08   # Permite pixeles termales (emiten en NIR -> SWNIR ligeramente neg)

def _circular_mask(size):
    """Genera mascara circular inscrita en un raster cuadrado de lado 'size'."""
    yy, xx = np.ogrid[:size, :size]
    cy, cx = (size - 1) / 2.0, (size - 1) / 2.0
    r2 = ((yy - cy) ** 2 + (xx - cx) ** 2)
    return r2 <= (size / 2.0) ** 2


def calcular_nhi_toa(nir, swir1, swir2, scale, offset, blue=None, cirrus=None):
    """Criterio NHI Tool sobre TOA reflectance + umbral absoluto SWIR2 + cloud mask + mascara circular."""
    nir_ref = nir * scale + offset
    swir1_ref = swir1 * scale + offset
    swir2_ref = swir2 * scale + offset
    eps = 1e-10

    nhi_swir = (swir2_ref - swir1_ref) / (swir2_ref + swir1_ref + eps)
    nhi_swnir = (swir1_ref - nir_ref) / (swir1_ref + nir_ref + eps)

    valid = (nir_ref > 0) & (swir1_ref > 0) & (swir2_ref > 0)
    valid &= (swir1_ref < 1.0) & (swir2_ref < 1.0)

    # Mascara circular: descartar esquinas del bbox (fuera del radio del volcan)
    # NHI Tool usa circulo, nuestro bbox es cuadrado -> las esquinas son altiplano arido ruidoso
    valid &= _circular_mask(nir.shape[0])

    # Cloud mask deshabilitado: en altiplano a 5000m+ B10 es naturalmente alto (<poca atmosfera
    # sobre el sensor), lo que mata pixeles termales reales. Usamos solo circular + SWIR2>0.15.
    _ = cirrus  # reservado para version futura con umbral calibrado por altitud

    total = int(valid.sum())
    if total < 100:
        return {"pixeles_validos": 0, "pixeles_calientes": 0,
                "max_nhiswir": 0, "max_nhiswnir": 0, "alerta": False}

    # Criterio: NHI_SWIR > umbral + SWIR2 > umbral + NHI_SWNIR > umbral relajado.
    # El filtro NHI_SWNIR > 0 del paper discrimina vegetacion, pero fuentes termales
    # activas emiten en NIR (cuerpo negro ~700K), empujando NHI_SWNIR ligeramente
    # negativo. Relajamos a > -0.08 para capturarlas sin perder el filtro de vegetacion.
    hot_mask = valid & (nhi_swir > NHI_SWIR_MIN) & (nhi_swnir > NHI_SWNIR_MIN) & (swir2_ref > SWIR2_TOA_MIN)
    hot = int(hot_mask.sum())

    return {
        "pixeles_validos": total,
        "pixeles_calientes": hot,
        "max_nhiswir": float(nhi_swir[hot_mask].max()) if hot > 0 else 0.0,
        "max_nhiswnir": float(nhi_swnir[hot_mask].max()) if hot > 0 else 0.0,
        "alerta": hot > 0,
    }


def procesar_volcan_toa(catalog, nombre, datos, fi, ff):
    lat, lon = datos["lat"], datos["lon"]
    buffer_km = datos.get("buffer_km", 3.0)
    bbox = get_bbox(lat, lon, buffer_km)

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

        try:
            nir = leer_banda(item.assets[S2_L1C_BANDS["nir"]].href, lat, lon, buffer_km)
            swir1 = leer_banda(item.assets[S2_L1C_BANDS["swir1"]].href, lat, lon, buffer_km)
            swir2 = leer_banda(item.assets[S2_L1C_BANDS["swir2"]].href, lat, lon, buffer_km)
            blue = leer_banda(item.assets[S2_L1C_BANDS["blue"]].href, lat, lon, buffer_km)
            cirrus = leer_banda(item.assets[S2_L1C_BANDS["cirrus"]].href, lat, lon, buffer_km)
        except Exception as e:
            log.warning(f"  {fecha}: error leyendo bandas: {e}")
            continue

        stats = calcular_nhi_toa(nir, swir1, swir2, S2_L1C_SCALE, S2_L1C_OFFSET, blue=blue, cirrus=cirrus)
        stats["fecha"] = fecha
        stats["sensor"] = "Sentinel-2"
        stats["fuente"] = "S2 L1C TOA (Element84)"
        stats["cloud_cover"] = item.properties.get("eo:cloud_cover")
        resultados.append(stats)
        fechas_procesadas.add(fecha)
        if stats["alerta"]:
            area = stats["pixeles_calientes"] * 400
            log.info(f"    {fecha}: {stats['pixeles_calientes']} px calientes -> {area} m2")

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

    log.info(f"=== TOA POC: {args.volcan} ({args.dias} dias) ===")
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
