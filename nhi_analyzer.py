"""
NHI Analyzer — Normalized Hotspot Indices para volcanes chilenos
Calcula NHISWIR y NHISWNIR usando Sentinel-2 y Landsat 8/9 via Planetary Computer.

Algoritmo (Marchese et al. 2019):
  NHISWIR  = (SWIR2 - SWIR1) / (SWIR2 + SWIR1)
  NHISWNIR = (SWIR1 - NIR)   / (SWIR1 + NIR)
  Pixel caliente: NHISWIR > 0 OR NHISWNIR > 0

Uso:
  python nhi_analyzer.py              # 43 volcanes, ultimos 60 dias
  python nhi_analyzer.py --test       # 3 volcanes de prueba
  python nhi_analyzer.py --dias 30    # ultimos 30 dias
  python nhi_analyzer.py --volcan Villarrica
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform_bounds

from config_nhi import (
    VOLCANES, STAC_URL, SENTINEL2_COLLECTION, LANDSAT_COLLECTION,
    SENTINEL2_BANDS, SENTINEL2_SCALE, SENTINEL2_OFFSET,
    LANDSAT_BANDS, LANDSAT_SCALE, LANDSAT_OFFSET,
    NHI_THRESHOLD, N_SIGMA, MIN_ABSOLUTE_NHI, MAX_HOT_FRACTION,
    SWIR_MIN_REFLECTANCE,
    MAX_CLOUD_COVER, DIAS_ATRAS, IMAGE_SIZE,
    get_active_volcanoes, get_bbox, get_nhi_data_dir,
)

# ============================================
# LOGGING
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ============================================
# STAC
# ============================================
def get_catalog():
    return pystac_client.Client.open(
        STAC_URL,
        modifier=planetary_computer.sign_inplace,
    )


def buscar_escenas(catalog, collection, lat, lon, buffer_km, fecha_inicio, fecha_fin):
    bbox = get_bbox(lat, lon, buffer_km)
    fecha_str = f"{fecha_inicio.strftime('%Y-%m-%d')}/{fecha_fin.strftime('%Y-%m-%d')}"

    search = catalog.search(
        collections=[collection],
        bbox=bbox,
        datetime=fecha_str,
        query={"eo:cloud_cover": {"lte": MAX_CLOUD_COVER}},
        sortby="-datetime",
    )
    return list(search.items())


# ============================================
# LECTURA DE BANDA
# ============================================
def leer_banda(asset_href, lat, lon, buffer_km, size=IMAGE_SIZE):
    bbox_wgs84 = get_bbox(lat, lon, buffer_km)

    with rasterio.open(asset_href) as src:
        try:
            bbox_crs = transform_bounds(
                CRS.from_epsg(4326), src.crs,
                bbox_wgs84[0], bbox_wgs84[1],
                bbox_wgs84[2], bbox_wgs84[3],
            )
        except Exception as e:
            log.warning(f"  Error transformando bbox: {e}")
            return None

        window = src.window(*bbox_crs)
        try:
            data = src.read(1, window=window, out_shape=(size, size),
                            resampling=rasterio.enums.Resampling.bilinear)
        except Exception as e:
            log.warning(f"  Error leyendo banda: {e}")
            return None

    return data.astype(np.float32)


# ============================================
# CALCULO NHI
# ============================================
def calcular_nhi(nir, swir1, swir2, scale, offset):
    """
    Calcula indices NHI a partir de 3 bandas con filtrado estadistico.

    Inspirado en VRP Chile triple-threshold:
      1. NHISWIR y NHISWNIR deben superar mediana + N_SIGMA * std
      2. Ambos indices deben ser > MIN_ABSOLUTE_NHI
      3. Si >MAX_HOT_FRACTION pixeles son calientes, escena descartada (ruido solar/nieve)

    Retorna dict con nhi_swir, nhi_swnir, hot_mask, stats.
    """
    # Convertir a reflectancia
    nir_ref = nir * scale + offset
    swir1_ref = swir1 * scale + offset
    swir2_ref = swir2 * scale + offset

    eps = 1e-10

    # NHISWIR = (SWIR2 - SWIR1) / (SWIR2 + SWIR1)
    nhi_swir = (swir2_ref - swir1_ref) / (swir2_ref + swir1_ref + eps)

    # NHISWNIR = (SWIR1 - NIR) / (SWIR1 + NIR)
    nhi_swnir = (swir1_ref - nir_ref) / (swir1_ref + nir_ref + eps)

    # Mascara de pixeles validos (reflectancia minima)
    valid = (swir1_ref > SWIR_MIN_REFLECTANCE) & (swir2_ref > SWIR_MIN_REFLECTANCE)
    valid &= (nir_ref > 0) & (swir1_ref < 1.0) & (swir2_ref < 1.0)  # eliminar saturados

    total_pixels = int(valid.sum())
    if total_pixels < 100:
        return _empty_result(nhi_swir, nhi_swnir)

    # --- Filtro estadistico (inspirado en VRP Chile background annulus) ---
    # Calcular estadisticas de fondo sobre pixeles validos
    swir_vals = nhi_swir[valid]
    swnir_vals = nhi_swnir[valid]

    median_swir = float(np.median(swir_vals))
    std_swir = float(np.std(swir_vals))
    median_swnir = float(np.median(swnir_vals))
    std_swnir = float(np.std(swnir_vals))

    # Umbral dinamico: mediana + max(MIN_ABSOLUTE, N_SIGMA * std)
    thresh_swir = median_swir + max(MIN_ABSOLUTE_NHI, N_SIGMA * std_swir)
    thresh_swnir = median_swnir + max(MIN_ABSOLUTE_NHI, N_SIGMA * std_swnir)

    # Pixel caliente: NHISWIR supera filtro estadistico Y NHISWNIR > 0 (confirma)
    # NHISWIR es el detector primario; NHISWNIR confirma sin filtro estadistico
    # porque su fondo es variable (vegetacion/roca tienen SWIR1 > NIR naturalmente)
    hot_swir = valid & (nhi_swir > thresh_swir) & (nhi_swir > NHI_THRESHOLD)
    hot_swnir = valid & (nhi_swnir > NHI_THRESHOLD)
    hot_mask = hot_swir & hot_swnir

    hot_pixels = int(hot_mask.sum())

    # --- Filtro de fraccion maxima (anti-ruido solar) ---
    # Si >5% de pixeles validos son "calientes", la escena es ruidosa
    fraction = hot_pixels / max(total_pixels, 1)
    if fraction > MAX_HOT_FRACTION:
        log.debug(f"    Escena descartada: {fraction:.1%} pixeles calientes (max {MAX_HOT_FRACTION:.0%})")
        hot_mask[:] = False
        hot_pixels = 0

    # Estadisticas
    swir2_hot_total = float(swir2_ref[hot_mask].sum()) if hot_pixels > 0 else 0.0
    max_nhi_swir = float(nhi_swir[hot_mask].max()) if hot_pixels > 0 else 0.0
    max_nhi_swnir = float(nhi_swnir[hot_mask].max()) if hot_pixels > 0 else 0.0

    stats = {
        "pixeles_validos": total_pixels,
        "pixeles_calientes": hot_pixels,
        "fraccion_caliente": round(fraction if hot_pixels > 0 else 0.0, 6),
        "max_nhiswir": round(max_nhi_swir, 6),
        "max_nhiswnir": round(max_nhi_swnir, 6),
        "swir2_total": round(swir2_hot_total, 4),
        "thresh_swir": round(thresh_swir, 6),
        "thresh_swnir": round(thresh_swnir, 6),
        "bg_median_swir": round(median_swir, 6),
        "bg_std_swir": round(std_swir, 6),
        "alerta": hot_pixels > 0,
    }

    return {
        "nhi_swir": nhi_swir,
        "nhi_swnir": nhi_swnir,
        "hot_mask": hot_mask,
        "stats": stats,
    }


def _empty_result(nhi_swir, nhi_swnir):
    """Resultado vacio cuando no hay suficientes pixeles validos."""
    return {
        "nhi_swir": nhi_swir,
        "nhi_swnir": nhi_swnir,
        "hot_mask": np.zeros_like(nhi_swir, dtype=bool),
        "stats": {
            "pixeles_validos": 0, "pixeles_calientes": 0,
            "fraccion_caliente": 0, "max_nhiswir": 0, "max_nhiswnir": 0,
            "swir2_total": 0, "thresh_swir": 0, "thresh_swnir": 0,
            "bg_median_swir": 0, "bg_std_swir": 0, "alerta": False,
        },
    }


# ============================================
# PROCESAR UN ITEM (una escena)
# ============================================
def procesar_item(item, lat, lon, buffer_km, band_map, scale, offset, sensor_name):
    """Lee las 3 bandas de un item y calcula NHI."""
    # Verificar que las bandas existen
    for key, band_name in band_map.items():
        if band_name not in item.assets:
            log.debug(f"  Banda {band_name} no disponible")
            return None

    # Leer bandas
    nir = leer_banda(item.assets[band_map["nir"]].href, lat, lon, buffer_km)
    swir1 = leer_banda(item.assets[band_map["swir1"]].href, lat, lon, buffer_km)
    swir2 = leer_banda(item.assets[band_map["swir2"]].href, lat, lon, buffer_km)

    if nir is None or swir1 is None or swir2 is None:
        return None

    resultado = calcular_nhi(nir, swir1, swir2, scale, offset)

    # Extraer fecha
    fecha = datetime.fromisoformat(
        item.properties["datetime"].replace("Z", "+00:00")
    ).strftime("%Y-%m-%d")

    resultado["stats"]["fecha"] = fecha
    resultado["stats"]["satelite"] = item.properties.get("platform", sensor_name)
    resultado["stats"]["cloud_cover"] = item.properties.get("eo:cloud_cover", None)
    resultado["stats"]["sensor"] = sensor_name

    return resultado


# ============================================
# PROCESAR UN VOLCAN
# ============================================
def procesar_volcan(catalog, nombre, datos, fecha_inicio, fecha_fin):
    """
    Analiza NHI de un volcan para el rango de fechas.
    Busca en Sentinel-2 y Landsat, fusiona resultados.
    Retorna lista de resultados por fecha.
    """
    lat = datos["lat"]
    lon = datos["lon"]
    buffer_km = datos.get("buffer_km", 3.0)

    resultados = []
    fechas_procesadas = set()

    # --- Sentinel-2 ---
    log.info(f"  Sentinel-2...")
    try:
        items_s2 = buscar_escenas(
            catalog, SENTINEL2_COLLECTION,
            lat, lon, buffer_km, fecha_inicio, fecha_fin
        )
        log.info(f"    {len(items_s2)} escenas encontradas")

        for item in items_s2:
            fecha = datetime.fromisoformat(
                item.properties["datetime"].replace("Z", "+00:00")
            ).strftime("%Y-%m-%d")

            if fecha in fechas_procesadas:
                continue

            res = procesar_item(
                item, lat, lon, buffer_km,
                SENTINEL2_BANDS, SENTINEL2_SCALE, SENTINEL2_OFFSET,
                "Sentinel-2"
            )
            if res:
                resultados.append(res["stats"])
                fechas_procesadas.add(fecha)
                if res["stats"]["alerta"]:
                    log.info(f"    {fecha}: {res['stats']['pixeles_calientes']} pixeles calientes")
    except Exception as e:
        log.error(f"  Error Sentinel-2: {e}")

    # --- Landsat 8/9 ---
    log.info(f"  Landsat 8/9...")
    try:
        items_ls = buscar_escenas(
            catalog, LANDSAT_COLLECTION,
            lat, lon, buffer_km, fecha_inicio, fecha_fin
        )
        log.info(f"    {len(items_ls)} escenas encontradas")

        for item in items_ls:
            fecha = datetime.fromisoformat(
                item.properties["datetime"].replace("Z", "+00:00")
            ).strftime("%Y-%m-%d")

            if fecha in fechas_procesadas:
                continue

            res = procesar_item(
                item, lat, lon, buffer_km,
                LANDSAT_BANDS, LANDSAT_SCALE, LANDSAT_OFFSET,
                "Landsat"
            )
            if res:
                resultados.append(res["stats"])
                fechas_procesadas.add(fecha)
                if res["stats"]["alerta"]:
                    log.info(f"    {fecha}: {res['stats']['pixeles_calientes']} pixeles calientes")
    except Exception as e:
        log.error(f"  Error Landsat: {e}")

    # Ordenar por fecha descendente
    resultados.sort(key=lambda x: x["fecha"], reverse=True)
    return resultados


# ============================================
# GUARDAR RESULTADOS
# ============================================
def guardar_resultados(nombre, resultados):
    """Guarda serie temporal NHI de un volcan en JSON."""
    data_dir = get_nhi_data_dir(nombre)
    ruta = os.path.join(data_dir, "nhi_timeseries.json")

    # Cargar datos existentes si hay
    existentes = {}
    if os.path.isfile(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            datos_prev = json.load(f)
            for entry in datos_prev:
                key = f"{entry['fecha']}_{entry.get('sensor', '')}"
                existentes[key] = entry

    # Merge nuevos resultados
    for r in resultados:
        key = f"{r['fecha']}_{r.get('sensor', '')}"
        existentes[key] = r

    # Guardar ordenado por fecha
    merged = sorted(existentes.values(), key=lambda x: x["fecha"], reverse=True)

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    log.info(f"  Guardado: {ruta} ({len(merged)} registros)")
    return merged


def generar_resumen_global(todos_los_resultados):
    """
    Genera resumen de alertas para todos los volcanes.
    docs/nhi_data/resumen_global.json
    """
    resumen = {}
    for nombre, resultados in todos_los_resultados.items():
        # Ultimas detecciones
        alertas_7d = [r for r in resultados
                      if r["alerta"]
                      and (datetime.now() - datetime.strptime(r["fecha"], "%Y-%m-%d")).days <= 7]

        alertas_30d = [r for r in resultados
                       if r["alerta"]
                       and (datetime.now() - datetime.strptime(r["fecha"], "%Y-%m-%d")).days <= 30]

        # Determinar nivel de alerta
        if alertas_7d:
            nivel = "rojo"
        elif alertas_30d:
            nivel = "amarillo"
        else:
            nivel = "verde"

        ultima_fecha = resultados[0]["fecha"] if resultados else None
        max_hot = max((r["pixeles_calientes"] for r in resultados), default=0)

        resumen[nombre] = {
            "nivel": nivel,
            "alertas_7d": len(alertas_7d),
            "alertas_30d": len(alertas_30d),
            "max_pixeles_calientes": max_hot,
            "ultima_fecha_analizada": ultima_fecha,
            "total_observaciones": len(resultados),
            "zona": VOLCANES.get(nombre, {}).get("zona", ""),
        }

    ruta = os.path.join("docs", "nhi_data", "resumen_global.json")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    log.info(f"Resumen global: {ruta}")

    # Estadisticas
    rojos = sum(1 for v in resumen.values() if v["nivel"] == "rojo")
    amarillos = sum(1 for v in resumen.values() if v["nivel"] == "amarillo")
    verdes = sum(1 for v in resumen.values() if v["nivel"] == "verde")
    log.info(f"  Rojo: {rojos} | Amarillo: {amarillos} | Verde: {verdes}")

    return resumen


# ============================================
# MAIN
# ============================================
def main():
    parser = argparse.ArgumentParser(description="Analisis NHI para volcanes chilenos")
    parser.add_argument("--test", action="store_true",
                        help="Modo test: 3 volcanes (Villarrica, Lascar, Calbuco)")
    parser.add_argument("--dias", type=int, default=DIAS_ATRAS,
                        help=f"Dias atras (default: {DIAS_ATRAS})")
    parser.add_argument("--volcan", type=str, default=None,
                        help="Procesar solo un volcan")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    fecha_fin = datetime.now()
    fecha_inicio = fecha_fin - timedelta(days=args.dias)

    volcanes = get_active_volcanoes()

    if args.test:
        log.info("=== MODO TEST: 3 volcanes ===")
        test_names = ["Villarrica", "Lascar", "Calbuco"]
        volcanes = {k: v for k, v in volcanes.items() if k in test_names}
    elif args.volcan:
        if args.volcan not in volcanes:
            log.error(f"Volcan '{args.volcan}' no encontrado")
            sys.exit(1)
        volcanes = {args.volcan: volcanes[args.volcan]}

    log.info(f"NHI Analyzer | {len(volcanes)} volcanes | {fecha_inicio.date()} -> {fecha_fin.date()}")

    # Conectar
    log.info("Conectando a Planetary Computer...")
    try:
        catalog = get_catalog()
    except Exception as e:
        log.error(f"Error conectando: {e}")
        sys.exit(1)

    # Procesar
    todos = {}
    ok = 0
    errores = 0

    for i, (nombre, datos) in enumerate(volcanes.items(), 1):
        log.info(f"\n[{i}/{len(volcanes)}] {nombre} ({datos['zona']})")
        try:
            resultados = procesar_volcan(catalog, nombre, datos, fecha_inicio, fecha_fin)
            if resultados:
                merged = guardar_resultados(nombre, resultados)
                todos[nombre] = merged
                ok += 1
                alertas = sum(1 for r in resultados if r["alerta"])
                log.info(f"  {len(resultados)} fechas, {alertas} con anomalias")
            else:
                log.info(f"  Sin datos")
                todos[nombre] = []
        except Exception as e:
            log.error(f"  ERROR: {e}")
            errores += 1

    # Resumen global
    generar_resumen_global(todos)

    log.info(f"\n{'='*50}")
    log.info(f"NHI completado: {ok} volcanes procesados, {errores} errores")
    log.info(f"{'='*50}")


if __name__ == "__main__":
    main()
