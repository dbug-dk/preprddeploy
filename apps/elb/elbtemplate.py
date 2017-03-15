#! coding=utf8
# Filename    : elbtemplate.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import os

from common.models import AwsAccount
from preprddeploy.settings import BASE_DIR, PREPRD_VPC


class ElbCfnTemplate(object):
    def __init__(self, region):
        self.region = region
        if region == 'cn-north-1':
            self.stack_name = 'elb-cn-beta'
        else:
            self.stack_name = 'elb-en-beta'
        self.elb_template_path = '%s/cfn-template/%s.template' % (os.path.join(BASE_DIR, 'static'),
                                                                  self.stack_name
                                                                  )

    def get_content(self):
        with open(self.elb_template_path) as elb_template:
            content = elb_template.read()
        return content

    def get_template_params(self, elbs):
        params_list = []
        vpc_id = PREPRD_VPC[self.region][1]
        param_dict = {
             "ParameterKey": "vpcId",
             "ParameterValue": vpc_id
        }
        params_list.append(param_dict)
        ec2conn = AwsAccount.get_awssession(self.region).resource('ec2')
        vpc = ec2conn.Vpc(vpc_id)
        # todo: get args from db table AwsResource
        subnets = vpc.subnets.all()
        private_subnets = []
        public_subnets = []
        for subnet in subnets:
            for tag in subnet.tags:
                if tag['Key'] == 'Name':
                    subnet_name = tag['Value']
                    if 'prv' in subnet_name:
                        private_subnets.append(subnet.subnet_id)
                    elif 'pub' in subnet_name:
                        public_subnets.append(subnet.subnet_id)
        params_list.append({
                        "ParameterKey": "privateSubnet1",
                        "ParameterValue": private_subnets[0]
                    })
        params_list.append({
                        "ParameterKey": "privateSubnet2",
                        "ParameterValue": private_subnets[1]
                    })
        params_list.append({
                        "ParameterKey": "publicSubnet1",
                        "ParameterValue": public_subnets[0]
                    })
        params_list.append({
                        "ParameterKey": "publicSubnet2",
                        "ParameterValue": public_subnets[1]
                    })
        for elb_name in elbs:
            params_list.append({
                        "ParameterKey": ''.join(elb_name.split('-')),
                        "ParameterValue": 'yes'
                    })
        return params_list
