import logging

import subprocess

import sys

from boto3 import Session
from django.db import models

from preprddeploy.settings import ACCOUNT_NAME

logger = logging.getLogger('deploy')


class RegionInfo(models.Model):
    region = models.CharField(max_length=32, unique=True)
    deploy_order = models.IntegerField()
    abbr = models.CharField(max_length=10)
    chinese_name = models.CharField(max_length=50)

    def __unicode__(self):
        return '%s| %s| %s| %s' % (self.region, self.deploy_order, self.abbr, self.chinese_name)

    @staticmethod
    def get_regions_infos(columns, include_regions=None, exclude_regions=None):
        """
        get region infos contain specify columns.
        Args:
            columns (list): column names you want to contains in region info.
            include_regions (list): specify region list want to get infos. if set, arg excludeRegions will be ignore.
            exclude_regions (list): exclude regions.
        Returns:
            a list of tuples, each tuple contains the region info of columnList
        """
        if include_regions is not None:
            region_infos_obj = RegionInfo.objects.filter(region__in=include_regions)
        elif exclude_regions is not None:
            region_infos_obj = RegionInfo.objects.exclude(region__in=exclude_regions)
        else:
            region_infos_obj = RegionInfo.objects.all()
        if not region_infos_obj:
            logger.info('no region info found. include %s, exclude: %s' % (include_regions, exclude_regions))
            return []
        region_infos = region_infos_obj.values_list(*columns)
        return list(region_infos)

    @staticmethod
    def get_all_regions(excludes=None):
        region_infos = RegionInfo.get_regions_infos(['region'], exclude_regions=excludes)
        return [region_info[0] for region_info in region_infos]

    @staticmethod
    def get_all_regions_group_by_order():
        """
            get all regions from autodeploy.models.RegionInfo,
            return a dict {order: region}
        """
        columns = ['deploy_order', 'region']
        regioninfos_order = RegionInfo.get_regions_infos(columns)
        order_region_dict = {}
        for regionInfo in regioninfos_order:
            region = regionInfo[columns.index('region')]
            deploy_order = regionInfo[columns.index('deploy_order')]
            if deploy_order in order_region_dict:
                order_region_dict[deploy_order].append(region)
            else:
                order_region_dict[deploy_order] = [region]
        return order_region_dict

    @staticmethod
    def get_region_attribute(region_name, attribute_name):
        """
        get region attribute(attrName) by region name
        Args:
            region_name (string): region name
            attribute_name (string): region's attribute name. must be one of columns of RegionInfo.
        """
        region_info_obj = RegionInfo.objects.filter(region=region_name)
        if not region_info_obj:
            error_msg = 'no region info of region name: %s' % region_name
            logger.error(error_msg)
            raise Exception(error_msg)
        return region_info_obj.values_list(attribute_name, flat=True)[0]

    @staticmethod
    def get_region(request):
        """
        get region arg in request, if arg not found, get current region
        Args:
            request (django.http.request.HttpRequest)
        """
        if 'region' in request.GET:
            current_region = request.GET['region']
        else:
            current_region = RegionInfo.get_current_region()
        return current_region

    @staticmethod
    def get_current_region():
        platform = sys.platform
        if platform == 'linux2':
            current_available_zone = RegionInfo.get_current_available_zone()
            return current_available_zone[:-1]
        else:
            # for test in windows
            return 'cn-north-1'

    @staticmethod
    def get_current_available_zone():
        cmd = ['wget', '-q', '-O', '-', 'http://169.254.169.254/latest/meta-data/placement/availability-zone']
        return subprocess.check_output(cmd)


class AwsAccount(models.Model):
    name = models.CharField(max_length=30)
    account_id = models.CharField(max_length=24)
    access_key_id = models.CharField(max_length=40)
    secret_access_key = models.CharField(max_length=80)
    valid_regions = models.ManyToManyField(RegionInfo)

    def __unicode__(self):
        valid_regions = self.valid_regions.all()
        region_list = []
        for region in valid_regions:
            region_list.append(region.abbr)
        return '%s| %s%s| %s%s| %s' % (
            self.name,
            '*' * len(self.access_key_id[:-4]),
            self.access_key_id[-4:],
            '*' * len(self.secret_access_key[:-4]),
            self.secret_access_key[-4:],
            ','.join(region_list)
        )

    @staticmethod
    def get_awssession(region, account=ACCOUNT_NAME):
        if region == 'cn-north-1':
            account_name = 'cn-%s' % account
        else:
            account_name = 'en-%s' % account
        try:
            aws_account = AwsAccount.objects.get(name=account_name)
        except AwsAccount.DoesNotExist:
            logger.error('account not found for region: %s, please contact administrator' % region)
            raise
        aws_session = Session(aws_access_key_id=aws_account.access_key_id,
                              aws_secret_access_key=aws_account.secret_access_key,
                              region_name=region)
        return aws_session


class AwsResource(models.Model):
    resource_name = models.CharField(max_length=500)
    resource_id = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100)
    parent = models.ForeignKey('self', default=None, null=True, blank=True)
    region = models.ForeignKey(RegionInfo)
    account = models.ForeignKey(AwsAccount)

    def __unicode__(self):
        return "['%s', '%s']" % (self.name, self.resource_id)

    def as_option(self):
        return [self.name, self.resource_id]
