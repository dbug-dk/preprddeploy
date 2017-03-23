from django.conf.urls import url
import views

urlpatterns = [
    url(r'^upload_file$', views.upload_file, name='uploadFile')
]
