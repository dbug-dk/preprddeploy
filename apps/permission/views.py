#! coding=utf8
# Filename    : views.py
# Description : user views functions
# Author      : dengken
# History:
#    1.  , dengken, first create
import logging
import urlparse

from django.contrib.auth import login as auth_login
from django.contrib.auth.views import logout as auth_logout
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url, render
from django.utils.http import is_safe_url, urlquote

from apps.permission.forms import BootstrapAuthenticationForm
from preprddeploy import settings
from preprddeploy.settings import LOGIN_URL

logger = logging.getLogger('common')


def login(request, template_name='registration/login.html',
          redirect_field_name='/',
          authentication_form=BootstrapAuthenticationForm,
          extra_context=None):
    if request.method == "POST":
        referrer = request.META.get('HTTP_REFERER')
        result = urlparse.urlparse(referrer)
        params = urlparse.parse_qs(result.query, True)
        redirect_to = ''.join(params.get('next', redirect_field_name))
        form = authentication_form(request, data=request.POST)
        if form.is_valid():
            # Ensure the user-originating redirection url is safe.
            if not is_safe_url(url=redirect_to, host=request.get_host()):
                redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)
            # Okay, security check complete. Log the user in.
            loginUser = form.get_user()
            auth_login(request, loginUser)
            logger.info('user: %s login' % loginUser.username)
            if 'remember' in request.POST:
                sessionExpireTime = 86400
            else:
                sessionExpireTime = 1800
            request.session.set_expiry(sessionExpireTime)
            return HttpResponseRedirect(redirect_to)
    else:
        form = authentication_form(request)
    current_site = get_current_site(request)
    context = {
        'form': form,
        'site': current_site,
        'site_name': current_site.name,
    }
    if extra_context is not None:
        context.update(extra_context)
    return render(request, template_name, context)


def logout(request):
    referrer = request.META.get('HTTP_REFERER')
    result = urlparse.urlparse(referrer)
    urlPath = result.path
    urlQuery = result.query
    nextParams = ''.join([urlPath, '?', urlQuery])
    nextParams = urlquote(nextParams)
    nextPage = ''.join([LOGIN_URL, '?next=', nextParams])
    logger.info('user %s logout.' % request.user.username)
    return auth_logout(request, next_page=nextPage)
