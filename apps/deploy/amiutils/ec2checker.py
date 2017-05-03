# -*- coding: UTF-8 -*
###############################################################################
# Copyright (C), 2016 , TP-LINK Technologies Co., Ltd.
#
# Filename    : ec2_checkr.py
# Version     : 0.0.1
# Description : class to check EC2 instances
# Author      : lihaomin
# History:
#   1. 2016/1/20: lihaomin, first create
#   2. 2016/2/15: lihaomin, finished EC2 basic checks
###############################################################################

import re
import os
import logging

from fabric.context_managers import settings, hide
from fabric.api import env, run

from bizmodule.models import BizServiceLayer
from common.libs import ec2api
from common.models import RegionInfo
from preprddeploy.settings import HOME_PATH, KEY_PATH, FILES, PACKAGES, PYTHON_MODULES, JAVA_PATH

logger = logging.getLogger('common')


class Ec2Checker(object):
    """
    Check EC2 instances and configurations.
    """
    def __init__(self, instances, region):
        """load config file."""
        self.region = region
        self.region_abbr = RegionInfo.objects.get(region=region).abbr
        self.instances = instances     

    @staticmethod
    def _set_env(instance):
        """Set fabric env so we can connect to this "instance\""""
        env.user = os.path.basename(HOME_PATH)
        env.host_string = instance.private_ip_address
        env.key_filename = "%s/%s.pem" % (KEY_PATH, instance.key_name)
            
    def check(self):
        logger.debug('start to check conf.')
        result = {}
        for instance in self.instances:
            self._set_env(instance)
            instance_result = {}
            instance_name = ec2api.get_instance_tag_name(instance)
            module_name, module_version = ec2api.get_module_info(instance_name)
            instance_result.update(self.basic_check(module_name))
            modules = module_name.split('_')
            versions = module_version.split('_')
            for name, version in zip(modules, versions):
                service_type = BizServiceLayer.objects.get(service_name=name).service_type
                attrname = "check_%s_module" % service_type
                try:
                    common_check_method = getattr(self, attrname)
                    instance_result.update({name: common_check_method(name, version)})
                except AttributeError:
                    logger.warn('no common check method for service type: %s not found, try %s special check' % (
                        service_type,
                        name
                    ))
                logger.info('search if module: %s has special check')
                try:
                    special_check_method = getattr(self, 'check_%s' % name)
                    special_check_method(version, instance_result)
                    logger.info('finished special check for module: %s' % name)
                except AttributeError:
                    logger.info('no special check method for %s, check for %s finished' % (name, name))
            result.update({instance.id: instance_result})
        return result

    # Basic checks
    # (These checks will be performed on all EC2 instances regardless their modules)
    @staticmethod
    def check_file_presence(file_path):
        """
        check if "file" exists.
        Args:
            file_path (string): file path
        """
        cmd = "test -f " + file_path
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            result = run(cmd)
        if result.return_code == 0:
            return True
        return False

    @staticmethod
    def check_file_line(line, file_path):
        """
        check if "file" contains "line".
        Args:
            line (string): line content to check
            file_path (string): file to check
        """
        cmd = "grep '%s' %s" % (line, file_path)
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            result = run(cmd)
        # grep exits 0 if a line is selected, 1 if no lines were selected:
        if result.return_code == 0:
            return True
        return False

    @staticmethod
    def check_package(package_name):
        """
        check if a software package is installed with 'apt-cache'.
        Args:
            package_name (string): package name installed by apt
        """
        cmd = "apt-cache policy %s" % (package_name,)
        result = run(cmd)
        # if apt-cache doesn't konw this package, it will print:
        # "N: Unable to locate package xxxx"
        if -1 != result.find("Unable to locate package"):
            return False
        # if package is recognized but not installed, apt-cache will print:
        # "Installed: (none)"
        if -1 != result.find("Installed: (none)"):
            return False
        # otherwise the package is installed:
        return True

    @staticmethod
    def check_python_module(module_name):
        """
        check if a python module is installed with 'import'.
        Args:
            module_name (string): python module name
        """
        cmd = "python -c \"import %s\" " % (module_name,)
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            result = run(cmd)
        # if import is not successful, python will exit error code:
        if result.return_code == 0:
            return True
        return False

    @staticmethod
    def check_nofile():
        """check if nofile is set to 1048576"""
        cmd = 'grep 1048576 /etc/security/limits.conf | grep nofile'
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            res = run(cmd)
        if res.return_code != 0:
            return False
        # fabric automatically converts newline in outputs (but not file contents)
        # thus "os.linesep" must be used here.
        lines = res.split(os.linesep)
        cnt = 0
        for line in lines:
            if not line.startswith("#"):
                cnt += 1
        if cnt == 2:
            return True
        return False

    @staticmethod
    def check_port_range():
        """check if ipv4 tcp port range is 1024 ~ 65535"""
        cmd = "grep '^net.ipv4.ip_local_port_range = 1024 65535' /etc/sysctl.conf"
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            res = run(cmd)
        return res.return_code == 0

    @staticmethod
    def check_awsconfig():
        """check if aws configure has no access_key and already set right region and output"""
        check_list = {
            'aws_access_key_id': '',
            'aws_secret_access_key': '',
            # 'region' : self.region,
            # 'output' : 'json'
        }
        result = {
            'aws_access_key_id': True,
            'aws_secret_access_key': True,
            # 'region' : True,
            # 'output' : True
        }
        for check_item in check_list:
            cmd = 'aws configure get %s' % check_item
            with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
                res = run(cmd)
                if res != check_list[check_item]:
                    result[check_item] = False
        return result

    @staticmethod
    def check_javapath(java_path):
        """
        check if $PATH contains /usr/local/jdk1.7.0_60/bin
        Args:
            java_path (string): java path
        """
        cmd = 'echo $PATH|grep %s' % java_path
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            rec = run(cmd)
        if rec.return_code == 0:
            return True
        return False

    @staticmethod
    def check_nofile_autostart():
        """check if /etc/rc.local contains ulimit -SHn 1048576"""
        cmd = 'grep "ulimit -SHn 1048576" /etc/rc.local |wc -l'
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            rec = run(cmd)
        if rec.return_code == 0 and rec == '1':
            return True
        return False

    @staticmethod
    def check_monitor_autostart():
        """check if /etc/rc.local contains sudo -u ubuntu /home/ubuntu/cloud-ops/openfalcon/agent/control start"""
        cmd = 'grep "sudo -u ubuntu /home/ubuntu/cloud-ops/openfalcon/agent/control start" /etc/rc.local|wc -l'
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            rec = run(cmd)
        if rec.return_code == 0 and rec == '1':
            return True
        return False

    def basic_check(self, module):
        """
        perform universal EC2 checks
        Args:
            module (string): module name
        """
        # init check results:
        # check file will occur 'ValueError: I/O operation on closed file', decomment this after solve this problem
        # results_file = {}
        results_pac = {}
        results_py = {}
        results_sysconf = {}
        results_awsconf = {}

        # check files presence. 
        # list of files is in configuration's "settings/FILES":
        # for file_path in FILES:
        #     result_file = self.check_file_presence(file_path)
        #     results_file.update({file_path: result_file})
        # check package installation:
        # list of packages is in configuration's "settings/PACKAGES":
        for package in PACKAGES:
            result_pac = self.check_package(package)
            results_pac.update({package: result_pac})
        # check python modules:
        # list of modules "settings/PYTHON_MODULES":
        for pymodule in PYTHON_MODULES:
            result_py = self.check_python_module(pymodule)
            results_py.update({pymodule: result_py})
        # check aws credentials except some modules
        if module not in ['device']:
            results_awsconf.update(self.check_awsconfig())

        # check system configurations:
        # check if nofile is set to 1M:
        results_sysconf.update({
            'open files': self.check_nofile()
        })
        # check if tcp port range is set to 1024~65535:
        results_sysconf.update({
            'port range': self.check_port_range()
        })
        self.java_path = JAVA_PATH
        results_sysconf.update(
            {'java path': self.check_javapath(self.java_path)}
        )
        results_sysconf.update(
            {'ulimit rclocal': self.check_nofile_autostart()}
        )
        # update check results:
        results = {
            # 'files': results_file,
            'packages': results_pac,
            'python_modules': results_py,
            'system configs': results_sysconf,
            'monitor_auto_start': self.check_monitor_autostart()
        }
        if results_awsconf:
            results.update({'aws_configs': results_awsconf})
        return results
        
    # Module checks #
    @staticmethod
    def check_files_diff(fpath1, fpath2):
        """
        check if file1 and file2 match
        Args:
            fpath1 (string): file 1 path
            fpath2 (string): file 2 path
        """
        logging.debug("comparing %s & %s" % (fpath1, fpath2))
        cmd = "diff '%s' '%s'" % (fpath1, fpath2)
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            result = run(cmd)
        return result.return_code == 0

    @staticmethod
    def check_log_scripts():
        """check if log scripts are deployed and will auto start"""
        check_items = {
            'logpackage.py': "test -f /home/%s/logpackage.py" % (env.user,),
            'logtransfer.py': "test -f /home/%s/logtransfer.py" % (env.user,),
            'log_service_checker.sh': "test -f /home/%s/log_service_checker.sh" % (env.user,),
            'log_service_start.sh': "test -f /home/%s/log_service_start.sh" % (env.user,)
        }
        result_dict = {}
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            for check_name in check_items:
                cmd = check_items[check_name]
                result = run(cmd)
                if result.return_code != 0:
                    result_dict.update({check_name: False})
                else:
                    result_dict.update({check_name: True})
            check_boot_cmd = "grep 'sudo -u %s /home/%s/log_service_start.sh' /etc/rc.local|wc -l" % (env.user,
                                                                                                      env.user)
            check_boot_result = run(check_boot_cmd)
            if check_boot_result.return_code == 0 and check_boot_result == '1':
                result_dict.update({'logtransfer autostart': True})
            else:
                result_dict.update({'logtransfer autostart': False})
        return result_dict

    @staticmethod
    def check_crontab(cronjob):
        logger.debug('check if crontab job existed : %s' % cronjob)
        cmd = "crontab -l|grep -v '^#' |grep -F '%s'|wc -l" % cronjob
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            result = run(cmd)
        if result.return_code == 0 and result == '1':
            return True
        return False
    
    def check_standard_module(self, module_name, version):
        """
        common check items of standard module
        Args:
            module_name (string): module name, eg: connector
            version (string): module version, eg: 1.1.0
        """
        result = {
            "module config": True,
            "autostart": True,
            "logscripts": True
        }
        module_path = "/home/%s/cloud-%s/cloud-%s-%s" % (
            env.user,
            module_name,
            module_name,
            version
        )
        files = [
            "conf/sys.properties",
            "conf/log4j.properties",
        ]
        # check file integrity:
        for conf_file in files:
            file_path = "/".join([module_path, conf_file])
            prdfile_path = '/home/%s/cloud-ops/serviceDeploy/cloud-service-conf/%s/%s.%s-prd' % (
                env.user,
                module_name,
                os.path.basename(file_path),
                self.region_abbr
                )
            result['module config'] &= self.check_files_diff(file_path, prdfile_path)

        patterns = [
            "^cd\s+%s/bin" % module_path,
            "^sudo\s+-u\s+%s\s+PATH=.*%s.*\s+JAVA_HOME=%s\s+\\./start\\.sh.*&" % (
                env.user,
                self.java_path.replace(".", "\\."),
                os.path.dirname(self.java_path).replace(".", "\\.")
            )
        ]
        # check service auto start
        # grep pattern:
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            for pattern in patterns:
                cmd = "grep -E '%s' /etc/rc.local|wc -l" % pattern
                r = run(cmd)
                if r.return_code == 0 and r == '1':
                    result['autostart'] &= True
                else:
                    result['autostart'] &= False
        # check log scripts and auto start
        r = self.check_log_scripts()
        result['logscripts'] = r
        return result
        
    def check_tomcat_module(self, module_name, version):
        result = {
            "module config": True,
            "autostart": True,
            "logscripts": True,
        }
        module_path = "/home/%s/cloud-%s/cloud-%s-%s" % (
            env.user,
            module_name,
            module_name,
            version
        )
        tomcat_path = "/home/%s/cloud-%s/tomcat" % (
            env.user,
            module_name
        )
        files = [
            "WEB-INF/classes/sys.properties",
            "WEB-INF/classes/log4j.properties",
        ]
        for conf_file in files:
            file_path = "/".join([module_path, conf_file])
            prdfile_path = '/home/%s/cloud-ops/serviceDeploy/cloud-service-conf/%s/%s.%s-prd' % (
                env.user,
                module_name,
                os.path.basename(conf_file),
                self.region_abbr
                )
            result['module config'] &= self.check_files_diff(file_path, prdfile_path)
        patterns = [
            "^cd\s+%s/bin" % tomcat_path,
            "^sudo\s+-u\s+%s\s+PATH=.*%s.*\s+JAVA_HOME=%s\s+\\./startup\\.sh.*&" % (
                env.user,
                self.java_path,
                os.path.dirname(self.java_path)
            )
        ]
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            for pattern in patterns:
                cmd = "grep -E '%s' /etc/rc.local|wc -l" % pattern
                r = run(cmd)
                if r.return_code == 0 and r == '1':
                    result['autostart'] &= True
                else:
                    result['autostart'] &= False
        # check log scripts and auto start
        r = self.check_log_scripts()
        result['logscripts'] = r
        result_tomcat = {}
        result_tomcat.update(
            {'docBase': self.check_docbase(tomcat_path, module_path)}
        )

        result_tomcat.update(
            {'.sh files': self.check_x_files(tomcat_path)}
        )
        result.update({'tomcat conf': result_tomcat})
        return result
    
    def check_appserver(self, version, result):
        """
        module cloud-connector specific checks
        Args:
            version (string): appserver version, not use, but for unify these special check method, don't remove it
            result (dict): common tomcat check result
        """
        module_name = "appserver"
        tomcat_path = "/home/%s/cloud-%s/tomcat" % (
            env.user,
            module_name
        )
        jars = [
            'joda-time-2.9.2.jar',
            'jolokia-core-1.3.1.jar',
            'jolokia-jvm-1.3.1-agent.jar'
        ]
        result_jars = True
        for jar in jars:
            result_jars &= self.check_file_presence('%s/lib/%s' % (tomcat_path, jar))
        result[module_name]['tomcat conf'].update(
            {'jars': result_jars}
        )
        crontab_job = "bash tomcatlog_transfer.sh"
        result[module_name].update({'crontab': {crontab_job: self.check_crontab(crontab_job)}})

    def check_appserverinternal(self, version, result):
        module_name = "appserver"
        tomcat_path = "/home/%s/cloud-%s/tomcat" % (
            env.user,
            module_name
        )
        jars = [
            'joda-time-2.9.2.jar',
            'jolokia-core-1.3.1.jar',
            'jolokia-jvm-1.3.1-agent.jar'
        ]
        result_jars = True
        for jar in jars:
            result_jars &= self.check_file_presence('%s/lib/%s' % (tomcat_path, jar))
        result['tomcat conf'].update(
            {'jars': result_jars}
        )
        crontab_job = "bash tomcatlog_transfer.sh"
        result.update({'crontab': {crontab_job: self.check_crontab(crontab_job)}})

    @staticmethod
    def check_docbase(tomcat_path, module_path):
        """
        check if the server.xml set Context docBase's value the appserver's path
        Args:
            tomcat_path (string): tomcat dir. eg: /home/ubuntu/cloud-appserver/tomcat"
            module_path (string): module dir. eg: /home/ubuntu/cloud-appserver/
        """
        cmd = "grep docBase %s/conf/server.xml" % tomcat_path
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            rec = run(cmd)
        if rec.return_code != 0:
            return False
        else:
            pattern = 'docBase="(.+?)"'
            p = re.compile(pattern)
            match = p.search(rec)
            if match:
                docbase = match.group(1)
                return docbase == module_path
            return False

    @staticmethod
    def check_x_files(tomcat_path):
        """
        check if all the .sh file can execute in ${tomcat_paht}/bin/
        Args:
            tomcat_path (string): tomcat path
        """
        cmd = 'ls %s/bin|grep .sh' % tomcat_path
        with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            rec = run(cmd)
        if rec.return_code != 0:
            return False
        xfiles = rec.splitlines()
        for xfile in xfiles:
            cmd = 'test -x %s/bin/%s' % (tomcat_path, xfile)
            if run(cmd).return_code != 0:
                return False
        return True