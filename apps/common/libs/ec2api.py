#! coding=utf8
# Filename    : ec2api.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import logging

import time

import subprocess

import re

from bizmodule.models import BizServiceLayer
from common.models import AwsAccount, RegionInfo
from module.models import ModuleInfo
from preprddeploy.settings import PREPRD_VPC, TOPO_MODULES

logger = logging.getLogger('common')


def get_instance_tag(ec2instance, tag_name):
    for tag in ec2instance.tags:
        if tag.get('Key') == tag_name:
            return tag.get('Value')


def get_instance_tag_name(instance):
    return get_instance_tag(instance, 'Name')


def get_module_info(instance_name):
    regex = '-'.join(['^[a-z,A-Z]+-([a-z,A-Z,0-9]+(_[a-z,A-Z,0-9]+)*)',
                      '(\d{1,3}\.\d{1,3}\.\d{1,3}[_\d{1,3}\.\d{1,3}\.\d{1,3}]*).*'])
    re_pattern = re.compile(regex)
    re_match = re.match(re_pattern, instance_name)
    if not re_match:
        logger.warn('instance name is not format: [env]-[module]-[version]-[regionAttr]-[az]-[num]\
        current instance name: %s' % instance_name)
        try:
            module_name = instance_name.split('-')[1]
        except IndexError:
            module_name = instance_name
        return module_name, '1.0.0'
    return re_match.group(1), re_match.group(3)


def find_instances(region, tag_name_patterns, is_running=False):
    vpc_id = PREPRD_VPC[region][1]
    ec2conn = AwsAccount.get_awssession(region).resource('ec2')
    filters = [
        {
            'Name': 'vpc-id',
            'Values': [vpc_id]
        },
        {
            'Name': 'tag:Name',
            'Values': tag_name_patterns
        }
    ]
    if is_running:
        filters.append({
            'Name': 'instance-state-name',
            'Values': ['running']
        })
    return ec2conn.instances.filter(Filters=filters)


def find_biz_instances(region, modules=None, version_filter='all', is_running=False):
    """
    find instances for module in region(just scan vpc for preprd)
    Args:
        region (string): region name
        modules (list): module name list, if None, means all modules
        version_filter (string): filter instances by version, choices: all, current, update
        is_running (bool): if True, just return running instances
    """
    if modules is None:
        module_infos = ModuleInfo.objects.all()
    else:
        module_infos = ModuleInfo.objects.filter(module_name__in=modules)
    if not module_infos:
        raise Exception('module name not found in ModuleInfo: %s' % modules)
    update_version_patterns = []
    current_version_patterns = []
    for module in module_infos:
        module_name = module.module_name
        current_version = module.current_version
        if current_version:
            current_version_patterns.append('*-%s-%s-*' % (module_name, current_version))
        update_version = module.update_version
        if update_version:
            update_version_patterns.append('*-%s-%s-*' % (module_name, update_version))
    if version_filter == 'all':
        tag_name_pattern = current_version_patterns + update_version_patterns
    elif version_filter == 'current':
        tag_name_pattern = current_version_patterns
    elif version_filter == 'update':
        tag_name_pattern = update_version_patterns
    else:
        raise Exception('version filter not correct: %s' % version_filter)
    biz_instances = find_instances(region, tag_name_pattern, is_running)
    logger.debug('%s instancs are:' % modules)
    for instance in biz_instances:
        logger.debug(instance.private_ip_address)
    return biz_instances


def find_basic_instances(region, services):
    tag_name_pattern = []
    for service_name in services:
        tag_name_pattern.append('*-%s-*' % service_name)
    return find_instances(region, tag_name_pattern)


def find_all_instance_by_layer(region, layer, version_filter):
    if layer == 'topoLayer':
        instance_name_patterns = ['*-%s-*' % module for module in TOPO_MODULES]
        instances = find_instances(region, instance_name_patterns)
    elif layer == 'basicService':
        region_obj = RegionInfo.objects.get(region=region)
        modules = region_obj.basicservicedeployinfo_set.all().values_list('service_name', flat=True)
        instance_name_patterns = ['*-%s-*' % module for module in modules]
        instances = find_instances(region, instance_name_patterns)
    else:
        modules = BizServiceLayer.get_modules_by_layer_name(layer, region)
        instances = find_biz_instances(region, modules, version_filter=version_filter)
    return instances


def fping_instance(instance_ip):
    """
    make sure all specified instances' state change to running
    use fping to check
    Args:
        instance_ip (string): fping destination
    """
    while not __test_instance_connect(instance_ip):
        time.sleep(10)


def __test_instance_connect(ip):
    """
    use fping command to check instance connection
    Args:
        ip (string): fping destination
    """
    try:
        p = subprocess.Popen(['fping', ip], stdout=subprocess.PIPE)
    except OSError:
        logger.error('fping %s failed, please check the fping has already installed' % ip)
        raise
    output = p.stdout.read()
    logger.debug('fping %s output: %s' % (ip, output))
    if 'alive' in output:
        logger.info('instance: %s has already started.' % ip)
        return True
    logger.info('wait instance: %s state change to running ' % ip)
    return False


def wait_instance_running(instance):
    while instance.state['Name'] != 'running':
        time.sleep(10)
        instance.load()


def wait_instance_stopped(instance):
    while instance.state['Name'] != 'stopped':
        time.sleep(5)
        instance.load()
