import json
import os
import urllib
import urllib2
import argparse

pwd = os.path.split(os.path.realpath(__file__))[0]


def get_upgrade_info(json_file_name):
    json_file_path = os.path.join(pwd, json_file_name)
    with open(json_file_path, 'r') as json_reader:
	json_content = json_reader.read()
    return json_content


def do_post(url, **kwargs):
    post_data = urllib.urlencode(kwargs)
    req = urllib2.Request(url=url, data=post_data)
    print 'post method request: %s' % req

    resp = urllib2.urlopen(req)
    resp_data = resp.read()
    return resp_data


def do_get(url, **kwargs):
    get_args = ['%s=%s'% (key, value) for key, value in kwargs.items()]
    if get_args:
	url = '%s?%s' % (url, '&'.join(get_args))
        print 'get url is: %s' % url
    req = urllib2.Request(url)
    print 'get method request: %s' % req
   
    resp = urllib2.urlopen(req)
    return resp.read()


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='for auto start test')
    argparser.add_argument('-s', '--start', action='store_true', default=False, help='start env?')
    argparser.add_argument('-g', '--get', action='store_true', default=False, help='get status')
    args = argparser.parse_args()
    if not (args.start ^ args.get):
        print '-s|--start and -g|--get, you must specify only one of them'
        exit(1)
    if args.start:
        json_file_name = 'test.json'
        print 'read upgrade json info from file: %s' % json_file_name
        json_content = get_upgrade_info(json_file_name)
        start_url = 'http://127.0.0.1:8001/autodeploy/start_process'
        resp = do_post(start_url, **{'method':'start_env','upgrade_infos':json_content})
	print json.dumps(resp, indent=2)
    else:
        url = 'http://127.0.0.1:8001/autodeploy/get_status'
        args = {'upgrade_version': 'EN-TEST'}
        resp = do_get(url, **args)
        print json.dumps(resp, indent=2)

    print ''

