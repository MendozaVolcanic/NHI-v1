# NHI Tool - Normalized Hotspot Indices para Monitoreo Volcanico

## Que es NHI

Sistema automatizado de deteccion de anomalias termales volcanicas desarrollado por
Marchese, Genzano et al. (CNR Italia / Politecnico di Milano). Corre sobre Google Earth Engine
y analiza datos Sentinel-2 MSI y Landsat 8/9 OLI para detectar pixeles calientes en condiciones
diurnas.

**App interactiva:** https://nicogenzano.users.earthengine.app/view/nhi-tool
**Sitio oficial:** https://sites.google.com/view/nhi-tool

## Algoritmo

NHI usa dos indices normalizados que analizan radiancia Top-of-Atmosphere (TOA) en bandas
SWIR y NIR para identificar pixeles con anomalias termales:

### Formulas

```
NHISWIR  = (L_SWIR2 - L_SWIR1) / (L_SWIR2 + L_SWIR1)
NHISWNIR = (L_SWIR1 - L_NIR)   / (L_SWIR1 + L_NIR)
```

Donde L = radiancia TOA en W m-2 sr-1 um-1

### Bandas utilizadas

| Sensor      | NIR (~0.8um) | SWIR1 (~1.6um) | SWIR2 (~2.2um) |
|-------------|-------------|----------------|----------------|
| Sentinel-2  | B8A         | B11            | B12            |
| Landsat 8/9 | B5          | B6             | B7             |
| ASTER       | B3N         | B4             | B5             |

### Criterio de deteccion

Un pixel se marca como "caliente" cuando:

```
NHISWIR > 0  OR  NHISWNIR > 0
```

Condiciones previas de filtro:
- Diurno: L_SWIR1 > 3.0 AND L_SWIR2 > 3.0
- Nocturno: L_SWIR1 > 5.0 OR NHISWNIR > 0

### Base fisica

A temperaturas normales (~300K), la radiancia emitida es dominante en TIR (8-12um).
Cuando hay actividad volcanica (>500K), la emision se desplaza hacia SWIR (1.6-2.2um),
haciendola detectable incluso de dia sobre la radiancia solar reflejada. Los indices
normalizados minimizan el efecto de la reflectancia solar.

## Salidas del sistema

- Conteo de pixeles calientes por fecha
- Radiancia total SWIR (W m-2 sr-1 um-1)
- Area total del hotspot (m2)
- Series temporales de todos los parametros

## Capacidades

- Monitorea >1400 volcanes activos globalmente
- Procesamiento en tiempo casi-real via GEE
- Datos desde 2013 (Landsat 8) y 2015 (Sentinel-2)
- Notificaciones automaticas cada 48 horas
- ~15% tasa de falsos positivos (incluye incendios forestales)

## Contactos del equipo NHI

- francesco.marchese@cnr.it
- nicola.genzano@polimi.it
- carolina.filizzola@cnr.it
- giuseppe-mazzeo@cnr.it

## Licencia de uso

Productos NHI son para "uso experimental/no-comercial" sin garantias de precision
o disponibilidad.

---

## Papers fundamentales del NHI

### Open Access (descargables)

1. **Marchese et al. 2019** - Paper original del algoritmo NHI
   "A Multi-Channel Algorithm for Mapping Volcanic Thermal Anomalies by Means of Sentinel-2 MSI and Landsat-8 OLI Data"
   *Remote Sensing*, 11(23), 2876
   https://www.mdpi.com/2072-4292/11/23/2876

2. **Genzano et al. 2020** - NHI Tool en Google Earth Engine
   "A Google Earth Engine Tool to Investigate, Map and Monitor Volcanic Thermal Anomalies at Global Scale"
   *Remote Sensing*, 12(19), 3232
   https://www.mdpi.com/2072-4292/12/19/3232

3. **Marchese et al. 2021** - NHI aplicado a ASTER
   "Implementation of the NHI Algorithm on Infrared ASTER Data: Results and Future Perspectives"
   *Sensors*, 21(4), 1538
   https://pmc.ncbi.nlm.nih.gov/articles/PMC7926431/

### Requiere acceso (buscar manualmente)

4. **Marchese et al. 2023** - Sistema NHI global operacional
   "Global volcano monitoring through the Normalized Hotspot Indices (NHI) system"
   *Journal of the Geological Society*, 180(1), jgs2022-014
   DOI: 10.1144/jgs2022-014
   > PAYWALLED - Geological Society of London

---

## Papers complementarios relevantes

### Deteccion termal (Open Access)

5. **Massimetti et al. 2020** - Sentinel-2 hot-spot vs MIROVA
   https://www.mdpi.com/2072-4292/12/5/820

6. **Coppola et al. 2020** - Sistema MIROVA (MODIS)
   https://www.frontiersin.org/articles/10.3389/feart.2019.00362/full

7. **Valade et al. 2019** - MOUNTS (multi-sensor + IA)
   https://www.mdpi.com/2072-4292/11/13/1528

8. **Galindo et al. 2020** - VOLCANOMS (Landsat, probado en Villarrica y Lascar)
   https://www.mdpi.com/2072-4292/12/10/1589

### Contexto latinoamericano (Open Access)

9. **Pritchard et al. 2018** - InSAR volcanes latinoamericanos (incluye SERNAGEOMIN)
   https://doi.org/10.1186/s13617-018-0074-0

10. **Reath et al. 2019** - Series temporales 47 volcanes latinoamericanos
    https://agupubs.onlinelibrary.wiley.com/doi/pdfdirect/10.1029/2018JB016199

### Preprocesamiento (Open Access)

11. **Skakun et al. 2022** - Comparacion algoritmos cloud masking (CMIX)
    https://www.sciencedirect.com/science/article/pii/S0034425722001043

12. **Parker et al. 2015** - Incertidumbre atmosferica en InSAR
    https://www.sciencedirect.com/science/article/pii/S0034425715301267

### Requiere acceso

13. **Zhu & Woodcock 2019** - Fmask 4.0 (cloud/snow detection)
    DOI: 10.1016/j.rse.2019.05.024
    > PAYWALLED - Elsevier
