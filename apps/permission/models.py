#! coding=utf8
# Filename    : models.py
# Description : models file for app permission
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.db import models

PAGE_INDEX = (
    ('permission', u'用户验证与权限管理'),
    ('module', u'模块版本管理'),
)


class SitePage(models.Model):
    name = models.CharField(max_length=50, choices=PAGE_INDEX)
    description = models.TextField(blank=True, null=True)
    staff_can_access = models.BooleanField()

    class Meta:
        permissions = (
            ('view', 'can view this page'),
            ('operate', 'can operate this page')
        )

    def __unicode__(self):
        return '%s|%s' % (self.name, self.description)
