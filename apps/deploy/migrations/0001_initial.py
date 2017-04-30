# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ModuleConf',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('module_name', models.CharField(max_length=32)),
                ('conf_name', models.CharField(max_length=32)),
                ('region', models.CharField(max_length=32)),
                ('prd_conf_content', models.TextField()),
                ('preprd_conf_content', models.TextField()),
                ('create_time', models.DateTimeField(auto_now_add=True)),
                ('module_version', models.CharField(max_length=8)),
            ],
        ),
        migrations.CreateModel(
            name='ModuleConfTemplate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('module_name', models.CharField(max_length=32)),
                ('conf_name', models.CharField(max_length=32)),
                ('env', models.CharField(max_length=32, choices=[(b'cn', '\u5185\u9500'), (b'en', '\u5916\u9500')])),
                ('conf_content', models.TextField()),
                ('save_time', models.DateTimeField()),
                ('template_version', models.CharField(max_length=10)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='moduleconftemplate',
            unique_together=set([('module_name', 'conf_name', 'env', 'template_version')]),
        ),
        migrations.AddField(
            model_name='moduleconf',
            name='template',
            field=models.ForeignKey(to='deploy.ModuleConfTemplate'),
        ),
    ]
