#! coding=utf8
# Filename    : templateutils.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
import logging
import os

import time
from datetime import datetime

from common.models import RegionInfo
from deploy.models import ModuleConfTemplate, ModuleConf
from preprddeploy.settings import MODULE_DEPLOY_CONF_DIR

logger = logging.getLogger('common')


class ConfTemplate(object):
    def __init__(self, module_name, conf_name, region, conf_content,
                 template_version):
        env = 'cn' if region == 'cn-north-1' else 'en'
        self.conf_template = self.get_or_create_conf_template(module_name, conf_name,
                                                              env, template_version)
        self.conf_template.conf_content = conf_content

    @staticmethod
    def get_or_create_conf_template(module_name, conf_name, env, template_version):
        """
        get ModuleConfTemplate object, if not found in database, create new one.
        Args:
            module_name (string): module name
            conf_name (string): config name, choices: sys, log4j
            env (string): region abbreviation, choices: cn, en
            template_version (string): config template version, same as module's version
        Returns:
            ModuleConfTemplate object
        """
        try:
            template_obj = ModuleConfTemplate.objects.get(
                module_name=module_name,
                conf_name=conf_name,
                env=env,
                template_version=template_version
            )
            return template_obj
        except ModuleConfTemplate.DoesNotExist:
            conf_template = ModuleConfTemplate(module_name=module_name, conf_name=conf_name,
                                               env=env, save_time=datetime.now(), template_version=template_version)
            return conf_template

    def save_or_update(self):
        self.conf_template.save_time = datetime.now()
        self.conf_template.save()


class ConfigSaver(object):
    def __init__(self, module_name, conf_name, region,
                 prd_conf_content='', preprd_conf_content='', template=None):
        self.module_name = module_name
        self.conf_name = conf_name
        self.region = region
        self.prd_conf_content = prd_conf_content
        self.preprd_conf_content = preprd_conf_content
        self.template = template
        self.ret = {}

    def save(self):
        """write content into file in deploy conf dir and save into database"""
        self._write_content_to_file()
        self._save_content_to_db()
        return self.ret

    def _save_content_to_db(self):
        module_conf = ModuleConf(module_name=self.module_name, conf_name=self.conf_name,
                                 region=self.region, prd_conf_content=self.prd_conf_content,
                                 preprd_conf_content=self.preprd_conf_content, template=self.template)
        env = 'cn' if self.region == 'cn-north-1' else 'en'
        logger.debug('module name: %s, conf name: %s, env: %s' % (
            self.module_name,
            self.conf_name,
            env
        ))
        module_conf_template = ModuleConfTemplate.objects.get(module_name=self.module_name,
                                                              conf_name=self.conf_name,
                                                              env=env
                                                              )
        update_version = module_conf_template.template_version
        if not update_version:
            raise Exception("module: %s's version not set." % self.module_name)
        module_conf.module_version = update_version
        module_conf.save(True)

    def _write_content_to_file(self):
        conf_save_dir = os.path.join(MODULE_DEPLOY_CONF_DIR, self.module_name)
        if not os.path.isdir(conf_save_dir):
            os.makedirs(conf_save_dir)
        region_abbr = RegionInfo.objects.get(region=self.region).abbr
        preprd_conf_name = '%s.properties.%s-pre-prd' % (self.conf_name,
                                                         region_abbr
                                                         )
        self._write_file(os.path.join(conf_save_dir, preprd_conf_name), self.preprd_conf_content)
        prd_conf_name = '%s.properties.%s-prd' % (self.conf_name,
                                                  region_abbr
                                                  )
        self._write_file(os.path.join(conf_save_dir, prd_conf_name), self.prd_conf_content)
        self.ret.update({
            preprd_conf_name: self.preprd_conf_content,
            prd_conf_name: self.prd_conf_content
        })

    @staticmethod
    def _write_file(file_path, file_content):
        with open(file_path, 'w') as file_writer:
            file_writer.write(file_content)
