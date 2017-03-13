# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('module', '0004_auto_20170312_2052'),
    ]

    operations = [
        migrations.AlterField(
            model_name='moduleinfo',
            name='current_version',
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
    ]
