#! coding=utf8
##############################################################################
# Copyright (C), 2016 , TP-LINK Technologies Co., Ltd.
# Filename    : 
# Description : 
# Author      : dengken
# History:
#    1. 2017年2月16日 , dengken, first create
##############################################################################
import logging
from datetime import datetime

import traceback
from multiprocessing import JoinableQueue
from multiprocessing import Process
from multiprocessing import Queue
from pydoc import locate

from autodeploy.models import AutoDeployHistory
from preprddeploy.celery import app
from preprddeploy.settings import AUTO_DEPLOY_PROGRESS

logger = logging.getLogger('deploy')


class ProgressStarter(object):
    def __init__(self, progress_name, result_worker_cls):
        self.progress_name = progress_name
        self.task_queue = JoinableQueue()
        self.result_queue = Queue()
        self.add_tasks()
        self.result_worker_cls = result_worker_cls

    def add_tasks(self):
        child_progresses = AUTO_DEPLOY_PROGRESS[self.progress_name]['child_progress']
        logger.debug("progress's tasks classes: %s" % [task[0] for task in child_progresses])
        for child_progress in child_progresses:
            process_class_path = child_progress[0]
            cls = locate(process_class_path)
            self.task_queue.put(cls())
        self.task_queue.put(None)

    @app.task(bind=True)
    def start(self):
        deploy_worker = DeployWorker(self.task_queue, self.result_queue)
        deploy_worker.start()
        result_worker = self.result_worker_cls(self.result_queue)
        result_worker.start()


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
            AutoDeployHistory.update_current_step_num()
        AutoDeployHistory.update_deploy_history(task_pid=0,
                                                is_success=success_flag,
                                                end_time=datetime.now())


class ResultWorker(Process):
    def __init__(self, result_queue):
        Process.__init__(self)
        self.resultQueue = result_queue

    def run(self):
        AutoDeployHistory.update_deploy_history(result_pid=self.pid)
        while True:
            result = self.resultQueue.get()
            if result is None:
                logger.info('Found None in result queue, result worker exiting')
                # add log to db, get current progress info(current first step-1), and read log file content
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
            logger.info('finish deal with deploy result: %s' % result)
        AutoDeployHistory.update_deploy_history(result_pid=0, is_finish=True)

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
        AutoDeployHistory.update_log_content()
