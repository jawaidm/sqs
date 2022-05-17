#from django.db import models
from django.contrib.gis.db import models
from django.contrib.postgres.fields.jsonb import JSONField
#from django.conf import settings
from reversion import revisions
from reversion.models import Version
import geopandas as gpd
import json


# Next lin needed, to migrate ledger_api_clinet module
from ledger_api_client.ledger_models import EmailUserRO as EmailUser

import logging
logger = logging.getLogger(__name__)

class RevisionedMixin(models.Model):
    """
    A model tracked by reversion through the save method.
    """
    def save(self, **kwargs):
        #import ipdb; ipdb.set_trace()
        if kwargs.pop('no_revision', False):
            super(RevisionedMixin, self).save(**kwargs)
        else:
            with revisions.create_revision():
                revisions.set_user(kwargs.pop('version_user', EmailUser.objects.get(id=255)))
                if 'version_user' in kwargs:
                    revisions.set_user(kwargs.pop('version_user', None))
                if 'version_comment' in kwargs:
                    revisions.set_comment(kwargs.pop('version_comment', ''))
                super(RevisionedMixin, self).save(**kwargs)

    @property
    def created_date(self):
        #return revisions.get_for_object(self).last().revision.date_created
        return Version.objects.get_for_object(self).last().revision.date_created

    @property
    def modified_date(self):
        #return revisions.get_for_object(self).first().revision.date_created
        return Version.objects.get_for_object(self).first().revision.date_created

    class Meta:
        abstract = True


#class DpawRegion(models.Model):
#    fid = models.CharField(max_length=64)
#    region = models.CharField(max_length=64)
#    ogc_fid = models.IntegerField(null=True, blank=True)
#    office = models.CharField(max_length=64, null=True, blank=True)
#    hectares = models.FloatField(null=True, blank=True)
#    md5_rowhash = models.CharField(max_length=64, null=True, blank=True)
#
#    geom = models.MultiPolygonField(srid=4283)
#
#    class Meta:
#        app_label = 'sqs'
#
#    def __str__(self):
#        return self.region


class Feature(models.Model):
    properties = JSONField(db_index=True)
    geometry = models.MultiPolygonField()
    #layer = models.ForeignKey('Layer', on_delete=models.CASCADE, related_name='%(class)s_features')
    layer = models.ForeignKey('Layer', on_delete=models.CASCADE, related_name='features')
 
    @property
    def srid(self):
        return self.geometry.crs.srid

    class Meta:
        app_label = 'sqs'

    @property
    def fid(self):
        return self.properties['id'] if 'id' in self.properties else 'NO_ID'

    def __str__(self):
        return f'{self.fid}'


#class LayerBase(RevisionedMixin, models.Model):
class LayerBase(models.Model):
    #name = models.CharField(max_length=64)
    #type = models.CharField(max_length=32, null=True, blank=True)
    type_name = models.CharField(max_length=64)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    #srid = models.IntegerField(null=True, blank=True)

    geojson = JSONField('Layer GeoJSON')

    @property
    def srid(self):
        if hasattr(self, 'features') and self.features.exists():
            feature = self.features.first()
            return feature.srid
        return None

    @property
    def layer_to_gdf(self):
        """
        Layer to Geo Dataframe (converted to settings.CRS ['epsg:4326'])
        """
        gdf = gpd.read_file(json.dumps(self.geojson))
        #return gdf.to_crs(settings.CRS)
        return gdf.to_crs('epsg:4326')

    class Meta:
        abstract = True
        #app_label = 'sqs'

    def __str__(self):
        return f'{self.type_name} - {self.created.strftime("%m/%d/%YT%H:%M:%S")}' 


class Layer(LayerBase):

    current = models.BooleanField()

    @property
    def layer_history(self):
        return LayerHistory.objects.filter(layer=self).order_by('-version')

    @property
    def version(self):
        #import ipdb; ipdb.set_trace()
        return LayerHistory.objects.filter(layer=self).order_by('-version')[0].version
        #if LayerHistory.objects.filter(layer=self):
        #    return LayerHistory.objects.filter(layer=self).order_by('-version')[0].version
        #return None

    def save(self, *args, **kwargs):
        from sqs.utils.loader_utils import has_layer_changed
        import ipdb; ipdb.set_trace()
        super(Layer, self).save(*args, **kwargs)

        # save layer history
        layer_history = self.layer_history
        if not layer_history or has_layer_changed(self.layer_to_gdf, layer_history[0].layer_to_gdf):
            newLayer = LayerHistory(layer=self, type_name=self.type_name, geojson=self.geojson)
            newLayer.save()

    class Meta:
        app_label = 'sqs'

    def __str__(self):
        return f'{self.type_name}, version: {self.version}, created: {self.created.strftime("%m/%d/%YT%H:%M:%S")}'


class LayerHistory(LayerBase):
    """ From https://stackoverflow.com/questions/10540111/store-versioned-history-of-field-in-a-django-model """
    version = models.IntegerField(editable=False)
    layer = models.ForeignKey('Layer', on_delete=models.CASCADE, related_name='+')

    def save(self, *args, **kwargs):
        # start with version 1 and increment it for each layer
        #current_version = LayerHistory.objects.filter(layer=self.layer).order_by('-version')[:1]
        current_version = LayerHistory.objects.filter(layer__type_name=self.layer.type_name).order_by('-version')[:1]
        self.version = current_version[0].version + 1 if current_version else 1
        super(LayerHistory, self).save(*args, **kwargs)

    def __str__(self):
        return f'{self.type_name}, verson: {self.version}, created: {self.created.strftime("%m/%d/%YT%H:%M:%S")}'

    class Meta:
        app_label = 'sqs'
        unique_together = ('version', 'layer',)


#import reversion
#reversion.register(Layer, follow=['features'])
#reversion.register(LayerHistory)

