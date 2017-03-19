from django.db import models

# Create your models here.
from common.models import RegionInfo


class BasicServiceDeployInfo(models.Model):
    service_name = models.CharField(max_length=50, unique=True)
    regions = models.ManyToManyField(RegionInfo)
    order = models.IntegerField()

    def __unicode__(self):
        regions = self.regions.all()
        region_names = []
        for region in regions:
            region_names.append(region.region)
        return '%s| %s| %s' % (self.service_name, self.order, region_names)

