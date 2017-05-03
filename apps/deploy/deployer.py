#! coding=utf8
# Filename    : deployer.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import logging
import traceback

import subprocess

import time

import threadpool

from common.libs import ec2api
from common.libs.ansible_api import AnsibleRunner
from common.models import RegionInfo
from deploy.scriptrunner import ServiceDeployScript
from preprddeploy.settings import MAX_WAIT_SECONDS_EVERY_LAYER

logger = logging.getLogger('deploy')


class Deployer(object):
    def __init__(self, **args):
        self.username = args['username']
        self.method = args['method']
        self.round_num = 1
        if self.method == 'deploy':
            self.round_num = args['round_num']
        self.region_order_dict = RegionInfo.get_all_regions_group_by_order()
        self.flag = True
        self.results = {}
        for order in self.region_order_dict:
            for region in self.region_order_dict[order]:
                self.results.update({region: {'success': [], 'failed': []}})

    def __call__(self):
        if self.round_num > 1:
            logger.info('stop old instances that belong to module deployed last round')
            try:
                self.stop_old_module_instances()
            except:
                return {'ret': False, 'msg': u'停止旧服务主机过程中出错，部署停止,异常信息:\n%s' % traceback.format_exc()}
            logger.info('old version instances are all stopped in all regions')
        total_region_round = len(self.region_order_dict)
        for region_round in range(1, total_region_round + 1):
            regions = self.region_order_dict.get(region_round)
            if not regions:
                error_msg = 'region order not continuous: %s, miss %s' % (self.region_order_dict,
                                                                          region_round
                                                                          )
                logger.error(error_msg)
                logger.error('start basic service cancel')
                return {'ret': False, 'msg': u'RegionInfo表中数据有误，中止部署服务\n%s' % error_msg}
            thread_pool = threadpool.ThreadPool(len(regions))
            thread_requests = threadpool.makeRequests(self.deploy_services_in_region, regions)
            [thread_pool.putRequest(req) for req in thread_requests]
            thread_pool.wait()
            start_result = self.__check_thread_success(regions)
            if not start_result['ret']:
                return {'ret': False, 'msg': start_result['msg']}
            logger.info('service deploy success in regions: %s, round: %s' % (regions, region_round))
        return {'ret': True, 'msg': u'所有区域%s' % {
            'deploy': '第%s轮服务部署成功' % self.round_num,
            'change': '替换生产环境配置成功',
            'changeback': '替换预生产配置成功'
        }.get(self.method)}

    def stop_old_module_instances(self):
        for _, regions in self.region_order_dict.items():
            for region_name in regions:
                region_obj = RegionInfo.objects.get(region=region_name)
                modules = region_obj.moduleinfo_set.filter(order=self.round_num - 1)
                instance_patterns = ['*-%s-%s-*' % (module.module_name, module.current_version) for module in modules]
                logger.debug('in %s, round %s ,old version instances patterns are %s' % (region_name,
                                                                                         self.round_num - 1,
                                                                                         instance_patterns))
                instances = ec2api.find_instances(region_name, instance_patterns, True)
                for instance in instances:
                    instance.stop()

    def __check_thread_success(self, regions):
        if not self.flag:
            return {'ret': False, 'msg': 'flag is False, something wrong before deploy service, see error logs'}
        for region in regions:
            failed_service_list = self.results[region]['failed']
            if failed_service_list:
                error_msg = 'in region %s, deploy %s service failed' % (region, failed_service_list)
                logger.error(error_msg)
                return {'ret': False, 'msg': error_msg}
        return {'ret': True}

    def deploy_services_in_region(self, region_name):
        region_obj = RegionInfo.objects.get(region=region_name)
        if self.method == 'deploy':
            modules = region_obj.moduleinfo_set.filter(order=self.round_num)
        else:
            modules = region_obj.moduleinfo_set.exclude(order=-1)
        if not modules.count():
            error_msg = 'no update module found in region: %s' % region_name
            logger.error(error_msg)
            self.flag = False
            return
        sorted_modules = self.get_module_deploy_order(region_name, modules)
        for module_obj in sorted_modules:
            module_name = module_obj.module_name
            logger.info('%s module %s in region: %s' % (self.method, module_name, region_name))
            try:
                deploy_return = self.deploy_module(module_obj, region_obj)
                if deploy_return['ret']:
                    logger.info('%s %s success' % (self.method, module_name))
                    self.results[region_name]['success'].append(module_name)
                else:
                    error_msg = deploy_return['msg']
                    logger.info('%s %s failed, error_msg: %s' % (self.method, module_name,  error_msg))
                    self.results[region_name]['failed'].append({module_name: error_msg})
                    # todo: if one module deploy failed, stop deploy others or not?
            except:
                error_msg = 'execute %s method for %s failed:\n%s' % (self.method, module_name, traceback.format_exc())
                logger.error(error_msg)
                self.results[region_name]['failed'].append({module_name: error_msg})

    def get_module_deploy_order(self, region_name, modules):
        module_order_dict = {1: [], 2: [], 3: [], 4: []}
        for module in modules:
            try:
                biz_service_obj = module.bizservicelayer_set.all()[0]
            except:
                error_msg = 'get module(%s) service layer failed\n%s' % (module.module_name, traceback.format_exc())
                logger.error(error_msg)
                self.results[region_name]['failed'].append({module.module_name: error_msg})
                continue
            start_order = biz_service_obj.start_order
            module_order_dict[start_order].append(module)
        sorted_module_list = []
        for i in range(1, 5):
            sorted_module_list.extend(module_order_dict[i])
        return sorted_module_list

    def deploy_module(self, module_obj, region_obj):
        region_name = region_obj.region
        module_name = module_obj.module_name
        module_version = module_obj.update_version
        service_deploy_script = ServiceDeployScript()
        current_time = time.time()
        while 1:
            try:
                instance_ips, key_file_path = service_deploy_script.get_deploy_instances('%s-%s' % (
                    module_name,
                    module_version
                ), region_name)
                break
            except:
                if time.time() - current_time > 180:
                    error_msg = 'no running instances for module: %s-%s in 180s' % (module_name, module_version)
                    logger.error(error_msg)
                    raise Exception(error_msg)
        self.wait_instances_can_be_deploy(instance_ips, key_file_path)
        command = service_deploy_script.pre_work(module_name, module_version, region_name, self.method, self.username)
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.1)  # forget why i sleep here, if not sure, don't modify this
        stdout, stderr = p.communicate()
        ret_code = p.poll()
        if not ret_code:
            script_result = stdout
            logger.info('run command: %s success, output:\n%s' % (command, stdout))
            service_deploy_script.add_script_exec_log(self.username, service_deploy_script.script_name,
                                                      service_deploy_script.script_path, True, script_result)
            return {'ret': True}
        else:
            script_result = stdout + stderr
            logger.error('run command: %s failed, output:\n%s' % (command, script_result))
            errout = [err for err in stderr.splitlines() if err]
            errout = '\n'.join(errout)
            service_deploy_script.add_script_exec_log(self.username, service_deploy_script.script_name,
                                                      service_deploy_script.script_path, False, script_result)
            return {'ret': False, 'msg': errout}

    def wait_instances_can_be_deploy(self, instance_ips, key_file_path):
        current_time = time.time()
        while 1:
            if self.ping_instances(instance_ips, key_file_path):
                break
            else:
                if time.time() - current_time > MAX_WAIT_SECONDS_EVERY_LAYER:
                    error_msg = "instances cannot ping in %s seconds: %s" % (
                        MAX_WAIT_SECONDS_EVERY_LAYER,
                        ','.join(instance_ips)
                    )
                    logger.error(error_msg)
                    raise Exception(error_msg)

    @staticmethod
    def get_deploy_command(module_name, module_version, method, username, region):
        module_name_list = module_name.split('_')
        module_version_list = module_version.split('_')
        if len(module_name_list) != len(module_version_list):
            raise Exception('module count are not equal with version count for module: %s, version: %s' % (
                module_name,
                module_version
            ))
        run_deploy_cmd = 'python serviceDeploy.py -m %s -n %s -u %s -r %s -p' % (
            method,
            ','.join(module_name_list),
            username,
            region
        )
        return run_deploy_cmd

    @staticmethod
    def ping_instances(instance_ips, key_file_path):
        ansible_runner = AnsibleRunner()
        ansible_runner.run_ansible(module_name='ping', ip=','.join(instance_ips), keyfile=key_file_path)
        ping_results = ansible_runner.results
        failed = ping_results[0]['failed']
        if failed:
            logger.debug('instances can not ping: %s' % failed.keys())
            return False
        return True
