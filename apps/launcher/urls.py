#! coding=utf8
# Filename    : urls.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.conf.urls import url
import views

urlpatterns = [
    url('^home$', views.home, name='launcher_home'),
    url('^update_resources$', views.update_resources, name='update_resources')
]
