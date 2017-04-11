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

    @staticmethod
    def get_all_basic_service(region, exclude=None):
        region_obj = RegionInfo.objects.get(region=region)
        if exclude:
            basic_service_list = region_obj.basicservicedeployinfo_set\
                                           .exclude(service_name__in=exclude)\
                                           .values_list('service_name', flat=True)
        else:
            basic_service_list = region_obj.basicservicedeployinfo_set.all().values_list('service_name', flat=True)
        return basic_service_list
