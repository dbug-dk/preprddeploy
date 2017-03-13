# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AwsResource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('resource_name', models.CharField(max_length=500)),
                ('resource_id', models.CharField(max_length=100)),
                ('resource_type', models.CharField(max_length=100)),
                ('account', models.ForeignKey(to='common.AwsAccount')),
                ('parent', models.ForeignKey(default=None, blank=True, to='common.AwsResource', null=True)),
                ('region', models.ForeignKey(to='common.RegionInfo')),
            ],
        ),
    ]
