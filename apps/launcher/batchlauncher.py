#! coding=utf8
# Filename    : batchlauncher.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging
import traceback

import threadpool
from django.db.models import Q
from multiprocessing import cpu_count

from common.models import RegionInfo, AwsAccount
from launcher.opsetutils import get_tags_by_module, run_instances, add_ec2_tags, add_volume_tags
from module.models import ModuleInfo

logger = logging.getLogger('deploy')


class Ec2BatchLauncher(object):
    def __init__(self):
        self.success_modules = {}
        self.failed_modules = {}

    def __call__(self):
        regions = RegionInfo.objects.all()
        thread_pool = threadpool.ThreadPool(regions.count())
        requests = threadpool.makeRequests(self.run_instance_in_region, regions)
        [thread_pool.putRequest(req) for req in requests]
        thread_pool.wait()
        return self.deal_results()

    def deal_results(self):
        error_msg = ''
        for region in self.failed_modules:
            if self.failed_modules[region]:
                error_msg += 'in region: %s, some module instances launch failed, details: %s' % (
                    region,
                    json.dumps(self.failed_modules[region])
                )
        if error_msg:
            return {'ret': False, 'msg': error_msg}
        all_update_modules = ModuleInfo.objects.filter(~Q(update_version=u'') & ~Q(update_version=None))
        module_names = all_update_modules.values_list('module_name', flat=True)
        return {'ret': True, 'msg': u'所有区域的实例创建成功: %s' % json.dumps(self.success_modules)}

    def run_instance_in_region(self, region_obj):
        modules = region_obj.moduleinfo_set.filter(~Q(update_version=u'') & ~Q(update_version=None))
        region_name = region_obj.region
        self.success_modules.update({region_name: []})
        self.failed_modules.update({region_name: {}})
        if not modules:
            self.failed_modules[region_name].update({'error_msg': 'no update module found in region: %s' % region_name})
            return
        thread_pool = threadpool.ThreadPool(cpu_count() * 3)
        thread_func_val = []
        for module in modules:
            thread_func_val.append(([region_obj, module], None))
        requests = threadpool.makeRequests(self.launch_instances, thread_func_val)
        logger.info('launch all instances in region: %s' % region_name)
        [thread_pool.putRequest(req) for req in requests]
        thread_pool.wait()
        logger.info('finish launching instances in region: %s' % region_name)

    def launch_instances(self, region_obj, module_obj):
        region_name = region_obj.region
        module_name = module_obj.module_name
        logger.info('launch instances for module: %s in region: %s' % (module_name, region_name))
        ec2opset_objs = module_obj.ec2optionset_set.filter(region=region_obj)
        opset_count = ec2opset_objs.count()
        if opset_count == 0:
            self.failed_modules[region_name].update({module_name: 'no launch parameters found in %s' % region_name})
            return
        if opset_count > 1:
            self.failed_modules[region_name].update({
                module_name: 'too many launch parameters (%s) found for module in %s.' % (
                    opset_count,
                    region_name
                )})
            return
        ec2opset_obj = ec2opset_objs[0]
        if ec2opset_obj.image is None:
            self.failed_modules[region_name].update({module_name: 'image in %s has been registered.' % region_name})
            return
        try:
            tags = get_tags_by_module(module_obj, region_name)
            ec2opset_obj.tags = tags
            session = AwsAccount.get_awssession(region_name)
            ec2res = session.resource('ec2')
            elbclient = session.client('elb')
            instance_ids = run_instances(ec2res, elbclient, ec2opset_obj, module_obj.instance_count)
        except:
            self.failed_modules[region_name].update({module_name: 'launch instance faled: \n%s' % traceback.format_exc()})
            return
        self.add_tags(ec2res, module_obj, region_name, instance_ids)

    def add_tags(self, ec2res, module_obj, region_name, instance_ids):
        module_name = module_obj.module_name
        try:
            instance_tags = get_tags_by_module(module_obj, region_name)
            result = add_ec2_tags(ec2res, instance_tags, instance_ids)
        except:
            error_msg = 'add instance tags failed, error msg:\n%s' % traceback.format_exc()
            logger.error(error_msg)
            self.failed_modules[region_name].update({module_name: error_msg})
            return
        if result['failed']:
            error_msg = 'some instances add instance tags failed %s' % ', '.join(result['failed'])
            logger.error(error_msg)
            self.failed_modules[region_name].update({module_name: error_msg})
            return
        logger.info('success add instance tags for module: %s' % module_name)
        try:
            add_volume_tags(ec2res, instance_ids)
        except:
            error_msg = 'add ebs tags failed, error msg:\n%s' % traceback.format_exc()
            logger.error(error_msg)
            self.failed_modules[region_name].update({module_name: error_msg})
        else:
            logger.info('add ebs tags success, launch %s instances in region %s success' % (module_name, region_name))
            self.success_modules[region_name].append(module_name)
