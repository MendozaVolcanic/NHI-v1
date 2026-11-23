# Serie de "Nevados de Chillan" medida en el lugar equivocado (hasta el 2026-11-23)

Hasta el commit `766afe4` (2026-11-22), `config_nhi.py` ponía el centro de "Nevados de Chillan" en
-37.41096, -71.35231. Ese punto está a 60,97 km del cráter Nicanor (-36.863, -71.377, el de `volcanoes.yaml` de
VRP Chile) y a menos de 1,5 km del centro de "Antuco" de este mismo archivo. Con un buffer de 3,3 km, cada escena de
"Nevados de Chillan" miraba el edificio de Antuco: la serie no dice nada de Chillán.

El hallazgo salió de VRP Chile (S195, `experiments/_s195_viirs_dia_control/extraer_nhi_cajas.py` y
`salida_nhi_cajas.txt`). Nicolás aprobó corregirlo el 2026-11-23.

Qué hay acá, sin modificar (sólo movido con `git mv`):
- `nhi_data/`: `nhi_timeseries.json` (117 escenas, 2026-02-06 a 2026-11-20) y los PNG de hotspots de esa ubicación.
- `nhi_data_toa/`: `nhi_timeseries.json` de la variante TOA.

Se sacó de `docs/` porque `guardar_resultados` mezcla por fecha y sensor: dejarla ahí habría mezclado escenas de Antuco
con las de Chillán en las fechas donde la ubicación nueva no tiene escena. La serie nueva de Chillán se regenera
despachando `nhi_analysis.yml` y `nhi_analysis_toa.yml` con `volcan = Nevados de Chillan`.
