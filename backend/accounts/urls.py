from django.urls import path

from . import views

urlpatterns = [
    path("auth/login/", views.auth_login),
    path("auth/logout/", views.auth_logout),
    path("auth/me/", views.auth_me),
    path("users/", views.users),
    path("users/<int:user_id>/", views.user_detail),
]
