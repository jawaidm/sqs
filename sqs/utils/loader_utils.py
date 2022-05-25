from django.contrib.gis.geos import GEOSGeometry, Polygon, MultiPolygon
from django.conf import settings
from django.db import transaction

import geopandas as gpd
import requests
import json
import os

from sqs.components.masterlist.models import Layer, Feature#, LayerHistory, Feature

import logging
logger = logging.getLogger(__name__)

class LayerLoader():
    """
    In [22]: from sqs.utils.loader_utils import LayerLoader
    In [23]: l=LayerLoader(url,name)
    In [24]: l.load_layer()


    In [23]: layer=Layer.objects.last()
    In [25]: layer.features.all().count()
    Out[25]: 9

    In [25]: layer.srid
    Out[25]: 4326

    """

    def __init__(self, url='https://kmi.dbca.wa.gov.au/geoserver/cddp/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=cddp:dpaw_regions&maxFeatures=50&outputFormat=application%2Fjson', type_name='cddp:dpaw_regions'):
        self.url = url
        #self.type = name.split(':')[0]
        #self.name = name.split(':')[1]
        self.type_name = type_name
        
    def retrieve_layer(self):
        try:
            res = requests.get('{}'.format(self.url), auth=(settings.LEDGER_USER,settings.LEDGER_PASS), verify=False)
            res.raise_for_status()
            #cache.set('department_users',json.loads(res.content).get('objects'),10800)
            return res.json()
        except:
            raise

    def retrieve_layer_from_file(self, filename='sqs/data/json/dpaw_regions.json'):
        try:
            with open(filename) as json_file:
                data = json.load(json_file)
            return data
        except:
            raise


    def load_layer(self, geojson=None):

        #layer_gdf = gpd.read_file('sqs/data/json/dpaw_regions.json')
        #layer_gdf = gpd.read_file(io.BytesIO(geojson_str))
        import ipdb; ipdb.set_trace()

        try:
            if not geojson:
                geojson = self.retrieve_layer()
            layer_gdf1 = gpd.read_file(json.dumps(geojson))
            #geojson = self.retrieve_layer_from_file()
            #layer_gdf1 = gpd.read_file(json.dumps(geojson))

            # uniformly projected layers in DB (allows buffer in meters by default)
            layer_gdf1.to_crs(settings.CRS, inplace=True) 

            layer_qs = Layer.objects.filter(type_name=self.type_name, current=True)
            current_layer = None
            msg = ''
            if layer_qs.count() == 1:
                # check if this layer already exists in DB. If it does exist, return (do nothing) if it has NOT changed

                current_layer = layer_qs[0]
                #import ipdb; ipdb.set_trace()
                layer_gdf2 = gpd.read_file(json.dumps(current_layer.geojson))
                layer_gdf2.to_crs(settings.CRS, inplace=True) 

                if not has_layer_changed(layer_gdf1, layer_gdf2):
                    # no change in geojson
                    msg = f'LAYER NOT SAVED/UPDATED: No change in layer'
                    logger.info(msg) 
                    return msg

            with transaction.atomic():
                if current_layer:
                    current_layer.current = False
                    current_layer.save()

                #import ipdb; ipdb.set_trace()
                layer = Layer.objects.create(type_name=self.type_name, geojson=geojson, current=True)
                msg = f'Created Layer: {layer}, with {layer.features.count()} features, srid {layer.srid}'
                logger.info(msg)

        except Exception as e: 
            raise repr(e)
        
        return  msg


def has_layer_changed(layer_gdf1, layer_gdf2):

    #import ipdb; ipdb.set_trace()
    # check columns are the same
    cols1 = list(layer_gdf1.columns.sort_values())
    cols2 = list(layer_gdf2.columns.sort_values())
    if cols1 != cols2:
        # GeoJSON has changed
        return True

    # remove the 'id' column from layer_gdf's and sort the columns [index(axis=1)]
    layer_gdf1 = layer_gdf1.loc[:, layer_gdf1.columns!='id'].sort_index(axis=1)
    layer_gdf2 = layer_gdf2.loc[:, layer_gdf2.columns!='id'].sort_index(axis=1)

    # check geo dataframes are the same
    #if (layer_gdf1 == layer_gdf2).eq(True).all().eq(True).all():
    if layer_gdf1.equals(layer_gdf2):
        # GeoJSON has not changed
        return False

    return True

