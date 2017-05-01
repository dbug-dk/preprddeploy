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

from multiprocessing import JoinableQueue
from multiprocessing import Queue
from pydoc import locate

from autodeploy.multiprocessmgr import DeployWorker
from preprddeploy.settings import AUTO_DEPLOY_PROGRESS

logger = logging.getLogger('deploy')


class ProgressStarter(object):
    def __init__(self, progress_name, result_worker_cls, **args):
        self.progress_name = progress_name
        self.task_queue = JoinableQueue()
        self.result_queue = JoinableQueue() 
        self.add_tasks(**args)
        self.result_worker_cls = result_worker_cls

    def add_tasks(self, **args):
        child_progresses = AUTO_DEPLOY_PROGRESS[self.progress_name]['child_progress']
        logger.debug("progress's tasks classes: %s" % [task[0] for task in child_progresses])
        for child_progress in child_progresses:
            process_class_path = child_progress[0]
            cls = locate(process_class_path)
            self.task_queue.put(cls(**args))
        self.task_queue.put(None)

    def start(self):
        deploy_worker = DeployWorker(self.task_queue, self.result_queue)
#        deploy_worker.daemon = True
        deploy_worker.start()
        result_worker = self.result_worker_cls(self.result_queue)
#        result_worker.daemon = True
        result_worker.start()

