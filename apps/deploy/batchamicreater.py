#! coding=utf8
# Filename    : batchamicreater.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import logging

import threadpool

from common.models import RegionInfo

logger = logging.getLogger('deploy')


class BatchAmiCreater(object):
    def __init__(self):
        self.regions = RegionInfo.get_all_regions()
        self.results = {}

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

    def create_ami_in_region(self, region):
        pass