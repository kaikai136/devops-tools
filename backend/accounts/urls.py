from django.urls import path

from . import views

urlpatterns = [
    path("auth/slider-challenge/", views.slider_challenge),
    path("auth/slider-verify/", views.slider_verify),
    path("auth/login/", views.auth_login),
    path("auth/login/2fa/", views.auth_login_2fa),
    path("auth/login/2fa/setup/", views.auth_login_2fa_setup),
    path("auth/logout/", views.auth_logout),
    path("auth/me/", views.auth_me),
    path("profile/", views.profile),
    path("profile/avatar/", views.profile_avatar),
    path("profile/password/", views.profile_password),
    path("profile/2fa/setup/", views.profile_2fa_setup),
    path("profile/2fa/confirm/", views.profile_2fa_confirm),
    path("profile/2fa/disable/", views.profile_2fa_disable),
    path("users/", views.users),
    path("users/<int:user_id>/", views.user_detail),
]
