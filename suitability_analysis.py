# -*- coding: utf-8 -*-

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterVectorDestination,
                       QgsProcessingParameterField,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterString,
                       QgsVectorLayer,
                       QgsSpatialIndex,
                       QgsFeature,
                       QgsPoint,
                       QgsGeometry,
                       QgsWkbTypes,
                       QgsField,
                       QgsExpression,
                       QgsExpressionContext,
                       QgsExpressionContextUtils,
                       QgsProject
                       )

from qgis.analysis import QgsGeometryCheckError
from PyQt5 import QtCore, QtGui, QtWidgets  #### works for pyqt5
from PyQt5.QtCore import QVariant
from PyQt5.QtGui import QColor
import pandas as pd
import os
from qgis import processing


class SuitabilityAnalysis(QgsProcessingAlgorithm):
    """
    DESCRIPTION
    The script conducts Spatial analysis of the study area for Growling Grass Frog habitat within administrative area of Victoria.
    The analysis is based on land use type, water type, vegetation type.
    The script inputs:
    1) vector layer of the Admin regions of Victoria. Any of these areas can be used as a cookie cutter for the other layers
    2) vector layer of the Hydrology of of Victoria.
    3) vector layer of the Main Roads of Victoria.
    4) vector layer of the Planning Zones of Victoria.
    5) vector layer of the Vegetation types of Victoria.
    6) csv table of the Vegetation codes.
    The outputs:
    1) new layer and shp file of the selected areas
    2) a 'csv' folder with csv files for each selected area
    
    Note: to reduce the amount of uploaded data the script only unducts the analysis for "SOUTHERN METROPOLITAN" region and all vector layers are already clipped to that area.
    """
    ##### SOME PATHS
    #### project data path
    data_path = f"{QgsProject.instance().homePath()}/data"
    ##### path to the table of vegetation codes - names
    veg_table_path = f"{data_path}/NVIS6_0_LUT_AUST_FLAT.csv"
    #### path to create csv files for selected areas
    csv_path = f"{data_path}/csv"

    """"
    all input parameters settings, as well as input layers and outputs are collected into dictionaries.
    the variables, layers and outputs are also collected into dictionaries 
    this is done to create uniform editing and access to data
    helps setting up parameters adding new ones or editing existing
    makes it easier finding and fixing bugs
    """

    VAR_PARAMS = {
        "admin_area" : {
            "parameter": QgsProcessingParameterString,
            "description": "Input Study Area Name",
            "input": "INPUT_AREA_NAME",
            "default": "SOUTHERN METROPOLITAN",
            "optional": False
        },
        "facilities_buffer" : {
            "parameter": QgsProcessingParameterNumber,
            "type": QgsProcessingParameterNumber.Double,
            "description": "Input Buffer Distance from Facilities",
            "input": "INPUT_FAC_BUFFER",
            "default": -50,
            "maxValue": 0,
            "optional": False
        },
        "water_buffer" : {
            "parameter":QgsProcessingParameterNumber,
            "type": QgsProcessingParameterNumber.Double,
            "description": "Input Buffer Distance from Water",
            "input": "INPUT_WATER_BUFFER",
            "default": 100,
            "minValue": 0,
            "optional": False
        },
        "min_water_area" : {
            "parameter":QgsProcessingParameterNumber,
            "type": QgsProcessingParameterNumber.Double,
            "description": "Input minimum Water area required",
            "input": "INPUT_MIN_WATER",
            "default": 4500,
            "minValue": 0,
            "optional": False
        },
        "veg_name" : {
            "parameter": QgsProcessingParameterString,
            "description": "Input Preferable Vegetation Type",
            "input": "INPUT_VEG_NAME",
            "default": "Temperate tussock grasslands",
            "optional": False
        }
    }
    """ 
    THIS VARIABLES FOR SELECTION WATER AND VEGETATIONTYPES WERE HARDCODED AS THEY ARE A RESULT OF PREVIOUS ANALYSIS
    THEY CAN BE INCLUDED AS VARIABLES THROUGH CHECKBOX INPUT, BUT WILL BE HARD TO NAVIGATE AS THERE IS A GREAT NUMBER OF THE OPTIONS
    """
    suitable_hydro_keywords = ['watercourse_area_river', 'wb_lake']
    suitable_zones_keywords = ['FARMING', 'GREEN WEDGE', 'CONSERVATION', 'RECREATION', 'PUBLIC USE ZONE']

    LAYERS_PARAMS = {
        "admin": {
            "label": "ADMIN",
            "input": 'INPUT_ADMIN',
            "geometry": QgsWkbTypes.PolygonGeometry,
            "check_field": "VGREG",
            'style': f"{data_path}/styles/veg.qml"
        },
        "hydro": {
            "label": "HYDROLOGY",
            "input": 'INPUT_HYDRO',
            "geometry": QgsWkbTypes.PolygonGeometry,
            "check_field": "FTYPE_CODE",
            'style': f"{data_path}/styles/hydro.qml"
        },
        "zones": {
            "label": "PLANNING ZONES",
            "input": 'INPUT_ZONES',
            "geometry": QgsWkbTypes.PolygonGeometry,
            "check_field": "ZONE_DESC",
            'style': f"{data_path}/styles/zones.qml"
        },
        "veg": {
            "label": "VEGETATION",
            "input": 'INPUT_VEG',
            "geometry": QgsWkbTypes.PolygonGeometry,
            "check_field": 'NVISDSC1',
            'style': f"{data_path}/styles/veg.qml"
        },
    }

    OUTPUT_PARAMS = {
        "output_1" :{
            "parameter": QgsProcessingParameterVectorDestination,
            "label": "OUTPUT_LAYER_1",
            "output": 'OUTPUT_LAYER_1',
        },
        # "output_2" :{
        #     "parameter": QgsProcessingParameterVectorDestination,
        #     "label": "OUTPUT_LAYER_2",
        #     "output": 'OUTPUT_LAYER_2',
        # },
    }
    
    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return SuitabilityAnalysis()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'suitability_analysis'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Suitability Analysis')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('scripts')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'examplescripts'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """

        script_description = """Suitability Analysis for Growling Frog habitat in Southern Metropolitan Melbourne
            -------------------------
            INPUTS:
            - Admin area layer or shape file. Must contain field 'VGREG'
            - Hydrology layer or shape file. Must contain field 'FTYPE_CODE'
            - Planning Zones or shapefile. Must contain field 'ZONE_DESC'
            - Vegetation layer of shapefile. Must contain field 'NVISDSC1'
            - the table of vegetation codes-names association 'NVIS6_0_LUT_AUST_FLAT.csv' must be present in th eproject './data' folder
            -------------------------
            VARIABLES:
            - Study Area Name, must be set to "SOUTHERN METROPOLITAN"
            - Buffer Distance from Facilities", default -50. Buffers the Planning Zones INSIDE
            - Buffer Distance from Water, default 100. Buffers the hydrology OUTSIDE
            - minimum Water area required, default": 4500
            - Preferable Vegetation Type, must be set to "Temperate tussock grasslands"
            -------------------------
            OUTPUT:
            - layer of selected suitable areas
            - folder './data/csv' with the vegetation summary for each selected area. the filename is associated with the OBJECTID of the feature in selected layer

            """
        return self.tr(script_description)

    def initAlgorithm(self, config=None):
        #### INPUTS
        #### add layers
        for name, value in self.LAYERS_PARAMS.items():
            self.addParameter(
                QgsProcessingParameterFeatureSource(
                    value['input'],
                    self.tr(f"Input layer {value['label']}"),
                    [QgsProcessing.TypeVectorAnyGeometry]
                )
            )

        for name, value in self.VAR_PARAMS.items():
            params = {
                "name": value["input"],
                "description": self.tr(value["description"]),
                "defaultValue": value["default"],
                "optional": value["optional"],
            }
            if "type" in value:
                params["type"] = value["type"]
            if "minValue" in value:
                params["minValue"] = value["minValue"]
            if "maxValue" in value:
                params["maxValue"] = value["maxValue"]
                
            self.addParameter(
                value['parameter'](**params)
            )
     
        for name, value in self.OUTPUT_PARAMS.items():
            self.addParameter(
                QgsProcessingParameterFeatureSink(
                    value['output'],
                    self.tr(f"Output layer {value['label']}"),
                )
            )

    def processAlgorithm(self, parameters, context, feedback):
        ##### define parameters variables locally
        LAYERS_PARAMS = self.LAYERS_PARAMS
        VAR_PARAMS = self.VAR_PARAMS
        OUTPUT_PARAMS = self.OUTPUT_PARAMS

         ####################################################################
         #### FUNCTIONS

        ####################################################################
        ##### DEFINE FUNCTIONS
        log = feedback.pushInfo
        def load_reproject_and_clip(name, layer, mask_layer):
            crs = mask_layer.crs()
            #### REPROJECT
            if layer.crs() != crs:
                log(f"reprojecting layer {name} to {crs}")
                params = {
                    'INPUT': layer, 
                    'TARGET_CRS': crs.authid(),
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }
                layer = processing.run('native:reprojectlayer', params)['OUTPUT']
            log(f"layer {name} is in to {crs} projection")

            #### CLIP
            params = {'INPUT': layer,
                'OVERLAY': mask_layer,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }
            layer = processing.run("native:clip", params)['OUTPUT']
            log(f"layer {name} was clipped by study area")
            return layer

        def add_shape_area(layer, field_names={'area': 'Shape_Area', 'length': 'Shape_Leng'}):

            geom = layer.geometryType()
            try:
                area = field_names['area']
            except:
                area = 'Shape_Area'

            try:
                length = field_names['length']
            except:
                length = 'Shape_Leng'

            prov = layer.dataProvider()
            attr_names = [field.name() for field in prov.fields()]
            #### add if the field doesn't exist
            if area not in attr_names:
                layer.startEditing()
                prov.addAttributes([QgsField(area, QVariant.Double)])
                attr_names = [field.name() for field in prov.fields()]
                layer.commitChanges()

            if length not in attr_names:
                layer.startEditing()
                prov.addAttributes([QgsField(length, QVariant.Double)])
                attr_names = [field.name() for field in prov.fields()]
                layer.commitChanges()

            layer.startEditing()
            expression_a = QgsExpression('$area')
            if geom == QgsWkbTypes.PolygonGeometry:
                expression_l = QgsExpression('$perimeter')
            else:
                expression_l = QgsExpression('$length')

            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
            for f in layer.getFeatures():
                context.setFeature(f)
                f[area] = expression_a.evaluate(context)
                f[length] = expression_l.evaluate(context)
                layer.updateFeature(f)
            layer.commitChanges()
            return layer

        def reduce_attributes(layer, attr_to_keep):
            fields = layer.dataProvider().fields()
            fList = list()
            count = 0
            for field in fields:
                if field.name() not in attr_to_keep:
                    fList.append(count)
                count += 1
            layer.dataProvider().deleteAttributes(fList)
            layer.updateFields()
            return layer

        def attributes_to_df(layer):
            cols = [field.name() for field in layer.fields()]
            row_list = [dict(zip(cols, feat.attributes())) for feat in layer.getFeatures()]
            df = pd.DataFrame(row_list, columns=cols)
            # print(f"attributes to df length: {len(df)}")
            return df

        ####################################################################
        #### DEFINE VARIABLES

        #### import the table with vegetation codes-names
        veg_table = QgsVectorLayer(self.veg_table_path, "table", "ogr")
        if veg_table is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, 'Please, locate "NVIS6_0_LUT_AUST_FLAT.csv" vegetation code-name table and add to the project ./data folder. This table is required for the analysis.'))
        else:
            log(f"'NVIS6_0_LUT_AUST_FLAT.csv' vegetation code-name table was located. OK.")

        #### create a dictionary of the layers
        LAYERS = {}
        for name, value in LAYERS_PARAMS.items():
            layer = self.parameterAsVectorLayer(
                parameters,
                value['input'],
                context
            )
            #### USER FEEDBACK
            if layer is None:
                raise QgsProcessingException(self.invalidSourceError(parameters, f"the layer {value['input']} failed to load. Make sure it is available"))

            if layer.geometryType() != value['geometry']:
                raise QgsProcessingException(f"Wrong source type for Input layer {value['label']}. Must be a vector layer with {QgsWkbTypes.displayString(int(value['geometry']))} geometry")

            if value["check_field"] not in [x.name() for x in layer.dataProvider().fields()]:
                raise QgsProcessingException(f"Looks like you have selected wrong layer for {value['label']}.")
            else:
                log(f"Layer {value['label']} loaded and of correct type. OK.")

            LAYERS[name] = layer

        #### apply style to the layers
        for name, layer in LAYERS.items():
            layer.loadNamedStyle(LAYERS_PARAMS[name]['style'])
            layer.triggerRepaint()

        #### create a dictionary of the variables
        VARS = {}
        for name, value in VAR_PARAMS.items():
            '''' At some testing runs enterring string into number field cause Qgis crash. Additional test was implemented, but it was properly tested. '''
            if value['parameter'].typeName() == "string":  #### QgsProcessingParameterString
                try:
                    VARS[name] = self.parameterAsString(
                        parameters,
                        value["input"], #### string "INPUT_...",
                        context
                    )
                except:
                    raise QgsProcessingException(f"Wrong variable type {value['description']}, it must be String")
            elif value['parameter'].typeName() == "number":  #### QgsProcessingParameterNumber
                try:
                    VARS[name] = self.parameterAsDouble(
                        parameters,
                        value["input"], #### string "INPUT_...",
                        context
                    )
                except:
                    raise QgsProcessingException(f"Wrong variable type {value['description']}, it must be Number")

        #### USER FEEDBACK ON ERRORS
        for var in ["admin_area", "veg_name"]:
            if VARS[var] != VAR_PARAMS[var]['default']:
                raise QgsProcessingException(f"This is a test algorythm working only for '{VAR_PARAMS[var]['default']}' as {VAR_PARAMS[var]['description']}. Please correct and try again.")    

        #### create dictionary for outputs
        OUTPUT = {}
        for name, value in OUTPUT_PARAMS.items():
            OUTPUT[name] = self.addParameter(
                value['parameter'](
                    value['output'],
                    self.tr(value['label'])
                )
            )

        # Send some information to the user and Error Handling
        log(f"CRS is {LAYERS['admin'].sourceCrs().authid()}")
  
        #### Check for cancelation
        if feedback.isCanceled():
            return {}

        ###################################################################
        ##### PROCESSING
        ####################################################################

        ###############################################
        ##### PREPARE THE LAYERS
        ##### refactor veg ID field from text to integer. make sure it's not a string
        params = {
            'INPUT':veg_table,
            'FIELDS_MAPPING':[ 
                {'expression': '\"NVIS_ID\"','length': 10,'name': 'NVIS_ID','precision': 0,'type': 4},
                {'expression': '\"MVG_NAME\"','length': 0,'name': 'MVG_NAME','precision': 0,'type': 10},
                {'expression': '\"MVS_NAME\"','length': 0,'name': 'MVS_NAME','precision': 0,'type': 10}
            ],
            'OUTPUT':'TEMPORARY_OUTPUT'
        }
        veg_table = processing.run("native:refactorfields", params)['OUTPUT']

        #### SELECT ADMIN AREA FROM VICTORIA (this step is done already to save on data upload)
        params = {
            'INPUT': LAYERS['admin'],
            'FIELD': 'VGREG',
            'OPERATOR': 0,
            'VALUE': VARS["admin_area"],
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }
        LAYERS['admin'] = processing.run("native:extractbyattribute", params)['OUTPUT']
        log('-'*30)
        log(f"{VARS['admin_area']} area from {LAYERS_PARAMS['admin']['label']} was selected")

        #### REPROJECT AND CLIP ALL LAYERS BY THE STUDY AREA, IF VEGETATION, ADD VEGETATION NAMES
        for name, layer in LAYERS.items():
            if name != 'admin':
                ##### this commented out step reprojects and clips each layer by admin polygon
                # layer = load_reproject_and_clip(name, layer, LAYERS['admin'])
                if name == 'veg':
                    ##### join vegetation layers to code
                    params = {
                        'INPUT': layer,
                        'FIELD': 'NVISDSC1',
                        'INPUT_2': veg_table,
                        'FIELD_2':'NVIS_ID',
                        'FIELDS_TO_COPY': ['MVS_NAME'],
                        'METHOD': 0,
                        'DISCARD_NONMATCHING': True,
                        'PREFIX': '',
                        'OUTPUT':'TEMPORARY_OUTPUT'
                    }
                    layer = processing.run("native:joinattributestable", params)['OUTPUT']
                LAYERS[name] = layer

        ###############################################
        ##### SITE LOCATION

        #### PLANNING ZONES
        #### select by type
        expr = '\"ZONE_DESC\"  LIKE \'%WEDGE%\' OR \"ZONE_DESC\"  LIKE \'%FARMING%\' OR \"ZONE_DESC\"  LIKE \'%CONSERVATION%\' OR \"ZONE_DESC\"  LIKE \'%RECREATION%\' OR \"ZONE_DESC\"  LIKE \'%PUBLIC USE ZONE%\' '
        params = {
            'INPUT':LAYERS['zones'],
            'EXPRESSION':expr,
            'OUTPUT':'TEMPORARY_OUTPUT'
        }
        layer = processing.run("native:extractbyexpression", params)['OUTPUT']

        #### dissolve
        params = {
            'INPUT':layer,
            'FIELD':[],
            'OUTPUT':'TEMPORARY_OUTPUT'
        }
        layer = processing.run("native:dissolve", params)['OUTPUT']

        #### buffer the zones inside
        params = {
            'INPUT': layer, 
            'DISTANCE': VARS['facilities_buffer'],
            'SEGMENTS': 5,
            'END_CAP_STYLE': 0,
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'DISSOLVE': False,
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }
        layer = processing.run("native:buffer", params)['OUTPUT']

        LAYERS['zones'] = layer

        log(f"Suitable areas from layer {LAYERS_PARAMS['zones']['label']} were selected")

        #### HYDROLOGY
        #### select hydrology by watertype
        expr = '\"FTYPE_CODE\" LIKE \'%watercourse_area_river%\' OR \"FTYPE_CODE\" LIKE \'%wb_lake%\' '
        params = {
            'INPUT': LAYERS['hydro'],
            'EXPRESSION':expr,
            'OUTPUT':'TEMPORARY_OUTPUT'
        }
        layer = processing.run("native:extractbyexpression", params)['OUTPUT']

        #### select hydrology by size
        #### add shape area
        layer = add_shape_area(layer)
        params = {
            'INPUT': layer,
            'FIELD': 'Shape_Area',
            'OPERATOR': 3,  # >=
            'VALUE': VARS['min_water_area'],
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }
        layer = processing.run("native:extractbyattribute", params)['OUTPUT']

        #### buffer hydro layer
        params = {
            'INPUT': layer, 
            'DISTANCE': VARS['water_buffer'],
            'SEGMENTS': 5,
            'END_CAP_STYLE': 0,
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'DISSOLVE': False,
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }
        layer = processing.run("native:buffer", params)['OUTPUT']

        LAYERS['hydro'] = layer
        log(f"Suitable areas from layer {LAYERS_PARAMS['hydro']['label']} were selected")

        ##### FIND INTERSECTION OF LAYERS
        #### INTERSECT HYDRO BUFFER WITH ZONES
        log(" ")
        log(f"*****  Intersection of the layers can take several minutes due to large amount of data. *****")
        log(" ")
        params = {
            'INPUT': LAYERS['hydro'],
            'OVERLAY': LAYERS['zones'],
            'INPUT_FIELDS':[],
            'OVERLAY_FIELDS':[],
            'OVERLAY_FIELDS_PREFIX':'',
            'OUTPUT':'TEMPORARY_OUTPUT'
        }
        layer = processing.run("native:intersection", params)['OUTPUT']
        log(f"hydro and zones intersected")
        #### INTERSECT HYDRO BUFFER WITH VEGETATION
        params = {
            'INPUT': LAYERS['veg'],
            'OVERLAY': layer,
            'INPUT_FIELDS':[],
            'OVERLAY_FIELDS':[],
            'OVERLAY_FIELDS_PREFIX':'',
            'OUTPUT':'TEMPORARY_OUTPUT'
        }
        layer = processing.run("native:intersection", params)['OUTPUT']
        log(f"veg and others were intersected")
        #### remove unnecessary fields

        fieldNames = ['OBJECTID', 'NVISDSC1', 'Shape_Leng', 'Shape_Area', 'NAME', 'FTYPE_CODE', 'LGA', 'ZONE_DESC', 'MVS_NAME']
        selected_layer_pieces = reduce_attributes(layer, fieldNames)

        log(f"All layers were intersected")
        log(" ")
        ###############################################
        ##### SITE SELECTION        
        log(" ")
        log(f"***** Selection sites by vegetation type can take several minutes due to large amount of data. *****")
        log(" ")
        ##### CREATE DISSOLVED POLYGONS FOR EACH REGION
        #### disolve all
        params = {
            'INPUT': selected_layer_pieces,
            'FIELD':[],
            'OUTPUT':'TEMPORARY_OUTPUT'
            }
        selected_layer_areas = processing.run("native:dissolve", params)['OUTPUT']
        #### separate to multiparts
        params =  {
            'INPUT': selected_layer_areas,
            'OUTPUT':'TEMPORARY_OUTPUT'
        }
        selected_layer_areas = processing.run("native:multiparttosingleparts", params)['OUTPUT']

        #### remove unnecessary fields
        fieldNames = ['OBJECTID', 'Shape_Leng', 'Shape_Area']
        selected_layer_areas = reduce_attributes(selected_layer_areas, fieldNames)
       
        #### recalculate Area and perimeter
        selected_layer_pieces = add_shape_area(selected_layer_pieces)
        selected_layer_areas = add_shape_area(selected_layer_areas)


        ################################
        #### SELECT REGIONS WHERE CERTAIN VEGETATION IS PRESENT
        #### filter suitable areas
        n = selected_layer_areas.featureCount()
        log(f"areas: {n}, small piecses: {selected_layer_pieces.featureCount()}")

        fields = [x for x in selected_layer_pieces.dataProvider().fields()]  
        total = 100.0 / n if n != 0 else 0
        area_ids = []
        total = 100.0 / n if n != 0 else 0
        current = 0

        # Check whether the specified path exists or not
        if not os.path.exists(f"{self.csv_path}"):
            # Create a new directory because it does not exist 
            os.makedirs(f"{self.csv_path}")
            log("The new directory csv is created!")
        selected_layer_areas.startEditing()
        for area in selected_layer_areas.getFeatures():
            #### set the feature ID to consequent integers
            # area['OBJECTID'] = current + 1
            # selected_layer_areas.updateFeature(area)
            selected_layer_areas.changeAttributeValue(area.id(), 0, current + 1)
            selected_layer_areas.updateFeature(area)

            #### collect all parts of each dissolved area into one layer and convert attribures to df
            layer = QgsVectorLayer("Polygon", "temp", "memory")
            layer.dataProvider().addAttributes(fields)
            layer.updateFields() 
            parts = []
            for part in selected_layer_pieces.getFeatures():
                if area.geometry().intersects(part.geometry()):
                    parts.append(part)
            layer.dataProvider().addFeatures(parts)
            df = attributes_to_df(layer)

            #### select areas where "Temperate tussock grasslands" is present    
            if VARS["veg_name"] in set(df['MVS_NAME'].tolist()):
                #### add the dissolved area id for selection
                area_ids.append(area.id())

                #### get stats on vegetation
                veg_sum_df = df.groupby(['MVS_NAME']).agg({'Shape_Area': 'sum'})
                veg_sum_df['veg_perc'] = veg_sum_df['Shape_Area'] / veg_sum_df['Shape_Area'].sum()
                veg_sum_df.to_csv(f"{self.csv_path}/vegetation_stats_area_{current+1}.csv")

                log(f"vegetation statistics for area {area.id()} saved to '.data/csv/' folder")

            current +=1
            feedback.setProgress(int(current * total))
        selected_layer_areas.commitChanges()

        selected_layer_areas.selectByIds(area_ids)
        result_layer = processing.run("native:saveselectedfeatures", {'INPUT': selected_layer_areas, 'OUTPUT': 'memory:'})['OUTPUT']
        selected_layer_areas.removeSelection()


        ###############################################
        ##### RESULT OUTPUT
        add_to_map = [result_layer]
        result = {}
        for i, layer in enumerate(add_to_map):
            outlayer = OUTPUT_PARAMS[f"output_{i+1}"]["output"]
            log(f"{outlayer}")
            (sink, i) = self.parameterAsSink(
                # OUTPUT[f"OUTPUT_LAYER_{i+1}"],
                parameters,
                outlayer,
                context,
                layer.fields(),
                layer.wkbType(),
                layer.sourceCrs()
            )
            if sink is None:
                raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

            features = layer.getFeatures()

            for current, feature in enumerate(features):
                # Add a feature in the sink
                sink.addFeature(feature, QgsFeatureSink.FastInsert)
            result[outlayer] = i
        return result
        

        
