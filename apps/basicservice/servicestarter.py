#! coding=utf8
# Copyright (C), 2017 , TP-LINK Technologies Co., Ltd.
# Filename    : servicestarter.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import logging

import threadpool
from multiprocessing import cpu_count

from basicservice import basiccls
from basicservice.models import BasicServiceDeployInfo
from common.libs import ec2api
from common.models import RegionInfo
from preprddeploy.settings import TOPO_MODULES

logger = logging.getLogger('deploy')


class BasicServiceStarter(object):
    def __init__(self):
        self.region_order_dict = RegionInfo.get_all_regions_group_by_order()
        self.flag = True
        self.results = {}
        for order in self.region_order_dict:
            for region in self.region_order_dict[order]:
                self.results.update({region: {'success': [], 'failed': []}})
        self.start_topo_and_basic_instances()

    def start_topo_and_basic_instances(self):
        for order, regions in self.region_order_dict.items():
            for region in regions:
                instance_patterns = ['*-%s-*' % topo_service for topo_service in TOPO_MODULES]
                basic_service_list = BasicServiceDeployInfo.get_all_basic_service(region, exclude=['rabbitmq'])
                instance_patterns.extend(['*-%s-*' % basic_service for basic_service in basic_service_list])
                instances = ec2api.find_instances(region, instance_patterns)
                start_failed_instances = ec2api.start_instances(instances)['failed']
                if start_failed_instances:
                    logger.error('start topo service failed in region: %s, failed services: %s' % (
                        region,
                        start_failed_instances
                    ))
                    raise Exception('start topo instances failed: %s,\
                    cancel basic service start process' % start_failed_instances)

    @staticmethod
    def start_service(service_name, region):
        """
        start basic service by name.
        Args:
            service_name (string): service name
            region (string): region name
        Returns:
            when start success, return {'ret': True}
                          else, return {'ret': False, 'msg': errorMsg}
        """
        service = BasicServiceStarter.upper_first_char(service_name)
        try:
            service_cls = getattr(basiccls, '%sService' % service)
        except AttributeError:
            logger.error("service %s's class not defined" % service)
            raise
        service_cls_obj = service_cls(region)
        ret = service_cls_obj.start_service()
        return ret

    @staticmethod
    def get_service_order(region):
        region_info_obj = RegionInfo.objects.get(region=region)
        basic_services = region_info_obj.basicservicedeployinfo_set.all()
        order_dict = {}
        for service in basic_services:
            service_name = service.service_name
            order = service.order
            if order_dict.get(order):
                order_dict[order].append(service_name)
            else:
                order_dict.update({order: [service_name]})
        return order_dict

    def __call__(self):
        # todo: in cn-north-1, starting all services cost 6 minute. use multiprocess instead of theadpool.
        total_round = len(self.region_order_dict)
        for round_num in xrange(1, total_round + 1):
            regions = self.region_order_dict.get(round_num)
            if not regions:
                error_msg = 'region order not continuous: %s, miss %s' % (self.region_order_dict,
                                                                          round_num
                                                                          )
                logger.error(error_msg)
                logger.error('start basic service cancel')
                return {'ret': False, 'msg': u'RegionInfo表中数据有误，中止启动基础服务\n%s' % error_msg}
            thread_pool = threadpool.ThreadPool(len(regions))
            thread_requests = threadpool.makeRequests(self.start_services_in_region, regions)
            [thread_pool.putRequest(req) for req in thread_requests]
            thread_pool.wait()
            start_result = self.__check_thread_success(regions)
            if not start_result['ret']:
                return {'ret': False, 'msg': start_result['msg']}
            logger.info('basic services started in regions: %s, round: %s' % (regions, round_num))
        return {'ret': True, 'msg': u'所有区域的基础服务启动完毕'}

    def __check_thread_success(self, regions):
        if not self.flag:
            return {'ret': False, 'msg': 'flag is False, something wrong before start service, see error logs'}
        for region in regions:
            failed_service_list = self.results[region]['failed']
            if failed_service_list:
                error_msg = 'in region %s, %s start failed' % (region, failed_service_list)
                logger.error(error_msg)
                return {'ret': False, 'msg': error_msg}
        return {'ret': True}

    def start_services_in_region(self, region):
        order_dict = self.get_service_order(region)
        if not order_dict:
            logger.error('no basic service deploy in region: %s' % region)
            self.flag = False
            return False
        total_round = len(order_dict)
        for round_num in xrange(1, total_round + 1):
            logger.info('start service in region: %s, round: %s, total: %s' % (region, round_num, total_round))
            service_name_list = order_dict.get(round_num)
            if not service_name_list:
                logger.error('start basic service round number not continuous, miss %s' % round_num)
                self.flag = False
                return False
            start_result = self.start_services_batch(service_name_list, region)
            if not start_result:
                return False
        return True

    def start_services_batch(self, service_name_list, region):
        thread_pool = threadpool.ThreadPool(cpu_count() * 3)
        thread_func_vals = []
        for service_name in service_name_list:
            varlist = [service_name, region]
            thread_func_vals.append((varlist, None))
        requests = threadpool.makeRequests(BasicServiceStarter.start_service, thread_func_vals,
                                           callback=self.__start_service_callback,
                                           exc_callback=self.__start_service_failed_callback)
        [thread_pool.putRequest(req) for req in requests]
        thread_pool.wait()
        if self.results[region]['failed']:
            return False
        return True

    def __start_service_callback(self, request, result):
        service_name, region = request.args
        if result['ret']:
            logger.info('start service complete: service_name: %s, region: %s' % (service_name, region))
            self.results[region]['success'].append(service_name)
        else:
            logger.info('start service failed: service_name: %s, region: %s' % (service_name, region))
            self.results[region]['failed'].append({service_name: result['msg']})

    def __start_service_failed_callback(self, request, error_infos):
        service_name, region = request.args
        error_msg = 'occur error when call start_service, service_name(%s), region(%s), error message: %s' % (
            service_name,
            region,
            error_infos[1].message
        )
        logger.error(error_msg)
        self.results[region]['failed'].append({service_name: error_msg})

    @staticmethod
    def upper_first_char(string):
        return string[0].upper() + string[1:]
