#! coding=utf8
# Filename    : scriptrunner.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import logging
import os
import threading

import subprocess

import time
import traceback

from django.contrib.auth.models import User

from bizmodule.models import BizServiceLayer
from common.libs import ec2api
from common.libs.ansible_api import AnsibleRunner
from common.models import RegionInfo
from deploy.scriptconfig import ScriptConfig
from module.models import ScriptExecLog
from preprddeploy.settings import DEVOPS_DIR, HOME_PATH
from redisqueue import RedisQueue

logger = logging.getLogger('common')


class ScriptRunner(object):
    def __init__(self):
        self.script_name = ''
        self.script_path = ''

    def run(self, command, username, region):
        t = threading.Thread(target=self._run_script_background, args=(command, username, region))
        t.start()

    def _run_script_background(self, command, username, region):
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.1)  # forget why i sleep here, if not sure, don't modify this
        rq = RedisQueue('script_serviceDeploy_%s_%s' % (region, username))
        rq.delete_queue()  # todo: delete key only
        stdout, stderr = p.communicate()
        ret_code = p.poll()
        if not ret_code:
            script_result = stdout
            logger.info('run command: %s success, output:\n%s' % (command, stdout))
            rq.put('*finished*')
            self.add_script_exec_log(username, self.script_name, self.script_path, True, script_result)
        else:
            script_result = stdout + stderr
            logger.error('run command: %s failed, output:\n%s' % (command, script_result))
            errout = [err for err in stderr.splitlines() if err]
            errout = '\n'.join(errout)
            rq.put('*failed*%s' % errout)
            self.add_script_exec_log(username, self.script_name, self.script_path, False, script_result)

    @staticmethod
    def add_script_exec_log(username, script_name, script_path, is_success, result):
        exec_user = User.objects.get(username=username)
        exec_script_log = ScriptExecLog(user=exec_user, script_name=script_name, script_content=script_path,
                                        if_success=is_success, script_result=result)
        try:
            exec_script_log.save()
        except:
            logger.error('add script log failed: \n%s' % traceback.format_exc())
            logger.error('script info:\nusername: %s\tscript name: %s\t script_path: %s\tsuccess:%s\nresult:%s' % (
                username,
                script_name,
                script_path,
                is_success,
                result
            ))


class ServiceDeployScript(ScriptRunner):
    def __init__(self):
        super(ScriptRunner, self).__init__()
        self.script_path = os.path.join(DEVOPS_DIR, 'serviceDeploy')
        self.script_name = 'serviceDeploy'
        self.instance_ips = None
        self.key_file_path = None

    def pre_work(self, module_name, module_version, region, method, username):
        command = self.get_script_command(module_name, module_version, region, method, username)
        self.deal_script_conf(module_name, module_version, region)
        return command

    def get_script_command(self, module_name, module_version, region, method, username):
        module_name_list = module_name.split('_')
        module_version_list = module_version.split('_')
        if len(module_name_list) != len(module_version_list):
            raise Exception('module count are not equal with version count for module: %s, version: %s' % (
                module_name,
                module_version
            ))
        deploy_module_name = '%s-%s' % (module_name, module_version)
        self.instance_ips, self.key_file_path = self.get_deploy_instances(deploy_module_name, region)
        run_deploy_cmd = 'python serviceDeploy.py -m %s -n %s -u %s -r %s' % (
            method,
            ','.join(module_name_list),
            username,
            region
        )
        logger.debug('cmd to run serviceDeploy.py: %s' % run_deploy_cmd)
        return '''ansible all -i %s, -m shell -a '/bin/bash -c "source /etc/profile;cd %s;%s"' --private-key %s''' % (
            ','.join(self.instance_ips),
            self.script_path,
            run_deploy_cmd,
            self.key_file_path
        )

    def deal_script_conf(self, module_name, module_version, region):
        if region == 'cn-north-1':
            script_conf_name = 'sys.properties_cn'
        else:
            script_conf_name = 'sys.properties_en'
        script_config = ScriptConfig('serviceDeploy', script_conf_name)
        conf_content = script_config.get_content()
        standard_modules = BizServiceLayer.objects.filter(service_type='standard')
        conf_content['set'].update({'standardService': ','.join([module.service_name for module in standard_modules])})
        tomcat_modules = BizServiceLayer.objects.filter(service_type='tomcat')
        conf_content['set'].update({'tomcatService': ','.join([module.service_name for module in tomcat_modules])})
        for name, version in zip(module_name.split('_'), module_version.split('_')):
            conf_content['serviceVersion'].update({name: version})
        region_abbr = RegionInfo.objects.get(region=region).abbr
        conf_content.update({'regions': {region: region_abbr}})
        script_config.write_config(conf_content, os.path.join(DEVOPS_DIR, 'serviceDeploy', 'sys.properties'))
        self.transport_to_remote()

    def transport_to_remote(self):
        zip_command = 'cd %s;zip -o -r serviceDeploy.zip serviceDeploy' % DEVOPS_DIR
        zip_process = subprocess.Popen(zip_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        zip_out, zip_err = zip_process.communicate()
        if zip_process.poll():
            err_msg = 'zip serviceDeploy dir failed, error msg: %s' % (zip_out + zip_err)
            logger.error(err_msg)
            raise Exception(err_msg)
        logger.info('zip serviceDeploy folder success')
        zip_file_path = os.path.join(DEVOPS_DIR, 'serviceDeploy.zip')
        ansible_runner = AnsibleRunner()
        dest_ips = ','.join(self.instance_ips)
        ansible_runner.run_ansible(module_name='copy', module_args="src=%s dest=%s" % (zip_file_path, zip_file_path),
                                   ip=dest_ips, keyfile=self.key_file_path)
        results = ansible_runner.results
        if results[1] + results[3]:
            error_msg = 'copy serviceDeploy.zip to remote instances failed, error msg: %s' % results[0]['failed']
            logger.error(error_msg)
            raise Exception(error_msg)
        logging.info('transport serviceDeploy.zip to %s success' % dest_ips)
        unzip_cmd = 'unzip -o %s -d %s' % (zip_file_path, DEVOPS_DIR)
        ansible_runner.run_ansible(module_args=unzip_cmd, ip=dest_ips, keyfile=self.key_file_path)
        results = ansible_runner.results
        if results[1] + results[3]:
            error_msg = 'unzip serviceDeploy.zip failed. error msg: %s' % results[0]['failed']
            logger.error(error_msg)
            raise Exception(error_msg)
        logger.info('unzip serviceDeploy.zip success')

    @staticmethod
    def get_deploy_instances(deploy_module_name, region):
        instances = ec2api.find_instances(region, ['*%s*' % deploy_module_name], is_running=True)
        private_ip_list = []
        key_name = None
        for instance in instances:
            key_name = instance.key_name
            private_ip_list.append(instance.private_ip_address)
        if not key_name:
            raise Exception('no instance found named: %s' % deploy_module_name)
        key_file_path = os.path.join(HOME_PATH, 'pem', '%s.pem' % key_name)
        return private_ip_list, key_file_path
