#! coding=utf8
# Filename    : bizrender.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging
import os

import time

from bizmodule.bizstarter import BizInstanceStarter
from bizmodule.models import BizServiceLayer
from common.libs import ec2api
from preprddeploy.settings import STATIC_DIR, HOSTS_CACHE_TIME_SECONDS

logger = logging.getLogger('common')


def instances_to_dict(instances, can_operate, check_state=False, region=None):
    instances_detail = {}
    for instance in instances:
        __render_instance(instances_detail, instance, can_operate, check_state, region)
    logger.debug('instances info: %s' % json.dumps(instances_detail))
    return instances_detail


def __render_instance(instances_detail_dict, instance, can_operate, bool_check_state, region):
    instance_name = ec2api.get_instance_tag_name(instance)
    module_name, module_version = ec2api.get_module_info(instance_name)
    instance_state = instance.state['Name']
    private_ip = instance.private_ip_address
    instance_info_dict = {
        'instance_name': instance_name,
        'public_ip': instance.public_ip_address,
        'private_ip': private_ip,
        'instance_state': instance_state,
        'module_state': 'stopped' if instance_state != 'running' else 'tbd'
    }
    if bool_check_state:
        if instance_state != 'running':
            is_running = False
        else:
            is_running = __check_service_state(module_name, module_version, region, private_ip)
            if is_running:
                instance_info_dict.update({'module_state': 'running'})
            else:
                instance_info_dict.update({'module_state': 'stopped'})
    module_info = '%s-%s' % (module_name, module_version)
    instance_info = instances_detail_dict.get(module_info)
    if instance_info:
        instance_info['total_count'] += 1
        if instance_state == 'running':
            instance_info['running_count'] += 1
        instance_info['instances'].append(instance_info_dict)
    else:
        instances_detail_dict.update({
            module_info: {
                "module_info": module_info,
                "module_name": module_name,
                "module_version": module_version,
                "total_count": 1,
                "running_count": 1 if instance_state == 'running' else 0,
                "service_started_count": 0,
                "instances": [instance_info_dict],
            }
        })
    if can_operate:
        operations = '''<button class="btn btn-primary btn-sm" type="button" onclick="startService('%s')">
                            <i class="fa fa-play"></i>
                        </button>
                        <button class="btn btn-primary btn-sm" type="button" onclick="stopService('%s')">
                            <i class="fa fa-power-off"></i>
                        </button>
                        <button class="btn btn-primary btn-sm" type="button" onclick="restartService('%s')">
                            <i class="fa fa-repeat"></i>
                        </button> ''' % (module_info, module_info, module_info)
    else:
        operations = '''<button class="btn btn-primary btn-sm" type="button"
                            onclick="alertMessage('没有实例操作权限！', 'normal', 'Message', 'primary')">
                            <i class="fa fa-ban"></i>
                        </button>'''
    instances_detail_dict[module_info].update({'operations': operations})
    if bool_check_state and is_running:
        instances_detail_dict[module_info]['service_started_count'] += 1


def __check_service_state(module_name, module_version, region, private_ip):
    is_running = True
    __generate_hosts_file(region)
    services = ['%s-%s' % (
        name,
        version
    ) for name, version in zip(module_name.split('_'), module_version.split('_'))]
    for service in services:
        service_name, service_version = service.split('-')
        service_type = BizServiceLayer.objects.get(service_name=service_name).service_type
        check_method = getattr(BizInstanceStarter, 'check_%s_service' % service_type)
        check_result = check_method(service_name, service_version, region, [private_ip])
        is_running = is_running and check_result['ret']
    return is_running


def __generate_hosts_file(region):
    hosts_file_path = os.path.join(STATIC_DIR, 'hosts/hosts-%s' % region)
    hosts_ctime = os.path.getctime(hosts_file_path)
    if time.time() - hosts_ctime <= HOSTS_CACHE_TIME_SECONDS:
        return
    instances_info_dict = BizInstanceStarter.scan_all_instances(region)
    BizInstanceStarter.generate_hosts_file(region, instances_info_dict)
