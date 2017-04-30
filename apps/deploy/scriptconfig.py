#! coding=utf8
##############################################################################
# Copyright (C), 2016 , TP-LINK Technologies Co., Ltd.
# Filename    : scriptConfig.py
# Description : manage deploy script's config file
# Author      : dengken
# History:
#    1. 2016年8月31日 , dengken, first create
##############################################################################
import os
import ConfigParser
import shutil
import subprocess
import logging
import time
import traceback

from preprddeploy.settings import BASE_DIR

logger = logging.getLogger('common')


class ScriptConfig(object):
    def __init__(self, script_name, conf_name):
        self.script_name = script_name
        self.conf_name = conf_name
        self.dirname = '%s/deploy/conf/%s' % (os.path.join(BASE_DIR, 'static'), script_name)
        self.conf_path = '%s/%s' % (self.dirname, conf_name)
        logger.debug('script conf path: %s' % self.conf_path)
        # use dict to store content: {sectionName:{paramName:paramValue}}
        self.content = {}
        
    def get_content(self):
        if self.content:
            return self.content
        cf = ConfigParser.ConfigParser()
        cf.read(self.conf_path)
        content = {}
        for section in cf.sections():
            config_dict = {}
            options = cf.options(section)
            for option in options:
                config_dict.update({option: cf.get(section, option)})
            content.update({section: config_dict})
        self.content = content    
        return self.content

    def modify_conf(self, changelist):
        """
        modify config file
        Args:
            changelist (list): a list of (section, param_name,param_value) need to modify
        """
        dest_modify_file = self.conf_path
        tmpfile = '%s/tmp-%d' % (self.dirname, time.time())
        cf = ConfigParser.ConfigParser()
        cf.read(tmpfile)
        for section, option, value in changelist:
            if not cf.has_section(section):
                cf.add_section(section)
            cf.set(section, option, value)
        with open(tmpfile, 'w') as tmpfile_writer:
            try:
                cf.write(tmpfile_writer)
            except:
                error_msg = 'modify conf failed when write changlist, ' \
                            'nothing changed. error msg:\n%s' % traceback.format_exc()
                logger.error(error_msg)
                os.remove(tmpfile)
                return {'ret': False, 'msg': error_msg}
        try:
            os.rename(tmpfile, dest_modify_file)
        except:
            error_msg = 'replace script conf by tmpfile: %s failed, error msg:\n%s' % (
                tmpfile,
                traceback.format_exc()
            )
            logger.error(error_msg)
            os.remove(tmpfile)
            return {'ret': False, 'msg': error_msg}
        return {'ret': True}

    @staticmethod
    def write_config(content_dict, dest_path):
        config_parser = ConfigParser.ConfigParser()
        for section in content_dict:
            config_parser.add_section(section)
            for option, value in content_dict[section].items():
                config_parser.set(section, option, value)
        with open(dest_path, 'w') as conf_writer:
            config_parser.write(conf_writer)

    
    def rename(self,newName):
        newFile = '%s/%s'%(self.dirname,newName)
        shutil.move(self.confPath,newFile)
        self.confName = newName
        self.confPath = newFile
        
    def copyFile(self,destFile):
        shutil.copy(self.confPath, destFile)
        return ScriptConfig(self.scriptName, os.path.basename(destFile))
        
    def transportFile(self,destHostList,destFile,privateKeyFile):
        destHostsString = ','.join(destHostList)
        ansibleCommand = 'ansible all -i %s, -m copy -a "src=%s dest=%s" --private-key %s'%(
                                                                                destHostsString,
                                                                                self.confPath,
                                                                                destFile,
                                                                                privateKeyFile        
                                                                                )
        p = subprocess.Popen(ansibleCommand,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        stdoutData,stderrData = p.communicate()
        if p.poll() == 0:
            logging.info(stdoutData)
            return True
        else:
            logging.error(stderrData)
            return False

