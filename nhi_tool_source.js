var volcanoes = ui.import && ui.import("volcanoes", "table", {
      "id": "users/nicogenzano/vulcani/volcanoV23082024"
    }) || ee.FeatureCollection("users/nicogenzano/vulcani/volcanoV23082024");
// var batch = require('users/fitoprincipe/geetools:batch');

var mainMap = ui.Map();
//widget titolo
var title = ui.Label('NHI Tool for volcanoes (v1.5)', {fontSize: '24px', fontWeight: 'bold'});
var subtitleNews = ui.Label('');//'Warning !!! Previous Sentinel-2 collection has been replaced with harmonized Sentinel-2. This may affect results of 2022.', {fontSize: '14px', Color: 'Red', fontWeight: 'bold'});
var subTitle = ui.Label('This tool enables the investigation of volcanic thermal anomalies from Landsat 8/9 and Sentinel 2 collections using the NHI (Normalized Hotspot Indices) algorithm (Marchese et al, 2019)');
var URLreadme = 'https://drive.google.com/file/d/1kt8MnblxwGuiWdtt4dLT88b6HjqHPqXj/view?usp=sharing';
var readme = ui.Label ('How to use the tool', {fontSize: '12px', fontWeight: 'bold'} , URLreadme);
// widget vulcani  
var styleVolcanoLabel = { fontWeight: 'bold', margin: '8px 8px 0px 8px'};
var volcanoLabel = ui.Label('1) Select volcano', styleVolcanoLabel);
var URLsmithsonian = 'https://nicogenzano.users.earthengine.app/view/nhi-real-time'; //https://volcano.si.edu/';
var subtitleVolcanoLabel = ui.Label ('(More than 1400 Holocene volcanoes listed by the Global Volcanism Program; Click here for the list of recent activities)', {}, URLsmithsonian);
var VOTW_HoloceneSorted =volcanoes.sort('Volcano Na');
var volcano = VOTW_HoloceneSorted.aggregate_array('Volcano Na');
//volcanoSelect.setPlaceholder('Choose a volcano...');
var volcanoSelect = ui.Select({items: volcano.getInfo(), onChange: showVolcano});
volcanoSelect.setPlaceholder('Choose a volcano...');
  function showVolcano(key){
    var selectedVolcano = ee.Feature(volcanoes.filterMetadata('Volcano Na', 'equals', volcanoSelect.getValue()).first());
    mainMap.clear();
    // mainMap.add(logo);
    mainMap.setOptions('TERRAIN');
    mainMap.centerObject(selectedVolcano, 11);
  }
// widget tempo
var periodLabel = ui.Label('2) Select period', {fontWeight: 'bold'});
var titleStartDate = ui.Label(' Start date (YYYY-MM-DD) since April 1, 2013');
var startDate = ui.Textbox('YYYY-MM-DD', '2025-01-01');
var titleEndDate = ui.Label(' End date (YYYY-MM-DD)');
var now = Date.now();
var nowDate = ee.Date(now).format('y-MM-dd');
var endDate = ui.Textbox('YYYY-MM-DD', nowDate.getInfo()); //.advance(1, 'day')
//widget buffer
var styleDistanceLabel = { fontWeight: 'bold', margin: '8px 8px 0px 8px'};
var distanceLabel = ui.Label('3) Define distance buffer', styleDistanceLabel);
var subtitleDistanceLabel = ui.Label ('(After writing the distance press ENTER for a preview of the investigated area. We suggest max 50.000 m for OLI and 30.000 m for MSI; max 100.000 m only for hot-spot pixel plot)');
var distanceMeters = ui.Textbox({placeholder: 'Distance in meters', onChange: showBuffer });
  function showBuffer(key){
    var selectedVolcano = ee.Feature(volcanoes.filterMetadata('Volcano Na', 'equals', volcanoSelect.getValue()).first());
    var area = selectedVolcano.buffer(parseFloat(distanceMeters.getValue()));
    var empty = ee.Image().byte();
    mainMap.clear();
    // mainMap.add(logo);
    mainMap.setOptions('TERRAIN');
    var outlineBufferVolcano = empty.paint({
      featureCollection:area,
      color: 1,
      width: 3});
    mainMap.addLayer(outlineBufferVolcano,{palette: 'red'}, 'Investigated area aroud ' + volcanoSelect.getValue());  
  }
// testo fondo pagina
var style = {fontSize: '12px', margin: '2px 8px 2px 8px'};
var URL = 'https://doi.org/10.3390/rs11232876';
var URL2 = 'https://doi.org/10.3390/rs12193232';
// var URL3 = 'https://doi.org/10.3390/s21041538';
var URL3 = 'https://sites.google.com/view/nhi-tool/references';
var text1 = ui.Label ('Use of the data',{fontSize: '12px', fontWeight: 'bold'});
var text2 = ui.Label ('The NHI tool provides hotspot products generated from freely available Sentinel-2 and Landsat-8/9 data as part of GEE data-set.', style);
var text3 = ui.Label ('As the products are developed within the Google Earth Engine platform, they follow its policy and terms of service', style);
var text4 = ui.Label ('Hotspot products from the tool may be used for research purposes by citing the paper Genzano et al., 2020. For any inquiries, please contact Nicola Genzano (nicola.genzano at polimi.it) or Francesco Marchese (francesco.marchese at imaa.cnr.it).', style);
var text5 = ui.Label ('References',{fontSize: '12px', fontWeight: 'bold'});
var text6 = ui.Label ('Genzano, N.; Pergola, N.; Marchese, F. “A Google Earth Engine Tool to Investigate, Map and Monitor Volcanic Thermal Anomalies at Global Scale by Means of Mid-high Spatial Resolution Satellite Data”. Remote Sens. 2020, 12(19), 3232.', style , URL2);
var text7 = ui.Label ('Marchese, F.; Genzano, N.; Neri, M.; Falconieri, A.; Mazzeo, G.; Pergola, N. “A Multi-Channel Algorithm for Mapping Volcanic Thermal Anomalies by Means of Sentinel-2 MSI and Landsat-8 OLI Data”. Remote Sens. 2019, 11(23), 2876.', style , URL);
// var text8 = ui.Label ('Mazzeo, G.; Ramsey, M.S.; Marchese, F.; Genzano, N.; Pergola, N. "Implementation of the NHI (Normalized Hot Spot Indices) Algorithm on Infrared ASTER Data: Results and Future Perspectives." Sensors 2021, 21, 1538.', style , URL3);
var text8 = ui.Label ('Other references.', style , URL3);

// widget pulsante Start
var button = ui.Button({
  label: 'Start NHI analysis',
  style: {color: 'red'},
  onClick: function() {
mainMap.clear();
mainMap.setOptions('TERRAIN');
// mainMap.add(logo);
// link feedback    
var URLfeedback = 'https://forms.gle/C5THv9KJzjLWx7M37';
var feedback =  ui.Label ('Please, give us a feedback', {fontSize: '14px', fontWeight: 'bold'} , URLfeedback);
panel.widgets().set(16, feedback);     
// area investigata
var selectedVolcano = ee.Feature(volcanoes.filterMetadata('Volcano Na', 'equals', volcanoSelect.getValue()).first());
var area = selectedVolcano.buffer(parseFloat(distanceMeters.getValue()));
var empty = ee.Image().byte();
mainMap.layers().reset();
var outlineBufferVolcano = empty.paint({
  featureCollection:area,
  color: 1,
  width: 3});

// parametri spazio tempo
var start = startDate.getValue();
var end = endDate.getValue();
var lat = selectedVolcano.get('Latitude');
var lon = selectedVolcano.get('Longitude');

// Collezione Landsat 8
var L8rt = ee.ImageCollection('LANDSAT/LC08/C02/T1_RT')
  .filterBounds(ee.Geometry.Point(ee.Number.expression(lon),ee.Number.expression(lat)))
  .filterDate(ee.Date(start),ee.Date(end).advance(1, 'day'))
  .filterMetadata('SUN_ELEVATION','greater_than', 0)
  .select(['B1','B5','B6','B7','QA_PIXEL']);
// var L8t1 = ee.ImageCollection('LANDSAT/LC08/C01/T1')
//   .filterBounds(ee.Geometry.Point(ee.Number.expression(lon),ee.Number.expression(lat)))
//   .filterDate(ee.Date(start),ee.Date(end).advance(1, 'day'))
//   .filterMetadata('SUN_ELEVATION','greater_than', 0)
//   .select(['B1','B5','B6','B7','BQA']);
var L8t2 = ee.ImageCollection('LANDSAT/LC08/C02/T2')
  .filterBounds(ee.Geometry.Point(ee.Number.expression(lon),ee.Number.expression(lat)))
  .filterDate(ee.Date(start),ee.Date(end).advance(1, 'day'))
  .filterMetadata('SUN_ELEVATION','greater_than', 0)
  .select(['B1','B5','B6','B7','QA_PIXEL']);
  
var L9 = ee.ImageCollection('LANDSAT/LC09/C02/T1')
  .filterBounds(ee.Geometry.Point(ee.Number.expression(lon),ee.Number.expression(lat)))
  .filterDate(ee.Date(start),ee.Date(end).advance(1, 'day'))
  .filterMetadata('SUN_ELEVATION','greater_than', 0)
  .select(['B1','B5','B6','B7','QA_PIXEL']);
  
var L8 = L8rt.merge(L8t2).merge(L9);


// Collezione Sentinel 
var S2 = ee.ImageCollection("COPERNICUS/S2_HARMONIZED") 
  .filterBounds(ee.Geometry.Point(ee.Number.expression(lon),ee.Number.expression(lat)))
  .filterDate(ee.Date(start),ee.Date(end).advance(1, 'day'))
//  .filterMetadata('quality_check','equals', 'PASSED')
//  .filterMetadata('SENSOR_QUALITY','equals', 'PASSED')
  .select(['B5','B8A','B11','B12','QA60']);
  
// conversione in radianza scene LANDSAT
var RADIANCE = function(image) {
    var bands = ['B1_1','B5_1', 'B6_1', 'B7_1', 'QA_PIXEL'];
    var new_bands = ['b400nm', 'b800nm', 'b1600nm', 'b2200nm', 'BQA'];
  return image.addBands(ee.Algorithms.Landsat.calibratedRadiance(image).rename(new_bands));
  };
// funzione NHI_SWIR
var NHI_SWIR = function(image) {
  return image.addBands(image.normalizedDifference(['b2200nm', 'b1600nm']).rename('NHI_SWIR'));
  };
// funzione NHI_SWNIR
var NHI_SWNIR = function(image) {
  return image.addBands(image.normalizedDifference(['b1600nm', 'b800nm']).rename('NHI_SWNIR'));
  };
// funzione NHI_SWIR l8
var NHI_SWIR_L8 = function(image) {
  return image.addBands((image.select('b2200nm').gt(2)).and(image.select('NHI_SWNIR_L8').eq(0)).and(image.select('NHI_SWIR').gt(0)).rename('NHI_SWIR_L8'));
  };
// funzione NHI_SWNIR l8
var NHI_SWNIR_L8 = function(image) {
  return image.addBands((image.select('b2200nm').gt(2)).and(image.select('NHI_SWNIR').gt(0)).rename('NHI_SWNIR_L8'));
  };   
// funzione EXTREME_PIXEL
var EXTREME_PIXEL = function(image) {
  return image.addBands(image.select('NHI_SWIR_L8').eq(0)
                          .and(image.select('NHI_SWNIR_L8').eq(0))
                          .and(image.select('b1600nm').gte(74))
                          .and(image.select('b400nm').lt(70))
                          .rename('EXTREME_PIXEL'));
  };  
// funzione NHI LANDSAT 8
var NHI_ALL = function(image) {
  return image.addBands(image.select('NHI_SWIR_L8').eq(1)
                          .or(image.select('NHI_SWNIR_L8').eq(1))
                          .or(image.select('EXTREME_PIXEL').eq(1)
                          ).rename('NHI'));
  };

// funzione conversione radianza Sentinel 2
var radiance = function (image) {
  var pi = ee.Number(3.14159265359);
  var SUN_ZEN_ANG_RAD = (ee.Number(image.get('MEAN_SOLAR_ZENITH_ANGLE'))).multiply(pi.divide(180));
  var SUN_EART_DIST = (pi.multiply(10000)).divide(ee.Number(image.get('REFLECTANCE_CONVERSION_CORRECTION')));
  var SOL_IRR_B5 = ee.Number(image.get('SOLAR_IRRADIANCE_B5'));
  var SOL_IRR_B8A = ee.Number(image.get('SOLAR_IRRADIANCE_B8A'));
  var SOL_IRR_B11 = ee.Number(image.get('SOLAR_IRRADIANCE_B11'));
  var SOL_IRR_B12 = ee.Number(image.get('SOLAR_IRRADIANCE_B12'));  
  return image.addBands(((((image.select(['B5'])).multiply(SOL_IRR_B5)).multiply(SUN_ZEN_ANG_RAD.cos())).divide(SUN_EART_DIST)).rename('b703nm')).toFloat()
              .addBands(((((image.select(['B8A'])).multiply(SOL_IRR_B8A)).multiply(SUN_ZEN_ANG_RAD.cos())).divide(SUN_EART_DIST)).rename('b800nm')).toFloat()
              .addBands(((((image.select(['B11'])).multiply(SOL_IRR_B11)).multiply(SUN_ZEN_ANG_RAD.cos())).divide(SUN_EART_DIST)).rename('b1600nm')).toFloat()
              .addBands(((((image.select(['B12'])).multiply(SOL_IRR_B12)).multiply(SUN_ZEN_ANG_RAD.cos())).divide(SUN_EART_DIST)).rename('b2200nm')).toFloat();  
  };
// funzione per Sentinel Miss registration
var TEST_MISS_REG = function(image) {
  return image.addBands(image.normalizedDifference(['b2200nm', 'b800nm']).rename('TEST_miss_reg'));
  };
// funzione NHI_SWIR s2
var NHI_SWIR_S2 = function(image) {
  return image.addBands(image.select('NHI_SWIR').gt(0)
              .and(image.select('NHI_SWNIR_S2').eq(0))
							.and(image.select('b2200nm').gt(2))
							.and(image.select('b703nm').lt(90))
                .and(image.select('TEST_miss_reg').gt(-0.6))
            .rename('NHI_SWIR_S2'));
  };
// funzione NHI_SWNIR s2
var NHI_SWNIR_S2 = function(image) {
  return image.addBands(image.select('NHI_SWNIR').gt(0)
              .and(image.select('b800nm').gt(10))
							.and(image.select('b2200nm').gt(2))
							.and(image.select('b703nm').lt(70))
                  .and(image.select('TEST_miss_reg').gt(-0.3))
            .rename('NHI_SWNIR_S2'));
  };
// funzione EXTREME PIXEL s2
var EXTREME_PIXEL_S2 = function(image) {
  return image.addBands(image.select('NHI_SWIR_S2').eq(0)
                          .and(image.select('NHI_SWNIR_S2').eq(0))
                          .and(image.select('b1600nm').gte(70))
                          .and(image.select('b703nm').lt(70))
                        .rename('EXTREME_PIXEL_S2'));
  };  
// funzione NHI s2
var NHI_ALL_S2 = function(image) {
  return image.addBands(image.select('NHI_SWIR_S2').eq(1)
                         .or(image.select('NHI_SWNIR_S2').eq(1))
                         .or(image.select('EXTREME_PIXEL_S2').eq(1))
                         .rename('NHI'));
  };
// funzione conta pixel NHI
var funzioneConta = function (img, list) {
    var sum = img.select(['NHI']).reduceRegion({
        reducer: ee.Reducer.sum(),
        geometry: area.geometry(),
        maxPixels: 1e13,
    }).get('NHI');
  return  ee.List(list).add(sum);
  };
// funzione calcola Radianza SWIR  
var firstSWIR = ee.List([]);
var calcolaRadianzaSWIR = function (image, list) {
      var Rad = image.select(['b1600nm']).reduceRegion({
      reducer: ee.Reducer.sum().unweighted(),
      geometry: image.select(['NHI']).clip(area.geometry()).reduceToVectors().filterMetadata('label', 'equals', 1),
      maxPixels: 1e13,
      }).get('b1600nm');
  return  ee.List(list).add(Rad);
  };
// funzione calcola Radianza SWNIR    
var firstSWNIR = ee.List([]);
var calcolaRadianzaSWNIR = function (image, list) {
      var Rad = image.select(['b2200nm']).reduceRegion({
        reducer: ee.Reducer.sum().unweighted(),
        geometry: image.select(['NHI']).clip(area.geometry()).reduceToVectors().filterMetadata('label', 'equals', 1),
        maxPixels: 1e13,
        }).get('b2200nm');
  return  ee.List(list).add(Rad);
  };
// funzione calcola tempo per grafici radianza
var tempo0 = ee.List([]);
var calcolaTempo = function (image, list) {
  var added = image.get('system:time_start');
  return ee.List(list).add(added);
  };

// crezione collezione L8 con indici
var L8_ALL = L8.map(RADIANCE)
                .map(NHI_SWIR)
                .map(NHI_SWNIR)
                .map(NHI_SWNIR_L8)
                .map(NHI_SWIR_L8)
                .map(EXTREME_PIXEL)
                .map(NHI_ALL);
// print(L8_ALL);


// batch.Download.ImageCollection.toDrive(L8_ALL.select('NHI_SWNIR_L8','NHI_SWIR_L8','EXTREME_PIXEL'), 'exportNHI', {
//   name: '{system:index}',
//   type: 'byte',
//   scale: 30,
//   region: area
// });

// batch.Download.ImageCollection.toDrive(L8_ALL.select('b800nm','b1600nm', 'b2200nm'), 'exportNHI', {
//   name: '{system:index}',
//   type: 'float',
//   scale: 30,
//   region: area
// });
var labelLandsat = ui.Label('INVESTIGATIONS WITH LANDSAT 8/9-OLI OBSERVATIONS', {fontWeight: 'bold', color:'grey'});
panel.widgets().set(17, labelLandsat);
// Grafico Landsat 
var first_NHI_L8 = ee.List([]);  
var sum_NHI_L8 = ee.List(L8_ALL.sort('DATE_ACQUIRED', true).iterate(funzioneConta, first_NHI_L8));
var tempo_L8 = ee.List(L8_ALL.sort('DATE_ACQUIRED', true).iterate(calcolaTempo, tempo0));
var graph_L8_NHI_SWNIR = (ui.Chart.array.values(sum_NHI_L8,0,tempo_L8)
  .setSeriesNames(['NHI'])
  .setChartType('AreaChart')
  .setOptions({
    title: volcanoSelect.getValue() + ' volcano (buffer of ' + distanceMeters.getValue() + ' m) - Landsat 8/9 OLI data',
    colors: ['blue'],
    vAxis: {title: 'Number of hotspot pixels'},
    }));
// print (ui.Chart.image.series(L8_ALL.select(['NHI','NHI_SWIR_L8','NHI_SWNIR_L8']), area, ee.Reducer.sum()));
//   // .setChartType('ColumnChart')
//     .setOptions({title: volcanoSelect.getValue() + ' volcano (buffer of ' + distanceMeters.getValue() + ' m) - Landsat 8 OLI data',
//     vAxis: {title: 'Number of hotspot pixels'},
//     }));
panel.widgets().set(18, graph_L8_NHI_SWNIR);

// widget pulsante grafico Radianze L8
var buttonRadianceL8 = ui.Button({
  label: 'Compute the total SWIR Radiance with L8/9-OLI data',
  style: {color: 'blue'},
  onClick: function() {
// Grafico Radianze Landsat senza cloud mask 
var RadianzeSWIR = ee.List(L8_ALL.sort('DATE_ACQUIRED', true).iterate(calcolaRadianzaSWIR, firstSWIR));
var RadianzeSWNIR = ee.List(L8_ALL.sort('DATE_ACQUIRED', true).iterate(calcolaRadianzaSWNIR, firstSWNIR));
var RadianzeSWIR_SWNIR = ee.Array.cat([RadianzeSWIR, RadianzeSWNIR],1);
//var tempo = ee.List(L8_ALL.sort('DATE_ACQUIRED', true).iterate(calcolaTempo, tempo0));
var graph_L8_radiance = ui.Chart.array.values(RadianzeSWIR_SWNIR,0,tempo_L8)
  .setSeriesNames(['1600 nm', '2200 nm'])
  .setChartType('AreaChart')
  .setOptions({
    title: 'Total SWIR Radiance of anomalous pixels (OLI)',
    colors: ['blue','red'],
    vAxis: {title: 'Total SWIR Radiance (W*m−2*sr−1*μm-1)'},
    });
panel.widgets().set(19, graph_L8_radiance);
  }
});
panel.widgets().set(19, buttonRadianceL8);

// Selezione scene Landsat per mappe 
var imageSelectL8 = L8_ALL.sort('system:time_start', false)
  .reduceColumns(ee.Reducer.toList(), ['system:index']) //DATE_ACQUIRED
  .get('list');
// interfaccia per scene Landsat
var pickerL8 = ui.Panel({
    widgets: [
      ui.Label('4) Select a Landsat 8/9 image to visualize', {fontWeight: 'bold'}),
      ui.Select({ items: imageSelectL8.getInfo(), placeholder: 'Select an image ID', onChange:refreshMapLayerL8})
    ],
  });
panel.widgets().set(20, pickerL8);

// funzioni per creare mappe con scene Landsat
// NHI SWIR
var L8_MAP_SWIR = function (image) {
  return image.select('NHI_SWIR_L8').clip(area).updateMask(image);
  };
var MAP_L8_NHI_SWIR = L8_ALL.select('NHI_SWIR_L8').map(L8_MAP_SWIR);
// NHI SWNIR
var L8_MAP_SWNIR = function (image) {
  return image.select('NHI_SWNIR_L8').clip(area).updateMask(image);
  };
var MAP_L8_NHI_SWNIR = L8_ALL.select('NHI_SWNIR_L8').map(L8_MAP_SWNIR);
// EXTREME PIXEL
var L8_MAP_EXTREME = function (image) {
  return image.select('EXTREME_PIXEL').clip(area).updateMask(image);
  };
var MAP_L8_EXTREME = L8_ALL.select('EXTREME_PIXEL').map(L8_MAP_EXTREME);
// CREAZIONE MAPPE LANDSAT
function refreshMapLayerL8(img){
  var L8image = L8_ALL.filterMetadata('system:index','equals', img);
  var L8_nhi_swir = MAP_L8_NHI_SWIR.filterMetadata('system:index','equals', img);
  var L8_nhi_swnir = MAP_L8_NHI_SWNIR.filterMetadata('system:index','equals', img);
  var L8_extreme = MAP_L8_EXTREME.filterMetadata('system:index','equals', img);

// var index_swnir_L8_vec = L8_nhi_swnir.first().reduceToVectors({
//   reducer: ee.Reducer.countEvery().unweighted(), 
//   geometry: area.geometry(), 
//   scale: 30,
//   maxPixels: 1e8
// });
// Export.table.toDrive(index_swnir_L8_vec, 'nhi_swnir', 'exportNHI', 'NHI_SWNIR_L8_', 'SHP');

// var index_swir_L8_vec = L8_nhi_swir.reduceToVectors({
//   reducer: ee.Reducer.countEvery().unweighted(),
//   geometry: area.geometry(), 
//   scale: 30,
//   maxPixels: 1e8
// });
// Export.table.toDrive(index_swir_L8_vec, 'nhi_swir', 'exportNHI', 'NHI_SWIR_L8_', 'SHP');

// var extremeL8_vec = L8_extreme.reduceToVectors({
//   reducer: ee.Reducer.countEvery().unweighted(), 
//   geometry: area.geometry(), 
//   scale: 30,
//   maxPixels: 1e8
// });
// Export.table.toDrive(extremeL8_vec, 'extremeL8', 'exportNHI', 'EXTREME_L8_', 'SHP');

  mainMap.layers().reset();
  mainMap.setOptions('satellite');
  mainMap.addLayer(L8image,{bands:['B7','B6','B5'], min: 3000, max: 15000},' OLI image (RGB: B7-B6-B5 Reflectance)', 0);
  mainMap.addLayer(L8_nhi_swir,{palette:"yellow"},'Mid-low intensity pixels', 1);
  mainMap.addLayer(L8_nhi_swnir,{palette:"red"},'High intensity pixels', 1);
  mainMap.addLayer(L8_extreme,{palette:"purple"},'Extreme pixels', 1);
  mainMap.addLayer(outlineBufferVolcano,{palette: 'White'}, 'Investigated area around ' + volcanoSelect.getValue());
  mainMap.remove(legend);
  mainMap.add(legend);
  }

// crezione collezione S2 con indici
var S2_ALL = S2.map(radiance)
                .map(NHI_SWIR)
                .map(NHI_SWNIR)
                .map(TEST_MISS_REG)
                .map(NHI_SWNIR_S2)
                .map(NHI_SWIR_S2)
                .map(EXTREME_PIXEL_S2)
                .map(NHI_ALL_S2);
// print(S2_ALL)

// batch.Download.ImageCollection.toDrive(S2_ALL.select('NHI_SWNIR_S2','NHI_SWIR_S2','EXTREME_PIXEL_S2'), 'exportNHI', {
//   name: '{system:index}',
//   type: 'byte',
//   scale: 20,
//   region: area
// });
// batch.Download.ImageCollection.toDrive(S2_ALL.select('b800nm','b1600nm', 'b2200nm'), 'exportNHI', {
//   name: '{system:index}',
//   type: 'float',
//   scale: 20,
//   region: area
// });
var labelSentinel = ui.Label('INVESTIGATIONS WITH SENTINEL 2-MSI OBSERVATIONS', {fontWeight: 'bold', color:'grey'});
panel.widgets().set(21, labelSentinel);
// Grafico Sentinel senza cloud mask
var first_NHI_S2 = ee.List([]);  
var sum_NHI_S2 = ee.List(S2_ALL.sort('DATE_ACQUIRED', true).iterate(funzioneConta, first_NHI_S2));
var tempo_S2 = ee.List(S2_ALL.sort('DATE_ACQUIRED', true).iterate(calcolaTempo, tempo0));
var graph_S2_NHI_SWNIR = (ui.Chart.array.values(sum_NHI_S2,0,tempo_S2)
  .setSeriesNames(['NHI'])
  .setChartType('AreaChart')
  .setOptions({
    title: volcanoSelect.getValue() + ' volcano (buffer of ' + distanceMeters.getValue() + ' m) - Sentinel 2 MSI data',
    colors: ['blue'],
    vAxis: {title: 'Number of hotspot pixels'},
    }));

// print (ui.Chart.image.series(S2_ALL.select(['NHI','NHI_SWIR_S2','NHI_SWNIR_S2']), area, ee.Reducer.sum()));
//   .setOptions({title: volcanoSelect.getValue() + ' volcano (buffer of ' + distanceMeters.getValue() + ' m) - Sentiel 2 MSI data',
//   vAxis: {title: 'Number of hotspot pixels'},
//   }));
panel.widgets().set(22, graph_S2_NHI_SWNIR);


// widget pulsante grafico Radianze S2
var buttonRadianceS2 = ui.Button({
  label: 'Compute the total SWIR Radiance with S2-MSI data',
  style: {color: 'blue'},
  onClick: function() {
// Grafico Radianze Sentinel senza cloud mask 
var Radianze_S2_SWIR = ee.List(S2_ALL.sort('DATE_ACQUIRED', true).iterate(calcolaRadianzaSWIR, firstSWIR));
var Radianze_S2_SWNIR = ee.List(S2_ALL.sort('DATE_ACQUIRED', true).iterate(calcolaRadianzaSWNIR, firstSWNIR));
var Radianze_S2_SWIR_SWNIR = ee.Array.cat([Radianze_S2_SWIR, Radianze_S2_SWNIR],1);
//var tempoS2 = ee.List(S2_ALL.sort('DATE_ACQUIRED', true).iterate(calcolaTempo, tempo0));
var graph_S2_radiance = ui.Chart.array.values(Radianze_S2_SWIR_SWNIR,0,tempo_S2)
  .setSeriesNames(['1600 nm', '2200 nm'])
  .setChartType('AreaChart')
  .setOptions({
    title: 'Total SWIR Radiance of anomalous pixels (MSI)',
    colors: ['blue','red'],
    vAxis: {title: 'Total SWIR Radiance (W*m−2*sr−1*μm-1)'},
    });
panel.widgets().set(23, graph_S2_radiance);
  }
});
panel.widgets().set(23, buttonRadianceS2);

// Selezione scene Sentinel per mappe 
var imageSelectS2 = S2_ALL.sort('system:time_start', false)
  .reduceColumns(ee.Reducer.toList(), ['system:index'])
  .get('list');
// interfaccia per scene Sentinel
var pickerS2 = ui.Panel({
    widgets: [
      ui.Label('5) Select a Sentinel 2 image to visualize', {fontWeight: 'bold'}),
      ui.Select({ items: imageSelectS2.getInfo(), placeholder: 'Select an image ID', onChange:refreshMapLayerS2})
    ],
  });
panel.widgets().set(24, pickerS2);

// funzioni per creare mappe con scene SENTINEL
// NHI SWIR S2
var S2_MAP_SWIR = function (image) {
  return image.select('NHI_SWIR_S2').clip(area).updateMask(image);
  };
var MAP_S2_NHI_SWIR = S2_ALL.select('NHI_SWIR_S2').map(S2_MAP_SWIR);
// NHI SWNIR S2
var S2_MAP_SWNIR = function (image) {
  return image.select('NHI_SWNIR_S2').clip(area).updateMask(image);
  };
var MAP_S2_NHI_SWNIR = S2_ALL.select('NHI_SWNIR_S2').map(S2_MAP_SWNIR);
// EXTREME PIXEL S2
var S2_MAP_EXTREME = function (image) {
  return image.select('EXTREME_PIXEL_S2').clip(area).updateMask(image);
  };
var MAP_S2_EXTREME = S2_ALL.select('EXTREME_PIXEL_S2').map(S2_MAP_EXTREME);
// CREAZIONE MAPPE SENTINEL
function refreshMapLayerS2(img){
  var S2image = S2_ALL.filterMetadata('system:index','equals', img);
  var S2_nhi_swir = MAP_S2_NHI_SWIR.filterMetadata('system:index','equals', img);
  var S2_nhi_swnir = MAP_S2_NHI_SWNIR.filterMetadata('system:index','equals', img);
  var S2_extreme = MAP_S2_EXTREME.filterMetadata('system:index','equals', img);
  
// var index_swnir_S2_vec = S2_nhi_swnir.first().reduceToVectors({
//   reducer: ee.Reducer.countEvery(), 
//   geometry: area.geometry(),
//   scale: 20,
//   maxPixels: 1e8
// });
// Export.table.toDrive(index_swnir_S2_vec, 'nhi_swnir', 'exportNHI', 'NHI_SWNIR_', 'SHP');

// var index_swir_S2_vec = S2_nhi_swir.first().reduceToVectors({
//   reducer: ee.Reducer.countEvery(), 
//   geometry: area.geometry(),
//   scale: 20,
//   maxPixels: 1e8
// });
// Export.table.toDrive(index_swir_S2_vec, 'nhi_swir', 'exportNHI', 'NHI_SWIR_', 'SHP');

// var index_extreme_hotpixels_S2 = S2_extreme.first().reduceToVectors({
//   reducer: ee.Reducer.countEvery(), 
//   geometry: area.geometry(),
//   scale: 20,
//   maxPixels: 1e8
// });
// Export.table.toDrive(index_extreme_hotpixels_S2, 'extreme', 'exportNHI', 'NHI_EXTREME_', 'SHP');


  mainMap.layers().reset();
  mainMap.setOptions('satellite');
  mainMap.addLayer(S2image,{bands:['B12','B11','B8A'], min: 500, max: 1800},' MSI image (RGB: B12-B11-B8A Reflectance)', 0);
  mainMap.addLayer(S2_nhi_swir,{palette:"yellow"},'Mid-low intensity pixels', 1);
  mainMap.addLayer(S2_nhi_swnir,{palette:"red"},'High intensity pixels', 1);
  mainMap.addLayer(S2_extreme,{palette:"purple"},'Extreme pixels', 1);
  mainMap.addLayer(outlineBufferVolcano,{palette: 'White'}, 'Investigated area around ' + volcanoSelect.getValue());
  mainMap.remove(legend);
  mainMap.add(legend);
  }
  
// INTEGRAZIONE DEI DATI
var labelIntegration = ui.Label('LANDSAT 8/9-OLI AND SENTINEL 2-MSI DATA INTEGRATION', {fontWeight: 'bold', color:'orange'});
panel.widgets().set(25, labelIntegration);
// REMANE BANDE RIFLETTANZA LANDSAT
var renameL8 = function(image) {
    var bands = ['B5', 'B6', 'B7','NHI'];
    var new_bands = ['Refb800nm', 'Refb1600nm', 'Refb2200nm','NHI'];
  return image.rename(new_bands);
  };
// CONVERSIONE A 16 BIT UNSIGNED PER SENTINEL  
var TOint16 = function(image) {
  return image.toUint16();
};
// FUNZIONI PER CALCOLARE AREA
var L8_AREA = function (image) {
  return image.addBands(image.select('NHI').multiply(900).rename('NHI_AREA'));
  };
var S2_AREA = function (image) {
  return image.addBands(image.select('NHI').multiply(400).rename('NHI_AREA'))
              .addBands(image.select('B8A').multiply(10).rename('Refb800nm'))   // PER UNIFORMARE CON LANDSAT
              .addBands(image.select('B11').multiply(10).rename('Refb1600nm'))  // PER UNIFORMARE CON LANDSAT
              .addBands(image.select('B12').multiply(10).rename('Refb2200nm')); // PER UNIFORMARE CON LANDSAT
  };
// CALCOLA AREA SU L8 E S2 E POI MERGE  
var L8_NHI_AREA = L8_ALL.select('B5', 'B6', 'B7', 'NHI').map(renameL8).map(L8_AREA);
var S2_NHI_AREA = S2_ALL.select('B8A', 'B11', 'B12', 'NHI').map(S2_AREA).map(TOint16);
var TOTAL_AREA = L8_NHI_AREA.merge(S2_NHI_AREA);
//print(TOTAL_AREA);
// VISUALIZZAZIONE RGB DELL'ULTIMA IMMAGINE DISPONIBILE
var lastImage = TOTAL_AREA.sort('system:time_start', false).first();
mainMap.addLayer(lastImage.select('Refb2200nm','Refb1600nm','Refb800nm'),{bands:['Refb2200nm','Refb1600nm','Refb800nm'], min: 5000, max: 18000},' last image (RGB: 2200nm-1600nm-800nm)', 1);
mainMap.addLayer(outlineBufferVolcano,{palette: 'Red'}, 'Investigated Area aroud ' + volcanoSelect.getValue());  
mainMap.centerObject(selectedVolcano, 12);

// widget pulsante grafico Radianze S2
var buttonArea = ui.Button({
  label: 'Compute the total hotspot area',
  style: {color: 'green'},
  onClick: function() {
// GRAFICO DELLE AREE
var graph_total_area = (ui.Chart.image.series(TOTAL_AREA.select(['NHI_AREA']), area, ee.Reducer.sum())
  .setSeriesNames(['Total hotspot area (m2) '])
  .setChartType('AreaChart')
  .setOptions({title: volcanoSelect.getValue() + ' volcano (buffer of ' + distanceMeters.getValue() + ' m) - OLI and MSI data',
  vAxis: {title: 'Total hotspot area (m2)'},
  colors: ['green'],
  }));
panel.widgets().set(26,graph_total_area);
  }
});
panel.widgets().set(26, buttonArea);

// set position of panel
var legend = ui.Panel({
  style: {
    position: 'bottom-right',
    padding: '8px 15px'
  }
});
// Create legend title
var legendTitle = ui.Label({
  value: 'NHI Legend',
  style: {
    fontWeight: 'bold',
    fontSize: '18px',
    margin: '0 0 4px 0',
    padding: '0'
    }
});
// Add the title to the panel
legend.add(legendTitle);
// Creates and styles 1 row of the legend.
var makeRow = function(color, name) {
// Create the label that is actually the colored box.
      var colorBox = ui.Label({
        style: {
          backgroundColor: '#' + color,
          // Use padding to give the box height and width.
          padding: '8px',
          margin: '0 0 4px 0'
        }
      });
      // Create the label filled with the description text.
      var description = ui.Label({
        value: name,
        style: {margin: '0 0 4px 6px'}
      });
      // return the panel
      return ui.Panel({
        widgets: [colorBox, description],
        layout: ui.Panel.Layout.Flow('horizontal')
      });
  };
//  Palette with the colors
var palette =['800080', 'FF0000', 'FFFF00'];
// name of the legend
var names = ['Extreme pixels','High intensity pixels','Mid-low intensity pixels'];
// Add color and and names
for (var i = 0; i < 3; i++) {
  legend.add(makeRow(palette[i], names[i]));
  }  
// add legend to map FATTO NEI REFRESH DI LANDSAT E SENTINEL

panel.widgets().set(27, text1);
panel.widgets().set(28, text2);
panel.widgets().set(29, text3);
panel.widgets().set(30, text4);
panel.widgets().set(31, text5);
panel.widgets().set(32, text6);
panel.widgets().set(33, text7);
panel.widgets().set(34, text8);

}
});

// Aggiunta Logo
// var logo = ui.Thumbnail({
//     image: ee.Image('users/nicogenzano/logo'),
//     params: { bands: ['b1','b2','b3'], min: 0, max: 255, format: 'jpg'},
//     style: { backgroundColor: '#00000000', position: 'bottom-left', width: '170px', height: '52px'},
//   });
// mainMap.add(logo);
// aggiunta pannello laterale e widget
var panel = ui.Panel();
panel.style().set('width', '36%');
panel.widgets().set(0, title);
panel.widgets().set(1, subtitleNews);
panel.widgets().set(2, subTitle);
panel.widgets().set(3, readme);
panel.widgets().set(4, volcanoLabel);
panel.widgets().set(5, subtitleVolcanoLabel);
panel.widgets().set(6, volcanoSelect);
panel.widgets().set(7, periodLabel);
panel.widgets().set(8, titleStartDate);
panel.widgets().set(9, startDate);
panel.widgets().set(10, titleEndDate);
panel.widgets().set(11, endDate);
panel.widgets().set(12, distanceLabel);
panel.widgets().set(13, subtitleDistanceLabel);
panel.widgets().set(14, distanceMeters);
panel.widgets().set(15, button);
panel.widgets().set(27, text1);
panel.widgets().set(28, text2);
panel.widgets().set(29, text3);
panel.widgets().set(30, text4);
panel.widgets().set(31, text5);
panel.widgets().set(32, text6);
panel.widgets().set(33, text7);
panel.widgets().set(34, text8);
var mapSplit = ui.SplitPanel({
  firstPanel: panel, 
  secondPanel: mainMap,
  orientation: 'horizontal',
  wipe: false,
});
ui.root.clear();
ui.root.add(mapSplit);