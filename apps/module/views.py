#! coding=utf8
# Filename    : views.py
# Description : views file for app module
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import render

from apps.common.models import RegionInfo, AwsAccount
from apps.module.models import ScriptExecLog, ModuleInfo
from apps.permission.models import SitePage
from apps.permission.permapi import UserPerm

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
