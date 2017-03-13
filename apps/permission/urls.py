#! coding=utf8
# Filename    : urls.py
# Description : urls file
# Author      : dengken
# History:
#    1.  , dengken, first create
import datetime
from django.conf.urls import url

from apps.permission.forms import BootstrapAuthenticationForm
from apps.permission.views import login, logout

urlpatterns = [
    url(r'^login$', login, {
        'template_name': 'registration/login.html',
        'authentication_form': BootstrapAuthenticationForm,
        'extra_context': {
            'title': 'Login',
            'year': datetime.datetime.now().year
        }
    }, name='login'),
    url(r'^logout$', logout, name='logout')
]
