#! coding=utf8
# Filename    : crontask.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import datetime
import json
import logging

from djcelery import models as celery_models
from django.utils import timezone

from preprddeploy.celery import app

logger = logging.getLogger('deploy')


def create_task(name, task, task_args, crontab_datetime):
    """
    create a crontab task by celery
    Args:
        name (string): task name
        task: celery task method
        task_args (dict): task args {'x': 1, 'y': 2}
        crontab_datetime (datetime.datetime): crontab datetime, {
            'month_of_year': 9, month
            'day_of_month': 5, day
            'hour': 1, hour
            'minute': 0, minute
        }
    """
    crontab_time = {
        'month_of_year': crontab_datetime.month,
        'day_of_month': crontab_datetime.day,
        'hour': crontab_datetime.hour,
        'minute': crontab_datetime.minute
    }
    task, created = celery_models.PeriodicTask.objects.get_or_create(name=name, task=task)
    crontab = celery_models.CrontabSchedule.objects.filter(**crontab_time).first()
    if crontab is None:
        crontab = celery_models.CrontabSchedule.objects.create(**crontab_time)
    task.crontab = crontab
    task.enabled = True
    task.kwargs = json.dumps(task_args)
    expiration = timezone.now() + datetime.timedelta(days=1)
    task.expires = expiration
    task.save()
    return True


def disable_task(name):
    try:
        task = celery_models.PeriodicTask.objects.get(name=name)
        task.enabled = False
        task.save(update_fields=['enabled'])
        return True
    except celery_models.PeriodicTask.DoesNotExist:
        logger.info('crontab task: %s has been deleted' % name)
        return True


@app.task
def delete_task():
    return celery_models.PeriodicTask.objects.filter(expires__lt=timezone.now()).delete()
