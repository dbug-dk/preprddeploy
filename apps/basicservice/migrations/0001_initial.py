# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0002_awsresource'),
    ]

    operations = [
        migrations.CreateModel(
            name='BasicServiceDeployInfo',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('service_name', models.CharField(unique=True, max_length=50)),
                ('order', models.IntegerField()),
                ('regions', models.ManyToManyField(to='common.RegionInfo')),
            ],
        ),
    ]
