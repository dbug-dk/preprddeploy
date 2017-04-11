#! coding=utf8
# Filename    : bizstarter.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging
import multiprocessing
import multiprocessing.pool

import os

import time


from bizmodule.models import BizServiceLayer
from common.libs import ec2api
from common.libs.ansible_api import AnsibleRunner
from common.models import RegionInfo

from preprddeploy.settings import STATIC_DIR, HOME_PATH, MAX_WAIT_SECONDS_EVERY_LAYER, MAX_WAIT_SECONDS_EVERY_SERVICE

logger = logging.getLogger('deploy')


def start_biz_service_in_region(region):
    instance_info_dict = BizInstanceStarter.scan_all_instances(region)
    BizInstanceStarter.generate_hosts_file(region, instance_info_dict)
    total_layer_num = BizServiceLayer.count_layer()
    for order in xrange(1, total_layer_num + 1):
        start_result = BizInstanceStarter.start_biz_service(region, order)
        if start_result['failed']:
            error_msg = 'some services start failed in region: %s, order: %s, details: %s' % (
                region,
                order,
                json.dumps(start_result['failed'])
            )
            logger.error(error_msg)
            return {'ret': False, 'msg': error_msg}
        logger.info('all biz instance service start success in region: %s, layer: %s, services: %s' % (
            region,
            order,
            start_result['success']
        ))
    return {'ret': True}


def check_module_state(module, region):
    module_name, module_version = module.split('-')
    ret = {'success': [], 'failed': {}}
    for service_name, service_version in zip(module_name.split('_'), module_version.split('_')):
        service_type = BizServiceLayer.objects.get(service_name=service_name).service_type
        check_method = getattr(BizInstanceStarter, 'check_%s_service' % service_type)
        check_result = check_method(service_name, service_version, region, retry=True)
        service = '%s-%s' % (service_name, service_version)
        if check_result['ret']:
            ret['success'].append(service)
        else:
            ret['failed'].update({service: check_result['msg']})
    return ret


class NoDaemonProcess(multiprocessing.Process):
    # make 'daemon' attribute always return False
    def _get_daemon(self):
        return False

    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)


class MyPool(multiprocessing.pool.Pool):
    Process = NoDaemonProcess


class BizInstanceStarter(object):
    def __init__(self):
        self.region_order = RegionInfo.get_all_regions_group_by_order()
        self.service_type_dict = {}

    def __call__(self):
        total_round = len(self.region_order)
        for round_num in xrange(1, total_round + 1):
            regions = self.region_order.get(round_num)
            if not regions:
                error_msg = 'region order not continuous: %s, miss %s' % (self.region_order,
                                                                          round_num
                                                                          )
                logger.error(error_msg)
                logger.error('start biz instance service cancel')
                return {'ret': False, 'msg': u'RegionInfo表中数据有误，中止启动基础服务\n%s' % error_msg}
            process_pool = MyPool()
            process_results = []
            for region in regions:
                result = process_pool.apply_async(start_biz_service_in_region, args=(region,))
                process_results.append((region, result))
            process_pool.close()
            process_pool.join()
            for region, start_result in process_results:
                process_return = start_result.get()
                if not start_result.successful():
                    error_msg = 'start biz service in region: %s failed, details: %s' % (
                        region,
                        process_return
                    )
                    logger.error(error_msg)
                    return {'ret': False, 'msg': error_msg}
                elif not process_return['ret']:
                    return process_return
            logger.info('all biz services started in regions: %s, round: %s' % (regions, round_num))
        return {'ret': True, 'msg': u'所有区域，业务实例启动完毕'}

    @staticmethod
    def scan_all_instances(region):
        biz_instances = ec2api.find_biz_instances(region)
        instance_info_dict = {}
        for instance in biz_instances:
            instance_name = ec2api.get_instance_tag_name(instance)
            ip = instance.private_ip_address
            key_name = instance.key_name
            module_name, module_version = ec2api.get_module_info(instance_name)
            services = module_name.split('_')
            versions = module_version.split('_')
            if len(services) != len(versions):
                error_msg = 'instance name not correct: %s, service number and version number not equal' % instance_name
                logger.error(error_msg)
                raise Exception(error_msg)
            for name, version in zip(services, versions):
                if not instance_info_dict.get(name):
                    instance_info_dict.update({
                        name: {
                            version: [
                                (ip, key_name)
                            ]
                        }
                    })
                elif not instance_info_dict[name].get(version):
                    instance_info_dict[name].update({
                        version: [
                            (ip, key_name)
                        ]
                    })
                else:
                    instance_info_dict[name][version].append(
                        (ip, key_name)
                    )
        logger.debug('all business isntances info dict: %s' % json.dumps(instance_info_dict))
        return instance_info_dict

    @staticmethod
    def generate_hosts_file(region, instance_info_dict):
        hosts_file_name = 'hosts-%s' % region
        pem_dir = os.path.join(HOME_PATH, 'pem')
        logger.info('start to write ansible hosts file: %s' % hosts_file_name)
        with open(os.path.join(STATIC_DIR, 'hosts', hosts_file_name), 'w') as file_writer:
            for module_name, version_info_dict in instance_info_dict.items():
                module_lines = ["[%s:children]\n" % module_name]
                for version, instance_infos in version_info_dict.items():
                    group_name = '%s-%s' % (module_name, version)
                    module_lines.append(group_name + '\n')
                    file_writer.write('[%s]\n' % group_name)
                    for instance_info in instance_infos:
                        file_writer.write('%s\tansible_ssh_private_key_file=%s/%s.pem\n' % (
                            instance_info[0],
                            pem_dir,
                            instance_info[1]
                        ))
                file_writer.writelines(module_lines)
        logger.info('successfully generate hosts file')

    @staticmethod
    def start_biz_service(region, order):
        biz_modules = BizInstanceStarter.get_biz_modules_by_layer(order)
        if not biz_modules:
            error_msg = '%sth layer found no service, please check the database.' % order
            logger.error(error_msg)
            raise Exception(error_msg)
        logger.info('start biz service in region %s, layer order: %s' % (region, order))
        return BizInstanceStarter.start_services(biz_modules, region)

    @staticmethod
    def get_biz_modules_by_layer(order):
        biz_services = BizServiceLayer.objects.filter(start_order=order)
        biz_modules = []
        for service in biz_services:
            module_name = service.module.module_name
            module_version = service.module.current_version
            hosts_pattern = '%s-%s' % (module_name, module_version)
            biz_modules.append(hosts_pattern)
        return list(set(biz_modules))

    @staticmethod
    def start_services(modules, region):
        instance_patterns = ['*-%s-*' % pattern for pattern in modules]
        instances = ec2api.find_instances(region, instance_patterns)
        start_results = ec2api.start_instances(instances)
        if start_results['failed']:
            raise Exception('some instance start failed: %s' % start_results['failed'])
        current_time = time.time()
        process_pool = MyPool()
        process_results = []
        while modules:
            module = modules.pop()
            if BizInstanceStarter.ping_services(module, region):
                result = process_pool.apply_async(check_module_state, (module, region))
                process_results.append((module, result))
            else:
                modules.insert(0, module)
                if time.time() - current_time > MAX_WAIT_SECONDS_EVERY_LAYER:
                    error_msg = "some modules' instances cannot ping in %s seconds: %s" % (
                        MAX_WAIT_SECONDS_EVERY_LAYER,
                        ','.join(modules)
                    )
                    logger.error(error_msg)
                    raise Exception(error_msg)
        process_pool.close()
        process_pool.join()
        ret = {'success': [], 'failed': {}}
        for module, process in process_results:
            process_return = process.get()
            if not process.successful():
                error_msg = 'execute check module: %s state failed, details: %s' % (
                    module,
                    process_return
                )
                ret['failed'].update({module: error_msg})
            else:
                ret['success'] += process_return['success']
                ret['failed'].update(process_return['failed'])
        logger.debug('start services success: %s, failed: %s' % (ret['success'], ret['failed'].keys()))
        return ret

    @staticmethod
    def check_standard_service(service_name, service_version, region, ips=None, retry=False):
        logger.info('start to check service: %s-%s status in region: %s' % (
            service_name,
            service_version,
            region
        ))
        start_time = time.time()
        service_bin_folder = '%s/cloud-%s/cloud-%s-%s/bin' % (
            HOME_PATH,
            service_name,
            service_name,
            service_version
        )
        check_cmd = '/bin/bash -c "source /etc/profile;cd %s;./status.sh"' % service_bin_folder
        hosts_file_path = os.path.join(STATIC_DIR, 'hosts/hosts-%s' % region)
        if ips:
            pattern = ':'.join(ips)
        else:
            pattern = '%s-%s' % (service_name, service_version)
        while True:
            check_result = BizInstanceStarter.__get_status(check_cmd, pattern, hosts_file_path, region)
            if not retry or check_result['ret']:
                return check_result
            if time.time() - start_time > MAX_WAIT_SECONDS_EVERY_SERVICE:
                logger.info('standard service: %s-%s not running in %s seconds, region: %s' % (
                    service_name,
                    service_version,
                    MAX_WAIT_SECONDS_EVERY_SERVICE,
                    region
                ))
                return check_result
            logger.debug('service: %s-%s not running in region: %s, sleep a while and check again.' % (
                service_name,
                service_version,
                region))
            time.sleep(10)

    @staticmethod
    def check_tomcat_service(service_name, service_version, region, ips=None, retry=False):
        logger.info('start to check service: %s-%s in region: %s' % (
            service_name,
            service_version,
            region
        ))
        start_time = time.time()
        status_file_path = '%s/cloud-%s/cloud-%s-%s/WEB-INF/classes' % (
            HOME_PATH,
            service_name,
            service_name,
            service_version
        )
        check_cmd = '/bin/bash -c "source /etc/profile;cd %s;./status.sh"' % status_file_path
        hosts_file_path = os.path.join(STATIC_DIR, 'hosts/hosts-%s' % region)
        if ips:
            pattern = ':'.join(ips)
        else:
            pattern = '%s-%s' % (service_name, service_version)
        while True:
            check_result = BizInstanceStarter.__get_status(check_cmd, pattern, hosts_file_path, region)
            if not retry or check_result['ret']:
                return check_result
            if time.time() - start_time > MAX_WAIT_SECONDS_EVERY_SERVICE:
                logger.info('tomcat service: %s-%s not running in %s seconds, region: %s' % (
                    service_name,
                    service_version,
                    MAX_WAIT_SECONDS_EVERY_SERVICE,
                    region
                ))
                return check_result
            logger.debug('service: %s-%s not running in region: %s, sleep a while and check again.' % (
                service_name,
                service_version,
                region))
            time.sleep(10)

    @staticmethod
    def __get_status(cmd, service, hosts_file, region):
        ansible_runner = AnsibleRunner()
        ansible_runner.run_ansible(module_args=cmd, pattern=service, hosts_file=hosts_file)
        check_results = ansible_runner.results
        failed_infos = check_results[0]['failed']
        if failed_infos:
            error_msg = 'execute status.sh failed, service: %s, region: %s' % (
                service,
                region
            )
            return {'ret': False, 'msg': error_msg}
        for host, stdout in check_results[0]['ok'].items():
            if not stdout:
                logger.info('%s(%s) in region: %s not running because of status.sh return nothing' % (
                    service,
                    host,
                    region
                ))
                return {'ret': False, 'msg': '%s status.sh return nothing' % host}
            stdout_line = stdout.split(' ')
            keyword_list = [word for word in stdout_line if word.lower() in ['no', 'not']]
            if keyword_list:
                logger.info("%s(%s) not running because of status.sh's stdout contain no or not" % (
                    service,
                    host
                ))
                return {'ret': False, 'msg': '%s status.sh returns no or not' % host}
        logger.info('service: %s are running in region: %s' % (service, region))
        return {'ret': True}

    @staticmethod
    def ping_services(service, region):
        hosts_file_path = os.path.join(STATIC_DIR, 'hosts/hosts-%s' % region)
        ansible_runner = AnsibleRunner()
        ansible_runner.run_ansible(module_name='ping',
                                   pattern=service,
                                   hosts_file=hosts_file_path)
        ping_results = ansible_runner.results
        failed = ping_results[0]['failed']
        if failed:
            logger.debug('service instances can not ping: %s' % failed.keys())
            return False
        return True

