#! coding=utf8
# Filename    : opsetutils.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging

import re
import traceback

from retrying import retry
from common.libs import ec2api
from common.models import RegionInfo

logger = logging.getLogger('common')


def check_params_set(opset):
    """
    check if all requried fields are set.
    Args:
        opset (dict): dict of ec2 option set
    """
    not_pass = []
    for key, value in opset.items():
        if isinstance(value, bool) or isinstance(value, int):
            continue
        if not value or value == [None]:
            not_pass.append(key)
    print not_pass
    if opset['use_default_ebs_settings']:
        for key in ['volume_size', 'volumn_type', 'volume_iops']:
            try:
                not_pass.remove(key)
            except ValueError:
                pass
    if not opset['add_instance_to_elb']:
        try:
            not_pass.remove('elbs')
        except ValueError:
            pass
    if not_pass:
        raise Exception('%s must not be empty.' % ', '.join(not_pass))
    return True


def _distribute_subnets(count, subnets):
    num_in_each_subnet = {}
    subnets_num = len(subnets)
    dec = int(round(float(count) / subnets_num))
    for index, subnet in enumerate(subnets):
        if index < subnets_num - 1:
            # put $dec numbers of instances in each subnet ...
            num_in_each_subnet.update({subnet[1]: dec})
            count -= dec
        else:
            # ... except the last one. It gets all the remainder:
            num_in_each_subnet.update({subnet[1]: count})
    return num_in_each_subnet


def _format_tags(tags):
    ret = []
    for key, value in tags.items:
        ret.append({
            'Key': key,
            'Value': value
        })
    return ret


def run_instances(ec2res, elbclient, optionset, count):
    """
    Run 'count' number of instances use settings defined in 'optionset'.
    Args:
        ec2res: boto3 ec2 resource
        elbclient: boto3 elb client
        optionset: Ec2OptionSet obj
        count: instance number to launcher
    Returns:
        a list of instance ids on success.
    """
    opset = json.loads(optionset.content)
    image = optionset.image
    # check disk settings:
    block_device_mappings = []
    if not opset['use_default_ebs_settings'] and opset['volume_type'] == 'io1':
        bdm = {
            'DeviceName': '/dev/sda1',
            'Ebs': {
                'VolumeSize': opset['volume_size'],
                'DeleteOnTermination': True,
                'VolumeType': 'io1',
                'Iops': opset['volume_iops']
            }
        }
        block_device_mappings = [bdm]
    # check security group settings:
    security_group_ids = [opset['security_group'][1]]
    num_in_each_subnet = _distribute_subnets(count, opset['subnets'])
    # try to run instances:
    instance_ids = []
    for subnet_id, instance_count in num_in_each_subnet.items():
        try:
            instances = ec2res.create_instances(
                BlockDeviceMappings=block_device_mappings,
                IamInstanceProfile={
                    'Arn': opset['instance_profile'][1]
                },
                ImageId=image.resource_id,
                InstanceType=opset['instance_type'],
                KeyName=opset['keypair'][1],
                MinCount=instance_count,
                MaxCount=instance_count,
                SecurityGroupIds=security_group_ids,
                SubnetId=subnet_id
            )
            ids = [x.id for x in instances]
            instance_ids.extend(ids)
        except:
            raise
    if opset['add_instance_to_elb']:
        logger.info("add instance: %s to elb :%s" % (instance_ids, ','.join(opset['elbs'])))
        for elb in opset['elbs']:
            elbclient.register_instances_with_load_balancer(
                LoadBalancerName=elb,
                Instances=[{'InstanceId': instance_id} for instance_id in instance_ids]
            )
    return instance_ids


def get_tags_by_module(module_info_obj, region_name):
    region_obj = RegionInfo.objects.get(region=region_name)
    tags = {"Category": "preprd"}
    instance_name = 'preprd-%s-%s-%s-a' % (module_info_obj.module_name,
                                           module_info_obj.update_version,
                                           region_obj.abbr)
    tags.update({'Name': instance_name})
    return tags


def _get_instances_max_number(prefix, instances):
    p = prefix + "-(\d+)"
    max_number = -1
    for instance in instances:
        name = ec2api.get_instance_tag_name(instance)
        m = re.match(p, name)
        if m is not None:
            num = int(m.groups()[0])
            if num > max_number:
                max_number = num
    return max_number


def add_ec2_tags(ec2res, tags, instance_ids):
    ret = {'success': [], 'failed': []}
    prefix = tags['Name']
    # list instances with the same prefix:
    instances = ec2res.instances.filter(
        Filters=[
            {
                'Name': 'tag:Name',
                'Values': [prefix+"*"]
            },
            {
                'Name': 'instance-state-name',
                'Values': ['running', 'stopped', 'stopping', 'pending']
            }
        ]
    )
    # get largest instance number:
    max = _get_instances_max_number(prefix, instances)
    # tag each instance:
    num = max + 1
    for instance_id in instance_ids:
        tags.update({'Name': prefix + "-" + str(num)})
        boto3tags = []
        for key in tags.keys():
            boto3tags.append({
                'Key': key,
                'Value': tags[key]
            })
        num += 1

        try:
            instance = ec2res.Instance(instance_id)
            instance.create_tags(
                Tags=boto3tags
            )
            ret['success'].append(instance_id)
        except:
            logger.error('add ec2(%s) tags failed:\n%s' % (
                instance_id,
                traceback.format_exc()
            ))
            ret['failed'].append(instance_id)
    return ret


@retry(stop_max_attempt_number=3, wait_fixed=10)
def add_volume_tags(ec2res, instance_ids):
    """
    Add volume tags with instance information
    Args:
        ec2res: boto3 ec2 resource
        instance_ids (list): instance ids
    """
    ret = {'success': [], 'failed': []}
    # for each instance
    for instance_id in instance_ids:
        try:
            instance = ec2res.Instance(instance_id)
            # get volume tags:
            boto3tags = [
                {
                    'Key': 'InstanceId',
                    'Value': instance_id
                },
                {
                    'Key': 'Name',
                    'Value': ec2api.get_instance_tag_name(instance)
                }]
            for volume in instance.volumes.all():
                volume.create_tags(Tags=boto3tags)
            ret['success'].append(instance_id)
        except Exception as ex:
            logger.error('add ebs(%s) tags failed:\n%s' % (
                instance_id,
                traceback.format_exc()
            ))
            ret['failed'].append(instance_id)
    if ret['failed']:
        raise Exception('add ebs tags failed: %s' % ', '.join(ret['failed']))


def get_opset_dict(ec2_opset_obj):
    ret = {}
    if ec2_opset_obj.image is None:
        ret.update({'image': None})
    else:
        ret.update({'image': [ec2_opset_obj.image.resource_name, ec2_opset_obj.image.resource_id]})
    ret.update({
        "name": ec2_opset_obj.name,
        "tags": json.loads(ec2_opset_obj.tags) if ec2_opset_obj.tags else None
    })
    if ec2_opset_obj.module is None:
        ret.update({'module': None})
    else:
        ret.update({'module': ec2_opset_obj.module.module_name})
    ret.update(json.loads(ec2_opset_obj.content))
    return ret
