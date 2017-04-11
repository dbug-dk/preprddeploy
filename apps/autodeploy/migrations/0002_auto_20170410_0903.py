# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('autodeploy', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='autodeployhistory',
            name='upgrade_progress',
        ),
        migrations.AddField(
            model_name='autodeployhistory',
            name='progress_name',
            field=models.CharField(default='start_env', max_length=30),
            preserve_default=False,
        ),
    ]
