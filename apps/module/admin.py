from django.contrib import admin
from apps.module.models import *
# Register your models here.

models = [ScriptExecLog, ModuleInfo, Ec2OptionSet]
for model in models:
    admin.site.register(model)
