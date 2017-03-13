#! coding=utf8
# Filename    : elb_api.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
from common.libs import ec2api
from common.models import AwsAccount


def to_dict(loadbalancer, region, can_operate):
    """
    generate elb infomation dict for datatables.
    Args:
        loadbalancer (dict): a loadbalancer infos return by describe-loadbalancers
        region (basestring): region name
        can_operate (bool): if has operate permission with elb page
    """
    ret = {}
    loadbalancer_name = loadbalancer.get('LoadBalancerName')
    ret.update({'loadbalancer_name': loadbalancer_name})
    ret.update({'dns_name': loadbalancer.get('DNSName')})
    instances = loadbalancer.get('Instances', '')
    in_services = []
    out_services = []
    if instances:
        awssession = AwsAccount.get_awssession(region)
        elbclient = awssession.client('elb')
        instance_states = elbclient.describe_instance_health(
            LoadBalancerName=loadbalancer_name,
            Instances=instances,
        ).get('InstanceStates')
        if instance_states:
            for state in instance_states:
                if state['State'] == 'InService':
                    in_services.append(state['InstanceId'])
                else:
                    out_services.append(state['InstanceId'])
            in_services, out_services = __format_instance_info(region, in_services, out_services)
    ret.update({'in_service_list': in_services})
    ret.update({'out_service_list': out_services})
    if can_operate:
        ret.update({'operations': '''<button class="btn btn-primary btn-sm" type="button" onclick="editInstance('%s')">
                                        <i class="fa fa-pencil"></i>
                                            编辑实例
                                     </button>''' % loadbalancer_name})
    else:
        ret.update({
            'operations': '''<button class="btn btn-primary btn-sm" type="button"
                                 onclick="alertMessage('无法编辑实例，请联系管理员进行授权', 'small', 'Message', 'Primary')">
                                <i class="fa fa-pencil"></i>
                                    编辑实例（未授权）
                             </button>'''})
    return ret


def __format_instance_info(region, in_services, out_services):
    in_list = []
    out_list = []
    if in_services:
        for instance_id in in_services:
            in_list.append(__to_str(region, instance_id))
    if out_services:
        for instance_id in out_services:
            out_list.append(__to_str(region, instance_id))
    return in_list, out_list


def __to_str(region, instance_id):
    ec2conn = AwsAccount.get_awssession(region)
    instance = ec2conn.Instance(instance_id)
    instance_name = ec2api.get_instance_tag_name(instance)
    return '%s(%s)' % (instance_name, instance_id)
