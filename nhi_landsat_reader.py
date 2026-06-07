"""
Lector Landsat 8/9 C2 L1 de produccion via USGS M2M (window COG, no bundle).

Genera observaciones con el MISMO schema que el pipeline S2 (nhi_analyzer_toa),
para mergear S2 + OLI en un unico timeseries por volcan.

Credenciales por entorno: USGS_USERNAME, USGS_TOKEN.
Si no estan, procesar_volcan_landsat() devuelve [] (Landsat queda desactivado,
el pipeline S2 sigue funcionando solo).

Eficiencia: lee solo el window del AOI (~200x200 px) desde landsatlook via
/vsicurl/. NO descarga la escena completa (90MB/banda).
Cuota: 5 download-requests por escena (4 bandas + MTL). ~600 escenas/anio -> 3000,
bajo el limite de 20.000.
"""
from __future__ import annotations
import os, re, time, logging, urllib.request
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.crs import CRS

import m2m_client as m
from config_nhi import get_bbox
from nhi_landsat import landsat_dn_to_radiance, calcular_nhi_landsat

log = logging.getLogger("nhi_landsat_reader")

BAND_TAGS = {"b400": "_B1.TIF", "b800": "_B5.TIF", "b1600": "_B6.TIF", "b2200": "_B7.TIF"}
PIXEL_AREA_M2 = 900.0   # Landsat OLI 30m
PIXEL_SIZE_M = 30.0


def landsat_available() -> bool:
    return bool(os.environ.get("USGS_USERNAME") and os.environ.get("USGS_TOKEN"))


def _parse_mtl(mtl_text):
    coef, extra = {}, {}
    for bnum, key in [("1", "b400"), ("5", "b800"), ("6", "b1600"), ("7", "b2200")]:
        mult = re.search(rf"RADIANCE_MULT_BAND_{bnum}\s*=\s*([-\d.E+]+)", mtl_text)
        add = re.search(rf"RADIANCE_ADD_BAND_{bnum}\s*=\s*([-\d.E+]+)", mtl_text)
        coef[key] = (float(mult.group(1)), float(add.group(1)))
    se = re.search(r"SUN_ELEVATION\s*=\s*([-\d.E+]+)", mtl_text)
    cc = re.search(r"CLOUD_COVER\s*=\s*([-\d.E+]+)", mtl_text)
    extra["sun_elevation"] = float(se.group(1)) if se else None
    extra["cloud_cover"] = float(cc.group(1)) if cc else None
    return coef, extra


def _read_window(url, lat, lon, buffer_km):
    bbox = get_bbox(lat, lon, buffer_km)
    with rasterio.open("/vsicurl/" + url) as src:
        bb = transform_bounds(CRS.from_epsg(4326), src.crs, *bbox)
        win = src.window(*bb)
        arr = src.read(1, window=win).astype(np.float64)
        tr = src.window_transform(win)
        crs = src.crs
    return arr, tr, crs


def _platform_from_id(display_id):
    if display_id.startswith("LC08"):
        return "Landsat-8"
    if display_id.startswith("LC09"):
        return "Landsat-9"
    return "Landsat"


def _resolver_urls(api_key, dls, label, all_files, max_polls=8, wait_s=15):
    """
    download-request batch + polling download-retrieve para las que quedan en
    'preparing' (escenas recientes que M2M stagea on-demand).
    Devuelve {displayId: url}. Mapea por displayId presente en la URL.
    """
    display_ids = [f["displayId"] for f in all_files]

    def _map(downloads, urls):
        for dd in downloads:
            u = dd.get("url", "")
            for did in display_ids:
                if did in u and did not in urls:
                    urls[did] = u

    urls = {}
    try:
        resp = m.download_request(api_key, dls, label=label)
    except m.M2MError as e:
        log.warning(f"  download-request fallo: {e}")
        return urls
    _map(resp.get("availableDownloads", []), urls)
    preparing = len(resp.get("preparingDownloads", []))

    polls = 0
    while len(urls) < len(display_ids) and polls < max_polls:
        time.sleep(wait_s)
        polls += 1
        try:
            ret = m.download_retrieve(api_key, label)
        except m.M2MError as e:
            log.warning(f"  download-retrieve fallo: {e}")
            break
        _map(ret.get("available", []), urls)
        if len(urls) >= len(display_ids):
            break
    if len(urls) < len(display_ids):
        log.warning(f"  {label}: {len(urls)}/{len(display_ids)} URLs resueltas "
                    f"(quedaron {preparing} en staging tras {polls} polls)")
    return urls


def procesar_volcan_landsat(api_key, nombre, datos, fi, ff, circular_mask_fn):
    """
    Procesa todas las escenas Landsat de un volcan en [fi, ff].
    Retorna lista de observaciones (schema homogeneo con S2).
    circular_mask_fn: funcion (shape, transform, crs, lat, lon, buffer_km) -> mask.
    """
    lat, lon = datos["lat"], datos["lon"]
    buffer_km = datos.get("buffer_km", 3.0)
    start, end = fi.strftime("%Y-%m-%d"), ff.strftime("%Y-%m-%d")

    try:
        data = m.scene_search(api_key, lat, lon, start, end, max_results=400)
    except m.M2MError as e:
        log.warning(f"  {nombre}: scene-search Landsat fallo: {e}")
        return []
    escenas = data.get("results", [])
    if not escenas:
        return []

    eids = [r["entityId"] for r in escenas]
    try:
        opts = m.download_options(api_key, eids)
    except m.M2MError as e:
        log.warning(f"  {nombre}: download-options fallo: {e}")
        return []

    needed = list(BAND_TAGS.values()) + ["_MTL.txt"]

    # Mapear: escena -> {tag: secondaryDownload} (4 bandas + MTL)
    por_escena = {}
    for o in opts:
        for s in (o.get("secondaryDownloads") or []):
            did = s.get("displayId") or ""
            for tag in needed:
                if did.endswith(tag):
                    scene_pref = did[:-len(tag)]
                    por_escena.setdefault(scene_pref, {})[tag] = {
                        "entityId": s["entityId"], "productId": s["id"], "displayId": did}

    # Solo escenas con las 4 bandas + MTL
    por_escena = {k: v for k, v in por_escena.items() if all(t in v for t in needed)}
    if not por_escena:
        return []

    # 1 download-request batch para TODO el volcan (con label) + polling retrieve.
    # Las escenas recientes quedan en "preparing" y se recuperan con retrieve.
    all_files = [f for files in por_escena.values() for f in files.values()]
    dls = [{"entityId": f["entityId"], "productId": f["productId"]} for f in all_files]
    label = f"nhi_{nombre.replace(' ', '_')}_{start}"
    urls = _resolver_urls(api_key, dls, label, all_files)

    resultados = []
    fechas_vistas = set()
    for scene_pref, files in por_escena.items():
        if not all(files[t]["displayId"] in urls for t in needed):
            continue
        display_id = files["_B6.TIF"]["displayId"].replace("_B6.TIF", "")
        mfecha = re.search(r"_(\d{8})_", display_id)
        if not mfecha:
            continue
        d = mfecha.group(1)
        fecha = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        if fecha in fechas_vistas:
            continue
        scene_urls = {t: urls[files[t]["displayId"]] for t in needed}

        try:
            mtl_text = urllib.request.urlopen(scene_urls["_MTL.txt"], timeout=60).read().decode("utf-8", "ignore")
            coef, extra = _parse_mtl(mtl_text)
            rad, ref_tr, ref_crs = {}, None, None
            for key, tag in BAND_TAGS.items():
                dn, tr, crs = _read_window(scene_urls[tag], lat, lon, buffer_km)
                mult, add = coef[key]
                rad[key] = landsat_dn_to_radiance(dn, mult, add)
                ref_tr, ref_crs = tr, crs
            mask = circular_mask_fn(rad["b1600"].shape, ref_tr, ref_crs, lat, lon, buffer_km)
            stats = calcular_nhi_landsat(rad["b400"], rad["b800"], rad["b1600"], rad["b2200"], mask)
        except Exception as e:
            log.warning(f"  {nombre} {fecha}: error procesando bandas: {e}")
            continue

        # Limpiar masks no serializables (PNG se genera aparte si se desea)
        for kk in ("_mask_a", "_mask_b", "_mask_extreme", "_b2200_radiance"):
            stats.pop(kk, None)
        stats["fecha"] = fecha
        stats["sensor"] = _platform_from_id(display_id)
        stats["fuente"] = "Landsat C2 L1 TOA radiance (USGS M2M) - algoritmo NHI Tool OLI"
        stats["cloud_cover"] = extra.get("cloud_cover")
        stats["sun_elevation"] = extra.get("sun_elevation")
        stats["pixel_area_m2"] = PIXEL_AREA_M2
        stats["pixel_size_m"] = PIXEL_SIZE_M
        resultados.append(stats)
        fechas_vistas.add(fecha)
        log.info(f"    [OLI] {fecha}: {stats['pixeles_calientes']} px -> "
                 f"{stats['pixeles_calientes']*900} m2 ({stats['sensor']})")

    return resultados
