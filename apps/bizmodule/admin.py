from django.contrib import admin
from bizmodule.models import *


models = [BizServiceLayer]
for model in models:
    admin.site.register(model)
