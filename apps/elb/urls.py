#! coding=utf8
# Filename    : urls.py
# Description : urls file for app elb
# Author      : dengken
# History:
#    1.  , dengken, first create
from django.conf.urls import url
import views

urlpatterns = [
    url(r'^home$', views.home, name='elb_home'),
    url(r'^get_loadbalancers$', views.get_loadbalancers, name='get_loadbalancers'),
    url(r'^get_elb_names$', views.get_elb_names, name='get_elb_names'),
    url(r'^create_elb_stack$', views.create_elb_stack, name='create_elb_stack'),
    url(r'^get_stack_events$', views.get_stack_events, name='get_stack_events'),
    url(r'^add_elb_instances$', views.add_elb_instances, name='add_elb_instances'),
    url(r'^get_instances_for_elb$', views.get_instances_for_elb, name='get_instances_for_elb'),
    url(r'^register_instance$', views.register_instance, name='register_instance'),
    url(r'^update_elb_stack$', views.update_elb_stack, name='update_elb_stack')
]
