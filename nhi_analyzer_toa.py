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
from PIL import Image as PILImage

from config_nhi import (
    VOLCANES, MAX_CLOUD_COVER, IMAGE_SIZE, HOTSPOT_IMAGE_SIZE,
    get_bbox, get_active_volcanoes,
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


def leer_banda_nativa(href, lat, lon, buffer_km):
    """
    Lee un window de la banda a RESOLUCION NATIVA (sin resampling).

    GEE procesa los pixeles a 20m nativo; el resampling bilinear que haciamos
    antes (a 400x400) promediaba hot pixels con vecinos frios, perdiendo signal.

    Retorna: (data, window_transform) — el transform se usa para calcular
    mascara circular en espacio geografico.
    """
    bbox_wgs84 = get_bbox(lat, lon, buffer_km)
    with rasterio.open(href) as src:
        bbox_crs = transform_bounds(CRS.from_epsg(4326), src.crs, *bbox_wgs84)
        window = src.window(*bbox_crs)
        data = src.read(1, window=window)
        # transform del window en el CRS del raster (para calcular distancias)
        win_transform = src.window_transform(window)
        src_crs = src.crs
    return data.astype(np.float32), win_transform, src_crs


def _circular_mask_geo(shape, transform, crs, lat, lon, buffer_km):
    """
    Mascara circular en espacio geografico: True si la distancia del centro
    del pixel al volcan es <= buffer_km.
    """
    rows, cols = shape
    # Centro de cada pixel en coordenadas del raster (CRS UTM local)
    xs = np.arange(cols) + 0.5
    ys = np.arange(rows) + 0.5
    xx = transform[0] * xs + transform[2]  # easting
    yy = transform[4] * ys + transform[5]  # northing (transform[4] es negativo)
    XX, YY = np.meshgrid(xx, yy)

    # Proyectar el volcano (lat,lon) al CRS del raster
    from rasterio.warp import transform as warp_transform
    xs_c, ys_c = warp_transform(CRS.from_epsg(4326), crs, [lon], [lat])
    cx, cy = xs_c[0], ys_c[0]

    # Distancia en metros (CRS es UTM, unidades metros)
    dist2 = (XX - cx) ** 2 + (YY - cy) ** 2
    return dist2 <= (buffer_km * 1000.0) ** 2


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


def calcular_nhi_toa(b703, b800, b1600, b2200, sun_elevation_deg, refl_conv_factor, circular_mask):
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
    valid = (b800_r > 0) & (b1600_r > 0) & (b2200_r > 0) & circular_mask

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
        # Masks (no se serializan en JSON; se usan para generar PNG)
        "_mask_a": cond_a,
        "_mask_b": cond_b,
        "_mask_extreme": cond_extreme,
        "_b2200_radiance": b2200_r,
    }


def _empty_result():
    return {
        "pixeles_validos": 0, "pixeles_calientes": 0,
        "pixeles_cond_a": 0, "pixeles_cond_b": 0, "pixeles_extreme": 0,
        "max_nhiswir": 0, "max_nhiswnir": 0, "max_b2200_radiance": 0,
        "alerta": False,
    }


def generar_mapa_hotspot_toa(b2200_r, mask_a, mask_b, mask_extreme, nombre, fecha):
    """
    Genera PNG con b2200 (SWIR2 radiance) como fondo grayscale + pixeles calientes
    coloreados por criterio:
      - Rojo (255,40,40):  cond A (NHI_SWIR fuerte) — actividad termal clara
      - Naranja (255,140,0): cond B (NHI_SWNIR + NIR alto) — actividad con emision NIR
      - Amarillo (255,220,0): EXTREME — pixel saturado, lava muy caliente

    Permite distinguir actividad volcanica concentrada (sobre crater) de ruido (disperso).
    Retorna nombre del archivo PNG generado o None si fallo.
    """
    try:
        out_size = HOTSPOT_IMAGE_SIZE
        src_size = b2200_r.shape[0]
        # Fondo grayscale: percentil 98 para contraste sin saturar
        if (b2200_r > 0).any():
            vmax = max(float(np.percentile(b2200_r[b2200_r > 0], 98)), 0.1)
        else:
            vmax = 1.0
        gray = np.clip(b2200_r / vmax * 255, 0, 255).astype(np.uint8)
        img = PILImage.fromarray(gray, mode='L').convert('RGB')
        img = img.resize((out_size, out_size), PILImage.Resampling.NEAREST)

        # Overlay por criterio (orden: extreme -> A -> B para que A y B sobrescriban EXTREME)
        scale = out_size / src_size
        pixels = img.load()

        def paint(mask, color):
            rows, cols = np.where(mask)
            for r, c in zip(rows, cols):
                y = int(r * scale); x = int(c * scale)
                # Pintamos un cuadrado 3x3 para que se vea bien
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < out_size and 0 <= ny < out_size:
                            pixels[nx, ny] = color

        # EXTREME primero (saturado, amarillo brillante)
        if mask_extreme.any():
            paint(mask_extreme, (255, 220, 0))
        # B (naranja)
        if mask_b.any():
            paint(mask_b, (255, 140, 0))
        # A (rojo, prioritario - se pinta arriba si overlap)
        if mask_a.any():
            paint(mask_a, (255, 40, 40))

        out_dir = os.path.join("docs", "nhi_data_toa", nombre)
        os.makedirs(out_dir, exist_ok=True)
        filename = f"{fecha}_s2_hotspot.png"
        img.save(os.path.join(out_dir, filename), optimize=True)
        return filename
    except Exception as e:
        log.warning(f"  {nombre} {fecha}: error generando PNG: {e}")
        return None


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

        sun_elev = item.properties.get("view:sun_elevation")
        refl_conv = item.properties.get("s2:reflectance_conversion_factor")
        if sun_elev is None or refl_conv is None:
            log.warning(f"  {fecha}: falta metadata SZA o reflectance_conversion_factor")
            continue

        try:
            b703,  tr, src_crs = leer_banda_nativa(item.assets[S2_ASSETS["b703"]].href,  lat, lon, buffer_km)
            b800,  _,  _       = leer_banda_nativa(item.assets[S2_ASSETS["b800"]].href,  lat, lon, buffer_km)
            b1600, _,  _       = leer_banda_nativa(item.assets[S2_ASSETS["b1600"]].href, lat, lon, buffer_km)
            b2200, _,  _       = leer_banda_nativa(item.assets[S2_ASSETS["b2200"]].href, lat, lon, buffer_km)
        except Exception as e:
            log.warning(f"  {fecha}: error leyendo bandas: {e}")
            continue

        # Las 4 bandas S2 (B5, B8A, B11, B12) son nativas a 20m -> mismo shape
        if not (b703.shape == b800.shape == b1600.shape == b2200.shape):
            log.warning(f"  {fecha}: shapes distintos (bilinear podria forzar)")
            continue

        circular_mask = _circular_mask_geo(b703.shape, tr, src_crs, lat, lon, buffer_km)
        stats = calcular_nhi_toa(b703, b800, b1600, b2200, sun_elev, refl_conv, circular_mask)

        # Generar PNG si hay alerta (color-coded por criterio A/B/EXTREME)
        if stats.get("alerta"):
            png = generar_mapa_hotspot_toa(
                stats.pop("_b2200_radiance"),
                stats.pop("_mask_a"),
                stats.pop("_mask_b"),
                stats.pop("_mask_extreme"),
                nombre, fecha
            )
            if png:
                stats["hotspot_image"] = png
        # Limpiar masks que no se serializan
        for k in ("_mask_a", "_mask_b", "_mask_extreme", "_b2200_radiance"):
            stats.pop(k, None)

        stats["fecha"] = fecha
        stats["sensor"] = "Sentinel-2"
        stats["fuente"] = "S2 L1C TOA radiance (Element84) — algoritmo NHI Tool exacto"
        stats["cloud_cover"] = item.properties.get("eo:cloud_cover")
        stats["sun_elevation"] = sun_elev
        # Pixel area nativo (20m x 20m = 400 m2 para bandas SWIR de S2)
        px_size_m = abs(tr[0])
        px_area = px_size_m * px_size_m
        stats["pixel_area_m2"] = px_area
        stats["pixel_size_m"] = px_size_m

        resultados.append(stats)
        fechas_procesadas.add(fecha)
        if stats["alerta"]:
            area = stats["pixeles_calientes"] * px_area
            log.info(f"    {fecha}: {stats['pixeles_calientes']} px ({stats['pixeles_cond_a']}A + {stats['pixeles_cond_b']}B + {stats['pixeles_extreme']}X) -> {area:.0f} m2 (pix={px_size_m:.0f}m)")

    resultados.sort(key=lambda x: x["fecha"], reverse=True)
    return resultados


# Buffer TOA por volcan: usa el buffer_km del config (que ya esta dimensionado por
# tamano del edificio volcanico — Cordon Caulle 10km, Hudson 8km, etc).
# Solo override explicito Lascar a 3km (match con default NHI Tool GEE para Lascar).
TOA_BUFFER_OVERRIDES = {
    "Lascar": 3.0,
}


def resolve_buffer(volcan):
    if volcan in TOA_BUFFER_OVERRIDES:
        return TOA_BUFFER_OVERRIDES[volcan]
    # Default: usar el buffer_km del config_nhi (dimensionado por geologo)
    return VOLCANES.get(volcan, {}).get("buffer_km", 5.0)


def procesar_y_guardar(catalog, nombre, datos, fi, ff):
    """Procesa un volcan y guarda JSON. Retorna numero de alertas."""
    datos = dict(datos)
    datos["buffer_km"] = resolve_buffer(nombre)
    try:
        resultados = procesar_volcan_toa(catalog, nombre, datos, fi, ff)
    except Exception as e:
        log.error(f"  {nombre}: ERROR {e}")
        return -1

    out_dir = os.path.join("docs", "nhi_data_toa", nombre)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "nhi_timeseries.json")

    # Mergear con historial existente: las nuevas obs reemplazan las antiguas con
    # la misma fecha; el resto del historial se preserva.
    historico: dict[str, dict] = {}
    if os.path.isfile(out_path):
        try:
            with open(out_path, encoding="utf-8") as f:
                prev = json.load(f)
            historico = {r["fecha"]: r for r in prev if "fecha" in r}
        except Exception as e:
            log.warning(f"  {nombre}: no se pudo leer historial previo ({e}), se sobreescribe")

    nuevas = len(resultados)
    for r in resultados:
        historico[r["fecha"]] = r

    merged = sorted(historico.values(), key=lambda r: r["fecha"], reverse=True)

    if len(merged) < len(historico) - nuevas:
        log.warning(f"  {nombre}: merged ({len(merged)}) < prev ({len(historico)}), revisar")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    alertas = sum(1 for r in merged if r.get("alerta"))
    log.info(f"  {nombre}: {nuevas} nuevas + {len(merged)-nuevas} hist = {len(merged)} total, {alertas} alertas -> {out_path}")
    return alertas


def generar_resumen_toa(volcanoes_data):
    """Genera resumen global TOA paralelo al principal."""
    resumen = {}
    for nombre, datos in volcanoes_data.items():
        path = os.path.join("docs", "nhi_data_toa", nombre, "nhi_timeseries.json")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            obs = json.load(f)
        alertas_7d = [r for r in obs if r.get("alerta") and
                      (datetime.now() - datetime.strptime(r["fecha"], "%Y-%m-%d")).days <= 7]
        alertas_30d = [r for r in obs if r.get("alerta") and
                       (datetime.now() - datetime.strptime(r["fecha"], "%Y-%m-%d")).days <= 30]
        if alertas_7d:
            nivel = "rojo"
        elif alertas_30d:
            nivel = "amarillo"
        else:
            nivel = "verde"
        ultima = obs[0]["fecha"] if obs else None
        max_area = max((r["pixeles_calientes"] * r.get("pixel_area_m2", 400) for r in obs), default=0)
        resumen[nombre] = {
            "nivel": nivel,
            "alertas_7d": len(alertas_7d),
            "alertas_30d": len(alertas_30d),
            "max_area_m2": round(max_area, 1),
            "ultima_fecha": ultima,
            "total_observaciones": len(obs),
            "buffer_km": resolve_buffer(nombre),
            "zona": datos.get("zona", ""),
            "lat": datos.get("lat", 0),
            "lon": datos.get("lon", 0),
        }
    out = os.path.join("docs", "nhi_data_toa", "resumen_global.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    log.info(f"Resumen TOA: {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--volcan", default=None, help="Procesar solo un volcan; si se omite, procesa todos")
    parser.add_argument("--zona", default=None, choices=["Norte","Centro","Sur","Austral"],
                        help="Procesar solo una zona (Norte/Centro/Sur/Austral)")
    parser.add_argument("--dias", type=int, default=60)
    args = parser.parse_args()

    volcanes = get_active_volcanoes()
    if args.volcan:
        if args.volcan not in volcanes:
            log.error(f"Volcan '{args.volcan}' no existe")
            sys.exit(1)
        volcanes = {args.volcan: volcanes[args.volcan]}
    elif args.zona:
        volcanes = {k: v for k, v in volcanes.items() if v.get("zona") == args.zona}
        log.info(f"Filtro zona '{args.zona}': {len(volcanes)} volcanes")

    ff = datetime.now()
    fi = ff - timedelta(days=args.dias)

    log.info(f"=== TOA NHI Tool replica: {len(volcanes)} volcanes, {args.dias} dias ===")
    catalog = pystac_client.Client.open(EARTHSEARCH_URL)

    for i, (nombre, datos) in enumerate(volcanes.items(), 1):
        log.info(f"[{i}/{len(volcanes)}] {nombre} ({datos.get('zona','')}) buffer={resolve_buffer(nombre)}km")
        procesar_y_guardar(catalog, nombre, datos, fi, ff)

    if len(volcanes) > 1:
        generar_resumen_toa(volcanes)


if __name__ == "__main__":
    main()
