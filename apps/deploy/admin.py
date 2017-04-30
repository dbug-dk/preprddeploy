from django.contrib import admin

# Register your models here.
from models import *

models = [ModuleConfTemplate, ModuleConf]
for model in models:
    admin.site.register(model)
