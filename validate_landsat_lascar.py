"""
Validacion del pipeline Landsat OLI contra NHI Tool GEE para Lascar.

Lee escenas L1 via M2M (window COG desde landsatlook), aplica el algoritmo
nhi_landsat y compara el area de hotspot con el CSV de referencia GEE.

Credenciales por entorno: USGS_USERNAME, USGS_TOKEN.
"""
import os, sys, urllib.request, re
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.crs import CRS

import m2m_client as m
from config_nhi import get_bbox
from nhi_analyzer_toa import _circular_mask_geo
from nhi_landsat import landsat_dn_to_radiance, calcular_nhi_landsat

LAT, LON, BUF = -23.36726, -67.73611, 3.0
BANDS = {"b400": "_B1.TIF", "b800": "_B5.TIF", "b1600": "_B6.TIF", "b2200": "_B7.TIF"}

# Referencia GEE (fechas Landsat del CSV oficial de Lascar)
GEE_REF = {
    "2026-02-19": 0, "2026-02-27": 2700, "2026-03-07": 1800,
    "2026-03-23": 2700, "2026-03-31": 1800, "2026-04-08": 3600, "2026-04-16": 1800,
}


def parse_mtl_radiance(mtl_text):
    """Extrae RADIANCE_MULT/ADD_BAND_x del MTL.txt. Devuelve {banda: (mult, add)}."""
    coef = {}
    for bnum, key in [("1", "b400"), ("5", "b800"), ("6", "b1600"), ("7", "b2200")]:
        mult = re.search(rf"RADIANCE_MULT_BAND_{bnum}\s*=\s*([-\d.E+]+)", mtl_text)
        add = re.search(rf"RADIANCE_ADD_BAND_{bnum}\s*=\s*([-\d.E+]+)", mtl_text)
        coef[key] = (float(mult.group(1)), float(add.group(1)))
    return coef


def read_window(url):
    bbox = get_bbox(LAT, LON, BUF)
    with rasterio.open("/vsicurl/" + url) as src:
        bb = transform_bounds(CRS.from_epsg(4326), src.crs, *bbox)
        win = src.window(*bb)
        arr = src.read(1, window=win).astype(np.float64)
        tr = src.window_transform(win)
        crs = src.crs
    return arr, tr, crs


def process_scene(api_key, start, end):
    data = m.scene_search(api_key, LAT, LON, start, end)
    res = data.get("results", [])
    if not res:
        return None
    eids = [r["entityId"] for r in res]
    opts = m.download_options(api_key, eids)
    # Recolectar las 4 bandas + MTL de la primera escena
    want = {}
    for o in opts:
        for s in (o.get("secondaryDownloads") or []):
            did = s.get("displayId") or ""
            for tag in list(BANDS.values()) + ["_MTL.txt"]:
                if did.endswith(tag):
                    want[tag] = {"entityId": s["entityId"], "productId": s["id"], "displayId": did}
    dls = [{"entityId": v["entityId"], "productId": v["productId"]} for v in want.values()]
    resp = m.download_request(api_key, dls)
    urls = {}
    for d in resp.get("availableDownloads", []):
        for tag, v in want.items():
            # match por displayId dentro de la url
            if v["displayId"] in d.get("url", ""):
                urls[tag] = d["url"]
    # MTL
    mtl_text = urllib.request.urlopen(urls["_MTL.txt"], timeout=60).read().decode("utf-8", "ignore")
    coef = parse_mtl_radiance(mtl_text)
    # Bandas -> radiancia
    rad = {}
    ref_tr = ref_crs = None
    for key, tag in BANDS.items():
        dn, tr, crs = read_window(urls[tag])
        mult, add = coef[key]
        rad[key] = landsat_dn_to_radiance(dn, mult, add)
        ref_tr, ref_crs = tr, crs
    mask = _circular_mask_geo(rad["b1600"].shape, ref_tr, ref_crs, LAT, LON, BUF)
    stats = calcular_nhi_landsat(rad["b400"], rad["b800"], rad["b1600"], rad["b2200"], mask)
    area = stats["pixeles_calientes"] * 900  # Landsat 30m -> 900 m2/px
    return area, stats["pixeles_calientes"], res[0]["displayId"]


if __name__ == "__main__":
    k = m.login_token()
    print(f"{'fecha':12} {'GEE m2':>8} {'OLI m2':>8}  match")
    fechas = sys.argv[1:] or ["2026-03-07"]
    ok = 0
    for f in fechas:
        from datetime import date, timedelta
        d0 = date.fromisoformat(f)
        out = process_scene(k, (d0 - timedelta(days=1)).isoformat(), (d0 + timedelta(days=1)).isoformat())
        if out is None:
            print(f"{f:12} {GEE_REF.get(f,'?'):>8} {'NO SCENE':>8}")
            continue
        area, px, did = out
        gee = GEE_REF.get(f, "?")
        match = (gee == area)
        ok += match
        print(f"{f:12} {gee:>8} {area:>8}  {'OK' if match else '<<< DIFF'}  ({px}px, {did})")
    print(f"\nMatch: {ok}/{len(fechas)}")
    m.logout(k)
