# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AwsAccount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=30)),
                ('account_id', models.CharField(max_length=24)),
                ('access_key_id', models.CharField(max_length=40)),
                ('secret_access_key', models.CharField(max_length=80)),
            ],
        ),
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
        migrations.AddField(
            model_name='awsaccount',
            name='valid_regions',
            field=models.ManyToManyField(to='common.RegionInfo'),
        ),
    ]
