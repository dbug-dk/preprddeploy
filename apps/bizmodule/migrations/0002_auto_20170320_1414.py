# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bizmodule', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='modulelayer',
            name='service_name',
            field=models.CharField(default='default', max_length=30),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='modulelayer',
            name='module',
            field=models.ForeignKey(to='module.ModuleInfo'),
        ),
    ]
