#! coding=utf8
# Filename    : batchamicreater.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging
import os
import traceback

import threadpool
from django.db.models import Q, datetime

from common.models import RegionInfo, AwsAccount
from deploy.amiutils.amicreater import get_update_instances, delete_logs, create_business_amis, add_auth
from deploy.amiutils.ec2checker import Ec2Checker
from deploy.amiutils.report import Report
from preprddeploy.settings import BASE_DIR

logger = logging.getLogger('deploy')


class BatchAmiCreater(object):
    def __init__(self, **args):
        self.regions = RegionInfo.get_all_regions()
        self.results = {}
        self.username = args['username']

    def __call__(self):
        thread_pool = threadpool.ThreadPool(len(self.regions))
        thread_requests = threadpool.makeRequests(self.create_ami_in_region, self.regions)
        [thread_pool.putRequest(req) for req in thread_requests]
        thread_pool.wait()
        create_ami_result = self.__check_thread_success()
        if not create_ami_result['ret']:
            return {'ret': False, 'msg': create_ami_result['msg']}
        logger.info('all ami create success in regions: %s' % self.regions)
        return {'ret': True, 'msg': u'所有区域[%s]ami制作完成' % ','.join(self.regions)}

    def __check_thread_success(self):
        for region in self.results:
            if 'failed' in self.results[region]:
                return {'ret': False, 'msg': self.results}
        return {'ret': True, 'msg': self.results}

    def create_ami_in_region(self, region_name):
        region_obj = RegionInfo.objects.get(region=region_name)
        modules = region_obj.moduleinfo_set.filter(~Q(update_version=u'') & ~Q(update_version=None))
        module_version_dict = {}
        for module in modules:
            module_version_dict.update({module.module_name: module.update_version})
        ret_dict = get_update_instances(region_name, module_version_dict, self.username)
        if not ret_dict['ret']:
            self.results.update({'region': {'failed': ret_dict['msg']}})
            return
        logger.info('find instances to create ami in region: %s' % region_name)
        boto_session = AwsAccount.get_awssession(region_name)
        ec2res = boto_session.resource('ec2')
        check_instances = []
        for instance_id in ret_dict['module_id_dict'].values():
            instance = ec2res.Instance(instance_id)
            check_instances.append(instance)
        try:
            ec2_checker = Ec2Checker(check_instances, region_name)
            check_result = ec2_checker.check()
            logger.debug('ec2 config check result:\n%s' % json.dumps(check_result))

            check_report = Report(check_instances, check_result)
            check_result_report = check_report.report()
            result_file_name = self.write_result_file(check_result_report, region_name)
            pass_check = check_report.pass_check(check_result)
        except:
            error_msg = 'occur error when checking instances conf in region:%s\n%s ' % (
                region_name,
                traceback.format_exc()
            )
            logger.error(error_msg)
            self.results.update({'region': {'failed': error_msg}})
            return
        if not pass_check:
            error_msg = 'instance conf check not pass in region %s, please see %s to get check result' % (
                region_name,
                result_file_name
            )
            logger.error(error_msg)
            self.results.update({'region': {'failed': error_msg}})
            return
        logger.info('instance check passed in region: %s' % region_name)
        try:
            retcode, ret_msg = delete_logs(self.username, region_name)
        except:
            error_msg = 'delete logs error: %s' % traceback.format_exc()
            logger.error(error_msg)
            self.results.update({'region': {'failed': error_msg}})
            return
        if not retcode:
            logger.error(ret_msg)
            self.results.update({'region': {'failed': ret_msg}})
            return
        logger.info('delete logs done.')
        try:
            avail_ami_list, failed_ami_list = create_business_amis(region_name,
                                                                   module_version_dict,
                                                                   ret_dict['module_id_dict'])
        except:
            error_msg = 'occur error when creating ami and waiting it available:\n%s' % traceback.format_exc()
            logger.error('in region: %s, %s' % (region_name, error_msg))
            self.results.update({'region': {'failed': ret_msg}})
            return
        if failed_ami_list:
            error_msg = 'some ami create failed: %s' % failed_ami_list
            logger.error('in region: %s, %s' % (region_name, error_msg))
            self.results.update({'region': {'failed': error_msg}})
            return
        logger.info('ami create success, start to auth to prd')
        ami_dict = {}
        for module_name, _, ami_id in avail_ami_list:
            ami_dict.update({module_name: ami_id})
        try:
            auth_success_list, auth_failed_list = add_auth(region_name, ami_dict)
        except:
            error_msg = 'occur error when add ami auth to prd:\n%s' % traceback.format_exc()
            logger.error('in region: %s, %s' % (region_name, error_msg))
            self.results.update({'region': {'failed': error_msg}})
            return
        if auth_failed_list:
            error_msg = 'some ami auth failed: %s' % auth_failed_list
            logger.error('in region: %s, %s' % (region_name, error_msg))
            self.results.update({'region': {'failed': error_msg}})
            return
        logger.info('ami create work done in %s' % region_name)
        self.results.update({'region': {'success': auth_success_list}})

    @staticmethod
    def write_result_file(check_result_report, region_name):
        date = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        result_file_name = 'ami_check_result_%s_%s' % (region_name, date)
        file_dir = os.path.join(BASE_DIR, 'static', 'ami_check_results')
        if not os.path.isdir(file_dir):
            os.makedirs(file_dir)
        with open(os.path.join(file_dir, result_file_name), 'w') as result_writer:
            result_writer.write(check_result_report)
        return result_file_name
