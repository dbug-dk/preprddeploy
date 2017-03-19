import json
import logging
import traceback

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from basicservice import basiccls
from basicservice.models import BasicServiceDeployInfo
from common.libs import ec2api
from common.models import RegionInfo
from permission.models import SitePage
from servicestarter import BasicServiceStarter

logger = logging.getLogger('common')


@login_required
def home(request):
    current_region = RegionInfo.get_region(request)
    regions = RegionInfo.get_regions_infos(['region', 'chinese_name'], exclude_regions=[current_region])
    service_order = BasicServiceStarter.get_service_order(current_region)
    service_list = []
    for services in service_order.values():
        service_list += services
    basic_service_instances = ec2api.find_basic_instances(current_region, service_list)
    basic_service_infos = {}
    for order in service_order:
        basic_service_infos[order] = {}
    for instance in basic_service_instances:
        instance_state = instance.state['Name']
        instance_name = ec2api.get_instance_tag_name(instance)
        logger.debug('instance name: %s' % instance_name)
        service_name = ec2api.get_module_info(instance_name)[0]
        ip = instance.private_ip_address
        service_state = True
        service_order = BasicServiceDeployInfo.objects.get(service_name=service_name).order
        service_info = basic_service_infos[service_order].get(service_name)
        if service_info:
            service_info['total_count'] += 1
            if instance_state == 'running':
                service_info['running_count'] += 1
            else:
                service_info['service_state'] = False
            service_info.get('details').append((instance_name, ip, instance_state))
        else:
            if instance_state == 'running':
                running_count = 1
            else:
                running_count = 0
                service_state = False
            basic_service_infos[service_order].update({
                service_name: {
                    'total_count': 1,
                    'running_count': running_count,
                    'service_state': service_state,
                    'details': [(instance_name, ip, instance_state)]
                }
            })
        logger.debug('basic service info after one instance: %s ' % json.dumps(basic_service_infos))
    logger.debug('basic service infos: %s' % json.dumps(basic_service_infos))
    basic_service_page = SitePage.objects.get(name='basic')
    return render(request, 'basic/basic-service-details.html', {
        'basic_service_infos': basic_service_infos,
        'current_region': current_region,
        'regions': regions,
        'basic_service_page': basic_service_page
    })


def start_basic_service(request):
    if 'service_name' in request.GET:
        service_name = BasicServiceStarter.upper_first_char(request.GET['service_name'])
        try:
            region = request.GET['region']
            service_cls = getattr(basiccls, '%sService' % service_name)(region)
            result = service_cls.start_service()
            return HttpResponse(json.dumps(result))
        except:
            error_msg = 'start service %s failed, details: \n%s' % (service_name,
                                                                    traceback.format_exc()
                                                                    )
            logger.error(error_msg)
            return HttpResponse(error_msg, status=500)
    else:
        return HttpResponse("service name not present!", status=400)


def stop_basic_service(request):
    if 'service_name' in request.GET:
        service_name = BasicServiceStarter.upper_first_char(request.GET['service_name'])
        try:
            region = request.GET['region']
            service_cls = getattr(basiccls, '%sService' % service_name)(region)
            result = service_cls.stop_service()
            return HttpResponse(json.dumps(result))
        except:
            error_msg = 'stop service %s failed, details: \n%s' % (service_name,
                                                                   traceback.format_exc()
                                                                   )
            logger.error(error_msg)
            return HttpResponse(error_msg, status=500)
    else:
        return HttpResponse('service name not present!', status=400)


def check_basic_service(request):
    if 'service_name' in request.GET:
        orgin_service_name = request.GET['service_name']
        service_name = BasicServiceStarter.upper_first_char(orgin_service_name)
        region = request.GET['region']
        service_cls = getattr(basiccls, '%sService' % service_name)(region)
        service_state = service_cls.check_service()
        return HttpResponse(json.dumps({
            "service_name": orgin_service_name,
            "service_state": service_state
        }), content_type='application/json')
    else:
        return HttpResponse("service name not present", status=400)
