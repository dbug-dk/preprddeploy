# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AutoDeployHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('upgrade_version', models.CharField(max_length=15)),
                ('log_content', models.TextField(blank=True)),
                ('upgrade_progress', models.TextField()),
                ('task_num', models.IntegerField()),
                ('task_pid', models.IntegerField(default=0)),
                ('result_pid', models.IntegerField(default=0)),
                ('is_finish', models.BooleanField(default=False)),
                ('is_success', models.BooleanField(default=False)),
                ('start_time', models.DateTimeField(auto_now_add=True)),
                ('managers', models.CharField(max_length=100)),
                ('end_time', models.DateTimeField(null=True, blank=True)),
            ],
        ),
    ]
