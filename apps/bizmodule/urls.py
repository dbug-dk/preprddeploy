#! coding=utf8
# Filename    : urls.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.conf.urls import url
import views

urlpatterns = [
    url(r'^home$', views.home, name='bizmodule_home'),
    url(r'^show_instances$', views.show_instances, name='show_instances'),
    url(r'^start_instance$', views.start_instance, name='start_instance')
]
