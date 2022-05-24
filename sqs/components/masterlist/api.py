from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db.models import Q

from wsgiref.util import FileWrapper
from rest_framework import viewsets, serializers, status, generics, views
#from rest_framework.decorators import detail_route, list_route, renderer_classes, parser_classes
from rest_framework.decorators import action, renderer_classes, parser_classes
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser, BasePermission
from rest_framework.pagination import PageNumberPagination
import traceback
import json

from sqs.components.masterlist.models import Layer, LayerHistory, Feature
from sqs.utils.geoquery_utils import LayerQueryHelper, PointQueryHelper
from sqs.components.masterlist.serializers import GeoTestSerializer, LayerSerializer, FeatureGeometrySerializer

import logging
#logger = logging.getLogger('payment_checkout')
logger = logging.getLogger(__name__)


#class _GeoTestViewSet(viewsets.ReadOnlyModelViewSet):
#    queryset = Layer.objects.all().order_by('id')
#    serializer_class = GeoTestSerializer
#
#    @detail_route(methods=['GET',])
#    def layers(self, request, *args, **kwargs):            
#        instance = self.get_object()
#        qs = instance.land_parks
#        qs.order_by('id')
#        serializer = ParkSerializer(qs,context={'request':request}, many=True)
#        return Response(serializer.data)
#
#    @detail_route(methods=['GET',])
#    def parks(self, request, *args, **kwargs):            
#        instance = self.get_object()
#        qs = instance.parks
#        qs.order_by('id')
#        serializer = ParkSerializer(qs,context={'request':request}, many=True)
#        return Response(serializer.data)


class LayerViewSet(viewsets.ReadOnlyModelViewSet):
    """ http://localhost:8002/api/layers.json """
    queryset = Layer.objects.filter(current=True).order_by('id')
    serializer_class = LayerSerializer

    @action(detail=True, methods=['GET',])
    def layer(self, request, *args, **kwargs):            
        """ http://localhost:8002/api/layers/50/layer.json """
        instance = self.get_object()
        seture_featuresrializer = self.get_serializer(instance) 
        return Response(serializer.data)

    @action(detail=False, methods=['POST',]) # POST because request will contain GeoJSON polygon to intersect with layer stored on SQS. If layer does not exist, SQS will retrieve from KMI
    def spatial_query(self, request, *args, **kwargs):            
        """ 
        http://localhost:8002/api/layers/spatial_query.json 

        curl -d @sqs/data/json/goldfields_curl_query.json -X POST http://localhost:8002/api/layers/spatial_query.json --header "Content-Type: application/json" --header "Accept: application/json"

        or
        curl -d '{"names":["office","region"],"geojson":{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[124.12353515624999,-30.391830328088137],[124.03564453125,-31.672083485607377],[126.69433593749999,-31.615965936476076],[127.17773437499999,-29.688052749856787],[124.12353515624999,-30.391830328088137]]]}}]}}' -X POST http://localhost:8002/api/layers/spatial_query.json --header "Content-Type: application/json"

        """
        layer_data = request.data['layers']
        geojson = request.data['geojson']

        import ipdb; ipdb.set_trace()
        helper = LayerQueryHelper(layer_data, geojson)
        #res = helper.intersection(['region', 'office'], request.data)
        res = helper.spatial_join()
        return Response(res)

    @action(detail=False, methods=['POST',]) # POST because request will contain GeoJSON polygon to intersect with layer stored on SQS. If layer does not exist, SQS will retrieve from KMI
    def point_query(self, request, *args, **kwargs):            
        """ 
        http://localhost:8002/api/layers/point_query.json

        curl -d '{"layer_name": "cddp:dpaw_regions", "layer_attrs":["office","region"], "longitude": 121.465836, "latitude":-30.748890}' -X POST http://localhost:8002/api/layers/point_query.json --header "Content-Type: application/json" --header "Accept: application/json"
        """
        try:
            layer_name = request.data['layer_name']
            longitude = request.data['longitude']
            latitude = request.data['latitude']
            layer_attrs = request.data.get('layer_attrs', [])
            predicate = request.data.get('predicate', 'within')

            #import ipdb; ipdb.set_trace()
            helper = PointQueryHelper(layer_name, layer_attrs, longitude, latitude)
            res = helper.spatial_join(predicate=predicate)
            return Response(res)
        except KeyError as e:
            #return Response(repr(e))
            raise repr(e)
        except Exception as e:
            #return Response(str(e))
            raise str(e)




class FeatureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Layer.objects.all().order_by('id')
    serializer_class = LayerSerializer

    @action(detail=True, methods=['GET',])
    def features(self, request, *args, **kwargs):            
        """ http://localhost:8002/api/layer_features/50/features.json """
        #import ipdb; ipdb.set_trace()
        instance = self.get_object()
        qs = instance.features.all()
        qs.order_by('id')
        serializer = FeatureGeometrySerializer(qs,context={'request':request}, many=True)
        return Response(serializer.data)

#    @action(detail=True, methods=['POST',]) # POST because request will contain GeoJSON polygon to intersect with layer stored on SQS
#    def intersect(self, request, *args, **kwargs):            
#        """ 
#        http://localhost:8002/api/layer_features/50/intersect.json 
#
#        curl -d @sqs/data/json/goldfields_curl_query.json -X POST http://localhost:8002/api/layer_features/50/intersect.json --header "Content-Type: application/json" --header "Accept: application/json"
#        or
#        curl -d '{"names":["office","region"],"geojson":{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[124.12353515624999,-30.391830328088137],[124.03564453125,-31.672083485607377],[126.69433593749999,-31.615965936476076],[127.17773437499999,-29.688052749856787],[124.12353515624999,-30.391830328088137]]]}}]}}' -X POST http://localhost:8002/api/layer_features/5/intersect.json --header "Content-Type: application/json"
#
#        """
#        import ipdb; ipdb.set_trace()
#        names = request.data['names']
#        geojson = request.data['geojson']
#        type_name = request.data['type_name']
#        layer = self.get_object()
#
#
#        helper=GeoQueryHelper(layer)
#        #res = helper.intersection(['region', 'office'], request.data)
#        res = helper.intersection(names, geojson)
#        return Response(res)



#    @detail_route(methods=['GET',])
#    def internal_proposal(self, request, *args, **kwargs):
#        instance = self.get_object()
#        serializer = InternalProposalSerializer(instance,context={'request':request})
#        if instance.application_type.name==ApplicationType.TCLASS:
#            serializer = InternalProposalSerializer(instance,context={'request':request})
#        elif instance.application_type.name==ApplicationType.FILMING:
#            serializer = InternalFilmingProposalSerializer(instance,context={'request':request})
#        elif instance.application_type.name==ApplicationType.EVENT:
#            serializer = InternalEventProposalSerializer(instance,context={'request':request})
#        return Response(serializer.data)

