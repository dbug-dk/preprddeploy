#! coding=utf8
import json
import logging
import traceback

import time
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from bizmodule import bizrender
from bizmodule.bizstarter import BizInstanceStarter
from bizmodule.models import BizServiceLayer
from common.libs import ec2api
from common.models import RegionInfo, AwsAccount
from module.models import ModuleInfo
from permission.models import SitePage
from permission.permapi import UserPerm
from preprddeploy.settings import TOPO_MODULES

logger = logging.getLogger('common')


@login_required
def home(request):
    current_region = RegionInfo.get_region(request)
    regions = RegionInfo.get_regions_infos(['region', 'chinese_name'], exclude_regions=[current_region])
    bizmodule_page = SitePage.objects.get(name='bizmodule')
    return render(request, 'bizmodule/business-module.html', {
        'current_region': current_region,
        'regions': regions,
        'bizmodule_page': bizmodule_page
    })


def show_instances(request):
    region = request.GET.get('region')
    instance_layer = request.GET.get('table_id')
    display_filter = request.GET.get('display_filter')
    if not region or not instance_layer or not display_filter:
        return HttpResponse('bad request!', status=400)
    instances = ec2api.find_all_instance_by_layer(region, instance_layer, display_filter)
    can_operate = UserPerm(request.user).judge_perm('operate', 'bizmodule')
    instance_infos = bizrender.instances_to_dict(instances, can_operate)
    return HttpResponse(json.dumps({'data': instance_infos.values()}))


def check_biz_state(request):
    layer = request.GET['layer']
    region = request.GET['region']
    display_filter = request.GET['display_filter']
    if not layer:
        return HttpResponse(json.dumps({'changed': False}))
    instances = ec2api.find_all_instance_by_layer(region, layer, display_filter)
    can_operate = UserPerm(request.user).judge_perm('operate', 'bizmodule')
    if layer in ['topoLayer', 'basicService']:
        ret = bizrender.instances_to_dict(instances, can_operate)
    else:
        ret = bizrender.instances_to_dict(instances, can_operate, check_state=True, region=region)
    return HttpResponse(json.dumps({'changed': True, 'infos': ret, 'layer': layer}))


def start_service(request):
    region = request.GET.get('region')
    layer_name = request.GET.get('layer_name')
    module_info = request.GET.get('module_info')
    if not module_info or not region or not layer_name:
        return HttpResponse('bad request!', status=400)
    if layer_name in ['topoLayer', 'basicService']:
        tag_pattern = '*-%s-*' % module_info.split('-')[0]
    else:
        tag_pattern = '*-%s-*' % module_info
    instances = ec2api.find_instances(region, [tag_pattern])
    ret = {'success': [], 'failed': [], 'ignore': []}
    for instance in instances:
        instance_name = ec2api.get_instance_tag_name(instance)
        instance_state = instance.state['Name']
        while instance_state == 'stopping':
            time.sleep(5)
            instance.load()
            instance_state = instance.state['Name']
        if instance_state == 'running':
            ret['ignore'].append(instance_name)
        elif instance_state == 'stopped':
            try:
                instance.start()
                ret['success'].append(instance_name)
            except:
                logger.error('start instance: %s failed, error msg: %s' % (
                    instance_name,
                    traceback.format_exc()
                ))
                ret['failed'].append(instance_name)
        elif instance_state in ['shutting-down', 'terminated']:
            ret['failed'].append(instance_name)
    return HttpResponse(json.dumps(ret))
