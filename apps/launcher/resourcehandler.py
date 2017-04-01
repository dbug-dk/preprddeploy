#! coding=utf8
# Filename    : resourcehandler.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import json
import logging

from common.models import AwsAccount, AwsResource
from preprddeploy.settings import DEFAULT_PREPRD_VPC, DEFAULT_IMAGE_PATTERN, DEFAULT_INSTANCE_PROFILE_NAME, \
                                  ELB_MODULES, DEFAULT_SUBNET, DEFAULT_SECURITY_GROUP
from tasks import save_aws_resource

logger = logging.getLogger('common')


class AwsResourceHandler(object):
    def __init__(self, account_name, region):
        self.account_name = account_name
        self.region = region
        self.session = AwsAccount.get_awssession(region, account_name)
        self.resources = {
            "images": [],
            "keypairs": [],
            "instance_types": [], # AwsResource.load_instance_types(self.region, self.account_name),
            "vpcs": [],
            "subnets": {},
            "security_groups": {},
            "instance_profiles": [],
            "elbs": {}
        }

    def update_resources(self):
        logger.info('updating images...')
        self.resources['images'] = self.list_images()
        logger.info('updating keypairs...')
        self.resources['keypairs'] = self.list_keypairs()
        logger.info('updating vpcs...')
        self.resources['vpcs'] = self.list_vpcs()
        logger.info('updating subnets')
        for vpc_name, vpc_id in self.resources['vpcs']:
            self.resources['subnets'].update({
                vpc_id: self.list_subnets(vpc_id)
            })
        logger.info('updating security groups...')
        for vpc_name, vpc_id in self.resources['vpcs']:
            self.resources["security_groups"].update({
                vpc_id: self.list_security_groups(vpc_id)
            })
        logger.info('updating instance profiles...')
        self.resources['instance_profiles'] = self.list_instance_profile()

    def list_images(self):
        ec2conn = self.session.resource('ec2')
        images = ec2conn.images.filter(Filters=[{
            'Name': 'is-public',
            'Values': ['false']
        }])
        default_ami_list = []
        other_ami_list = []
        for image in images:
            if DEFAULT_IMAGE_PATTERN in image.name:
                default_ami_list.append([image.name, image.id])
            else:
                other_ami_list.append([image.name, image.id])
        default_ami_list.sort(reverse=True)
        default_ami_list.extend(other_ami_list)
        save_aws_resource.delay(default_ami_list, 'ami', self.region, self.account_name)
        return default_ami_list

    def list_keypairs(self):
        ec2conn = self.session.resource('ec2')
        keypairs = ec2conn.key_pairs.all()
        ret = []
        default_key = None
        for keypair in keypairs:
            keypair_name = keypair.name
            if 'preprd' in keypair_name and 'cloud' in keypair_name:
                default_key = (keypair_name, keypair_name)
            else:
                ret.append((keypair_name, keypair_name))
        ret.sort()
        if default_key:
            ret.insert(0, default_key)
        else:
            logger.error('there is no keypair name like: preprd-xxx-cloud')
        save_aws_resource.delay(ret, 'keypair', self.region, self.account_name)
        return ret

    def list_instance_profile(self):
        iamconn = self.session.resource('iam')
        instance_profiles = iamconn.instance_profiles.all()
        ret = []
        default = None
        for instance_profile in instance_profiles:
            instance_profile_name = instance_profile.name
            if instance_profile_name == DEFAULT_INSTANCE_PROFILE_NAME:
                default = (instance_profile_name, instance_profile.arn)
            else:
                ret.append((instance_profile_name, instance_profile.arn))
        ret.sort()
        if default:
            ret.insert(0, default)
        else:
            logger.error('there is no instance profile named s3_upload')
        save_aws_resource.delay(ret, 'instance_profile', self.region, self.account_name)
        return ret

    def list_vpcs(self):
        ec2conn = self.session.resource('ec2')
        vpcs = ec2conn.vpcs.all()
        ret = []
        default_vpc = DEFAULT_PREPRD_VPC[self.region]
        default_vpc_id = default_vpc[1]
        for vpc in vpcs:
            vpcid = vpc.vpc_id
            if vpcid != default_vpc_id:
                vpc_name = self.get_resource_tag(vpc, 'Name')
                ret.append((vpc_name, vpcid))
        ret.sort()
        ret.insert(0, default_vpc)
        save_aws_resource(ret, 'vpc', self.region, self.account_name)
        return ret

    def list_subnets(self, vpc_id):
        ec2conn = self.session.resource('ec2')
        subnets = ec2conn.subnets.filter(Filters=[
            {
                'Name': 'vpc-id',
                'Values': [vpc_id]
            }
        ])
        ret = []
        for subnet in subnets:
            subnet_name = self.get_resource_tag(subnet, 'Name')
            ret.append((subnet_name, subnet.subnet_id))
        ret.sort()
        vpc_obj = AwsResource.objects.get(resource_id=vpc_id)
        save_aws_resource.delay(ret, 'subnet', self.region, self.account_name, vpc_obj)
        return ret

    def list_security_groups(self, vpc_id):
        ec2conn = self.session.resource('ec2')
        security_groups = ec2conn.security_groups.filter(Filters=[
            {
                'Name': 'vpc-id',
                'Values': [vpc_id]
            }
        ])
        ret = []
        for sg in security_groups:
            sg_name = self.get_resource_tag(sg, 'Name')
            if sg_name:
                ret.append((sg_name, sg.group_id))
            else:
                ret.append((sg.group_name, sg.group_id))
        ret.sort()
        vpc_obj = AwsResource.objects.get(resource_id=vpc_id)
        save_aws_resource.delay(ret, 'security_group', self.region, self.account_name, vpc_obj)
        return ret

    def list_loadbalancers(self, vpc_id):
        elbconn = self.session.client('elb')
        loadbalancers = elbconn.describe_load_balancers()['LoadBalancerDescriptions']
        ret = []
        for loadbalancer in loadbalancers:
            elb_name = loadbalancer['LoadBalancerName']
            belong_vpc = loadbalancer['VPCId']
            if belong_vpc == vpc_id:
                ret.append((elb_name, ''))
        ret.sort()
        vpc_obj = AwsResource.objects.get(resource_id=vpc_id)
        save_aws_resource.delay(ret, 'loadbalancer', self.region, self.account_name, vpc_obj)
        return ret

    @staticmethod
    def get_resource_tag(resource, tag_name):
        resource_tags = resource.tags
        if resource_tags is None:
            return ""
        for tag in resource_tags:
            if tag['Key'] == tag_name:
                return tag['Value']
        return ""


