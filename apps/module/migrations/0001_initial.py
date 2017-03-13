# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RegionInfo',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('region', models.CharField(unique=True, max_length=32)),
                ('deploy_order', models.IntegerField()),
                ('abbr', models.CharField(max_length=10)),
                ('chinese_name', models.CharField(max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='ScriptExecLog',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('script_name', models.CharField(max_length=100)),
                ('script_content', models.TextField()),
                ('exec_time', models.DateTimeField(auto_now_add=True)),
                ('if_success', models.BooleanField()),
                ('script_result', models.TextField()),
                ('user', models.ForeignKey(related_name='script_exec_user', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
