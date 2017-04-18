import json
import logging
import traceback

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.

from common.models import RegionInfo, AwsAccount, AwsResource
from launcher.opsetutils import check_params_set, run_instances, add_ec2_tags, add_volume_tags, get_tags_by_module, \
    get_opset_dict
from launcher.resourcehandler import AwsResourceHandler
from module.models import Ec2OptionSet
from permission.models import SitePage
from preprddeploy.settings import ACCOUNT_NAME

logger = logging.getLogger('common')


@login_required
def home(request):
    current_region = RegionInfo.get_region(request)
    regions = RegionInfo.get_regions_infos(['region', 'chinese_name'], exclude_regions=[current_region])
    launcher_page = SitePage.objects.get(name='launcher')
    return render(request, 'launcher/ec2-launcher.html', {
        'current_region': current_region,
        'regions': regions,
        'launcher_page': launcher_page,
        'account_name': ACCOUNT_NAME
    })


def get_resources(request):
    account_name = request.GET.get('account_name')
    region = request.GET.get('region')
    if not account_name or not region:
        return HttpResponse('bad request!', status=400)
    aws_resource_handler = AwsResourceHandler(account_name, region)
    try:
        awsresources = aws_resource_handler.load_resources()
    except:
        return HttpResponse('load resources failed. error msg:\n%s' % traceback.format_exc(), status=500)
    return HttpResponse(json.dumps(awsresources))


def update_resources(request):
    account_name = request.GET.get('account_name')
    region = request.GET.get('region')
    if not account_name or not region:
        return HttpResponse('bad request!', status=400)
    aws_resource_handler = AwsResourceHandler(account_name, region)
    try:
        awsresources = aws_resource_handler.update_resources()
    except:
        return HttpResponse('update resource failed, error msg:\n%s' % traceback.format_exc(), status=500)
    return HttpResponse(json.dumps(awsresources))


def create_ec2optionset(request):
    account_name = request.POST.get('account')
    region = request.POST.get('region')
    new_opset = json.loads(request.POST.get('json'))
    if not account_name or not region or not new_opset:
        return HttpResponse('bad request!', status=400)
    try:
        check_params_set(new_opset)
    except Exception as e:
        return HttpResponse(e.message, status=500)
    try:
        name = new_opset.pop('name')
        account_name = 'cn-%s' % account_name if region == 'cn-north-1' else 'en-%s' % account_name
        account_obj = AwsAccount.objects.get(name=account_name)
        region_obj = RegionInfo.objects.get(region=region)
        if Ec2OptionSet.objects.filter(account=account_obj, region=region_obj, name=name).exists():
            return HttpResponse(json.dumps({
                'ret': False,
                'msg': 'optionset name: %s already exist.' % name
            }))
        image_id = new_opset.pop('image')[1]
        image_obj = AwsResource.objects.get(resource_id=image_id, resource_type='ami',
                                            region=region_obj, account=account_obj)
        tags = new_opset.pop('tags')
        ec2opset_obj = Ec2OptionSet(name=name, account=account_obj, region=region_obj, module=None,
                                    image=image_obj, tags=json.dumps(tags), content=json.dumps(new_opset))
        ec2opset_obj.save()
        return HttpResponse(json.dumps({'ret': True}))
    except:
        return HttpResponse('create ec2 optionset failed, error msg: \n%s' % traceback.format_exc(), status=500)


def get_ec2optionsets(request):
    account_name = request.GET.get('account')
    region = request.GET.get('region')
    if not account_name or not region:
        return HttpResponse('bad request!', status=400)
    try:
        account_name = 'cn-%s' % account_name if region == 'cn-north-1' else 'en-%s' % account_name
        account_obj = AwsAccount.objects.get(name=account_name)
        region_obj = RegionInfo.objects.get(region=region)
        ec2optionsets = Ec2OptionSet.objects.filter(account=account_obj, region=region_obj)
        opsets = []
        for opset in ec2optionsets:
            ret = get_opset_dict(opset)
            opsets.append(ret)
        return HttpResponse(json.dumps(opsets))
    except:
        return HttpResponse('get existed optionsets failed, error msg: \n%s' % traceback.format_exc(), status=500)


def update_ec2optionset(request):
    account_name = request.POST.get('account')
    region_name = request.POST.get('region')
    old_opset_name = request.POST.get('oldName')
    new_opset = json.loads(request.POST.get('json'))
    if not account_name or not region_name or not old_opset_name or not new_opset:
        return HttpResponse('bad request!', status=400)
    try:
        check_params_set(new_opset)
    except Exception as e:
        return HttpResponse(e.message, status=500)
    try:
        new_name = new_opset.pop('name')
        account_name = 'cn-%s' % account_name if region_name == 'cn-north-1' else 'en-%s' % account_name
        account_obj = AwsAccount.objects.get(name=account_name)
        region_obj = RegionInfo.objects.get(region=region_name)
        old_opset_obj = Ec2OptionSet.objects.get(account=account_obj, region=region_obj, name=old_opset_name)
        image_id = new_opset.pop('image')[1]
        image_obj = AwsResource.objects.get(resource_id=image_id, resource_type='ami',
                                            region=region_obj, account=account_obj)
        tags = new_opset.pop('tags')
        old_opset_obj.name = new_name
        old_opset_obj.account = account_obj
        old_opset_obj.region = region_obj
        old_opset_obj.image = image_obj
        old_opset_obj.tags = json.dumps(tags)
        old_opset_obj.content = json.dumps(new_opset)
        old_opset_obj.save(update_fields=['name', 'account', 'region', 'image', 'tags', 'content'])
        return HttpResponse(json.dumps({'ret': True}))
    except:
        return HttpResponse('update ec2 option set: %s failed, error msg:\n%s' % (
            old_opset_name,
            traceback.format_exc()
        ), status=500)


def del_ec2optionset(request):
    account_name = request.POST.get('account')
    region_name = request.POST.get('region')
    opset_name = request.POST.get('ec2optionsetName')
    if not account_name or not region_name or not opset_name:
        return HttpResponse('bad request!', status=400)
    account_name = 'cn-%s' % account_name if region_name == 'cn-north-1' else 'en-%s' % account_name
    account_obj = AwsAccount.objects.get(name=account_name)
    region_obj = RegionInfo.objects.get(region=region_name)
    del_opset = Ec2OptionSet.objects.filter(account=account_obj, region=region_obj, name=opset_name)
    if del_opset.exists():
        try:
            del_opset.delete()
        except Exception as e:
            return HttpResponse('delete opset: %s in db failed, error msg: %s\n' % (
                opset_name,
                e.message
            ), status=500)
        else:
            return HttpResponse(json.dumps({'ret': True}))
    else:
        return HttpResponse('can not found the specified optionset: %s, please check' % opset_name, status=500)


def run_ec2optionset(request):
    account = request.GET.get('account')
    region = request.GET.get('region')
    opset_name = request.GET.get('ec2optionset')
    num = request.GET.get('num')
    if not account or not region or not opset_name:
        return HttpResponse('bad request!', status=400)
    if not num:
        return HttpResponse('please enter the number of instances to launch.', status=400)
    try:
        region_obj = RegionInfo.objects.get(region=region)
        account_name = 'cn-%s' % account if region == 'cn-north-1' else 'en-%s' % account
        account_obj = AwsAccount.objects.get(name=account_name)
        ec2optionset = Ec2OptionSet.objects.get(name=opset_name, region=region_obj, account=account_obj)
    except (RegionInfo.DoesNotExist, AwsAccount.DoesNotExist, Ec2OptionSet.DoesNotExist) as ne:
        return HttpResponse('model not found in db: %s' % ne.message, status=500)
    session = AwsAccount.get_awssession(region, account)
    ec2_resource = session.resource('ec2')
    elb_client = session.client('elb')
    logger.info('launch instances: %s, %s, %s, %s' % (
        account_name,
        region,
        opset_name,
        num
    ))

    try:
        instance_ids = run_instances(ec2_resource, elb_client, ec2optionset, int(num))
    except:
        error_msg = "launch instances with opset: %s failed: \n%s" % (
            opset_name,
            traceback.format_exc()
        )
        logger.error(error_msg)
        return HttpResponse(error_msg, status=500)
    logger.info('launch instances done: %s' % opset_name)
    return HttpResponse(json.dumps({'ret': True, 'msg': instance_ids}))


def add_instance_tags(request):
    region = request.POST.get('region')
    account = request.POST.get('account')
    instance_ids = request.POST.getlist('instanceIds[]')
    opset_name = request.POST.get('opsetName')
    if not region or not account or not instance_ids or not opset_name:
        return HttpResponse('bad request!', status=400)
    try:
        region_obj = RegionInfo.objects.get(region=region)
        account_name = 'cn-%s' % account if region == 'cn-north-1' else 'en-%s' % account
        account_obj = AwsAccount.objects.get(name=account_name)
        ec2optionset = Ec2OptionSet.objects.get(name=opset_name, region=region_obj, account=account_obj)
    except (RegionInfo.DoesNotExist, AwsAccount.DoesNotExist, Ec2OptionSet.DoesNotExist) as ne:
        return HttpResponse('model not found in db: %s' % ne.message, status=500)
    session = AwsAccount.get_awssession(region, account)
    ec2_resource = session.resource('ec2')
    logger.info('add instance and ebs tags: %s, %s, %s, %s' % (
        account_name,
        region,
        opset_name,
        instance_ids
    ))

    try:
        tags = get_tags_by_module(ec2optionset.module, region)
        result = add_ec2_tags(ec2_resource, tags, instance_ids, region)
    except:
        error_msg = 'add instance tags failed, error msg:\n%s' % traceback.format_exc()
        logger.error(error_msg)
        return HttpResponse(error_msg, status=500)
    if result['failed']:
        error_msg = 'some instances add instance tags failed %s' % ', '.join(result['failed'])
        logger.error(error_msg)
        return HttpResponse(error_msg, status=500)
    logger.info('all instance tags add success')

    try:
        add_volume_tags(ec2_resource, instance_ids)
    except:
        error_msg = 'add ebs tags failed, error msg:\n%s' % traceback.format_exc()
        logger.error(error_msg)
        return HttpResponse(error_msg, status=500)
    return HttpResponse(json.dumps({'ret': True}))


def get_all_update_modules(request):
    if 'region' in request.GET:
        region_name = request.GET.get('region')
        region_obj = RegionInfo.objects.get(region=region_name)
        modules = region_obj.moduleinfo_set.filter(~Q(update_version=u'')&~Q(update_version=None))
        print modules
        # modules = ModuleInfo.objects.filter(~Q(update_version=u''), region=region_obj)
        module_infos = []
        for module in modules:
            module_name = module.module_name
            current_version = module.current_version
            update_version = module.update_version
            module_infos.append([module_name, current_version, update_version])
        return render(request, 'launcher/choose-modules.html', {'module_infos': module_infos})
    else:
        return HttpResponse('bad request.', status=400)


def run_instances_batch(request):
    module_name = request.GET.get('module_name')
    region = request.GET.get('region')
    account = request.GET.get('account')
    if not module_name or not region or not account:
        return HttpResponse('bad request!', status=400)
    region_obj = RegionInfo.objects.get(region=region)
    module = region_obj.moduleinfo_set.get(module_name=module_name)
    ec2opset_objs = module.ec2optionset_set.filter(region=region_obj)
    if ec2opset_objs.count() == 0:
        return HttpResponse(json.dumps({'success': False,
                                        'module': module_name,
                                        'info': 'module has no launch parameters'}))
    if ec2opset_objs.count() > 1:
        return HttpResponse(json.dumps({'success': False,
                                        'module': module_name,
                                        'info': 'too many launch parameters found.'}))
    ec2opset_obj = ec2opset_objs[0]
    if ec2opset_obj.image is None:
        return HttpResponse(json.dumps({'success': False,
                                        'module': module_name,
                                        'info': 'image has been registered.'}))
    tags = get_tags_by_module(module, region)
    ec2opset_obj.tags = tags
    session = AwsAccount.get_awssession(region, account)
    ec2res = session.resource('ec2')
    elbclient = session.client('elb')
    try:
        instance_ids = run_instances(ec2res, elbclient, ec2opset_obj, module.instance_count)
    except:
        return HttpResponse(json.dumps({'success': False,
                                        'module': module_name,
                                        'info': 'launch instance faled: \n%s' % traceback.format_exc()}))
    return HttpResponse(json.dumps({'success': True,
                                    'module': module_name,
                                    'info': ', '.join(instance_ids)
                                    }))
