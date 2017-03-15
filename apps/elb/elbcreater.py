#! coding=utf8
# Filename    : elbcreater.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging
from multiprocessing import cpu_count
import time
import traceback

from botocore.exceptions import ClientError
import threadpool

from common.libs import ec2api
from common.models import RegionInfo, AwsAccount
from elb import elb_api
from elb.elbtemplate import ElbCfnTemplate
from elb.models import LoadbalancerInfo
from preprddeploy.settings import PREPRD_VPC

logger = logging.getLogger('deploy')


class LoadBalancerCreater(object):
    def __init__(self):
        self.regions = RegionInfo.get_all_regions()
        self.flag = True
        self.result_reason = None

    @staticmethod
    def get_can_create_elbs(region):
        """
        read elb-{region}-beta.template and get all elbs in it.
        Args:
            region (basestring): region name
        """
        elb_cfn_template = ElbCfnTemplate(region)
        template_content = json.loads(elb_cfn_template.get_content())
        resources = template_content.get('Resources')
        if not resources:
            raise Exception('no resources found in cfn templates')
        elbs = []
        for resource in resources:
            if resource.startswith('elb'):
                elb_name = resources[resource]['Properties'].get('LoadBalancerName')
                if elb_name:
                    elbs.append(elb_name)
        return elbs

    @staticmethod
    def create_elb_stack(region, elbs):
        """
        create elb's cloudformation stack in specified region.
        Args:
            region (basestring): region name
            elbs (list): list of elb names want to create
        """
        aws_session = AwsAccount.get_awssession(region)
        cfnconn = aws_session.resource('cloudformation')
        elb_cfn_template = ElbCfnTemplate(region)
        template_content = elb_cfn_template.get_content()
        stack_name = elb_cfn_template.stack_name
        template_params = elb_cfn_template.get_template_params(elbs)
        stack = cfnconn.create_stack(StackName=stack_name,
                                     TemplateBody=template_content,
                                     Parameters=template_params,
                                     OnFailure='DELETE'  # when create elb stack failed, delete it
                                     )
        return stack.stack_name

    @staticmethod
    def get_statck_status(region, stack_name):
        aws_session = AwsAccount.get_awssession(region)
        cfnconn = aws_session.resource('cloudformation')
        stack = cfnconn.Stack(stack_name)
        try:
            stack_status = stack.stack_status
        except ClientError, ce:
            if 'does not exist' in ce.message:
                stack_status = 'DELETE_COMPLETE'
            else:
                raise
        return stack_status

    @staticmethod
    def get_stack_resources_status(region, stack_name):
        aws_session = AwsAccount.get_awssession(region)
        cfnconn = aws_session.resource('cloudformation')
        stack = cfnconn.Stack(stack_name)
        events = stack.events.all()
        resource_dict = {}
        for e in events:
            resource_name = e.logical_resource_id
            resource_status = e.resource_status
            resource_status_reason = e.resource_status_reason
            if resource_name in resource_dict:
                continue
            resource_dict.update({resource_name: [resource_status, resource_status_reason]})
        return resource_dict

    @staticmethod
    def _add_instances_to_elbs(region, elb_names):
        """
        deal all elbs in stack, add instances to these.
        Args:
            region (basestring): region name
            elb_names (list): elb name list want to add instances
        """
        thread_pool = threadpool.ThreadPool(cpu_count() * 3)
        thread_func_var = []
        for elb_name in elb_names:
            varlists = [region, elb_name]
            thread_func_var.append((varlists, None))
        requests = threadpool.makeRequests(LoadBalancerCreater.register_instances, thread_func_var)
        logger.info('start to add instances to all the elbs %s in region: %s' % (elb_names,
                                                                                 region))
        [thread_pool.putRequest(req) for req in requests]
        thread_pool.wait()
        logger.info('finish adding instances to elbs in region: %s' % region)

    @staticmethod
    def _create_elbs_in_region(region, elb_list=None):
        """
        create an elb stack in specify region and wait it create complete.
        after create success, add instances to each elb.
        Args:
            region (basestring): region name
            elb_list (list): elb name list, if set None or empty, will create all elbs in elb cfn template.
        """
        try:
            if not elb_list:
                elb_list = LoadBalancerCreater.get_can_create_elbs(region)
            stack_name = LoadBalancerCreater.create_elb_stack(region, elb_list)
            while True:
                stack_status = LoadBalancerCreater.get_statck_status(region, stack_name)
                if stack_status == 'CREATE_COMPLETE':
                    aws_session = AwsAccount.get_awssession(region)
                    elbclient = aws_session.client('elb')
                    loadbalancers = elbclient.describe_load_balancers().get('LoadBalancerDescriptions')
                    if loadbalancers:
                        for lb in loadbalancers:
                            if lb['VPCId'] == PREPRD_VPC[region][1]:
                                LoadbalancerInfo.save_elb_info(lb, RegionInfo.objects.get(region=region))
                    LoadBalancerCreater._add_instances_to_elbs(region, elb_list)
                    return True
                elif stack_status == 'DELETE_COMPLETE':
                    error_msg = 'create elb stack failed in region: %s' % region
                    logger.error(error_msg)
                    # todo: send mail
                    # mailSender = MailSender()
                    # mailSender.send_mail_when_exception_in_deamon(error_msg)
                    return False
                time.sleep(1)
        except:
            error_msg = 'occur error at progress of creating elbs in region: %s\n' % region
            error_msg += traceback.format_exc()
            logger.error(error_msg)
            # todo: send mail
            # MailSender().send_mail_when_exception_in_deamon(error_msg)
            return False

    def __call__(self):
        LoadbalancerInfo.objects.all().delete()
        create_elbs_pool = threadpool.ThreadPool(len(self.regions))
        thread_requests = threadpool.makeRequests(LoadBalancerCreater._create_elbs_in_region, self.regions,
                                                  callback=self.create_elbs_success,
                                                  exc_callback=self.create_elbs_failed)
        [create_elbs_pool.putRequest(req) for req in thread_requests]
        create_elbs_pool.wait()
        if self.flag:
            return {'ret': True, 'msg': u'所有区域ELB创建完毕，实例已导入'}
        else:
            return {'ret': False, 'msg': u'创建ELB过程出现错误，错误信息: %s' % self.result_reason}

    def create_elbs_success(self, _, result):
        """
        callback method after thread _create_elbs_in_region execute complete
        Args:
            _: threadpool request object(not use)
            result: return value of thread function.
        """
        self.flag = result

    def create_elbs_failed(self, request, error_info):
        thread_args = request.args
        error_msg = 'Exception occured in request: create_elbs_in_region(%s), message: %s' % (thread_args,
                                                                                              error_info[1].message)
        logger.error(error_msg)
        self.flag = False
        self.result_reason = error_msg

    @staticmethod
    def get_instances_of_elb(region, elb_name):
        module_name = elb_api.get_module_name(elb_name)
        instances = ec2api.find_instances(region, [module_name])
        return instances

    @staticmethod
    def register_instances(region, elb_name):
        logger.info('start to add instances to elb: %s in region: %s' % (elb_name, region))
        try:
            instances = LoadBalancerCreater.get_instances_of_elb(region, elb_name)
            register_instance_ids = []
            for instance in instances:
                instance_id = instance.instance_id
                register_instance_ids.append({'InstanceId': instance_id})
            if register_instance_ids:
                elbconn = AwsAccount.get_awssession(region).client('elb')
                elbconn.register_instances_with_load_balancer(LoadBalancerName=elb_name,
                                                              Instances=register_instance_ids
                                                              )
        except:
            error_msg = 'failed when adding instances to elb: %s in %s\n' % (elb_name, region)
            error_msg += traceback.format_exc()
            logger.error(error_msg)
            return {'ret': False, 'msg': error_msg}
            # todo: send mail
            # MailSender().send_mail_when_exception_in_deamon(errorMsg)
        else:
            logger.info('success adding instances to elb: %s in %s' % (elb_name, region))
            return {'ret': True}
