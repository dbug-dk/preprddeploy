# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('basicservice', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BasicServiceIps',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('service_name', models.CharField(max_length=50)),
                ('account', models.CharField(max_length=6, choices=[(b'beta', b'preprd'), (b'prd', b'prd')])),
                ('ips', models.TextField()),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='basicserviceips',
            unique_together=set([('service_name', 'account')]),
        ),
    ]
