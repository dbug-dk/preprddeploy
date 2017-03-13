from django.db import models

# Create your models here.
from common.models import RegionInfo
from module.models import ModuleInfo


class LoadbalancerInfo(models.Model):
    module = models.ForeignKey(ModuleInfo)
    elb_name = models.CharField(max_length=100)
    region = models.ForeignKey(RegionInfo)
    elb_scheme = models.CharField(max_length=20, choices=(
        ('internet-facing', 'internet-facing'),
        ('internal', 'internal')
    ))
    dns_name = models.CharField(max_length=100)

    class Meta:
        unique_together = (("elb_name", "region"),)

    def __unicode__(self):
        return '%s| %s' % (self.elb_name, self.region.region)



