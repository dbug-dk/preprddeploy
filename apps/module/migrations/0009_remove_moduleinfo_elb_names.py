# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('module', '0008_auto_20170414_1418'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='moduleinfo',
            name='elb_names',
        ),
    ]
