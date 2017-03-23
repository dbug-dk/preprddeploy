#! coding=utf8
# Filename    : bizstarter.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging
import os
from multiprocessing import Pool

import time


from bizmodule.models import BizServiceLayer
from common.libs import ec2api
from common.libs.ansible_api import AnsibleRunner
from common.models import RegionInfo
from preprddeploy.settings import STATIC_DIR, HOME_PATH

logger = logging.getLogger('deploy')


class BizInstanceStarter(object):
    def __init__(self):
        self.region_order = RegionInfo.get_all_regions_group_by_order()

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
            process_pool = Pool()
            process_results = []
            for region in regions:
                result = process_pool.apply_async(self.start_biz_service_in_region, args=(region,))
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
                elif process_return['failed']:
                    error_msg = 'not all services start success in region: %s, successed: %s, failed: %s' % (
                        region,
                        process_return['success'],
                        json.dumps(process_return['failed'])
                    )
                    logger.error(error_msg)
                    return {'ret': False, 'msg': error_msg}
            logger.info('all biz services started in regions: %s, round: %s' % (regions, round_num))
        return {'ret': True, 'msg': u'所有区域，业务实例启动完毕'}

    @staticmethod
    def start_biz_service_in_region(region):
        instance_info_dict = BizInstanceStarter.scan_all_instances(region)
        BizInstanceStarter.generate_hosts_file(region, instance_info_dict)
        total_layer_num = BizServiceLayer.count_layer()
        for order in xrange(1, len(total_layer_num) + 1):
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

    @staticmethod
    def scan_all_instances(region):
        biz_instances = ec2api.find_biz_instances(region)
        instance_info_dict = {}
        for instance in biz_instances:
            # TODO: start instance now?
            instance.start()
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
        biz_module_infos = BizInstanceStarter.get_biz_info_by_layer(order)
        if not biz_module_infos:
            error_msg = '%sth layer found no service, please check the database.' % order
            logger.error(error_msg)
            raise Exception(error_msg)
        logger.info('start biz service in region %s, layer order: %s' % (region, order))
        process_pool = Pool()
        process_results = []
        for service_type, services in biz_module_infos.items():
            process_results.append(process_pool.apply_async(BizInstanceStarter.start_services,
                                                            args=(services, service_type, region)))
        process_pool.close()
        process_pool.join()
        ret = {'success': [], 'failed': {}}
        for process_result in process_results:
            result = process_result.get()
            ret['success'] += result['success']
            ret['failed'].update(result['failed'])
        return ret

    @staticmethod
    def get_biz_info_by_layer(order):
        biz_services = BizServiceLayer.objects.filter(start_order=order)
        biz_module_infos = {}
        for service in biz_services:
            service_type = service.service_type
            module_name = service.module.module_name
            module_version = service.module.current_version
            hosts_pattern = '%s-%s' % (module_name, module_version)
            try:
                biz_module_infos[service_type].append(hosts_pattern)
            except KeyError:
                biz_module_infos.update({service_type: [hosts_pattern]})
        return biz_module_infos

    @staticmethod
    def start_services(services, service_type, region):
        try:
            start_method = getattr(BizInstanceStarter, 'start_%s_service' % service_type)
        except AttributeError:
            logger.warn('start method not found for type: %s, ignore these.' % service_type)
            return {'success': services, 'failed': {}}
        process_pool = Pool()
        process_results = []
        while services:
            service = services.pop()
            if BizInstanceStarter.ping_services(service, region):
                result = process_pool.apply_async(start_method, args=(service, region))
                process_results.append((service, result))
            else:
                services.insert(0, service)
        process_pool.close()
        process_pool.join()
        ret = {'success': [], 'failed': {}}
        for service, process_result in process_results:
            successful = process_result.successful()
            process_return = process_result.get()
            if not successful:
                # when not successful, process return the exception stack
                ret['failed'].update({service: process_return})
            elif process_return['ret']:
                ret['success'].append(service)
            else:
                ret['failed'].update({service: process_return['msg']})
        logger.debug('start services success: %s, failed: %s' % (ret['success'], ret['failed'].keys()))
        return ret

    @staticmethod
    def start_standard_service(service, region):
        logger.info('start standard service: %s in region: %s' % (service, region))
        service_name, service_version = service.split('-')
        service_bin_folder = '%s/cloud-%s/cloud-%s-%s/bin' % (
            HOME_PATH,
            service_name,
            service_name,
            service_version
        )
        start_cmd = '/bin/bash -c "source /etc/profile;cd %s;./start.sh -t' % service_bin_folder
        hosts_file_path = os.path.join(STATIC_DIR, 'hosts/hosts-%s' % region)
        ansible_runner = AnsibleRunner()
        ansible_runner.run_ansible(module_args=start_cmd,
                                   pattern=service,
                                   hosts_file=hosts_file_path)
        start_results = ansible_runner.results
        failed_infos = start_results[0]['failed']
        if failed_infos:
            error_msg = 'execute start.sh failed for %s in region: %s, failed instance num: %s, details: %s' % (
                service,
                region,
                start_results[1] + start_results[3],
                json.dumps(failed_infos)
            )
            logger.error(error_msg)
            return {'ret': False, 'msg': start_results['failed']}
        check_result = BizInstanceStarter.check_standard_service(service, region)
        if not check_result['ret']:
            return {'ret': False, 'msg': check_result['msg']}
        return {'ret': True}

    @staticmethod
    def check_standard_service(service, region):
        logger.info('start to check service: %s status in region: %s' % (service, region))
        service_name, service_version = service.split('-')
        service_bin_folder = '%s/cloud-%s/cloud-%s-%s/bin' % (
            HOME_PATH,
            service_name,
            service_name,
            service_version
        )
        check_cmd = '/bin/bash -c "source /etc/profile;cd %s;./status.sh' % service_bin_folder
        hosts_file_path = os.path.join(STATIC_DIR, 'hosts/hosts-%s' % region)
        return BizInstanceStarter.__get_status(check_cmd, service, hosts_file_path, region)

    @staticmethod
    def start_tomcat_service(service, region):
        logger.info('start tomcat service: %s in region: %s' % (service, region))
        service_name = service.split('-')[0]
        tomcat_bin_folder = '%s/cloud-%s/tomcat/bin' % (HOME_PATH, service_name)
        start_cmd = '/bin/bash -c "source /etc/profile;cd %s,nohup ./startup.sh&"' % tomcat_bin_folder
        hosts_file_path = os.path.join(STATIC_DIR, 'hosts/hosts-%s' % region)
        ansible_runner = AnsibleRunner()
        ansible_runner.run_ansible(module_args=start_cmd,
                                   pattern=service,
                                   hosts_file=hosts_file_path)
        start_results = ansible_runner.results
        failed_infos = start_results[0]['failed']
        if failed_infos:
            logger.error('start %s tomcat failed in region: %s, failed num: %s, details: %s' % (
                service,
                region,
                start_results[1] + start_results[3],
                json.dumps(failed_infos)
            ))
            return {'ret': False, 'msg': failed_infos}
        check_result = BizInstanceStarter.check_standard_service(service, region)
        if not check_result['ret']:
            return {'ret': False, 'msg': check_result['msg']}
        return {'ret': True}

    @staticmethod
    def check_tomcat_service(service, region):
        logger.info('start to check service: %s in region: %s' % (service, region))
        wait_time = 60
        start_time = time.time()
        service_name, service_version = service.split('-')
        status_file_path = '%s/cloud-%s/cloud-%s-%s/WEB-INF/classes' % (
            HOME_PATH,
            service_name,
            service_name,
            service_version
        )
        check_cmd = '/bin/bash -c "source /etc/profile;cd %s;./status.sh"' % status_file_path
        hosts_file_path = os.path.join(STATIC_DIR, 'hosts/hosts-%s' % region)
        while True:
            check_result = BizInstanceStarter.__get_status(check_cmd, service, hosts_file_path, region)
            if check_result['ret']:
                return check_result
            if time.time() - start_time > wait_time:
                logger.info('tomcat service: %s not running in %s seconds, region: %s' % (
                    service,
                    wait_time,
                    region
                ))
                return check_result
            logger.debug('service: %s not running in region: %s, sleep a while and check again.' % (service, region))
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
        if ping_results['failed']:
            logger.debug('service instances can not ping: %s' % ping_results['failed'].keys())
            return False
        return True
