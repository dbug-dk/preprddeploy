# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SitePage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=50, choices=[(b'user', '\u7528\u6237\u7ba1\u7406'), (b'module', '\u6a21\u5757\u7248\u672c\u7ba1\u7406')])),
                ('description', models.TextField(null=True, blank=True)),
                ('staff_can_access', models.BooleanField()),
            ],
            options={
                'permissions': (('view', 'can view this page'), ('operate', 'can operate this page')),
            },
        ),
    ]
