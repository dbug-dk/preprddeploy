from django.conf.urls import include, url
from django.contrib import admin
from module.views import home

urlpatterns = [
    # Examples:
    # url(r'^$', 'preprddeploy.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    url(r'^$', home, name='index'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^user/', include('permission.urls')),
    url(r'^module/', include('module.urls')),
    url(r'^elb/', include('elb.urls')),
    url(r'^basic/', include('basicservice.urls')),
    url(r'^biz/', include('bizmodule.urls'))
]
