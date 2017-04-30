from django import template
import random

register = template.Library()


@register.assignment_tag(takes_context=True)
def get_service_ips(context, service_name, region):
    if not region:
        region = context['region']
    service_ips = context[service_name]
    return service_ips.get(region)


def get_region_abbr(value):
    region_abbr = {
        'cn-north-1': 'cn',
        'ap-southeast-1': 'aps1',
        'eu-west-1': 'eu',
        'us-east-1': 'use1'
    }
    return region_abbr.get(value)


@register.simple_tag(takes_context=True)
def contactIpAndPort(context, service_ips, port, random_order=False, contact_symbol=','):
    if random_order:
        random.shuffle(service_ips)
    service_ip_with_port = ['%s:%s'%(ip, port) for ip in service_ips]
    return contact_symbol.join(service_ip_with_port)


@register.simple_tag(takes_context=True)
def getElbAccessUrl(context, module_name, region, internal=False):
    if not region:
        region = context['region']
    elb_dns_names = context[module_name]
    elb_model = 'internal' if internal else 'internet-facing'
    return elb_dns_names[region][elb_model]


@register.simple_tag(takes_context=True)
def getMysqlHost(context, rdsname, region=''):
    mysql_hosts = {
        'beta': {
            'ap-southeast-1': {'cloud': '10.7.2.76',
                               'ddns': '10.7.2.76'},
            'eu-west-1': {'cloud': '10.92.2.35',
                          'ddns': '10.92.2.35'},
            'us-east-1': {'cloud': '10.5.2.212',
                          'ddns': '10.5.2.212'},
        },
        'prd': {
            'ap-southeast-1': {'cloud': 'prd-cloud-main-readonly-db.ccwjpx9npjkl.ap-southeast-1.rds.amazonaws.com',
                               'ddns': 'prd-cloud-main-readonly-db.ccwjpx9npjkl.ap-southeast-1.rds.amazonaws.com'},
            'eu-west-1': {'cloud': 'prd-cloud-main-readonly-db.cbtkcyzasevu.eu-west-1.rds.amazonaws.com',
                          'ddns': 'prd-cloud-main-readonly-db.cbtkcyzasevu.eu-west-1.rds.amazonaws.com'},
            'us-east-1': {'cloud': 'prd-cloud-main-db.cnoztcvdrtsm.us-east-1.rds.amazonaws.com',
                          'ddns': 'prd-cloud-main-db.cnoztcvdrtsm.us-east-1.rds.amazonaws.com'},
        }
    }
    if not region:
        region = context['region']
    env = context['env']
    return mysql_hosts[env][region][rdsname]


@register.simple_tag(takes_context=True)
def getMysqlUrl(context, rdsname, dbname):
    jdbc_url_prefix = 'jdbc:mysql://'
    jdbc_url_postfix = ':3306/%s?useUnicode=true&characterEncoding=utf8' % dbname
    mysql_host = getMysqlHost(context, rdsname)
    return '%s%s%s' % (jdbc_url_prefix, mysql_host, jdbc_url_postfix)

register.filter("regionAttr", get_region_abbr)
