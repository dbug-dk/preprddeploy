from django.contrib import admin
from module.models import *
# Register your models here.

models = [ScriptExecLog, ModuleInfo, Ec2OptionSet]
for model in models:
    admin.site.register(model)
