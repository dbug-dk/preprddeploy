# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('module', '0006_auto_20170312_2119'),
        ('common', '0002_awsresource'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoadbalancerInfo',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('elb_name', models.CharField(max_length=100)),
                ('elb_scheme', models.CharField(max_length=20, choices=[(b'internet-facing', b'internet-facing'), (b'internal', b'internal')])),
                ('dns_name', models.CharField(max_length=100)),
                ('module', models.ForeignKey(to='module.ModuleInfo')),
                ('region', models.ForeignKey(to='common.RegionInfo')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='loadbalancerinfo',
            unique_together=set([('elb_name', 'region')]),
        ),
    ]
