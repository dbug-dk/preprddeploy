#! coding=utf8
# Filename    : ec2api.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import logging

from common.models import AwsAccount
from module.models import ModuleInfo
from preprddeploy.settings import PREPRD_VPC

logger = logging.getLogger('common')


def get_instance_tag(ec2instance, tag_name):
    for tag in ec2instance.tags:
        if tag.get('Key') == tag_name:
            return tag.get('Value')


def get_instance_tag_name(instance):
    return get_instance_tag(instance, 'Name')


def find_instances(region, modules, is_running=False):
    """
    find instances for module in region(just scan vpc for preprd)
    Args:
        region (basestring): region name
        modules (list): module name list
        is_running (bool): if instances' state must be running
    """
    tag_name_pattern = []
    module_infos = ModuleInfo.objects.filter(module_name__in=modules)
    if not module_infos:
        raise Exception('module name not found in ModuleInfo: %s' % modules)
    for module in module_infos:
        module_name = module.module_name
        current_version = module.current_version
        update_version = module.update_version
        pattern = ['*-%s-%s-*' % (module_name, version) for version in [current_version, update_version] if version]
        tag_name_pattern += pattern
    vpc_id = PREPRD_VPC[region][1]
    ec2conn = AwsAccount.get_awssession(region).resource('ec2')
    filters = [
        {
            'Name': 'vpc-id',
            'Values': [vpc_id]
        },
        {
            'Name': 'tag:Name',
            'Values': tag_name_pattern
        }
    ]
    if is_running:
        filters.append({
            'Name': 'instance-state-name',
            'Values': ['running']
        })
    logger.debug(filters)
    instances = ec2conn.instances.filter(Filters=filters)
    return instances
