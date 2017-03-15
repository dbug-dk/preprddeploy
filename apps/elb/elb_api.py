#! coding=utf8
# Filename    : elb_api.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import logging
import traceback

from common.libs import ec2api
from common.models import AwsAccount
from preprddeploy.settings import ELB_MODULES

logger = logging.getLogger('common')


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
    logger.debug('elb row data: %s' % ret)
    return ret


def get_module_name(loadbalancer_name):
    for module_name in ELB_MODULES:
        if loadbalancer_name in ELB_MODULES[module_name]:
            return module_name
    error_msg = 'loadbalancer name not found in settings: %s' % loadbalancer_name
    logger.error(error_msg)
    raise Exception(error_msg)


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
    ec2conn = AwsAccount.get_awssession(region).resource('ec2')
    instance = ec2conn.Instance(instance_id)
    instance_name = ec2api.get_instance_tag_name(instance)
    return '%s(%s)' % (instance_name, instance_id)


def get_instances_in_elb(region, elbname):
    elbclient = AwsAccount.get_awssession(region).client('elb')
    instances = elbclient.describe_instance_health(LoadBalancerName=elbname)['InstanceStates']
    return [instance['InstanceId'] for instance in instances]


def deal_instance_for_elb(elbname, region, instance_ids):
    """
    register or unregister instance for elb
    Args:
        elbname (basestring): loadbalancer name
        region (basestring): region name
        instance_ids (list): instance id list that finally registed in elb.
    """
    registered_instance_ids = get_instances_in_elb(region, elbname)
    logger.debug('registered_ids: %s' % registered_instance_ids)
    logger.debug('choosed instance ids: %s' % instance_ids)
    regist_instance_ids = [instance_id for instance_id in instance_ids if instance_id not in registered_instance_ids]
    logger.debug(regist_instance_ids)
    deregist_instance_ids = [instance_id for instance_id in registered_instance_ids if instance_id not in instance_ids]
    logger.debug(deregist_instance_ids)
    elbconn = AwsAccount.get_awssession(region).client('elb')
    if deregist_instance_ids:
        deregister_instances_params = []
        for instance_id in deregist_instance_ids:
            deregister_instances_params.append({'InstanceId': instance_id})
        try:
            elbconn.deregister_instances_from_load_balancer(LoadBalancerName=elbname,
                                                            Instances=deregister_instances_params
                                                            )
        except:
            error_msg = 'deregister instance failed for %s, error message: \n%s' % (elbname,
                                                                                    traceback.format_exc())
            logger.error(error_msg)
            return {'ret': False, 'msg': error_msg}
    if regist_instance_ids:
        register_instances_params = []
        for instance_id in regist_instance_ids:
            register_instances_params.append({'InstanceId': instance_id})
        try:
            elbconn.register_instances_with_load_balancer(LoadBalancerName=elbname,
                                                          Instances=register_instances_params
                                                          )
        except:
            error_msg = 'register instance failed for %s, error message: \n%s' % (elbname,
                                                                                  traceback.format_exc())
            logger.error(error_msg)
            return {'ret': False, 'msg': error_msg}
    return {'ret': True}
