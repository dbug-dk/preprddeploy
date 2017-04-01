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

from common.libs.dbconn import check_db_connection
from common.models import RegionInfo, AwsAccount, AwsResource
from preprddeploy.celery import app
from preprddeploy.settings import ELB_MODULES, ACCOUNT_NAME, DEFAULT_PREPRD_VPC, DEFAULT_SUBNET, DEFAULT_SECURITY_GROUP

logger = logging.getLogger('deploy')


class ModuleInfo(models.Model):
    module_name = models.CharField(max_length=30, unique=True)
    update_version = models.CharField(max_length=20, blank=True, null=True)
    current_version = models.CharField(max_length=20, blank=True, null=True)
    instance_count = models.IntegerField(default=2)
    regions = models.ManyToManyField(RegionInfo)
    elb_names = models.CharField(max_length=1000, null=True, blank=True)
    user = models.ForeignKey(User, related_name='module_user', on_delete=models.SET_NULL, null=True)
    order = models.IntegerField(default=-1)

    def __unicode__(self):
        region_abbrs = self.__get_abbrs()
        return self.module_name + '|' + ','.join(region_abbrs)

    def __get_abbrs(self):
        regions = self.regions.all()
        region_abbrs = []
        for region in regions:
            region_abbrs.append(region.abbr)
        region_abbrs.sort()
        return region_abbrs

    def to_dict(self, bool_operate=True):
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
        region_abbrs = self.__get_abbrs()
        return {'regions': ','.join(region_abbrs)}

    @staticmethod
    def create_module(post_params):
        """
        Args:
            post_params (dict): post parameters when creating new model.
                        example: {
                                    u'module_name': u'test',
                                    u'current_version': u'1.0.0',
                                    u'update_version': u'1.0.1',
                                    u'instance_count': u'2',
                                    u'order': u'1',
                                    u'user': u'root',
                                    u'regions': u'cn1',
                                }
        """
        module_obj = ModuleInfo()
        region_abbrs = post_params.pop('regions').split(',')
        module_user = post_params.pop('user')
        for key, value in post_params.items():
            setattr(module_obj, key, value)
        module_name = post_params['module_name']
        if module_name in ELB_MODULES:
            module_obj.elb_names = ','.join(ELB_MODULES[module_name])
        module_obj.user = User.objects.get(username=module_user)
        module_obj.save()
        regions_obj = RegionInfo.objects.filter(abbr__in=region_abbrs)
        for region_obj in regions_obj:
            module_obj.regions.add(region_obj)
            get_default_resources.delay(module_name, region_obj.region, ACCOUNT_NAME)
        return module_obj.to_dict()

    @staticmethod
    def delete_module(post_params):
        module_name = post_params['module_name']
        module = ModuleInfo.objects.get(module_name=module_name)
        module.delete()

    @staticmethod
    def edit_module(post_params):
        """
        update module info
        Args:
            post_params (dict): post parameters when edit module.
                                only current_version, update_version, instance_count, user, order
        """
        cannot_edit = ['module_name', 'regions']
        username = post_params.pop('user')
        module = ModuleInfo.objects.get(module_name=post_params['module_name'])
        module.user = User.objects.get(username=username)
        for key, value in post_params.items():
            if key not in cannot_edit:
                setattr(module, key, value)
        module.save()
        return module.to_dict()


@app.task
def get_default_resources(module_name, region, account):
    logger.error('start to get %s default launch parameters in region: %s, account: %s' % (
        module_name,
        region,
        account
    ))
    default_resources = {
        "alloc_public_ip": False,
        "num": 2,
        "keypair": None,
        "instance_type": None,
        "vpc": DEFAULT_PREPRD_VPC[region],
        "subnet": DEFAULT_SUBNET[region],
        'use_default_ebs_settings': True,
        'volume_type': 'gp2',
        'volume_size': 8,
        'volume_iops': 24,
        "security_group": DEFAULT_SECURITY_GROUP,
        "sourceDestCheck": True,
        "instance_profile": None,
        "elbs": []
    }
    region_obj = RegionInfo.objects.get(region=region)
    if region == 'cn-north-1':
        account_name = 'cn-%s' % account
    else:
        account_name = 'en-%s' % account
    account_obj = AwsAccount.objects.get(name=account_name)
    default_image = AwsResource.objects.get(resource_type='ami', default=True,
                                            region=region_obj, account=account_obj)
    default_resources['keypair'] = AwsResource.get_default_resource('keypair', region_obj, account_obj)
    default_resources['instance_type'] = AwsResource.get_default_resource('instance_type', region_obj, account_obj)
    default_resources['instance_profile'] = AwsResource.get_default_resource('instance_profile', region_obj, account_obj)
    if module_name in ELB_MODULES:
        default_resources['elbs'] = ELB_MODULES[module_name]
    module_obj = ModuleInfo.objects.get(module_name=module_name)
    ec2_option_set = Ec2OptionSet(account=account_obj, region=region_obj, module=module_obj,
                                  image=default_image, content=default_resources
                                  )
    ec2_option_set.save()
    logger.info('finished save %s launch parameter in region: %s, account: %s' % (module_name, region, account))


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
