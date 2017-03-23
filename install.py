#! coding=utf8
# Filename    : install.py.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.contrib.auth.models import User

from bizmodule.models import BizServiceLayer
from common.libs import ec2api
from common.models import RegionInfo, AwsAccount
from module.models import ModuleInfo
from preprddeploy.settings import ELB_MODULES

biz_modules = {
    'dataAccessLayer': ['dal', 'crosssync', 'dalForFailover'],
    'businessLayer': ['account', 'accountweb', 'device', 'appservice', 'pushservice',
                      'vaservice', 'mail', 'mailvalidator', 'sms'],
    'forwardingLayer': ['dispatcher', 'assembler', 'jmsservice', 'notification'],
    'accessLayer': ['appserver', 'appserverinternal', 'connector', 'appconnector', 'sefcore',
                    'ipcamera', 'oamanager', 'vaserver', 'ddns', 'devconnector',
                    'kafka2es', 'eswatcher', 'eventloop']
}

layer_order_map = {
    'dataAccessLayer': 1,
    'businessLayer': 2,
    'forwardingLayer': 3,
    'accessLayer': 4
}
STANDARD_MODULES = ['dal', 'crosssync', 'account', 'device', 'appservice', 'pushservice', 'ddns', 'ipcamera',
                    'dispatcher', 'assembler', 'connector', 'appconnector', 'mail', 'vaservice', 'sefcore',
                    'mailvalidator', 'dalForFailover', 'jmsservice', 'sms', 'notification', 'devconnector',
                    'kafka2es', 'eswatcher', 'eventloop']
TOMCAT_MODULES = ['accountweb', 'appserver', 'appserverinternal', 'vaserver', 'eweb']


def scan_instances_and_save_module(region, username):
    region_obj = RegionInfo.objects.get(region=region)
    user_obj = User.objects.get(username=username)
    ec2conn = AwsAccount.get_awssession(region).resource('ec2')
    biz_modules = {
    'dataAccessLayer': ['dal', 'crosssync', 'dalForFailover'],
    'businessLayer': ['account', 'accountweb', 'device', 'appservice', 'pushservice',
                      'vaservice', 'mail', 'mailvalidator', 'sms'],
    'forwardingLayer': ['dispatcher', 'assembler', 'jmsservice', 'notification'],
    'accessLayer': ['appserver', 'appserverinternal', 'connector', 'appconnector', 'sefcore',
                    'ipcamera', 'oamanager', 'vaserver', 'ddns', 'devconnector',
                    'kafka2es', 'eswatcher', 'eventloop']
}
    for layer, modules in biz_modules.items():

        order = layer_order_map[layer]
        for module in modules:
            if module in STANDARD_MODULES:
                service_type = 'standard'
            elif module in TOMCAT_MODULES:
                service_type = 'tomcat'
            else:
                servict_type = 'other'
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
                                instance_count=count+1, elb_names=elb_names, user=user_obj,order=-1)
                mi.save()
                mi.regions.add(region_obj)
                biz_module = BizServiceLayer(module=mi, service_name=module, layer_name=layer,start_order=order,
                                             service_type=service_type)
                biz_module.save()
            print 'module name: %s, current_version: %s, instance_count: %s, elb_names: %s, service_name: %s, layer_name:%s, start_order: %s, service_type: %s' %(
                module_name,
                max_version,
                count,
                elb_names,
                module,
                layer,
                order,
                service_type
            )

def version_cmp(x, y):
    arrVersionX = x.split('.')
    arrVersionY = y.split('.')
    lenX = len(arrVersionX)
    lenY = len(arrVersionY)
    cmpCount = min(lenX, lenY)
    i = 0
    while i < cmpCount:
        try:
            xVersion = int(arrVersionX[i])
        except ValueError:
            raise Exception('Can not parse version as integer: %s'%arrVersionX[i])
        try:
            yVersion = int(arrVersionY[i])
        except ValueError:
            raise Exception('Can not parse version as integer: %s'%arrVersionY[i])
        if xVersion < yVersion:
            return -1
        if xVersion > yVersion:
            return 1
        i += 1
    if lenX > lenY:
        return 1
    if lenX < lenY:
        return -1
    return 0

if __name__ == '__main__':
    scan_instances_and_save_module('cn-north-1', 'root')
