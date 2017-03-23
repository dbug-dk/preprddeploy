#! coding=utf8
import json
import logging
import traceback

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from bizmodule.models import BizServiceLayer
from common.libs import ec2api
from common.models import RegionInfo, AwsAccount
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
    if 'table_id' in request.GET:
        instance_layer = request.GET['table_id']
        region = request.GET['region']
        if instance_layer == 'topoLayer':
            instance_name_patterns = ['*-%s-*' % module for module in TOPO_MODULES]
            instances = ec2api.find_instances(region, instance_name_patterns)
        elif instance_layer == 'basicService':
            region_obj = RegionInfo.objects.get(region=region)
            modules = region_obj.basicservicedeployinfo_set.all().values_list('service_name', flat=True)
            instance_name_patterns = ['*-%s-*' % module for module in modules]
            instances = ec2api.find_instances(region, instance_name_patterns)
        else:
            modules = BizServiceLayer.get_modules_by_layer_name(instance_layer, region)
            instances = ec2api.find_biz_instances(region, modules)
        can_operate = UserPerm(request.user).judge_perm('operate', 'bizmodule')
        instance_infos = __instances_to_dict(instances, can_operate)
        return HttpResponse(instance_infos)
    else:
        return HttpResponse('table id not present!', status=400)


def __instances_to_dict(instances, can_operate):
    ret = []
    for instance in instances:
        instance_id = instance.instance_id
        instance_state = instance.state['Name']
        instance_name = ec2api.get_instance_tag_name(instance)
        module_info = '-'.join(ec2api.get_module_info(instance_name))
        instance_info = {
            'extra': 'extra data',
            'checkbox': '<input type="checkbox">',
            'instance_id': instance_id,
            'instance_name': instance_name,
            'module_info': module_info,
            'public_ip': instance.public_ip_address,
            'private_ip': instance.private_ip_address,
            'instance_state': instance_state,
        }
        if instance_state != 'running':
            instance_info['module_state'] = 'stopped'
        else:
            instance_info['module_state'] = 'tbd'
        if can_operate:
            instance_info.update({
                'operations': '''<button class="btn btn-primary btn-sm" type="button" onclick="startInstance('%s')">
                                    <i class="fa fa-play"></i>
                                 </button>
                                 <button class="btn btn-primary btn-sm" type="button" onclick="stopInstance('%s')">
                                    <i class="fa fa-power-off"></i>
                                 </button>
                                 <button class="btn btn-primary btn-sm" type="button" onclick="restartInstance('%s')">
                                    <i class="fa fa-repeat"></i>
                                 </button> ''' % (instance_id, instance_id, instance_id)
            })
        else:
            instance_info.update({
                'operations': '''<button class="btn btn-primary btn-sm" type="button"
                                         onclick="alertMessage('没有实例操作权限！', 'normal', 'Message', 'primary')">
                                     <i class="fa fa-ban"></i>
                                 </button>'''
            })
        ret.append(instance_info)
    logger.debug(json.dumps(ret))
    return json.dumps({'data': ret})


def start_instance(request):
    instance_id = request.GET.get('instance_id')
    region = request.GET.get('region')
    layer_name = request.GET.get('layer_name')
    module_info = request.GET.get('module_info')
    if not instance_id or not region or not layer_name:
        return HttpResponse('bad request!', status=400)
    ec2conn = AwsAccount.get_awssession(region).resource('ec2')
    instance = ec2conn.Instance(instance_id)
    try:
        instance.start()
    except:
        error_msg = "%s(%s) cannot start now. details: %s" % (
            module_info,
            instance_id,
            traceback.format_exc()
        )
        logger.error(error_msg)
        return HttpResponse(error_msg, status=500)
    instance_ip = instance.private_ip_address
    module_name = module_info.split('-')[0]
    service_names = module_name.split('_')
    service_info_dict = {}
    for service in service_names:
        try:
            service_obj = BizServiceLayer.objects.get(service_name=service)
        except BizServiceLayer.DoesNotExist:
            error_msg = 'service: %s not found in db table bizservicelayer' % service
            logger.error(error_msg)
            return HttpResponse(error_msg, status=500)
        service_type = service_obj.service_type
        #try:
            #service_info_dict[service_type].append()

