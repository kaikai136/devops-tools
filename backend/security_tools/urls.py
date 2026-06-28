from django.urls import path

from . import views

urlpatterns = [
    path("security/command-rules/", views.command_rules),
    path("security/command-rules/<int:rule_id>/", views.command_rule_detail),
    path("security/command-rules/<int:rule_id>/toggle/", views.command_rule_toggle),
    path("security/command-records/", views.command_records),
]
