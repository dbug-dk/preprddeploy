#! coding=utf8
# Filename    : urls.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.conf.urls import url
import views


urlpatterns = [
    url('^start_process$', views.start_process, name='start_process'),
    url('^get_status$', views.get_status, name='get_status')
]