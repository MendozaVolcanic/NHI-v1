# NHI Dashboard — Session Status (cierre 2026-04-25)

## TL;DR

Dashboard con **dos pipelines paralelos** (L2A legacy + TOA replica NHI Tool).
TOA es el default. Backfill 1 año en marcha en GitHub Actions (4 jobs paralelos por zona).
Pendiente principal: aprobación USGS para agregar Landsat L1 TOA al pipeline TOA.

## Repo

- **GitHub:** https://github.com/MendozaVolcanic/NHI-v1
- **Pages:** GitHub Pages activo (servido desde `/docs`)
- **Branch principal:** `main`
- **Branch alternativa:** `toa-migration` (reservada, sin uso activo)

## Arquitectura actual

```
docs/
├── index.html                    # Dashboard (toggle L2A ↔ TOA)
├── nhi_data/                     # Pipeline L2A (legacy)
│   └── {volcan}/
│       ├── nhi_timeseries.json
│       └── *_hotspot.png         # PNGs B/W con pixeles rojos
└── nhi_data_toa/                 # Pipeline TOA (replica NHI Tool)
    ├── resumen_global.json
    └── {volcan}/
        ├── nhi_timeseries.json
        └── *_s2_hotspot.png      # PNGs color-coded (rojo/naranja/amarillo por criterio A/B/EXTREME)

nhi_analyzer.py                   # Pipeline L2A (Planetary Computer, S2 L2A + Landsat C2 L2)
nhi_analyzer_toa.py               # Pipeline TOA (Element84 S2 L1C, replica algoritmo NHI Tool)
nhi_tool_source.js                # Source GEE del NHI Tool descargado (referencia)
config_nhi.py                     # 43 volcanes con buffer_km dimensionado por geologo

.github/workflows/
├── nhi_analysis.yml              # Cron 12:00 UTC, L2A diario --dias 14
└── nhi_analysis_toa.yml          # Cron 14:00 UTC, TOA diario --dias 14, soporta --zona/--volcan
```

## Algoritmo TOA (replica NHI Tool)

Decifrado del source GEE en `nhi_tool_source.js` (asset `users/nicogenzano/default:vulcani/nhi-v1.5`).

```
Conversion S2 L1C: b = (DN - 1000) * ESUN_band * cos(SZA) / d
                   d = pi * 10000 / reflectance_conversion_factor
                   ESUN nominal S2B: B5=1287.69, B8A=956.52, B11=247.15, B12=87.83

Indices: NHI_SWIR  = (b2200 - b1600) / (b2200 + b1600)
         NHI_SWNIR = (b1600 - b800)  / (b1600 + b800)
         TEST_missreg = (b2200 - b800) / (b2200 + b800)

Pixel HOT si CUALQUIERA (OR):
  A) NHI_SWIR  > 0 AND b2200 > 2  AND b703 < 90 AND TEST_missreg > -0.6
  B) NHI_SWNIR > 0 AND b800 > 10  AND b2200 > 2 AND b703 < 70 AND TEST_missreg > -0.3
  C) EXTREME (saturados): NOT(A) AND NOT(B) AND b1600 >= 70 AND b703 < 70
```

**Validacion vs NHI Tool GEE para Lascar Feb-Abr 2026** (CSV oficial en `docs/nhi_data_toa/Lascar/nhi_tool_gee_reference.csv`):
- 11 de 12 escenas S2 matchean BIT A BIT (mismo numero)
- 1 borderline (04-17: GEE 1 pixel = 400 m2; nuestro 0)

## Estado de los pipelines

### L2A (legacy, Planetary Computer)
- ✅ Funcionando, cron diario activo
- ⚠️ Genera FPs grandes (Lascar 31-mar 120k m2 falso positivo)
- ✓ Tiene Landsat 8/9 ya integrado
- ✓ Genera PNGs hotspot (mono-color rojo)

### TOA (replica NHI Tool, Element84)
- ✅ Algoritmo replica linea por linea
- ✅ Buffer respeta `config_nhi.py` (Cordon Caulle 10km, Hudson 8km, Lascar 3km, Villarrica 1.5km)
- ✅ PNGs color-coded por criterio (A=rojo, B=naranja, EXTREME=amarillo)
- ❌ Sin Landsat aun (falta aprobacion USGS)
- 🔄 Backfill 1 año en curso

## En curso al cierre de sesion

**4 GitHub Actions workflows paralelos (uno por zona) corriendo backfill 365 dias:**

| Run ID | Zona | Volcanes | Duracion al cierre |
|---|---|---|---|
| [24938897151](https://github.com/MendozaVolcanic/NHI-v1/actions/runs/24938897151) | Norte | 8 | 1h 42m |
| [24938898573](https://github.com/MendozaVolcanic/NHI-v1/actions/runs/24938898573) | Centro | 9 | 1h 42m |
| [24938899994](https://github.com/MendozaVolcanic/NHI-v1/actions/runs/24938899994) | Sur | 13 | 1h 42m |
| [24938901275](https://github.com/MendozaVolcanic/NHI-v1/actions/runs/24938901275) | Austral | 13 | 1h 42m |

Cada uno hace auto-commit a `docs/nhi_data_toa/` cuando termina. Estimado total: ~3h.

## Pendiente

### Bloqueado esperando USGS (1-3 dias)
**Aprobacion de acceso descarga Landsat L1 TOA via M2M API.**

- Cuenta USGS ERS creada: username `nicolas.mendoza`
- Application Token generado: `Nhd_fUXftzphJQddHj2Y4FcIHeBx5rWH7qw43BVsn67FbKvcRYh@2jpPzf2q1ZJK` (vence 31-10-2029)
- Token funciona para login + scene-search; bloqueado en download-options (HTTP 403)
- Solicitud de Bulk Download Access enviada (necesita aprobacion humana)
- **Cuando llegue email de aprobacion:** integrar Landsat al analyzer TOA, regenerar backfill, charts separados S2 vs OLI

### Validacion de FPs/FNs sospechosos en TOA

Si conseguis CSVs del NHI Tool GEE para estos volcanes y los pegas en `docs/nhi_data_toa/{volcan}/nhi_tool_gee_reference.csv`, la pestana BETA muestra automaticamente la comparacion:

- **Carran-Los Venados: 1.96M m2** (sospechoso FP grande, capaz cuerpo de agua/glaciar)
- **Mocho-Choshuenco: 558k m2** (sospechoso FP)
- **Villarrica: 0 alertas 30d** (lago de lava activo, posible FN del algoritmo)

### Mejoras dashboard (no bloqueadas)
- [ ] Selector de imagen individual (PNGs por escena) — esperar a que termine backfill 1 año
- [ ] Charts separados por sensor (S2 vs OLI) — esperar Landsat
- [ ] Suma SWIR/SWNIR radiance en JSON (campo extra) — agregar al analyzer + recompute
- [ ] Considerar Buffer presets multi-tamaño (3km / 5km / 8km pre-computados)

### Mantenimiento
- [ ] Despues de validar TOA con Landsat por 1-2 semanas: deprecar L2A, borrar `docs/nhi_data/`
- [ ] El cron diario incremental (`--dias 14`) mantiene los datos frescos automatico

## Lo que SI podemos hacer (serverless con datos pre-computados)

- ✅ Replicar el algoritmo NHI Tool exacto en backend Python
- ✅ Multi-volcan, multi-anios pre-computado
- ✅ Date range filter in-memory en frontend
- ✅ Mapa con buffer real dibujado
- ✅ Charts L2A vs TOA comparativos
- ✅ Buffer multi-tamano si pre-computamos varios
- ✅ Exportar CSVs / JSONs para validacion externa
- ✅ Imagen overlay sobre mapa (PNG posicionado en bbox del volcan)
- ✅ Almacenar 10-20 anios de history (JSONs son tiny ~40KB/volcan/año)

## Lo que NO podemos hacer (requiere backend en vivo, descartado)

- ❌ Volcanes fuera de los 43 chilenos (NHI Tool tiene 1400 globales — usa lista del Smithsonian)
- ❌ Buffer arbitrario en cualquier numero de metros (cada buffer = recompute)
- ❌ Cambiar algoritmo / umbrales en vivo desde el dashboard
- ❌ Datos de hoy mismo (cron daily ya da T+0; live solo necesario para sub-dia)
- ❌ "Compute on demand" estilo NHI Tool — somos serverless

**Razon tecnica:** GitHub Pages es solo HTML+JSON estatico. NHI Tool corre live compute en infraestructura Google (GEE) — cada click del usuario dispara una query que computa indices sobre el catalogo entero. Para igualar eso necesitariamos o GEE (vendor lock-in) o un backend con compute (costos + setup), ambos descartados.

## Decisiones tomadas en esta sesion

1. **TOA default** — pipeline mas confiable (matchea GEE 1:1 para S2)
2. **L2A se mantiene** como toggle hasta que TOA tenga Landsat
3. **GitHub Actions con chunking por zona** para evitar limite de 6h por job
4. **Buffer respeta `config_nhi.py`** (geologo lo dimensiono) — solo override Lascar a 3km
5. **Free tier:** USGS M2M en vez de AWS requester-pays (sin costos)
6. **PNGs color-coded** por criterio A/B/EXTREME para distinguir actividad real de ruido
7. **No GEE** — mantener independencia tecnologica (filosofia del proyecto)

## Comandos utiles para retomar

```bash
# Ver progreso de backfill
gh run list --workflow=nhi_analysis_toa.yml --limit 5

# Disparar backfill manual de una zona
gh workflow run nhi_analysis_toa.yml -f dias=365 -f zona=Sur

# Disparar backfill de un volcan especifico
gh workflow run nhi_analysis_toa.yml -f dias=365 -f volcan=Lascar

# Generar resumen TOA local (despues de pull)
python -c "from nhi_analyzer_toa import generar_resumen_toa; from config_nhi import get_active_volcanoes; generar_resumen_toa(get_active_volcanoes())"

# Validar contra CSV GEE (si tenes ee-chart.csv para un volcan)
cp ~/Downloads/ee-chart.csv docs/nhi_data_toa/{Volcan}/nhi_tool_gee_reference.csv
git add docs/nhi_data_toa/{Volcan}/nhi_tool_gee_reference.csv
git commit -m "ref: agregar CSV GEE para {Volcan}"
git push
# Dashboard pestana BETA muestra comparacion automatica
```

## Tokens / credenciales

⚠️ **El token USGS esta en este documento por conveniencia de retomar la sesion.**
Cuando llegue la aprobacion de descarga, considerá rotarlo (revocar este, crear nuevo)
y guardarlo solo como GitHub Actions Secret `USGS_TOKEN` (con `USGS_USERNAME`).

- USGS ERS Username: `nicolas.mendoza`
- USGS M2M Token (vence 2029-10-31): `Nhd_fUXftzphJQddHj2Y4FcIHeBx5rWH7qw43BVsn67FbKvcRYh@2jpPzf2q1ZJK`

---

**Sesion cerrada con:** 75+ mensajes. Recomendacion fue iniciar nueva sesion para mantener contexto limpio.
