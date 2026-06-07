"""
Cliente minimo USGS M2M (Machine-to-Machine) API para Landsat C2 L1.

Credenciales SOLO por variable de entorno (nunca en archivo / commit):
  USGS_USERNAME, USGS_TOKEN

Flujo: login_token -> scene_search -> download_options -> download_request.
scene-search y download-options NO consumen cuota de descarga; solo
download-request cuenta para el limite diario.
"""
from __future__ import annotations
import os
import json
import urllib.request

BASE = "https://m2m.cr.usgs.gov/api/api/json/stable"
DATASET_L1 = "landsat_ot_c2_l1"   # Landsat 8/9 OLI/TIRS Collection 2 Level-1


class M2MError(RuntimeError):
    pass


def _post(endpoint: str, payload: dict, api_key: str | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/{endpoint}", data=data)
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("X-Auth-Token", api_key)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise M2MError(f"HTTP {e.code} en {endpoint}: {e.read().decode('utf-8', 'ignore')[:300]}")
    if body.get("errorCode"):
        raise M2MError(f"{endpoint} errorCode={body['errorCode']}: {body.get('errorMessage')}")
    return body.get("data")


def login_token() -> str:
    user = os.environ.get("USGS_USERNAME")
    token = os.environ.get("USGS_TOKEN")
    if not user or not token:
        raise M2MError("Faltan USGS_USERNAME / USGS_TOKEN en el entorno")
    api_key = _post("login-token", {"username": user, "token": token})
    if not api_key:
        raise M2MError("login-token no devolvio apiKey")
    return api_key


def scene_search(api_key, lat, lon, start, end, half_deg=0.05, max_results=50):
    """Busca escenas L1 que cubren (lat,lon) en [start,end]. No consume cuota."""
    payload = {
        "datasetName": DATASET_L1,
        "sceneFilter": {
            "spatialFilter": {
                "filterType": "mbr",
                "lowerLeft": {"latitude": lat - half_deg, "longitude": lon - half_deg},
                "upperRight": {"latitude": lat + half_deg, "longitude": lon + half_deg},
            },
            "acquisitionFilter": {"start": start, "end": end},
        },
        "maxResults": max_results,
        "metadataType": "summary",
    }
    return _post("scene-search", payload, api_key)


def download_options(api_key, entity_ids):
    """Lista productos descargables por escena. No consume cuota."""
    return _post("download-options",
                 {"datasetName": DATASET_L1, "entityIds": entity_ids}, api_key)


def download_request(api_key, downloads):
    """Pide URLs de descarga. CONSUME cuota (download-request)."""
    return _post("download-request", {"downloads": downloads}, api_key)


def logout(api_key):
    try:
        _post("logout", {}, api_key)
    except Exception:
        pass
