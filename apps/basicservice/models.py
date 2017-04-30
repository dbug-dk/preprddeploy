import json

from django.db import models

# Create your models here.
from common.models import RegionInfo, AwsAccount


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

    @staticmethod
    def find_all_instances(region, account_name):
        region_obj = RegionInfo.objects.get(region=region)
        basicservice_objs = region_obj.basicservicedeployinfo_set.all()
        basic_service_names = [service.service_name for service in basicservice_objs]
        session = AwsAccount.get_awssession(region, account_name)
        ec2conn = session.resource('ec2')
        instances = ec2conn.instances.filter(Filters=[
            {
                'Name': 'tag:Name',
                'Values': ['*-%s-*' % service_name for service_name in basic_service_names]
            }
        ])
        return instances


class BasicServiceIps(models.Model):
    service_name = models.CharField(max_length=50)
    account = models.CharField(max_length=6, choices=(('beta', 'preprd'), ('prd', 'prd')))
    ips = models.TextField()

    class Meta:
        unique_together = (('service_name', 'account'),)

    def __unicode__(self):
        return '%s| %s' % (self.service_name, self.account)

    @staticmethod
    def get_all_basic_ips():
        all_basic_ip_objs = BasicServiceIps.objects.all()
        betacontext = {'env': 'beta'}
        prdcontext = {'env': 'prd'}
        for basic_service_ips in all_basic_ip_objs:
            service_name = basic_service_ips.service_name
            service_ips = basic_service_ips.ips
            account_name = basic_service_ips.account
            if account_name == 'beta':
                betacontext.update({service_name: json.loads(service_ips)})
            elif account_name == 'prd':
                prdcontext.update({service_name: json.loads(service_ips)})
            else:
                raise Exception('account name is not correct, please check the database or update.')
        return betacontext, prdcontext
