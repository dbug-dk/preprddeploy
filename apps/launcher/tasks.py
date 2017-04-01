#! coding=utf8
# Filename    : tasks.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging

from celery import shared_task

from common.libs.dbconn import check_db_connection
from common.models import AwsResource, RegionInfo, AwsAccount
from module.models import ModuleInfo, Ec2OptionSet
from preprddeploy.settings import DEFAULT_PREPRD_VPC, DEFAULT_SECURITY_GROUP, ELB_MODULES
from preprddeploy.settings import DEFAULT_SUBNET

logger = logging.getLogger('common')


@shared_task
@check_db_connection
def save_aws_resource(resource_list, resource_type, region, account, parent=None):
    """
    save resources into AwsResource table.
    Args:
        resource_list (list): each element contains resource name and resource id.
        resource_type (string): resource type. eg: vpc, subnet, ami
        region (string): region name
        account (string): account name. eg: alpha, beta, prd
        parent (AwsResource): if resource type belong to another resource, set this.
    """
    region_obj = RegionInfo.objects.get(region=region)
    if region == 'cn-north-1':
        account_name = 'cn-%s' % account
    else:
        account_name = 'en-%s' % account
    account_obj = AwsAccount.objects.get(name=account_name)
    logger.info('delete all %s rows with account: %s' % (resource_type, account_name))
    AwsResource.objects.filter(resource_type=resource_type, region=region_obj,
                               account=account_obj, parent=parent).delete()
    logger.info('start to add %s rows with account: %s' % (resource_type, account_name))
    for index, resource_info in enumerate(resource_list):
        resource_name, resource_id = resource_info
        if index == 0:
            default = True
        else:
            default = False
        awsresource_obj = AwsResource(resource_name=resource_name, resource_id=resource_id, resource_type=resource_type,
                                      parent=parent, default=default, region=region_obj, account=account_obj
                                      )
        awsresource_obj.save()
    logger.debug('finish save all %s resource with account %s to table AwsResource' % (resource_type, account_name))




