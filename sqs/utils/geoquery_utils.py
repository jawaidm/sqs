from django.contrib.gis.geos import GEOSGeometry, Polygon, MultiPolygon
from django.conf import settings
from django.db import transaction

import pandas as pd
import geopandas as gpd
import requests
import json
import os
import io

from sqs.components.masterlist.models import Layer, Feature#, LayerHistory

import logging
logger = logging.getLogger(__name__)


#class GeoQueryHelper():
#
#    def __init__(self, layer):
#        self.layer = layer if isinstance(layer, Layer) else gdf.read_file(layer)
#
#    def filter_dict(self, feature, required_attributes):
#        return dict((key,value) for key, value in feature.attributes.items() if key in required_attributes)
#
#    def intersection_v1(self, required_attributes, polygon_geojson=None):
#
#        #with open('sqs/data/json/south_wa.json') as f:
#        if not polygon_geojson:
#            with open('sqs/data/json/goldfields.json') as f:
#                polygon_geojson = json.load(f)
#
#        intersection_geom = []
#        for ft in polygon_geojson['features']:
#            geom_str = json.dumps(ft['geometry'])
#            geom = GEOSGeometry(geom_str)
#            try:
#                if isinstance(geom, MultiPolygon):
#                    continue
#
#                elif isinstance(geom, Polygon):
#                    geom = MultiPolygon([geom])
#             
#                    #for region in DpawRegion.objects.filter(geom__intersects=geom):
#                    #import ipdb; ipdb.set_trace()
#                    for feature in self.layer.features.filter(geometry__intersects=geom):
#                        #intersection_geom.append(geom.intersection(feature.geometry))
#                        intersection_geom.append(self.filter_dict(feature, required_attributes))
#                        #print(feature)
#                    #import ipdb; ipdb.set_trace()
#                print(intersection_geom)
#            except TypeError as e:
#                print(e)
#        return intersection_geom
#
#    def intersection(self, required_attributes, mpoly=None):
#
#        import ipdb; ipdb.set_trace()
#        if not mpoly:
#            mpoly = gpd.read_file('sqs/data/json/goldfields.json')
#        else:
#            mpoly = gpd.read_file(json.dumps(mpoly))
#
#        # 
#        if mpoly.crs.srs != 'EPSG:4236':
#            mpoly.to_crs('EPSG:4236', inplace=True)
#
#        layer_gdf = self.layer.layer_to_gdf
#        layer_gdf.to_crs(mpoly.crs, inplace=True)
#        overlay = layer_gdf.overlay(mpoly, how='intersection')
#
#        return overlay[required_attributes].to_json()


class LayerQueryHelper():

    def __init__(self, layer_data, geojson):
        #self.layer = layer if isinstance(layer, Layer) else gdf.read_file(layer)
        self.layer_data = layer_data
        self.geojson = self.read_geojson(geojson)

    def read_geojson(self, geojson):
        """ geojson is the use specified polygon, used to intersect the layers """
        mpoly = gpd.read_file(json.dumps(geojson))
        if mpoly.crs.srs != settings.CRS:
            # CRS = 'EPSG:4236'
            mpoly.to_crs(settings.CRS, inplace=True)

        return mpoly

    def spatial_join(self):

        import ipdb; ipdb.set_trace()

        res = [] 
        for data in self.layer_data:
            
            column_names = data['names']
            type_name = data['type_name']

            layer = Layer.objects.get(type_name=type_name, current=True)
            layer_gdf = layer.layer_to_gdf
            if layer_gdf.crs.srs != settings.CRS:
                layer_gdf.to_crs(settings.CRS, inplace=True)

            overlay_res = layer_gdf.overlay(self.geojson, how='intersection')
            res.append(
                dict(type_name=type_name, res=overlay_res[column_names].to_json())
            )

        return res


class PointQueryHelper():
    """
    pq = PointQueryHelper('cddp:dpaw_regions', ['region','office'], 121.465836, -30.748890)
    pq.spatial_join()
    """

    def __init__(self, layer_name, layer_attrs, longitude, latitude):
        self.layer_name = layer_name
        self.layer_attrs = layer_attrs
        self.longitude = longitude
        self.latitude = latitude

    def spatial_join(self, predicate='within'):

        #import ipdb; ipdb.set_trace()
        layer = Layer.objects.get(type_name=self.layer_name, current=True)
        layer_gdf = layer.layer_to_gdf

        # Lat Long for Kalgoolie, Goldfields
        # df = pd.DataFrame({'longitude': [121.465836], 'latitude': [-30.748890]})
        # settings.CRS = 'EPSG:4236'
        df = pd.DataFrame({'longitude': [self.longitude], 'latitude': [self.latitude]})
        point_gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs=settings.CRS)

        overlay_res = gpd.sjoin(point_gdf, layer_gdf, predicate=predicate)

        attrs_exist = all(item in overlay_res.columns for item in self.layer_attrs)
        errors = None
        if len(self.layer_attrs)==0 or overlay_res.empty:
            # no attrs specified - so return them all
            layer_attrs = overlay_res.drop('geometry', axis=1).columns
        elif len(self.layer_attrs)>0 and attrs_exist:
            # return only requested attrs
            layer_attrs = self.layer_attrs 
        else: #elif not attrs_exist:
            # one or more attr requested not found in layer - return all attrs and error message
            layer_attrs = overlay_res.drop('geometry', axis=1).columns
            errors = f'Attribute(s) not available: {self.layer_attrs}. Attributes available in layer: {list(layer_attrs.array)}'

        #layer_attrs = self.layer_attrs if len(self.layer_attrs)>0 and attrs_exist else overlay_res.drop('geometry', axis=1).columns
        overlay_res = overlay_res.iloc[0] if not overlay_res.empty else overlay_res # convert row to pandas Series (removes index)

        try: 
            res = dict(type_name=self.layer_name, errors=errors, res=overlay_res[layer_attrs].to_dict() if not overlay_res.empty else None)
        except Exception as e:
            logger.error(e)
            res = dict(type_name=self.layer_name, error=str(e), res=overlay_res.to_dict() if not overlay_res.empty else None)

        return res

