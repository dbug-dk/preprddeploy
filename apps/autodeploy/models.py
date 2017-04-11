#! coding=utf8
import logging

from django.core.exceptions import MultipleObjectsReturned
from django.db import models

# Create your models here.
from django.db.models import Q

logger = logging.getLogger('deploy')


class AutoDeployHistory(models.Model):
    """
    column:
        upgrade_version: version of a preprd upgrade. like CN_2.1.0.json
        log_content: text of upgrade logs. will save after upgrade complete.
        upgrade_progress: the total progress of an upgrade.
                          example: {1: {'label':'first step', 'child_progress':{1:('startEnv',u'启动环境'}}}
        step_num: current step number
        task_num: in current step, the number of running task
        task_pid: process id of task runner.
        result_pid: process id of result dealer.
        is_finish: whether upgrade work finished.
        is_success: whether upgrade work finish successed.
        start_time: upgrade work start time, auto add.
        managers: all upgrade managers' mail. split by comma
    """
    upgrade_version = models.CharField(max_length=15)
    log_content = models.TextField(blank=True)
    progress_name = models.CharField(max_length=30)
    task_num = models.IntegerField()
    task_pid = models.IntegerField(default=0)
    result_pid = models.IntegerField(default=0)
    is_deploy_finish = models.BooleanField(default=False)
    is_result_finish = models.BooleanField(default=False)
    is_success = models.BooleanField(default=False)
    start_time = models.DateTimeField(auto_now_add=True)
    managers = models.CharField(max_length=100)
    end_time = models.DateTimeField(blank=True, null=True)

    def __unicode__(self):
        return '%s| %s| %s| %s| %s' % (
            self.upgrade_version,
            self.progress_name,
            self.is_deploy_finish and self.is_result_finish,
            self.is_success,
            self.managers
        )

    @staticmethod
    def get_current_deploy():
        try:
            auto_deploy_history = AutoDeployHistory.objects.get(Q(is_deploy_finish=False) | Q(is_result_finish=False))
        except AutoDeployHistory.DoesNotExist as e:
            logger.error('%s, query: is_deploy_finish=False or is result_finish=False' % e.message)
            raise Exception('no upgrade progress is running')
        except MultipleObjectsReturned as e:
            logger.error('%s, query: is_deploy_finish=False or is result_finish=False' % e.message)
            raise Exception('two or more upgrade progresses have not been finished, please check db.')
        return auto_deploy_history

    @staticmethod
    def update_deploy_history(model=None, **update_attrs):
        if not model:
            autodeploy_model = AutoDeployHistory.get_current_deploy()
        else:
            autodeploy_model = model
        for key, value in update_attrs.items():
            setattr(autodeploy_model, key, value)
        autodeploy_model.save(update_fields=update_attrs.keys())

    @staticmethod
    def update_current_task_num():
        """get current task num and add 1."""
        current_deploy_history_model = AutoDeployHistory.get_current_deploy()
        current_deploy_history_model.task_num += 1
        current_deploy_history_model.save(update_fields=['task_num'])

    @staticmethod
    def update_log_content(result):
        """get current task num and add 1."""
        current_deploy_history_model = AutoDeployHistory.get_current_deploy()
        current_deploy_history_model.log_content += '\n%s' % result
        current_deploy_history_model.save(update_fields=['log_content'])

    @staticmethod
    def add_new_deploy_history(upgrade_version, managers, method):
        """
        add a new deploy history when auto deploy start.
        Args:
            upgrade_version (string): upgrade version's pattern like EN/CN_X.Y.Z_ALPHA_YYYYMMDD
            managers (List): store all managers's mail address
            method(string): progress name
        """
        auto_deploy_history = AutoDeployHistory(upgrade_version=upgrade_version,
                                                progress_name=method,
                                                task_num=1, managers=','.join(managers))
        auto_deploy_history.save()

