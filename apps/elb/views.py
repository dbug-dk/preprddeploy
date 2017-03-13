import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from common.models import RegionInfo, AwsAccount
from elb import elb_api
from elb.models import LoadbalancerInfo
from permission.models import SitePage
from permission.permapi import UserPerm
from preprddeploy.settings import PREPRD_VPC

logger = logging.getLogger('common')


@login_required
def home(request):
    current_region = RegionInfo.get_region(request)
    regions = RegionInfo.get_regions_infos(['region', 'chinese_name'], exclude_regions=[current_region])
    elb_page = SitePage.objects.get(name='elb')
    return render(request, 'elb/loadbalancer-info.html', {
        'current_region': current_region,
        'regions': regions,
        'elb_page': elb_page
    })


def get_loadbalancers(request):
    if 'region' in request.GET:
        region = request.GET.get('region')
        try:
            vpc_id = PREPRD_VPC[region][1]
        except KeyError:
            return HttpResponse(json.dumps({
                                            'data': [],
                                            'debugMessage': 'region selected not deploy PrePRD'
                                            }))
        awssession = AwsAccount.get_awssession(region)
        elbclient = awssession.client('elb')
        loadbalancers = elbclient.describe_load_balancers().get('LoadBalancerDescriptions')
        ret = []
        LoadbalancerInfo.objects.filter(region=RegionInfo.objects.get(region=region)).delete()
        can_operate = UserPerm(request.user).judge_perm('operate', 'elb')
        if loadbalancers:
            for lb in loadbalancers:
                if lb['VPCId'] == vpc_id:
                    ret.append(elb_api.to_dict(lb, region, can_operate))
                    # addElbInfoToDb(lb, region)
        return HttpResponse(json.dumps({'data': ret}))
    else:
        return HttpResponse('region not present!', status=400)
