from pandas.core.algorithms import isin
from processing.core.Processing import Processing
import processing
import os
import pandas as pd
from qgis.core import (
    QgsProject,
    QgsApplication,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsProperty,
    QgsPropertyCollection,
    QgsSpatialIndex,
    QgsVectorFileWriter,
    QgsGeometry,
    QgsFeature,
    QgsPointXY,
    QgsField,
    QgsExpressionContext,
    QgsExpressionContextUtils,

    QgsMarkerSymbol,
    QgsSymbolLayer,
    QgsExpression,
    QgsRasterBandStats,
    QgsSimpleMarkerSymbolLayerBase,
    QgsCategorizedSymbolRenderer,
    QgsSingleSymbolRenderer,
    QgsFillSymbol,
    QgsSymbol,
    QgsLineSymbol,
    QgsRendererRange,
    QgsRendererCategory,
    QgsStyle
)
from qgis.analysis import QgsGeometryCheckError
from PyQt5 import QtCore, QtGui, QtWidgets  #### works for pyqt5
from PyQt5.QtCore import QVariant
from PyQt5.QtGui import QColor

####################################################################
from my_functions import (check_and_fix, load_and_clip, attributes_to_df, add_shape_area)

####################################################################
import os

####################################################################
#### paths
path_app = "C:\Program Files\QGIS 3.16.9"
path_project = './FinalProject.qgz'
project = QgsProject.instance()
project.read(path_project)

#### the path to the project is set
QgsApplication.setPrefixPath(path_app, True)
#### QGX app is stored as variable
qgs = QgsApplication([], False)
#### print (QgsApplication.showSettings())
#### Initialize app
qgs.initQgis()
#### Processing
Processing.initialize()

####################################################################
#### EXISTING FROG HABITAT
frog_layer_params = {
    'fn_in': './data/_FIXED_DATA/frogs_existing_habitat.shp',
    'fn_out': './FinalQGIS/data/frogs_existing_habitat.shp',
    'name': "FROGS_EXISTING_HABITAT"
}
#### DISSOLVE FROG LAYER, SAVE AND LOAD TO PROJECT
frog_layer = QgsVectorLayer(frog_layer_params['fn_out'], frog_layer_params['name'] , "ogr")
if not frog_layer.isValid():
    print(f"{frog_layer_params['fn_out']} layer failed to load!")
    frog_layer = QgsVectorLayer(frog_layer_params['fn_in'], frog_layer_params['name'] , "ogr")
    if not frog_layer.isValid():
        print(f"{frog_layer_params['fn_in']} layer failed to load!")
    else:
        params = {
            'INPUT':frog_layer,
            'FIELD':['ASI_TYPE'],
            'OUTPUT':'TEMPORARY_OUTPUT'
            }
        frog_layer = processing.run("native:dissolve", params)['OUTPUT']
        QgsVectorFileWriter.writeAsVectorFormat(frog_layer, frog_layer_params['fn_out'], 'utf-8', driverName='ESRI Shapefile')
print(f"features in dissolved frog layer: {len([x for x in frog_layer.getFeatures()])}")

####################################################################
#### VEGETATION MAP
veg_layer_params = {
    'fn_in': "./data/_FIXED_DATA/vegetation.shp",   
    'fn_out': './FinalQGIS/data/vegetation_existing_habitat.shp',
    'name': "VEGETATION_EXISTING_HABITAT"
    }
#### CLIP BY EXISTING FROG HABITAT
veg_layer = QgsVectorLayer(veg_layer_params['fn_out'], veg_layer_params['name'] , "ogr")
if not veg_layer.isValid():
    print(f"{veg_layer_params['fn_out']} layer failed to load!")
    veg_layer = QgsVectorLayer(veg_layer_params['fn_in'], veg_layer_params['name'] , "ogr")
    if not veg_layer.isValid():
        print(f"{veg_layer_params['fn_in']} layer failed to load!")
    else:
        params = {
            'INPUT':veg_layer,
            'OVERLAY':frog_layer,
            'OUTPUT': 'TEMPORARY_OUTPUT'
            }
        veg_layer = processing.run("native:clip", params)['OUTPUT']
        QgsVectorFileWriter.writeAsVectorFormat(veg_layer, veg_layer_params['fn_out'], 'utf-8', driverName='ESRI Shapefile')
#### ADD ATTRIBUTE AREA AND CALCULATE
add_shape_area(veg_layer, 'area_m')
QgsVectorFileWriter.writeAsVectorFormat(veg_layer, veg_layer_params['fn_out'], 'utf-8', driverName='ESRI Shapefile')

# veg_layer = QgsVectorLayer(veg_layer_params['fn_out'], veg_layer_params['name'] , "ogr")
print(f"features in veg existing habitat layer: {len([x for x in veg_layer.getFeatures()])}")

#### CALCULATE PERCENTAGE
df = attributes_to_df(veg_layer)
df = df[['NVISDSC1', 'area_m']]
df['NVIS_ID'] = df['NVISDSC1']

veg_class_df = pd.read_csv("./data/_VEGETATION/FGDB_VIC_EXT/NVIS_6_0_LUT_AUST_FLAT/NVIS6_0_LUT_AUST_FLAT.csv")
# print(f"veg_class_df length {len(veg_class_df.index)}")

df = df.merge(veg_class_df, on='NVIS_ID', how='left')
df = df.groupby(['MVS_NAME'], as_index=False).agg({'area_m':'sum', 'NVIS_ID': set})
df = df.loc[df["MVS_NAME"] != "Cleared, non-native vegetation, buildings"]

df['percent'] = (df['area_m'] / df['area_m'].sum()) * 100
df = df.sort_values(by=['percent'], ascending=False)
# print(df)
df.to_csv('vegetation_existing_habitat.csv', index=False)

####################################################################
#### HYDROLOGY MAP
hydro_layer_params = {
    'fn_in': "./data/_FIXED_DATA/hy_water_area_polygon.shp",
    'fn_out': './FinalQGIS/data/hydro_existing_habitat.shp',
    'name': "HYDROLOGY_EXISTING_HABITAT"
}
#### CLIP BY EXISTING FROG HABITAT
hydro_layer = QgsVectorLayer(hydro_layer_params['fn_out'], hydro_layer_params['name'] , "ogr")
if not hydro_layer.isValid():
    print(f"{hydro_layer_params['fn_out']} layer failed to load!")
    hydro_layer = QgsVectorLayer(hydro_layer_params['fn_in'], hydro_layer_params['name'] , "ogr")
    if not hydro_layer.isValid():
        print(f"{hydro_layer_params['fn_in']} layer failed to load!")
    else:
        params = {
            'INPUT':hydro_layer,
            'OVERLAY':frog_layer,
            'OUTPUT': 'TEMPORARY_OUTPUT'
            }
        hydro_layer = processing.run("native:clip", params)['OUTPUT']
        QgsVectorFileWriter.writeAsVectorFormat(hydro_layer, hydro_layer_params['fn_out'], 'utf-8', driverName='ESRI Shapefile')

#### ADD ATTRIBUTE AREA AND CALCULATE
add_shape_area(hydro_layer, 'area_m')
QgsVectorFileWriter.writeAsVectorFormat(hydro_layer, hydro_layer_params['fn_out'], 'utf-8', driverName='ESRI Shapefile')
print(f"features in hydro existing habitat layer: {len([x for x in hydro_layer.getFeatures()])}")

#### CALCULATE PERCENTAGE
df = attributes_to_df(hydro_layer)
print(df)
df = df.groupby(['FTYPE_CODE'], as_index=False).agg({'area_m':'sum'})
df['percent'] = (df['area_m'] / df['area_m'].sum()) * 100
df = df.sort_values(by=['percent'], ascending=False)
print(df)
df.to_csv('hydro_existing_habitat.csv', index=False)

#### ADD TO PROJECT
project.addMapLayers([frog_layer, veg_layer, hydro_layer], True)
# project.addMapLayers([hydro_layer], True)
#### SAVE THE PROJECT
project.write()
#### remove the provider and layer registries from memory
qgs.exitQgis()

