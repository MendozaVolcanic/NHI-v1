# Plan: Implementacion NHI para volcanes chilenos

## Decision: Dashboard separado o integrado?

**Recomendacion: Dashboard SEPARADO (NHI-v1) con link cruzado desde Copernicus-v1**

Razones:
- NHI no genera imagenes visuales (RGB/SWIR composites) — genera DATOS numericos
  (conteo pixeles, radiancia total, area hotspot)
- La visualizacion ideal es series temporales (graficos), no mosaicos de imagenes
- El dashboard actual (Copernicus-v1) esta optimizado para comparacion visual de composites
- NHI necesita su propio pipeline de datos (calculos de indices, no descarga de imagenes)
- Separar permite que cada dashboard cargue rapido sin bloquear al otro

**Integracion sugerida:**
- Boton en Copernicus-v1 que abre NHI-v1 para el volcan seleccionado
- NHI-v1 muestra graficos temporales + mapa de pixeles calientes
- Ambos repos publicos bajo MendozaVolcanic

## Arquitectura propuesta

```
NHI-v1/
├── .github/workflows/
│   └── nhi_analysis.yml          # Cron diario: calcula indices NHI
├── nhi_analyzer.py               # Script principal
│   ├── Descarga bandas B8A/B11/B12 (Sentinel-2)
│   ├── Descarga bandas B5/B6/B7 (Landsat 8/9)
│   ├── Calcula NHISWIR y NHISWNIR por volcan
│   ├── Cuenta pixeles calientes (umbral > 0)
│   ├── Calcula radiancia total y area hotspot
│   └── Guarda resultados en JSON
├── config_volcanes.py            # 43 volcanes (reusar de Copernicus-v1)
├── docs/
│   ├── index.html                # Dashboard con graficos
│   ├── nhi_data/
│   │   ├── {Volcan}/
│   │   │   ├── nhi_timeseries.json    # Serie temporal de detecciones
│   │   │   └── {fecha}_hotspots.png   # Mapa de pixeles calientes (opcional)
│   │   └── resumen_global.json        # Estado de todos los volcanes
│   └── fechas_nhi.json
└── requirements.txt
```

## Datos a generar por volcan y fecha

```json
{
  "volcan": "Villarrica",
  "fecha": "2026-04-03",
  "satelite": "Sentinel-2A",
  "nhi_swir": {
    "max": 0.15,
    "pixeles_positivos": 3,
    "pixeles_total": 2500
  },
  "nhi_swnir": {
    "max": 0.08,
    "pixeles_positivos": 2,
    "pixeles_total": 2500
  },
  "radiancia_total_swir2": 45.3,
  "area_hotspot_m2": 1200,
  "alerta": true
}
```

## Dashboard NHI (index.html)

Secciones:
1. **Resumen global** — tabla de 43 volcanes con semaforo (verde/amarillo/rojo)
   basado en detecciones NHI de los ultimos 7 dias
2. **Vista individual** — selector volcan → grafico temporal de:
   - Pixeles calientes (barras)
   - Radiancia total SWIR (linea)
   - Area hotspot (linea)
3. **Mapa de calor** — imagen del volcan con pixeles NHI positivos superpuestos
4. **Comparacion con MIROVA** — link externo a mirovaweb.it para el volcan

## Fuente de datos

Opciones para obtener bandas SWIR/NIR sin Google Earth Engine:

1. **Microsoft Planetary Computer** (ya usado en Landsat-v1)
   - Sentinel-2 L2A: bandas B8A, B11, B12 disponibles
   - Landsat: bandas B5, B6, B7 disponibles
   - Sin costo, sin autenticacion

2. **Copernicus Data Space** (ya tenemos credenciales SentinelHub)
   - Acceso directo a bandas individuales Sentinel-2

**Recomendacion: Planetary Computer** — ya tenemos el patron de descarga de Landsat-v1,
solo hay que adaptarlo para extraer bandas individuales en vez de composites RGB.

## Fases de implementacion

### Fase 1: Pipeline basico
- [ ] Crear repo NHI-v1
- [ ] Adaptar landsat_downloader.py para calcular indices NHI
- [ ] Generar JSON de series temporales por volcan
- [ ] Workflow GitHub Actions diario

### Fase 2: Dashboard
- [ ] index.html con graficos (Chart.js o similar)
- [ ] Tabla resumen con semaforo
- [ ] Vista individual con selector
- [ ] Deploy en GitHub Pages

### Fase 3: Integracion
- [ ] Boton en Copernicus-v1 que abre NHI-v1
- [ ] Alertas automaticas (destacar volcanes con detecciones recientes)
