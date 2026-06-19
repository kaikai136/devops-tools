from django.urls import path

from . import views

urlpatterns = [
    path("host-management/groups/", views.host_groups),
    path("host-management/groups/<int:group_id>/", views.host_group_detail),
    path("host-management/hosts/", views.managed_hosts),
    path("host-management/hosts/<int:host_id>/", views.managed_host_detail),
    path("host-management/accounts/", views.host_credentials),
    path("host-management/accounts/<int:credential_id>/", views.host_credential_detail),
]
