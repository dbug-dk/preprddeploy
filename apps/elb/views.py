#! coding=utf8
import json
import logging

import time
import traceback

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from django.template import Template, Context

from common.libs import ec2api
from common.models import RegionInfo, AwsAccount
from elb import elb_api
from elb.elbcreater import LoadBalancerCreater
from elb.elbtemplate import ElbCfnTemplate
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
        start_time = time.time()
        awssession = AwsAccount.get_awssession(region)
        elbclient = awssession.client('elb')
        loadbalancers = elbclient.describe_load_balancers().get('LoadBalancerDescriptions')
        logger.debug('get all elbs cost %s seconds' % (time.time() - start_time))
        ret = []
        start_time = time.time()
        region_obj = RegionInfo.objects.get(region=region)
        LoadbalancerInfo.objects.filter(region=region_obj).delete()
        logger.debug('delete elb info cost %s seconds' % (time.time() - start_time))
        can_operate = UserPerm(request.user).judge_perm('operate', 'elb')
        start_time = time.time()
        if loadbalancers:
            for lb in loadbalancers:
                if lb['VPCId'] == vpc_id:
                    # todo: reduce to_dict method cost time(three times awsapi call)
                    ret.append(elb_api.to_dict(lb, region, can_operate))
                    LoadbalancerInfo.save_elb_info(lb, region_obj)
        logger.debug('generate elb table info cost %s seconds' % (time.time() - start_time))
        return HttpResponse(json.dumps({'data': ret}))
    else:
        return HttpResponse('region not present!', status=400)


def get_elb_names(request):
    if 'region' in request.GET:
        region = request.GET['region']
        elbs_in_template = LoadBalancerCreater.get_can_create_elbs(region)
        existed_elbs = request.GET.get('createdElbs', '')
        if existed_elbs:
            existed_elbs = existed_elbs.split(',')
        else:
            existed_elbs = []
        not_created_elbs = [elbname for elbname in elbs_in_template if elbname not in existed_elbs]
        return render(request, 'elb/choose-loadbalancers.html', {
            'createdElbs': existed_elbs,
            'notCreateElbs': not_created_elbs
        })
    else:
        return HttpResponse('bad request!', status=400)


def create_elb_stack(request):
    region = request.GET.get('region')
    choosed_elbs = request.GET.get('choosedElbs')
    if not region or not choosed_elbs:
        return HttpResponse('request param not right!', status=400)
    elb_list = choosed_elbs.split(',')
    try:
        LoadBalancerCreater.create_elb_stack(region, elb_list)
    except:
        logger.error('create elb in %s failed.' % region)
        return HttpResponse(traceback.format_exc(), status=500)
    return HttpResponse(json.dumps({'ret': True}))


def update_elb_stack(request):
    region = request.GET.get('region')
    if not region:
        return HttpResponse('region not present!', status=400)
    choosed_elbs = request.GET.get('choosedElbs')
    method = request.GET.get('method')
    if not method:
        return HttpResponse('method not present!', status=400)
    elb_cfn_template = ElbCfnTemplate(region)
    stackname = elb_cfn_template.stack_name
    cfnconn = AwsAccount.get_awssession(region).resource('cloudformation')
    stack = cfnconn.Stack(stackname)
    if method == 'delete':
        try:
            stack.delete()
        except Exception, e:
            return HttpResponse(json.dumps({'ret': False,
                                            'msg': 'delete stack failed: %s' % str(e)
                                            }))
        return HttpResponse(json.dumps({'ret': True}))
    elif method == 'update':
        choosed_elbs = choosed_elbs.split(',')
        template_params = elb_cfn_template.get_template_params(choosed_elbs)
        try:
            stack.update(UsePreviousTemplate=True,
                         Parameters=template_params
                         )
        except Exception, e:
            return HttpResponse(json.dumps({'ret': False,
                                            'msg': 'update stack failed: %s' % str(e)
                                            }))
        return HttpResponse(json.dumps({'ret': True}))
    else:
        return HttpResponse('wrong method', status=400)


def get_stack_events(request):
    if 'region' in request.GET:
        region = request.GET['region']
        elb_cfn_template = ElbCfnTemplate(region)
        stackname = elb_cfn_template.stack_name
        stack_status = LoadBalancerCreater.get_statck_status(region, stackname)
        if stack_status == 'DELETE_COMPLETE':
            return HttpResponse(json.dumps({
                'status': stack_status,
                'html': '''<div class="panel panel-info">
                               <div class="panel-heading">
                                   堆栈名：%s ,堆栈状态：DELETE_COMPLETE
                               </div>
                           </div>''' % stackname
            }))
        resources = LoadBalancerCreater.get_stack_resources_status(region, stackname)
        django_template = Template("""<div class="panel panel-info">
                                          <div class="panel-heading">
                                              堆栈名：{{stack_name}},堆栈状态：{{stack_status}}
                                          </div>
                                          <div class="panel-body">
                                              <div class="table-responsive">
                                                  <table class="table table-striped">
                                                      <thead>
                                                          <tr>
                                                              <th>资源名</th>
                                                              <th>资源状态</th>
                                                              <th>状态原因</th>
                                                          </tr>
                                                      </thead>
                                                      <tbody>
                                                          {% for resource_name,resource_info in resources.items %}
                                                          <tr>
                                                              <td>{{resource_name}}</td>
                                                              <td>{{resource_info.0}}</td>
                                                              <td>{{resource_info.1}}</td>
                                                          </tr>
                                                          {% endfor %}
                                                      </tbody>
                                                  </table>
                                              </div>
                                          </div>
                                      </div>""")
        context = Context({'stack_name': stackname,
                           'stack_status': stack_status,
                           'resources': resources
                           })
        stack_event_html = django_template.render(context)
        return HttpResponse(json.dumps({'status': stack_status,
                                        'html': stack_event_html
                                        }))
    else:
        return HttpResponse('bad request!', status=400)


def add_elb_instances(request):
    """
    add instances to each elb.
    Args:
        request (django.http.request.HttpRequest)
    """
    region = request.GET.get('region')
    if not region:
        return HttpResponse('region not present!', status=400)
    elbconn = AwsAccount.get_awssession(region).client('elb')
    loadbalancers = elbconn.describe_load_balancers().get('LoadBalancerDescriptions')
    elbs = []
    if loadbalancers:
        for lb in loadbalancers:
            if lb['VPCId'] == PREPRD_VPC[region][1]:
                elbs.append(lb.get('LoadBalancerName'))
    response = {'ret': True, 'msg': {}}
    for elbname in elbs:
        register_result = LoadBalancerCreater.register_instances(region, elbname)
        if not register_result['ret']:
            response.update({'ret': False})
            response['msg'].update({elbname: register_result['msg']})
    return HttpResponse(json.dumps(response))


def get_instances_for_elb(request):
    region = request.GET.get('region')
    elbname = request.GET.get('loadbalancerName')
    if not region or not elbname:
        return HttpResponse('params not correct!', status=400)
    instances = LoadBalancerCreater.get_instances_of_elb(region, elbname)
    instance_ids = elb_api.get_instances_in_elb(region, elbname)
    registered_instances = []
    unregistered_instances = []
    for instance in instances:
        instance_name = ec2api.get_instance_tag_name(instance)
        instance_id = instance.instance_id
        if instance_id in instance_ids:
            registered_instances.append([instance_id, instance_name])
        else:
            unregistered_instances.append([instance_id, instance_name])
    return render(request, 'elb/choose-elb-instances.html', {
        'unregistered_instances': unregistered_instances,
        'registered_instances': registered_instances
    })


def register_instance(request):
    region = request.GET.get('region')
    if not region:
        return HttpResponse('region not present!', status=400)
    elbname = request.GET.get('loadbalancerName')
    if not elbname:
        return HttpResponse('loadbalancer name not present!', status=400)
    instance_ids = request.GET['choosedInstanceIds']
    if not instance_ids.startswith('i-'):
        id_list = []
    else:
        id_list = instance_ids.split(',')
    deal_result = elb_api.deal_instance_for_elb(elbname, region, id_list)
    if not deal_result['ret']:
        return HttpResponse(deal_result['msg'], status=500)
    time.sleep(1)
    elbconn = AwsAccount.get_awssession(region).client('elb')
    lb = elbconn.describe_load_balancers(LoadBalancerNames=[elbname])['LoadBalancerDescriptions'][0]
    rowdata = elb_api.to_dict(lb, region, True)
    return HttpResponse(json.dumps(rowdata))
