import os

import subprocess

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from common.models import RegionInfo
from permission.models import SitePage
from preprddeploy.settings import BASE_DIR


@login_required
def upload_file(request):
    """
    if request is post: upload files to server and deal with these(unzip or save to database)
    else: show upload page
    Args:
        request (django.http.request.HttpRequest)
    """
    if request.method == "POST":
        region = request.POST['region']
        upload_files = request.FILES.getlist('file')
        upload_dir = '/tmp'
        for uploadFile in upload_files:
            upload_file_name = uploadFile.name
            # when upload zip, unzip and copy to dirname(${BASE_DIR})
            if upload_file_name.endswith('.zip'):
                filepath = os.path.join(os.path.dirname(BASE_DIR), upload_file_name)
                with open(filepath, 'wb+') as f:
                    for chunk in uploadFile.chunks():
                        f.write(chunk)
            else:
                return HttpResponse('error', status=500)
        return HttpResponse('success')
    current_region = RegionInfo.get_region(request)
    regions = RegionInfo.get_regions_infos(['region', 'chinese_name'], exclude_regions=[current_region])
    uploader_page = SitePage.objects.get(name='uploader')
    return render(request, 'uploader/upload.html', locals())
