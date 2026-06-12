"""
Validador generico contra el NHI Tool GEE para CUALQUIER volcan.

Procesa S2 (Element84) + Landsat (M2M) con un CENTRO y RADIO dados (los mismos
que uso el NHI Tool al generar el CSV) y compara el area de hotspot por fecha.

Uso:
  USGS_USERNAME=... USGS_TOKEN=... python validate_gee.py \
      --nombre Villarrica --lat -39.420 --lon -71.930 --radio 2000 \
      --start 2025-01-01 --end 2026-06-11 --csv ruta/al/ee-chart.csv

Las coords deben ser las del Smithsonian GVP (centro que usa el NHI Tool):
  Villarrica:        -39.420, -71.930
  Planchon-Peteroa:  -35.240, -70.570
  Lascar:            -23.367, -67.736
El --radio en METROS debe ser EXACTAMENTE el que pusiste en el campo buffer del NHI Tool.
"""
import argparse, csv, os, datetime
import pystac_client

from nhi_analyzer_toa import procesar_volcan_toa, _circular_mask_geo, EARTHSEARCH_URL
from nhi_landsat_reader import procesar_volcan_landsat, landsat_available
import m2m_client


def parse_gee_csv(path):
    """CSV del NHI Tool: 'Mmm d, YYYY',area_m2. Devuelve {fecha_iso: area}."""
    ref = {}
    with open(path, encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)
        for row in rd:
            if len(row) < 2 or not row[0].strip():
                continue
            try:
                d = datetime.datetime.strptime(row[0].strip().strip('"'), "%b %d, %Y").date().isoformat()
                ref[d] = int(float(row[1].replace(",", "").strip().strip('"')))
            except Exception:
                pass
    return ref


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radio", type=float, required=True, help="radio en METROS (igual al NHI Tool)")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--csv", default=None, help="CSV GEE de referencia (opcional)")
    args = ap.parse_args()

    datos = {"lat": args.lat, "lon": args.lon, "buffer_km": args.radio / 1000.0}
    fi = datetime.datetime.strptime(args.start, "%Y-%m-%d")
    ff = datetime.datetime.strptime(args.end, "%Y-%m-%d")

    catalog = pystac_client.Client.open(EARTHSEARCH_URL)
    print(f"Procesando {args.nombre} @ ({args.lat},{args.lon}) r={args.radio}m  {args.start}..{args.end}")

    s2 = procesar_volcan_toa(catalog, args.nombre, datos, fi, ff)
    print(f"  S2: {len(s2)} obs")

    oli = []
    if landsat_available():
        k = m2m_client.login_token()
        try:
            oli = procesar_volcan_landsat(k, args.nombre, datos, fi, ff, _circular_mask_geo)
        finally:
            m2m_client.logout(k)
        print(f"  Landsat: {len(oli)} obs")

    # area por fecha (m2); si hay 2 sensores el mismo dia, el NHI Tool los muestra
    # como puntos separados -> guardamos por (fecha, sensor) y comparamos por fecha.
    nuestro = {}
    for r in s2 + oli:
        area = r["pixeles_calientes"] * r.get("pixel_area_m2", 400)
        nuestro[r["fecha"]] = nuestro.get(r["fecha"], 0) + area  # suma si mismo dia

    if not args.csv or not os.path.isfile(args.csv):
        print("\nSin CSV de referencia. Fechas con deteccion (nuestro pipeline):")
        for f in sorted(nuestro):
            if nuestro[f] > 0:
                print(f"  {f}: {nuestro[f]:.0f} m2")
        return

    ref = parse_gee_csv(args.csv)
    comun = sorted(set(ref) & set(nuestro))
    print(f"\n{'fecha':12} {'GEE m2':>9} {'NHI-v1 m2':>10}  match")
    ok = 0
    for f in comun:
        m = ref[f] == nuestro[f]
        ok += m
        print(f"  {f:12} {ref[f]:>9} {nuestro[f]:>10.0f}  {'OK' if m else '<<< DIFF'}")
    print(f"\nMATCH: {ok}/{len(comun)} = {100*ok/max(len(comun),1):.0f}%")
    solo_gee = sorted(set(ref) - set(nuestro))
    solo_n = sorted(f for f in nuestro if f not in ref and nuestro[f] > 0)
    if solo_gee:
        print(f"Solo en GEE (no capturamos): {solo_gee}")
    if solo_n:
        print(f"Solo nuestro (no en GEE): {solo_n}")


if __name__ == "__main__":
    main()
