#! coding=utf8
import json
import logging
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from bizmodule import bizrender
from common.libs import ec2api
from common.models import RegionInfo
from permission.models import SitePage
from permission.permapi import UserPerm

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
    ret = ec2api.start_instances(instances)
    return HttpResponse(json.dumps(ret))


def start_services(request):
    region = request.GET.get('region')
    layer = request.GET.get('layer_name')
    module_infos = request.GET.get('module_infos')
    if not region or not layer or not module_infos:
        return HttpResponse('bad request!', status=400)
    module_info_list = module_infos.split(',')
    if layer in ['topoLayer', 'basicService']:
        tag_pattern = ['*-%s-*' % module_info.split('-')[0] for module_info in module_info_list]
    else:
        tag_pattern = ['*-%s-*' % module_info for module_info in module_info_list]
    instances = ec2api.find_instances(region, tag_pattern)
    ret = ec2api.start_instances(instances)
    return HttpResponse(json.dumps(ret))


def stop_service(request):
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
    ret = ec2api.stop_instances(instances)
    return HttpResponse(json.dumps(ret))


def stop_services(request):
    region = request.GET.get('region')
    layer = request.GET.get('layer_name')
    module_infos = request.GET.get('module_infos')
    if not region or not layer or not module_infos:
        return HttpResponse('bad request!', status=400)
    module_info_list = module_infos.split(',')
    if layer in ['topoLayer', 'basicService']:
        tag_pattern = ['*-%s-*' % module_info.split('-')[0] for module_info in module_info_list]
    else:
        tag_pattern = ['*-%s-*' % module_info for module_info in module_info_list]
    instances = ec2api.find_instances(region, tag_pattern)
    ret = ec2api.stop_instances(instances)
    return HttpResponse(json.dumps(ret))


def restart_service(request):
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
    ret = ec2api.restart_instances(instances)
    return HttpResponse(json.dumps(ret))


def restart_services(request):
    region = request.GET.get('region')
    layer = request.GET.get('layer_name')
    module_infos = request.GET.get('module_infos')
    if not region or not layer or not module_infos:
        return HttpResponse('bad request!', status=400)
    module_info_list = module_infos.split(',')
    if layer in ['topoLayer', 'basicService']:
        tag_pattern = ['*-%s-*' % module_info.split('-')[0] for module_info in module_info_list]
    else:
        tag_pattern = ['*-%s-*' % module_info for module_info in module_info_list]
    instances = ec2api.find_instances(region, tag_pattern)
    ret = ec2api.restart_instances(instances)
    return HttpResponse(json.dumps(ret))
