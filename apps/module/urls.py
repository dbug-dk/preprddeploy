#! coding=utf8
# Filename    : urls.py
# Description : urls file for app module
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.conf.urls import url
import views

urlpatterns = [
    url(r'^home$', views.home, name='module_home'),
    url(r'^get_resources_num$', views.get_resources_num, name='get_resources_num'),
    url(r'^get_users$', views.get_users, name='get_users'),
    url(r'^show_modules$', views.show_modules, name='show_modules')
]
