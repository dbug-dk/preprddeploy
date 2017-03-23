# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bizmodule', '0002_auto_20170320_1414'),
    ]

    operations = [
        migrations.AddField(
            model_name='modulelayer',
            name='service_type',
            field=models.CharField(default='standard', max_length=10),
            preserve_default=False,
        ),
    ]
