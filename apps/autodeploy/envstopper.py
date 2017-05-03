#! coding=utf8
# Filename    : envstopper.py
# Description : 
# Url         : 
# Author      : iwannarock
# History:
# 1. 2017/5/2 0:42 , iwannarock, first create
import logging
import traceback

import threadpool
from multiprocessing import cpu_count

from basicservice import basiccls
from basicservice.servicestarter import BasicServiceStarter
from common.libs import ec2api
from common.models import AwsAccount, RegionInfo

logger = logging.getLogger('deploy')


class EnvStopper(object):
    def __init__(self, **kwargs):
        self.stop_basic_results = {}
        self.results = {}

    def __call__(self):
        regions = RegionInfo.get_all_regions()
        thread_pool = threadpool.ThreadPool(len(regions))
        thread_requests = threadpool.makeRequests(self.stop_env_in_region, regions)
        [thread_pool.putRequest(req) for req in thread_requests]
        thread_pool.wait()
        stop_result = self.__check_thread_success()
        if not stop_result['ret']:
            return {'ret': False, 'msg': stop_result['msg']}
        logger.info('success stop all environments in regions: %s' % regions)
        return {'ret': True, 'msg': u'所有区域[%s]环境已停止' % ','.join(regions)}

    def __check_thread_success(self):
        for region in self.results:
            if 'failed' in self.results[region]:
                return {'ret': False, 'msg': self.results}
        return {'ret': True, 'msg': self.results}

    def stop_env_in_region(self, region):
        self.results.update({region: {}})
        try:
            self.stop_biz_instances(region)
        except:
            error_msg = 'stop biz instances failed:\n%s' % traceback.format_exc()
            logger.error('in region: %s, %s' % (region, error_msg))
            self.results[region].update({'failed': error_msg})
            return
        try:
            self.stop_basic_instances(region)
        except:
            error_msg = 'occur error when stopping basic services\n%s' % traceback.format_exc()
            logger.error('in region: %s, %s' % (region, error_msg))
            self.results[region].update({'failed': error_msg})
            return
        if self.results[region]:
            return
        try:
            self.delete_elb_stack(region)
        except:
            error_msg = 'delete elb stack failed:\n%s' % traceback.format_exc()
            logger.error('in region: %s, %s' % (region, error_msg))
            self.results[region].update({'failed': error_msg})
            return
        try:
            self.stop_topo_instances(region)
        except:
            error_msg = 'stop stop instances failed:\n%s' % traceback.format_exc()
            logger.error('in region: %s, %s' % (region, error_msg))
            self.results[region].update({'failed': error_msg})
        else:
            logger.info('stop work done in region: %s' % region)

    @staticmethod
    def stop_biz_instances(region):
        service_layers = ['accessLayer', 'forwardingLayer', 'businessLayer', 'dataAccessLayer']
        for layer in service_layers:
            instances = ec2api.find_all_instance_by_layer(region, layer, 'all')
            for instance in instances:
                instance.stop()

    def stop_basic_instances(self, region):
        self.stop_basic_results.update({region: {'success': [], 'failed': []}})
        service_order_dict = BasicServiceStarter.get_service_order(region)
        total_round = len(service_order_dict)
        for round_num in range(total_round, 0, -1):
            logger.info('stop service in region: %s, round: %s, total: %s' % (region, round_num, total_round))
            service_name_list = service_order_dict.get(round_num)
            if not service_name_list:
                error_msg = 'basic service round number not continuous, miss %s' % round_num
                logger.error(error_msg)
                self.results[region].update({'failed': '%s, cancel stopping basic instances' % error_msg})
                break
            if not self.stop_services_batch(service_name_list, region):
                break

    def stop_services_batch(self, service_name_list, region):
        thread_pool = threadpool.ThreadPool(cpu_count() * 3)
        thread_func_vals = []
        for service_name in service_name_list:
            varlist = [service_name, region]
            thread_func_vals.append((varlist, None))
        requests = threadpool.makeRequests(self.stop_service, thread_func_vals)
        [thread_pool.putRequest(req) for req in requests]
        thread_pool.wait()
        stop_failed_list = self.stop_basic_results[region]['failed']
        if stop_failed_list:
            error_msg = 'some basic service stop failed: %s' % stop_failed_list
            logger.error('in region: %s, %s' % (region, error_msg))
            self.results[region].update({'failed': error_msg})
            return False
        return True

    def stop_service(self, service_name, region):
        service = BasicServiceStarter.upper_first_char(service_name)
        try:
            service_cls = getattr(basiccls, '%sService' % service)
        except AttributeError:
            error_msg = "service %s's class not defined" % service
            logger.error(error_msg)
            self.stop_basic_results[region]['failed'].append({service_name: error_msg})
            return
        service_cls_obj = service_cls(region)
        ret = service_cls_obj.stop_service()
        if ret['ret']:
            self.stop_basic_results[region]['success'].append(service_name)
        else:
            self.stop_basic_results[region]['failed'].append({service_name: ret['msg']})

    @staticmethod
    def delete_elb_stack(region):
        stack_name = 'elb-cn-beta' if region == 'cn-north-1' else 'elb-en-beta'
        session = AwsAccount.get_awssession(region)
        cfnconn = session.resource('cloudformation')
        stack = cfnconn.Stack(stack_name)
        stack.delete()

    @staticmethod
    def stop_topo_instances(region):
        topo_instances = ec2api.find_all_instance_by_layer(region, 'topoLayer', 'all')
        for instance in topo_instances:
            instance.stop()
