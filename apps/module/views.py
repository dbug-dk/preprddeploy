#! coding=utf8
# Filename    : views.py
# Description : views file for app module
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging

import re
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404

from common.models import RegionInfo, AwsAccount, AwsResource
from launcher.opsetutils import get_opset_dict
from launcher.resourcehandler import AwsResourceHandler
from module.models import ScriptExecLog, ModuleInfo, Ec2OptionSet
from permission.models import SitePage
from permission.permapi import UserPerm
from preprddeploy.settings import ACCOUNT_NAME, DEFAULT_PREPRD_VPC

logger = logging.getLogger('common')


@login_required
def home(request):
    current_region = RegionInfo.get_region(request)
    regions = RegionInfo.get_regions_infos(['region', 'chinese_name'], exclude_regions=[current_region])
    script_exec_logs = ScriptExecLog.objects.order_by('-exec_time')[:10]
    module_page = SitePage.objects.get(name='module')
    return render(request, 'module/index.html', {
        'regions': regions,
        'current_region': current_region,
        'module_page': module_page,
        'script_logs': script_exec_logs
    })


def get_resources_num(request):
    """
    get num of EC2, ELB, AMI in selected region
    Args:
        request (django.http.request.HttpRequest)
    """
    region = RegionInfo.get_region(request)
    awssession = AwsAccount.get_awssession(region)
    elb_client = awssession.client('elb')
    elbs = elb_client.describe_load_balancers()
    elbnum = len(elbs['LoadBalancerDescriptions'])
    ec2conn = awssession.resource('ec2')
    instances = ec2conn.instances.filter(Filters=[{
        'Name': 'tag:Name',
        'Values': ['preprd-*', 'prd-*', 'PRD-*']
    }])
    ec2num = 0
    for _ in instances:
        ec2num += 1
    images = ec2conn.images.filter(Filters=[{
        'Name': 'is-public',
        'Values': ['false']
    }])
    aminum = 0
    for _ in images:
        aminum += 1
    logger.debug('thers are %s ec2, %s elb, %s ami' % (ec2num, elbnum, aminum))
    return HttpResponse(json.dumps({'aminum': aminum,
                                    'ec2num': ec2num,
                                    'elbnum': elbnum}))


def get_users(request):
    users = User.objects.all()
    ret = []
    if users:
        for user in users:
            user_option = {}
            user_option.update({'label': user.username, 'value': user.username})
            ret.append(user_option)
        return HttpResponse(json.dumps({'options': ret}))
    else:
        return HttpResponse(json.dumps({'options': [{'label': 'no user in system, please create a user first'}]}))


def show_modules(request):
    modules = ModuleInfo.objects.all()
    result = []
    has_operate_perm = UserPerm(request.user).judge_perm('operate', 'module')
    for module in modules:
        result.append(module.to_dict(has_operate_perm))
    return HttpResponse(json.dumps({"data": result}))


def update_module_info(request):
    post_params = {}
    method = None
    for key in request.POST:
        if key == 'action':
            method = request.POST.get(key)
            continue
        module_name, _, field_name = re.split('\]|\[', key)[1:4]
        field_value = request.POST.get(key)
        post_params.update({field_name: field_value})
    logger.debug('update module args: %s' % post_params)
    if method == 'create':
        module_info = ModuleInfo.create_module(post_params)
        return HttpResponse(json.dumps({
            'data': [module_info]
        }))
    elif method == 'remove':
        ModuleInfo.delete_module(post_params)
        return HttpResponse(json.dumps({'data': 'success'}))
    elif method == 'edit':
        module_info = ModuleInfo.edit_module(post_params)
        return HttpResponse(json.dumps({'data': [module_info]}))
    else:
        return HttpResponse('method not correct, update module info failed')


def get_launch_params(request):
    """
    show module's launch params
    Args:
        request (django.http.request.HttpRequest)
    """
    module_name = request.GET.get('module_name')
    if not module_name:
        return HttpResponse('bad request!', status=400)
    module = get_object_or_404(ModuleInfo, module_name=module_name)
    ec2_option_sets = module.ec2optionset_set.all()
    region_names = [region.region for region in module.regions.all()]
    params_dict = dict.fromkeys(region_names)
    for ec2_option_set in ec2_option_sets:
        region_name = ec2_option_set.region.region
        optionset_dict = get_opset_dict(ec2_option_set)
        params_dict.update({region_name: optionset_dict})
    logger.info(params_dict['cn-north-1'])
    return render(request, 'module/launch-params.html', {'launch_params': params_dict})


def get_module_region(request):
    module_name = request.GET.get('module_name')
    if not module_name:
        return HttpResponse('bad request!', status=400)
    module = get_object_or_404(ModuleInfo, module_name=module_name)
    region_names = [region.region for region in module.regions.all()]
    return HttpResponse(json.dumps({'regions': region_names}))


def get_modify_launch_params(request):
    module_name = request.GET.get('module_name')
    region = request.GET.get('region')
    if not module_name or not region:
        return HttpResponse('bad request!', status=400)
    region_obj = RegionInfo.objects.get(region=region)
    module = region_obj.moduleinfo_set.get(module_name=module_name)
    resource_handler = AwsResourceHandler(ACCOUNT_NAME, region)
    resources = resource_handler.load_resources()
    try:
        ec2_option_set = module.ec2optionset_set.get(region=region_obj)
    except Ec2OptionSet.DoesNotExist:
        logger.error('in region: %s, no ec2 option set found for module: %s' % (region, module_name))
        current_vpc = DEFAULT_PREPRD_VPC[region]
        current_vpc_id = current_vpc[1]
        return render(request, 'module/new-params-modal.html', {
            'region': region,
            'current_vpc': current_vpc,
            'subnets': resources['subnets'][current_vpc_id],
            'images': resources['images'],
            'instance_types': resources['instance_types'],
            'keypairs': resources['keypairs'],
            'security_groups': resources['security_groups'][current_vpc_id],
            'volume_types': [['gp2', ''], ['io1', '']],
            'instance_profiles': resources['instance_profiles'],
            'loadbalancers': resources['elbs'][current_vpc_id]
        })
    optionset_dict = get_opset_dict(ec2_option_set)
    current_vpc_id = optionset_dict['vpc'][1]
    return render(request, 'module/modify-params-modal.html', {
        'current_params': optionset_dict,
        'subnets': resources['subnets'][current_vpc_id],
        'images': resources['images'],
        'instance_types': resources['instance_types'],
        'keypairs': resources['keypairs'],
        'security_groups': resources['security_groups'][current_vpc_id],
        'volume_types': [['gp2', ''], ['io1', '']],
        'instance_profiles': resources['instance_profiles'],
        'loadbalancers': resources['elbs'][current_vpc_id]
    })


def modify_launch_params(request):
    module_name = request.POST.get('module_name')
    region = request.POST.get('region')
    table_post_info = json.loads(request.POST.get('table_info'))
    if not module_name or not region or not table_post_info:
        return HttpResponse('bad request!', status=400)
    region_obj = RegionInfo.objects.get(region=region)
    image = table_post_info.pop('image')
    try:
        image_obj = AwsResource.objects.get(resource_name=image[0], resource_id=image[1], region=region_obj)
    except AwsResource.DoesNotExist:
        return HttpResponse('image you choose has been deregistered, please update resource first', status=500)
    module_info = ModuleInfo.objects.get(module_name=module_name)
    try:
        ec2_option_set = Ec2OptionSet.objects.get(name=module_name, region=region_obj, module=module_info)
    except Ec2OptionSet.DoesNotExist:
        logger.error('no Ec2OptionSet found for module: %s in region: %s, create new' % (module_name, region))
        account_name = 'cn-%s' % ACCOUNT_NAME if region == 'cn-north-1' else 'en-%s' % ACCOUNT_NAME
        account_obj = AwsAccount.objects.get(name=account_name)
        table_post_info.update({'vpc': DEFAULT_PREPRD_VPC[region]})
        ec2_option_set = Ec2OptionSet(name=module_name, account=account_obj, region=region_obj,
                                      module=module_info, image=image_obj, content=json.dumps(table_post_info))
        ec2_option_set.save()
        return HttpResponse('ok')
    ec2_option_set.image = image_obj
    current_content = json.loads(ec2_option_set.content)
    current_content.update(table_post_info)
    ec2_option_set.content = json.dumps(current_content)
    ec2_option_set.save(update_fields=['image', 'content'])
    return HttpResponse('ok')

