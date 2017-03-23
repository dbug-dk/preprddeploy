# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('module', '0006_auto_20170312_2119'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='moduleinfo',
            name='module_type',
        ),
    ]
