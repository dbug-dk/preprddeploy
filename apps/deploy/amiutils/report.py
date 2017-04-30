# -*- coding: UTF-8 -*
###############################################################################
# Copyright (C), 2016 , TP-LINK Technologies Co., Ltd.
#
# Filename    : report.py
# Version     : 0.0.1
# Description : Generate HTML report from ec2_checker results
# Author      : lihaomin
# History:
#   1. 2016/2/25: lihaomin, first create
#   2. 2016/2/26: lihaomin, changed HTML stylesheet
###############################################################################

import json
import logging
import os

from jinja2 import Template

from common.libs import ec2api
from deploy.htmltemplate import check_result_panel_html

logger = logging.getLogger('common')


class Report(object):
    def __init__(self, instances, results):
        self.instances = instances
        self.results = results
        self.output = ""

    def report(self):
        report_ret = ''
        output_template = Template(check_result_panel_html)
        for instance_id in self.results:
            instance_result = self.results[instance_id]
            self.output += '<table class="table table-hover">'
            current_instance = None
            for instance in self.instances:
                if instance.id == instance_id:
                    current_instance = instance
                    break
            if current_instance:
                instance_name = ec2api.get_instance_tag_name(current_instance)
                self.report_instance(current_instance, instance_result, instance_name)
                output_header = '%s (%s) - %s' % (
                    instance_name,
                    instance_id,
                    current_instance.private_ip_address
                )
            else:
                output_header = ''
                logger.warn("<Warning> Unrecognized instance: %s " % instance_id)
            self.output += "</table>\r\n"
            if self.output.find('False') == -1:
                pass_or_not = 'success'
            else:
                pass_or_not = 'danger'
            report_ret += output_template.render(pass_or_not=pass_or_not, instance_id=instance_id, header=output_header,
                                                 result_table=self.output)
            self.output = ''
        pwd = os.path.split(os.path.realpath(__file__))[0]
        fp = open(os.path.join(pwd, "report_body.html"), 'r')
        output = fp.read()
        fp.close()
        report_ret = output.replace("{{replaceContent}}", report_ret)
        fp = open(os.path.join(pwd, "report.html"), 'w')
        fp.write(report_ret)
        fp.close()
        return report_ret

    def report_instance(self, instance, instance_result, instance_name):
        print("%s (%s) - %s" % (
            instance_name,
            instance.id,
            instance.private_ip_address
        ))
        for category in instance_result:
            cat_result = instance_result[category]
            if type(cat_result) is dict:
                # if category result is dict, draw a merged cell:
                self.output += '<tr><th rowspan="%d">%s</th>' % (
                    self.get_length(cat_result) + 1,
                    category
                )
                print("%s" % (category,))
                self.output_dict(cat_result)
                self.output += "</tr>\r\n"
            elif type(cat_result) is bool:
                if cat_result:
                    trclass = "pass"
                else:
                    trclass = "fail"
                self.output += '<tr class="%s"><th colspan="3">%s</th><td>%s</td></tr>' % (
                    trclass,
                    category,
                    str(cat_result)
                )
                logger.debug("%s:\t%s" % (category, str(cat_result)))

    @staticmethod
    def get_length(cat_result):
        length = 0
        for k, v in cat_result.items():
            if type(v) is bool:
                length += 1
            else:
                length += len(v)
        return length
     
    def output_dict(self, d):
        for k in d:
            if type(d[k]) is dict:
                self.output_dict(d[k])
            else:
                if d[k]:
                    trclass = "pass"
                else:
                    trclass = "fail"
                self.output += '<tr class="%s"><th colspan="2">%s</th><td>%s</td></tr>\r\n' % (
                    trclass,
                    k, 
                    str(d[k])
                )
            logger.debug("\t%s:\t%s" % (k, str(d[k])))

    @staticmethod
    def pass_check(result):
        jsonstring = json.dumps(result)
        if jsonstring.find('false') == -1:
            return True
        return False  
