from django.db import models

# Create your models here.
from common.models import RegionInfo
from elb import elb_api
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

    @staticmethod
    def save_elb_info(loadbalancer, region):
        """
        save loadbalancer infomation to db
        Args:
            loadbalancer (dict): elb infomations return by describe-loadbalancers.
            region (RegionInfo): RegionInfo object
        """
        loadbalancer_name = loadbalancer.get('LoadBalancerName')
        module_name = elb_api.get_module_name(loadbalancer_name)
        module_info = ModuleInfo.objects.get(module_name=module_name)
        elb_info = LoadbalancerInfo(module=module_info, elb_name=loadbalancer_name, region=region,
                                    elb_scheme=loadbalancer['Scheme'], dns_name=loadbalancer['DNSName'])
        elb_info.save()
