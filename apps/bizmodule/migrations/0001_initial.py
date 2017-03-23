# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('module', '0006_auto_20170312_2119'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModuleLayer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('layer_name', models.CharField(max_length=30, choices=[(b'dataAccessLayer', '\u6570\u636e\u8bbf\u95ee\u5c42'), (b'businessLayer', '\u4e1a\u52a1\u5c42'), (b'forwardingLayer', '\u8f6c\u53d1\u5c42'), (b'accessLayer', '\u63a5\u5165\u5c42')])),
                ('start_order', models.IntegerField()),
                ('module', models.OneToOneField(to='module.ModuleInfo')),
            ],
        ),
    ]
