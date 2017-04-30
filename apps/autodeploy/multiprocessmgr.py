#! coding=utf8
# Filename    : multiprocessmgr.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import traceback
from datetime import datetime
from multiprocessing import Process

import logging

from autodeploy.models import AutoDeployHistory

logger = logging.getLogger('deploy')


class DeployWorker(Process):
    def __init__(self, task_queue, result_queue):
        Process.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        AutoDeployHistory.update_deploy_history(task_pid=self.pid)
        success_flag = True
        while True:
            next_task = self.task_queue.get()
            if next_task is None:
                logger.info('all tasks in task queue have finished. wait all tasks done and exit.')
                AutoDeployHistory.update_deploy_history()
                self.result_queue.put(None)
                self.task_queue.task_done()
                break
            logger.info('start task: %s' % next_task)
            try:
                answer = next_task()
            except:
                error_msg = 'occur error when task exec, deploy worker exiting.\n'
                error_msg += traceback.format_exc()
                logger.error(error_msg)
                self.result_queue.put(error_msg)
                self.result_queue.put(None)
                success_flag = False
                break
            if answer['ret']:
                self.result_queue.put(answer['msg'])
            else:
                error_msg = 'auto deploy failed. error message:\n'
                error_msg += answer['msg']
                logger.error(error_msg)
                self.result_queue.put(error_msg)
                self.result_queue.put(None)
                success_flag = False
                break
            self.task_queue.task_done()
            logger.info('task done: %s' % next_task)
            AutoDeployHistory.update_current_task_num()
        AutoDeployHistory.update_deploy_history(task_pid=0,
                                                is_deploy_finish=True,
                                                is_success=success_flag,
                                                end_time=datetime.now())


class ResultWorker(Process):
    def __init__(self, result_queue):
        Process.__init__(self)
        self.resultQueue = result_queue

    def run(self):
        logger.info('start run result worker.')
        AutoDeployHistory.update_deploy_history(result_pid=self.pid)
        while True:
            result = self.resultQueue.get()
            if result is None:
                logger.info('Found None in result queue, result worker exiting')
                # add log to db, get current progress info(current first step-1), and read log file content
                self.resultQueue.task_done()
                break
            logger.info('get new deploy result: %s, start to deal with it.' % result)
            # do work with result
            try:
                self.deal_result(result)
            except:
                error_msg = 'Error occured when result worker deal result.'
                error_msg += traceback.format_exc()
                logger.error(error_msg)
                break
            else:
                logger.info('finish deal with deploy result: %s' % result)
                self.resultQueue.task_done()
        AutoDeployHistory.update_deploy_history(result_pid=0, is_result_finish=True)

    def deal_result(self, result):
        """
        work to do with deploy work result, overwrite this method to define operations
        Args:
            result (object): the result get from result queue.
        """
        pass


class StartEnvResultWorker(ResultWorker):
    def __init__(self, result_queue):
        ResultWorker.__init__(self, result_queue)

    def deal_result(self, result):
	logger.info('deal result by StartEnvResultWorker')
        AutoDeployHistory.update_log_content(result)

