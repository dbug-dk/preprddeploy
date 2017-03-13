# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('module', '0005_auto_20170312_2053'),
    ]

    operations = [
        migrations.AlterField(
            model_name='moduleinfo',
            name='module_name',
            field=models.CharField(unique=True, max_length=30),
        ),
    ]
