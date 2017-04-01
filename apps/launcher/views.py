import json
import logging


from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from common.models import RegionInfo
from launcher.resourcehandler import AwsResourceHandler
from permission.models import SitePage
from preprddeploy.settings import ACCOUNT_NAME

logger = logging.getLogger('common')


@login_required
def home(request):
    current_region = RegionInfo.get_region(request)
    regions = RegionInfo.get_regions_infos(['region', 'chinese_name'], exclude_regions=[current_region])
    launcher_page = SitePage.objects.get(name='launcher')
    return render(request, 'launcher/ec2-launcher.html', {
        'current_region': current_region,
        'regions': regions,
        'launcher_page': launcher_page,
        'account_name': ACCOUNT_NAME
    })

def get_resources(request):
    pass

def update_resources(request):
    account_name = request.GET.get('account_name')
    region = request.GET.get('region')
    if not account_name or not region:
        return HttpResponse('bad request!', status=400)
    aws_resource_handler = AwsResourceHandler(account_name, region)
    awsresources = aws_resource_handler.update_resources()
    return HttpResponse(json.dumps(awsresources))
