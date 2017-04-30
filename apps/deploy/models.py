#! coding=utf8
import difflib
import logging
import os

from django.contrib.auth.models import User
from django.db import models

from preprddeploy.settings import BASE_DIR

logger = logging.getLogger('common')


class ModuleConfTemplate(models.Model):
    module_name = models.CharField(max_length=32)
    conf_name = models.CharField(max_length=32)
    env = models.CharField(max_length=32, choices=(
        ('cn', u'内销'),
        ('en', u'外销')
    ))
    conf_content = models.TextField()
    save_time = models.DateTimeField()
    template_version = models.CharField(max_length=10)

    class Meta:
        unique_together = (('module_name', 'conf_name', 'env', 'template_version'),)

    def create_diff_file(self, version):
        """
        make diff between current template and template of the specify version.
        Args:
            version (basestring): the template version you want to compare
        Returns
            flag: if diff operation success
            module_name: module name
            diffResultFileName: generated diff file name, like: differ-{conf_name}-{version1}-{version2}.html
            all diffResultFile save dir: BASE_DIR/templates/templateDiffer/{module_name}
        """
        success_flag = True
        try:
            other_conf_template = ModuleConfTemplate.objects.get(module_name=self.module_name,
                                                                 conf_name=self.conf_name,
                                                                 template_version=version)
        except ModuleConfTemplate.DoesNotExist:
            logger.error('no conf template found with the specified version: %s' % version)
            template_content = 'no conf template found: %s-%s-%s' % (self.module_name,
                                                                     self.conf_name,
                                                                     version)
            success_flag = False
        else:
            template_content = other_conf_template.conf_content
        html_differ = difflib.HtmlDiff()
        diff_result = html_differ.make_file(template_content.splitlines(),
                                            self.conf_content.splitlines())
        diff_result_file_name = 'differ-%s-%s-%s.html' % (self.conf_name, version, self.template_version)
        diff_result_file_dir = os.path.join(BASE_DIR, 'templates', 'templateDiffer', self.module_name)
        if not os.path.isdir(diff_result_file_dir):
            os.makedirs(diff_result_file_dir)
        with open(os.path.join(diff_result_file_dir, diff_result_file_name), 'w') as fw:
            fw.write(diff_result)
        return success_flag, self.module_name, diff_result_file_name


class ModuleConf(models.Model):
    module_name = models.CharField(max_length=32)
    conf_name = models.CharField(max_length=32)
    region = models.CharField(max_length=32)
    prd_conf_content = models.TextField()
    preprd_conf_content = models.TextField()
    create_time = models.DateTimeField(auto_now_add=True)
    template = models.ForeignKey(ModuleConfTemplate)
    module_version = models.CharField(max_length=8)
