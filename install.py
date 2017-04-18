#! coding=utf8
# Filename    : install.py.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import os
import sys

import django


project_dir = os.path.split(os.path.realpath(__file__))[0]
project_name = os.path.basename(project_dir)
sys.path.append(project_dir)
os.environ['DJANGO_SETTINGS_MODULE'] = '%s.settings' % project_name
django.setup()


from django.contrib.auth.models import User

from bizmodule.models import BizServiceLayer
from basicservice.models import BasicServiceDeployInfo
from common.libs import ec2api
from common.models import RegionInfo
from launcher.tasks import save_aws_resource
from module.models import ModuleInfo
from preprddeploy.settings import ELB_MODULES, ACCOUNT_NAME

regions = [
    ['us-east-1', 1, 'use1', '美国区']
]

biz_modules = {
    'dataAccessLayer': ['dal', 'crosssync', 'notification'],
    'businessLayer': ['account_accountweb', 'appservice_pushservice', 'device', 'mail', 'mailvalidator', 'vaservice'],
    'forwardingLayer': ['dispatcher', 'assembler'],
    'accessLayer': ['appserver', 'appserverinternal', 'connector', 'ddns', 'eweb', 'ipcamera', 'sefcore', 'vaserver']
}

layer_order_map = {
    'dataAccessLayer': 1,
    'businessLayer': 2,
    'forwardingLayer': 3,
    'accessLayer': 4
}
STANDARD_MODULES = ['dal', 'crosssync', 'notification', 'account', 'appservice', 'pushservice', 'device', 'mail', 'mailvalidator', 'vaservice','dispatcher', 'assembler', 'connector', 'ddns', 'ipcamera', 'sefcore']
TOMCAT_MODULES = ['accountweb', 'appserver', 'appserverinternal', 'vaserver', 'eweb']

INSTANCE_TYPE = ['t2.small', 't2.micro', 't2.medium', 't2.large', 't2.xlarge', 't2.2xlarge', 'm1.small',
                 'm1.medium', 'm1.large', 'm1.xlarge', 'm3.medium', 'm3.large', 'm3.xlarge', 'm3.2xlarge', 'm4.large',
                 'm4.xlarge', 'm4.2xlarge', 'm4.4xlarge', 'm4.10xlarge', 'm4.16xlarge', 'm2.xlarge', 'm2.2xlarge',
                 'm2.4xlarge', 'cr1.8xlarge', 'r3.large', 'r3.xlarge', 'r3.2xlarge', 'r3.4xlarge', 'r3.8xlarge',
                 'r4.large', 'r4.xlarge', 'r4.2xlarge', 'r4.4xlarge', 'r4.8xlarge', 'r4.16xlarge', 'x1.16xlarge',
                 'x1.32xlarge', 'i2.xlarge', 'i2.2xlarge', 'i2.4xlarge', 'i2.8xlarge', 'i3.large', 'i3.xlarge',
                 'i3.2xlarge', 'i3.4xlarge', 'i3.8xlarge', 'i3.16xlarge', 'hi1.4xlarge', 'hs1.8xlarge', 'c1.medium',
                 'c1.xlarge', 'c3.large', 'c3.xlarge', 'c3.2xlarge', 'c3.4xlarge', 'c3.8xlarge', 'c4.large',
                 'c4.xlarge', 'c4.2xlarge', 'c4.4xlarge', 'c4.8xlarge', 'cc1.4xlarge', 'cc2.8xlarge', 'g2.2xlarge',
                 'g2.8xlarge', 'cg1.4xlarge', 'p2.xlarge', 'p2.8xlarge', 'p2.16xlarge', 'd2.xlarge', 'd2.2xlarge',
                 'd2.4xlarge', 'd2.8xlarge', 'f1.2xlarge', 'f1.16xlarge']

basic_services = (
    ('pushCassandra', 1, 'use1'),
    ('cassandra', 1, 'use1'),
    ('codis', 2, 'use1'),
    ('mysql', 1, 'use1'),
    ('redisClusterMaster', 1, 'use1'),
    ('zookeeper', 1, 'use1'),
    ('redis', 1, 'use1'),
    ('rabbitmq', 1, 'use1'),
    ('redisClusterSlave', 2, 'use1')
)


def save_regions():
    for region_name, order, abbr, chinese_name in regions:
        region_info = RegionInfo(region=region_name, deploy_order=order,
                                 abbr=abbr, chinese_name=chinese_name)
        region_info.save()


def save_basic():
    for service_name, order, regions in basic_services:
        basic_obj = BasicServiceDeployInfo(service_name=service_name, order=order)
        basic_obj.save()
        for region_abbr in regions.split(','):
            region_obj = RegionInfo.objects.get(abbr=region_abbr)
            basic_obj.regions.add(region_obj)


def scan_instances_and_save_module(region, username):
    region_obj = RegionInfo.objects.get(region=region)
    user_obj = User.objects.get(username=username)
    for layer, modules in biz_modules.items():
        order = layer_order_map[layer]
        for module in modules:
            instances = ec2api.find_instances(region, ['*-%s-*' % module])
            max_version = '1.0.0'
            count = 0
            instance_name = None
            module_name = None
            module_version = None
            for instance in instances:
                instance_name = ec2api.get_instance_tag_name(instance)
                module_name, module_version = ec2api.get_module_info(instance_name)
                if version_cmp(module_version, max_version) == 1:
                    count = 0
                    max_version = module_version
                elif version_cmp(module_version, max_version) == 0:
                    count += 1
            elb_names = ELB_MODULES.get(module_name)
            if count:
                mi = ModuleInfo(module_name=module_name, current_version=max_version,
                                instance_count=count + 1, elb_names=elb_names, user=user_obj, order=-1)
                mi.save()
                mi.regions.add(region_obj)
        for service in module.split('_'):
            if service in STANDARD_MODULES:
                service_type = 'standard'
            elif service in TOMCAT_MODULES:
                service_type = 'tomcat'
            else:
                service_type = 'other'
            biz_module = BizServiceLayer(module=mi, service_name=service, layer_name=layer, start_order=order,
                                         service_type=service_type)
            biz_module.save()


def version_cmp(x, y):
    x = x.split('_')
    y = y.split('_')
    for vx, vy in zip(x, y):
        arr_version_x = vx.split('.')
        arr_version_y = vy.split('.')
        lenx = len(arr_version_x)
        leny = len(arr_version_y)
        cmp_count = min(lenx, leny)
        i = 0
        while i < cmp_count:
            try:
                xversion = int(arr_version_x[i])
            except ValueError:
                raise Exception('Can not parse version as integer: %s' % arr_version_x[i])
            try:
                yversion = int(arr_version_y[i])
            except ValueError:
                raise Exception('Can not parse version as integer: %s' % arr_version_y[i])
            if xversion < yversion:
               return -1
            if xversion > yversion:
               return 1
            i += 1
        if lenx > leny:
            return 1
        if lenx < leny:
            return -1
    return 0


def save_aws_resource_can_not_scan(region):
    types = [(itype, '') for itype in INSTANCE_TYPE]
    save_aws_resource(types, 'instance_type', region, ACCOUNT_NAME)


if __name__ == '__main__':
    print 'save region info...'
    #save_regions()
    print 'save basic service...'
    #save_basic()
    region = 'us-east-1'
    scan_instances_and_save_module(region, 'root')
    save_aws_resource_can_not_scan(region)
