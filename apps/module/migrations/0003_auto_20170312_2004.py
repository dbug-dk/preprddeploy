# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0002_awsresource'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('module', '0002_delete_regioninfo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ec2OptionSet',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('tags', models.TextField(default=None, null=True, blank=True)),
                ('content', models.TextField()),
                ('account', models.ForeignKey(to='common.AwsAccount')),
                ('image', models.ForeignKey(to='common.AwsResource')),
            ],
        ),
        migrations.CreateModel(
            name='ModuleInfo',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('module_name', models.CharField(max_length=30)),
                ('update_version', models.CharField(max_length=20, null=True, blank=True)),
                ('current_version', models.CharField(max_length=20)),
                ('instance_count', models.IntegerField(default=2)),
                ('elb_names', models.CharField(max_length=1000)),
                ('module_type', models.CharField(max_length=10)),
                ('order', models.IntegerField(default=-1)),
                ('regions', models.ManyToManyField(to='common.RegionInfo')),
                ('user', models.ForeignKey(related_name='module_user', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
        migrations.AlterField(
            model_name='scriptexeclog',
            name='user',
            field=models.ForeignKey(related_name='script_exec_user', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True),
        ),
        migrations.AddField(
            model_name='ec2optionset',
            name='module',
            field=models.ForeignKey(to='module.ModuleInfo'),
        ),
        migrations.AddField(
            model_name='ec2optionset',
            name='region',
            field=models.ForeignKey(to='common.RegionInfo'),
        ),
    ]
