#! coding=utf8
# Filename    : tasks.py
# Description : 
# Url         : 
# Author      : iwannarock
# History:
# 1. 2017/5/3 0:57 , iwannarock, first create
import os
import urllib
import urllib2

from celery.task import task
from django.template import Template, Context

from autodeploy.mailsender.mailsender import MailSender
from autodeploy.models import AutoDeployHistory
from preprddeploy.settings import BASE_DIR, MAIL_TEMPLATE_DIR, MAIL_SUBJECT_PREFIX, MAIL_DOMAIN, ADMINS


@task
def start_env_request(upgrade_version, managers):
    start_url = 'http://127.0.0.1:8001/autodeploy/start_env'
    args = {'upgrade_version': upgrade_version, 'managers': managers}
    resp = do_get(start_url, **args)
    print resp


@task
def mail_conf_create_result(to_addrs, failed_dict, diff_result_dict):
    html = __generate_html_content('create-conf-result.html', **{'failed_dict': failed_dict,
                                                                 'diff_result_dict': diff_result_dict
                                                                 })
    for _, admin_mail in ADMINS:
        if admin_mail not in to_addrs:
            to_addrs.append(admin_mail)
    subject = u'%s配置生成结果' % MAIL_SUBJECT_PREFIX
    print diff_result_dict
    MailSender().send_html_mail(to_addrs, subject, html)


@task
def send_progress_result():
    deploy_history_obj = AutoDeployHistory.objects.order_by('-id').first()
    progress_name = deploy_history_obj.progress_name
    start_time = deploy_history_obj.start_time
    end_time = deploy_history_obj.end_time
    status = {
        "log_content": deploy_history_obj.log_content,
        "progress_name": progress_name,
        "start_time": start_time.strftime('%Y:%m:%d %H:%M:%S'),
        "end_time": end_time.strftime('%Y:%m:%d %H:%M:%S'),
        "duration": '%s seconds' % (start_time - end_time).total_seconds(),
        'is_success': deploy_history_obj.is_success,
        'upgrade_version': deploy_history_obj.upgrade_version
    }
    html = __generate_html_content('progress-result.html', **status)
    managers = deploy_history_obj.managers
    to_addrs = managers.split(',')
    for _, admin_mail in ADMINS:
        if admin_mail not in to_addrs:
            to_addrs.append(admin_mail)
    subject = u'%s[%s]执行结果' % (MAIL_SUBJECT_PREFIX, progress_name)
    MailSender().send_html_mail(to_addrs, subject, html)


def __generate_html_content(mail_template_name, **args):
    mail_template_path = os.path.join(BASE_DIR, MAIL_TEMPLATE_DIR, mail_template_name)
    with open(mail_template_path, 'r') as template_reader:
        template_content = template_reader.read()
    template_obj = Template(template_content)
    context = Context(args)
    return template_obj.render(context)


def do_post(url, **kwargs):
    post_data = urllib.urlencode(kwargs)
    req = urllib2.Request(url=url, data=post_data)
    print 'post method request: %s' % req

    resp = urllib2.urlopen(req)
    resp_data = resp.read()
    return resp_data


def do_get(url, **kwargs):
    get_args = ['%s=%s' % (key, value) for key, value in kwargs.items()]
    if get_args:
        url = '%s?%s' % (url, '&'.join(get_args))
        print 'get url is: %s' % url
    req = urllib2.Request(url)
    print 'get method request: %s' % req

    resp = urllib2.urlopen(req)
    return resp.read()
