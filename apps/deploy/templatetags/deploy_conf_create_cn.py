from django import template
import random

register = template.Library()


@register.assignment_tag(takes_context=True)
def get_service_ips(context, service_name, region):
    if not region:
        region = context['region']
    service_ips = context[service_name]
    return service_ips.get(region)


def get_region_attr(value):
    region_attr = {
        'cn-north-1': 'cn',
        'ap-southeast-1': 'aps1',
        'eu-west-1': 'eu',
        'us-east-1': 'use1'
    }
    return region_attr.get(value)


@register.simple_tag(takes_context=True)
def contactIpAndPort(context, service_ips, port, random_order=False, contact_symbol=','):
    if random_order:
        random.shuffle(service_ips)
    service_ip_with_port = ['%s:%s' % (ip, port) for ip in service_ips]
    return contact_symbol.join(service_ip_with_port)


@register.simple_tag(takes_context=True)
def getElbAccessUrl(context, module_name, region, internal=False):
    if not region:
        region = context['region']
    elb_dns_names = context[module_name]
    elb_model = 'internal' if internal else 'internet-facing'
    return elb_dns_names[region][elb_model]


@register.simple_tag(takes_context=True)
def getMysqlHost(context, database_type):
    mysql = {
        'beta': {
            'cloud': '172.31.14.240',
            'ddns': '172.31.5.119',
        },
        'prd': {
            'cloud': 'prd-cloud-main-db0.clfpg2d5hazy.rds.cn-north-1.amazonaws.com.cn',
            'ddns': 'prd-ddns-db.clfpg2d5hazy.rds.cn-north-1.amazonaws.com.cn'
        }
    }
    current_env = context['env']
    return mysql[current_env][database_type]


@register.simple_tag(takes_context=True)
def getMysqlUrl(context, rds_name, db_name):
    jdbc_url_prefix = 'jdbc:mysql://'
    jdbc_url_postfix = ':3306/%s?useUnicode=true&characterEncoding=utf8' % db_name
    mysql_host = getMysqlHost(context, rds_name)
    return '%s%s%s' % (jdbc_url_prefix, mysql_host, jdbc_url_postfix)


@register.simple_tag(takes_context=True)
def getCertificateName(context, name):
    certificate_name_map = {
        'beta': {
            'connector': 'tplinkcloud-com-cn-20190915-connector',
            'web': 'tplinkcloud-com-cn-20190915-web'
        },
        'prd': {
            'connector': 'tplinkcloud-com-cn-connector-2019-9-14',
            'web': 'tplinkcloud-com-cn-web-2019-9-14'
        }
    }
    env = context['env']
    return certificate_name_map[env][name]

register.filter("regionAttr", get_region_attr)
