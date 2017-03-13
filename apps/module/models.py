#! coding=utf8
# Filename    : models.py
# Description :
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging

from django.contrib.auth.models import User
from django.db import models

from apps.common.models import RegionInfo, AwsAccount, AwsResource

logger = logging.getLogger('deploy')


class ModuleInfo(models.Model):
    module_name = models.CharField(max_length=30, unique=True)
    update_version = models.CharField(max_length=20, blank=True, null=True)
    current_version = models.CharField(max_length=20, blank=True, null=True)
    instance_count = models.IntegerField(default=2)
    regions = models.ManyToManyField(RegionInfo)
    elb_names = models.CharField(max_length=1000, null=True, blank=True)
    user = models.ForeignKey(User, related_name='module_user', on_delete=models.SET_NULL, null=True)
    module_type = models.CharField(max_length=10)
    order = models.IntegerField(default=-1)

    def __unicode__(self):
        regions = self.regions.all()
        regionabbrs = []
        for region in regions:
            regionabbrs.append(region.abbr)
        return self.module_name + '|' + ','.join(regionabbrs) + '|' + self.module_type

    def to_dict(self, bool_operate):
        """
        return dict for current module info to be shown in datatables
        Args:
            bool_operate (bool): if user has operate auth with module page
        """
        module_infos = {}
        exclude_fields = ['instance_count', 'elb_names']
        special_fields = ['user', 'regions']
        for field in self._meta.fields:
            field_name = field.name
            if field_name in exclude_fields + special_fields:
                continue
            else:
                module_infos.update({field_name: getattr(self, field_name)})
        for field_name in special_fields:
            module_infos.update(getattr(self, 'deal_field_%s' % field_name)())
        logger.debug('module infos without operations: %s' % module_infos)
        operation = '''<button class="btn btn-info btn-xs" onclick="showLaunchParams('%s')">
                            <span class="fa fa-eye">
                                view
                            </span>
                        </button>
                    ''' % self.module_name
        if bool_operate:
            operation += '''<button class="btn btn-primary btn-xs" onclick="chooseRegion('%s')">
                                    <span class="fa fa-pencil">
                                        modify
                                    </span>
                                </button>
                         ''' % self.module_name
        module_infos.update({"operation": operation})
        logger.debug('module %s to dict: %s' % (self.module_name, json.dumps(module_infos)))
        return module_infos

    def deal_field_user(self):
        return {'user': self.user.username}

    def deal_field_regions(self):
        regions = self.regions.all()
        region_abbrs = []
        for region in regions:
            region_abbrs.append(region.abbr)
        return {'regions': ','.join(region_abbrs)}

     # def save_new_model(self):
    #     region = self.region
    #     if region == 'cn-north-1':
    #         account_name = 'cn-%s' % ACCOUNT_NAME
    #     else:
    #         account_name = 'global-%s' % ACCOUNT_NAME
    #     maccount = ModelAccount.objects.get(name=account_name)
    #     account = Account()
    #     account.from_json(maccount.text)
    #     module_name = self.module_name
    #     launch_params = get_default_resources(module_name, region, account)
    #     try:
    #         ec2option_set = ModelEc2OptionSet.objects.get(name=module_name, region=region)
    #         ec2option_set.text = launch_params
    #     except ModelEc2OptionSet.DoesNotExist:
    #         logger.info('no ec2 option set found for module: %s, region: %s, create new' % (module_name, region))
    #         ec2option_set = ModelEc2OptionSet(name=module_name, account=account_name,
    #                                           region=region, text=launch_params)
    #     ec2option_set.save()
    #     self.default_launch_params = ec2option_set
    #     self.save()
    #
    #


class ScriptExecLog(models.Model):
    user = models.ForeignKey(User, related_name='script_exec_user', on_delete=models.SET_NULL, null=True)
    script_name = models.CharField(max_length=100)
    script_content = models.TextField()
    exec_time = models.DateTimeField(auto_now_add=True)
    if_success = models.BooleanField()
    script_result = models.TextField()


class Ec2OptionSet(models.Model):
    account = models.ForeignKey(AwsAccount)
    region = models.ForeignKey(RegionInfo)
    module = models.ForeignKey(ModuleInfo)
    image = models.ForeignKey(AwsResource)
    tags = models.TextField(default=None, null=True, blank=True)
    content = models.TextField()
