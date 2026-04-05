# NHI-v1 - Monitoreo de Anomalias Termales Volcanicas

Dashboard automatizado para deteccion de anomalias termales en **43 volcanes activos de Chile**, usando indices NHI (Normalized Hotspot Indices) sobre imagenes satelitales Sentinel-2 y Landsat 8/9.

**Dashboard:** https://mendozavolcanic.github.io/NHI-v1/

## Que hace este proyecto

1. Descarga bandas NIR/SWIR de Sentinel-2 L2A y Landsat C2 L2 via [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/)
2. Calcula los indices NHISWIR y NHISWNIR para cada escena
3. Aplica filtrado estadistico para separar anomalias reales de ruido (nieve, suelo, nubes)
4. Genera un dashboard web con tabla semaforo y graficos temporales por volcan

## Algoritmo NHI

Basado en Marchese et al. 2019, adaptado para reflectancia L2A (el original usa radiancia TOA):

```
NHISWIR  = (SWIR2 - SWIR1) / (SWIR2 + SWIR1)
NHISWNIR = (SWIR1 - NIR)   / (SWIR1 + NIR)
```

### Bandas

| Sensor      | NIR (~0.86um) | SWIR1 (~1.61um) | SWIR2 (~2.19um) | Resolucion |
|-------------|---------------|-----------------|-----------------|------------|
| Sentinel-2  | B8A           | B11             | B12             | 20m        |
| Landsat 8/9 | B5            | B6              | B7              | 30m        |

### Deteccion de pixeles calientes

Un pixel se marca como anomalia termal cuando cumple **todas** las condiciones:

1. Reflectancia SWIR1 y SWIR2 > 0.05 (filtro de pixeles validos)
2. NHISWIR > mediana + max(0.02, 3*sigma) — supera fondo estadistico
3. NHISWIR > 0 — criterio base del paper
4. NHISWNIR > 0 — confirma anomalia en segundo indice (AND)
5. Fraccion de pixeles calientes < 0.5% del total (anti-ruido solar/nieve)

El filtro estadistico se aplica solo a NHISWIR (detector primario) porque el fondo de NHISWNIR es variable en terrenos con vegetacion/roca donde SWIR1 > NIR naturalmente.

El filtrado estadistico (pasos 2-3) esta inspirado en la metodologia VRP Chile (triple-threshold sobre background annulus).

### Clasificacion semaforo

| Nivel     | Criterio                            |
|-----------|-------------------------------------|
| Rojo      | Anomalias detectadas en ultimos 7 dias  |
| Amarillo  | Anomalias detectadas en ultimos 30 dias |
| Verde     | Sin anomalias en 30 dias            |

## Estructura del proyecto

```
NHI-Tool/
  nhi_analyzer.py        # Analizador principal (busqueda STAC + calculo NHI)
  config_nhi.py           # Configuracion: 43 volcanes, bandas, umbrales
  requirements.txt        # Dependencias Python
  docs/
    index.html            # Dashboard web (Chart.js)
    nhi_data/
      resumen_global.json # Tabla semaforo de todos los volcanes
      {Volcan}/
        nhi_timeseries.json  # Serie temporal de cada volcan
  .github/workflows/
    nhi_analysis.yml      # Cron diario (12:00 UTC) + workflow_dispatch
    deploy.yml            # Deploy a GitHub Pages
```

## Uso local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Analizar todos los volcanes (ultimos 60 dias)
python nhi_analyzer.py

# Analizar un volcan especifico
python nhi_analyzer.py --volcan Villarrica --dias 30

# Test rapido (3 volcanes)
python nhi_analyzer.py --test
```

## Automatizacion

El workflow `nhi_analysis.yml` corre diariamente a las 12:00 UTC y analiza los 43 volcanes.
Despues, `deploy.yml` publica los resultados en GitHub Pages automaticamente.

Para ejecutar manualmente: Actions > NHI Analysis > Run workflow.

## Volcanes monitoreados (43)

| Zona    | Volcanes |
|---------|----------|
| Norte   | Taapaca, Parinacota, Guallatiri, Isluga, Irruputuncu, Ollague, San Pedro, Lascar |
| Centro  | Tupungatito, San Jose, Tinguiririca, Planchon-Peteroa, Descabezado Grande, Tatara-San Pedro, Laguna del Maule, Nevado de Longavi, Nevados de Chillan |
| Sur     | Antuco, Copahue, Callaqui, Lonquimay, Llaima, Sollipulli, Villarrica, Quetrupillan, Lanin, Mocho-Choshuenco, Carran - Los Venados, Puyehue - Cordon Caulle, Antillanca - Casablanca |
| Austral | Osorno, Calbuco, Yate, Hornopiren, Huequi, Michinmahuida, Chaiten, Corcovado, Melimoyu, Mentolat, Cay, Maca, Hudson |

## Diferencias con el NHI Tool original

| Aspecto | NHI Tool (Genzano) | Esta implementacion |
|---------|--------------------|--------------------|
| Plataforma | Google Earth Engine | Python + Planetary Computer |
| Datos | Radiancia TOA (L1C) | Reflectancia superficie (L2A) |
| Criterio | NHISWIR > 0 OR NHISWNIR > 0 | NHISWIR(stats) AND NHISWNIR > 0 + fraccion max |
| Cobertura | >1400 volcanes global | 43 volcanes Chile |
| Salida | Mapa interactivo GEE | Dashboard estatico GitHub Pages |
| Automatizacion | GEE + notificaciones | GitHub Actions (cron diario) |

## Fuentes de datos

- **Sentinel-2 L2A:** via [Planetary Computer STAC](https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a)
- **Landsat C2 L2:** via [Planetary Computer STAC](https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2)

## Referencias

### Papers fundamentales

1. **Marchese et al. 2019** - Algoritmo NHI original
   *Remote Sensing*, 11(23), 2876 — [Open Access](https://www.mdpi.com/2072-4292/11/23/2876)

2. **Genzano et al. 2020** - NHI Tool en Google Earth Engine
   *Remote Sensing*, 12(19), 3232 — [Open Access](https://www.mdpi.com/2072-4292/12/19/3232)

3. **Marchese et al. 2021** - NHI sobre ASTER
   *Sensors*, 21(4), 1538 — [Open Access](https://pmc.ncbi.nlm.nih.gov/articles/PMC7926431/)

4. **Marchese et al. 2023** - NHI global operacional
   *J. Geological Society*, 180(1) — DOI: 10.1144/jgs2022-014 (acceso pagado)

### Papers complementarios

5. Massimetti et al. 2020 — Sentinel-2 hot-spot vs MIROVA ([link](https://www.mdpi.com/2072-4292/12/5/820))
6. Coppola et al. 2020 — Sistema MIROVA ([link](https://www.frontiersin.org/articles/10.3389/feart.2019.00362/full))
7. Valade et al. 2019 — MOUNTS multi-sensor ([link](https://www.mdpi.com/2072-4292/11/13/1528))
8. Galindo et al. 2020 — VOLCANOMS, probado en Villarrica y Lascar ([link](https://www.mdpi.com/2072-4292/12/10/1589))

### NHI Tool original

- App: https://nicogenzano.users.earthengine.app/view/nhi-tool
- Sitio: https://sites.google.com/view/nhi-tool

## Proyectos relacionados

- [Copernicus-v1](https://github.com/MendozaVolcanic/Copernicus-v1) — Dashboard Sentinel-2 RGB/SWIR/Thermal
- [Landsat-v1](https://github.com/MendozaVolcanic/Landsat-v1) — Dashboard Landsat 8/9 RGB/SWIR/Thermal
