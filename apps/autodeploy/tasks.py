#! coding=utf8
# Filename    : tasks.py
# Description : 
# Url         : 
# Author      : iwannarock
# History:
# 1. 2017/5/3 0:57 , iwannarock, first create
import urllib
import urllib2

from celery.task import task


@task
def start_env_request(upgrade_version, managers):
    start_url = 'http://127.0.0.1:8001/autodeploy/start_env'
    args = {'upgrade_version': upgrade_version, 'managers': managers}
    resp = do_get(start_url, **args)
    print resp


def do_post(url, **kwargs):
    post_data = urllib.urlencode(kwargs)
    req = urllib2.Request(url=url, data=post_data)
    print 'post method request: %s' % req

    resp = urllib2.urlopen(req)
    resp_data = resp.read()
    return resp_data


def do_get(url, **kwargs):
    get_args = ['%s=%s' % (key, value) for key, value in kwargs.items()]
    if get_args:
        url = '%s?%s' % (url, '&'.join(get_args))
        print 'get url is: %s' % url
    req = urllib2.Request(url)
    print 'get method request: %s' % req

    resp = urllib2.urlopen(req)
    return resp.read()
