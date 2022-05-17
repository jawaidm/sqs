from django.core.management.base import BaseCommand
from django.conf import settings
import subprocess
import os
from sqs.utils.loader_utils import LayerLoader #, has_layer_changed
from sqs.components.masterlist.models import Layer, LayerHistory, Feature


import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Load Layer util
    """

    help = 'Load Layer util: ./manage.py layer_loader --url \'https://kmi.dbca.wa.gov.au/geoserver/cddp/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=cddp:dpaw_regions&maxFeatures=50&outputFormat=application%2Fjson\' --type_name cddp:dpaw_regions'
    #log_file = os.getcwd() + '/logs/layer_loader.log'

    def add_arguments(self, parser):
        parser.add_argument('--url', nargs='?', type=str, default='https://kmi.dbca.wa.gov.au/geoserver/cddp/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=cddp:dpaw_regions&maxFeatures=50&outputFormat=application%2Fjson')
        parser.add_argument('--type_name', nargs='?', type=str, default='cddp:dpaw_regions')

    def handle(self, *args, **options):
        type_name = options['type_name']
        url = options['url']
        #import ipdb; ipdb.set_trace()
        layer_loader = LayerLoader(url=url, type_name=type_name)
        layer_loader.load_layer()

        for l in LayerHistory.objects.all():
            #print(l.id, l, l.layer.features.count(), l.layer.features.values_list('id', flat=True))
            print(l.id, l)


