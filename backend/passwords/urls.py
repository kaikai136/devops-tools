from django.urls import path

from . import views

urlpatterns = [
    path("passwords/generate/", views.password_generate),
    path("passwords/history/", views.password_history),
    path("passwords/history/<int:record_id>/", views.password_history_item),
]
