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
# from my_functions import (check_and_fix, load_and_clip, attributes_to_df, add_shape_area)

####################################################################
import os

def check_and_fix(layer_params):
    layer = QgsVectorLayer(layer_params['fn_in'], layer_params['name'] , "ogr")
    if not layer.isValid():
        print(f"{layer_params['fn_in']} layer failed to load!")
    #### check if geometry is valid
    params = {'INPUT_LAYER':layer,
        'METHOD': 2,
        'IGNORE_RING_SELF_INTERSECTION':False,
        'VALID_OUTPUT':'TEMPORARY_OUTPUT',
        'INVALID_OUTPUT':'TEMPORARY_OUTPUT',
        'ERROR_OUTPUT':'TEMPORARY_OUTPUT'
    }
    result = processing.run("qgis:checkvalidity", params)
    print(result)

    #### fix geometry if needed
    if result['ERROR_COUNT'] != 0:
        print(f"Errors in layer: {result['ERROR_COUNT']}")
        layer_valid = result['VALID_OUTPUT']
        print(layer_valid)
        print('Fixing geometry')
        params = {'INPUT': layer,'OUTPUT':'TEMPORARY_OUTPUT'}
        layer = processing.run("native:fixgeometries", params)['OUTPUT']
    else:
        print(f"Errors in layer: 0")
    return layer

#### paths
path_app = "C:\Program Files\QGIS 3.16.9"
path_project = './FinalQGIS/FinalProject.qgz'
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

layers = [
    #### EXISTING FROG HABITAT
    {
        'fn_in': './data/_FROGS/Order_CS5ANC/ll_gda2020/esrishape/whole_of_dataset/victoria/FLORAFAUNA1/MSA_BCS_GGF_ASI.shp',   
        'fn_out': './data/_FIXED_DATA/frogs_existing_habitat.shp',
        'name': "FROGS_EXISTING_HABITAT"
    },

    #### SOUTH-EASTERN MELBOURNE
    {
        'fn_in': "./data/_ADMIN/VMADMIN/layer/ad_vicgov_region.shp",
        'fn_out': "./data/_FIXED_DATA/region.shp",
        'name': "SOUTHERN METROPOLITAN"
    },
    #### HYDROLOGY MAP
    {
        'fn_in': "./data/_HYDRO/VMHYDRO/layer/hy_water_area_polygon.shp",
        'fn_out': "./data/_FIXED_DATA/hydro.shp",
        'name': "HYDROLOGY"
    },
    #### ROADS MAP
    {
        'fn_in': "./data/_ROADS/AU_NERP-TE-13-1_AIMS-OSM_MajorRoads_Dec-2011/AU_OSM_MajorRoads_Dec-2011.shp",
        'fn_out': "./data/_FIXED_DATA/major_roads.shp",
        'name': "MAJOR ROADS"
    },
    #### VEGETATION MAP
    {
        'fn_in': "./data/_VEGETATION/FGDB_VIC_EXT/NVIS6_0_AUST_EXT_VIC.gdb",   
        'fn_out': "./data/_FIXED_DATA/vegetation.shp",
        'name': "VEGETATION"
    },
    #### PLANNING MAP
    {
        'fn_in': "./data/VMPLAN/layer/plan_zone.shp",   
        'fn_out': "./data/_FIXED_DATA/plan_zone.shp",
        'name': "PLAN_ZONES"
    }
]

for layer_params in layers:
    layer = QgsVectorLayer(layer_params['fn_out'], layer_params['name'] , "ogr")
    if not layer.isValid():
        print(f"{layer_params['fn_out']} OUT layer failed to load! Checking and Repairing the file")
        layer = check_and_fix(layer_params)
    else:
        print(f"{layer_params['fn_out']} OUT layer is fixed already")
    QgsVectorFileWriter.writeAsVectorFormat(layer, layer_params['fn_out'], 'utf-8', driverName='ESRI Shapefile')
    print('*'*30)