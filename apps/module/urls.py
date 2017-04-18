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
    url(r'^show_modules$', views.show_modules, name='show_modules'),
    url(r'^update_module_info', views.update_module_info, name='update_module_info'),
    url(r'^get_launch_params$', views.get_launch_params, name='get_launch_params'),
    url(r'^get_module_region$', views.get_module_region, name='get_module_region'),
    url(r'^get_modify_launch_params$', views.get_modify_launch_params, name='get_modify_launch_params'),
    url(r'^modify_launch_params$', views.modify_launch_params, name='modify_launch_params')
]
