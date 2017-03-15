#! coding=utf8
# Filename    : tasks.py
# Description : store task for celery
# Author      : dengken
# History:
#    1.  , dengken, first create
from celery import shared_task

from elb.models import LoadbalancerInfo


@shared_task
def save_elb_model(loadbalancer_dict, region):
    LoadbalancerInfo.save_elb_info(loadbalancer_dict, region)
