#! coding=utf8
##############################################################################
# Copyright (C), 2016 , TP-LINK Technologies Co., Ltd.
# Filename    : mailsender.py
# Description : send mail with django.core.mail
# Author      : dengken
# History:
#    1. 2017年2月7日 , dengken, first create
##############################################################################
import logging
import traceback

from django.core import mail
from django.core.mail.message import EmailMultiAlternatives

from preprddeploy.settings import SERVER_EMAIL, MAIL_DOMAIN

logger = logging.getLogger('deploy')


class MailSender(object):
    def __init__(self):
        self.from_addr = SERVER_EMAIL

    def send_html_mail(self, to_addrs, subject, html):
        """
            send mail with no attachment.
            charset depend on CHARSET in settings.py. if not set, default is utf8.
        Args:
            html (string): html mail content
            subject (string): subject string
            to_addrs (list): email address list to recieve mail.
        """
        logger.info('start to send email to %s, subject: %s' % (to_addrs, subject))
        try:
            to_addrs.remove('root@%s' % MAIL_DOMAIN)
        except:
            pass
        if not mail.send_mail(subject, '', self.from_addr, recipient_list=to_addrs, html_message=html):
            error_msg = 'mail send to nobody. subject: %s, toAddrs: %s' % (subject, to_addrs)
            logger.error(error_msg)
            raise Exception(error_msg)
        logger.info('successfully send mail to %s, subject: %s' % (to_addrs, subject))

    def send_raw_mail(self, to_addrs, subject, html, attachfile_paths=None):
        """
        send mail with attachments.
        charset depend on CHARSET in settings.py. if not set, default is utf8.
        Args:
            to_addrs (list): email address list
            subject (string): subject string
            html (string): html mail content
            attachfile_paths (list): a list contains all the attachments path want to send.
                                     if this arg is None, will use self.send_mail to send an email
        """
        if not attachfile_paths:
            logger.warn('use send_raw_mail method but with no attachment. to %s, subject: %s' % (
                to_addrs,
                subject
            ))
            self.send_html_mail(to_addrs, subject, html)
            return
        logger.info('start to send raw mail to %s, subject: %s' % (to_addrs, subject))
        email = EmailMultiAlternatives(subject, html, self.from_addr, to_addrs)
        email.content_subtype = 'html'
        for attachment_path in attachfile_paths:
            email.attach_file(attachment_path)
        if not email.send():
            error_msg = 'mail send to nobody. subject: %s, toAddrs: %s' % (subject, to_addrs)
            logger.error(error_msg)
            raise Exception(error_msg)
        logger.info('successfully send raw mail to %s, subject: %s' % (to_addrs, subject))

    def send_mail_when_module_error(self, errorModules, upgradeInfoJson, managers):
        subject = u'%s录入模块更新信息失败' % MAIL_SUBJECT_PREFIX
        mailHtmlMaker = MailHtmlMaker()
        mailHtmlMaker.add_line(u'以下模块的更新信息存在异常。')
        toAddrs = [admin[1] for admin in ADMINS]
        for moduleName, errorMsg in errorModules.items():
            mailHtmlMaker.add_line('%s: %s'%(moduleName, errorMsg), 'text-indent:2em;')
            if not DEBUG:
                moduleManager = upgradeInfoJson['modules'][moduleName]['author']
                toAddrs.append('%s@%s' % (moduleManager, MAIL_DOMAIN))
        if not DEBUG:
            managerEmailList = ['%s@%s' % (name, MAIL_DOMAIN) for name in managers]
            toAddrs += managerEmailList
        try:
            mailHtml = mailHtmlMaker.render_template()
        except:
            errorMsg = traceback.format_exc()
            logger.error('render mail template failed.')
            logger.error(errorMsg)
            raise Exception(errorMsg)
        toAddrs = set(toAddrs)
        self.send_html_mail(toAddrs, subject, mailHtml)

    def send_mail_when_new_module(self, newModules, upgradeInfoJson, managers, httpHost):
        subject = u'%s新模块启动参数确认'
        mailHtmlMaker = MailHtmlMaker()
        mailHtmlMaker.add_line(u'此次更新存在第一次上线的模块，请负责人确认模块的实例启动参数是否正确。')
        toAddrs = [admin[1] for admin in ADMINS]

        for moduleName, regions in newModules.items():
            mailHtmlMaker.add_line('%s 部署区域: %s' % (moduleName, regions))
            if not DEBUG:
                moduleManager = upgradeInfoJson['modules'][moduleName]['author']
                toAddrs.append('%s@%s' % (moduleManager, MAIL_DOMAIN))
        moduleInfoPageUrl = mailHtmlMaker.get_url(httpHost, 'index')
        mailHtmlMaker.add_button(u'模块信息管理页面', moduleInfoPageUrl)
        if not DEBUG:
            managerEmailList = ['%s@%s' % (name, MAIL_DOMAIN) for name in managers]
            toAddrs += managerEmailList
        try:
            mailHtml = mailHtmlMaker.render_template()
        except:
            errorMsg = traceback.format_exc()
            logger.error('render mail template failed.')
            logger.error(errorMsg)
            raise Exception(errorMsg)
        toAddrs = set(toAddrs)
        self.send_html_mail(toAddrs, subject, mailHtml)


