from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
import pyotp

from .models import UserProfile
from .views import SLIDER_CHALLENGE_SESSION_KEY
from system_management.services import FEATURE_PERMISSION_CODE_BY_KEY, PAGE_ACTION_PERMISSION_CODE_BY_KEY, ensure_builtin_admin, ensure_feature_permissions


def grant_profile_permissions(user, *actions):
    ensure_feature_permissions()
    role = Group.objects.create(name=f"profile-permissions-{user.id}-{Group.objects.count()}")
    permissions = [Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["profile"])]
    permissions.extend(Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("profile", action)]) for action in actions)
    role.permissions.add(*permissions)
    user.groups.add(role)
    return role


class SliderChallengeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operator", password="UserPass123")

    def complete_slider(self) -> str:
        challenge_response = self.client.get("/api/auth/slider-challenge/")
        self.assertEqual(challenge_response.status_code, 200)
        challenge = challenge_response.json()

        verify_response = self.client.post(
            "/api/auth/slider-verify/",
            data={"challengeId": challenge["challengeId"], "offsetX": challenge["targetX"], "elapsedMs": 400},
            content_type="application/json",
        )
        self.assertEqual(verify_response.status_code, 200)
        return verify_response.json()["sliderToken"]

    def test_slider_challenge_returns_expected_payload(self):
        response = self.client.get("/api/auth/slider-challenge/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("challengeId", payload)
        self.assertGreaterEqual(payload["targetX"], 54)
        self.assertLessEqual(payload["targetX"], 266)
        self.assertEqual(payload["trackWidth"], 320)
        self.assertEqual(payload["tolerance"], 8)
        self.assertEqual(payload["expiresIn"], 120)
        self.assertIn(payload["challengeId"], self.client.session[SLIDER_CHALLENGE_SESSION_KEY])

    def test_slider_verify_accepts_target_and_issues_token(self):
        token = self.complete_slider()

        self.assertTrue(token)

    def test_slider_verify_rejects_bad_offset(self):
        challenge_response = self.client.get("/api/auth/slider-challenge/")
        challenge = challenge_response.json()

        response = self.client.post(
            "/api/auth/slider-verify/",
            data={"challengeId": challenge["challengeId"], "offsetX": challenge["targetX"] + 20, "elapsedMs": 400},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("位置不正确", response.json()["error"])

    def test_slider_verify_rejects_expired_challenge(self):
        challenge_response = self.client.get("/api/auth/slider-challenge/")
        challenge = challenge_response.json()
        session = self.client.session
        session[SLIDER_CHALLENGE_SESSION_KEY][challenge["challengeId"]]["expiresAt"] = 0
        session.save()

        response = self.client.post(
            "/api/auth/slider-verify/",
            data={"challengeId": challenge["challengeId"], "offsetX": challenge["targetX"], "elapsedMs": 400},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("过期", response.json()["error"])

    def test_login_requires_slider_token(self):
        response = self.client.post(
            "/api/auth/login/",
            data={"account": "operator", "password": "UserPass123", "remember": False},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("滑块", response.json()["error"])

    def test_login_consumes_token_on_attempt(self):
        token = self.complete_slider()

        failed_response = self.client.post(
            "/api/auth/login/",
            data={"account": "operator", "password": "wrong-password", "remember": False, "sliderToken": token},
            content_type="application/json",
        )
        retry_response = self.client.post(
            "/api/auth/login/",
            data={"account": "operator", "password": "UserPass123", "remember": False, "sliderToken": token},
            content_type="application/json",
        )

        self.assertEqual(failed_response.status_code, 400)
        self.assertEqual(retry_response.status_code, 400)
        self.assertIn("失效", retry_response.json()["error"])

    def test_login_succeeds_with_verified_slider_token(self):
        token = self.complete_slider()

        response = self.client.post(
            "/api/auth/login/",
            data={"account": "operator", "password": "UserPass123", "remember": False, "sliderToken": token},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["username"], "operator")


class ProfileApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="operator",
            password="UserPass123",
            email="operator@example.com",
            first_name="Operator",
        )
        grant_profile_permissions(self.user, "edit", "avatar", "password", "2fa_enable", "2fa_disable")
        self.client.force_login(self.user)

    def test_profile_returns_current_user_metadata(self):
        response = self.client.get("/api/profile/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["username"], "operator")
        self.assertEqual(payload["user"]["displayName"], "Operator")
        self.assertFalse(payload["profile"]["twoFactorEnabled"])

    def test_profile_requires_page_permission(self):
        viewer = get_user_model().objects.create_user(username="viewer", password="UserPass123")
        self.client.force_login(viewer)

        response = self.client.get("/api/profile/")

        self.assertEqual(response.status_code, 403)

    def test_profile_update_requires_edit_action(self):
        limited = get_user_model().objects.create_user(username="limited", password="UserPass123", first_name="Limited")
        grant_profile_permissions(limited)
        self.client.force_login(limited)

        response = self.client.put(
            "/api/profile/",
            data={"username": "limited-renamed", "first_name": "Renamed", "email": "renamed@example.com"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        limited.refresh_from_db()
        self.assertEqual(limited.username, "limited")

    def test_avatar_upload_requires_avatar_action(self):
        limited = get_user_model().objects.create_user(username="avatar-limited", password="UserPass123")
        grant_profile_permissions(limited)
        self.client.force_login(limited)
        avatar = SimpleUploadedFile("avatar.png", b"fake-image", content_type="image/png")

        response = self.client.post("/api/profile/avatar/", data={"avatar": avatar})

        self.assertEqual(response.status_code, 403)

    def test_password_change_requires_password_action(self):
        limited = get_user_model().objects.create_user(username="password-limited", password="UserPass123")
        grant_profile_permissions(limited)
        self.client.force_login(limited)

        response = self.client.post(
            "/api/profile/password/",
            data={"currentPassword": "UserPass123", "newPassword": "NewPass123", "confirmPassword": "NewPass123"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        limited.refresh_from_db()
        self.assertTrue(limited.check_password("UserPass123"))

    def test_two_factor_setup_requires_enable_action(self):
        limited = get_user_model().objects.create_user(username="two-factor-limited", password="UserPass123")
        grant_profile_permissions(limited)
        self.client.force_login(limited)

        response = self.client.post("/api/profile/2fa/setup/", data={}, content_type="application/json")

        self.assertEqual(response.status_code, 403)

    def test_profile_update_rejects_duplicate_username(self):
        get_user_model().objects.create_user(username="taken", password="UserPass123")

        response = self.client.put(
            "/api/profile/",
            data={"username": "taken", "first_name": "New Name", "email": "new@example.com"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("用户名已存在", response.json()["error"])

    def test_profile_update_changes_current_user(self):
        response = self.client.put(
            "/api/profile/",
            data={"username": "renamed", "first_name": "New Name", "email": "new@example.com"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "renamed")
        self.assertEqual(response.json()["user"]["displayName"], "New Name")

    def test_avatar_upload_rejects_large_file(self):
        avatar = SimpleUploadedFile("avatar.png", b"x" * (2 * 1024 * 1024 + 1), content_type="image/png")

        response = self.client.post("/api/profile/avatar/", data={"avatar": avatar})

        self.assertEqual(response.status_code, 400)
        self.assertIn("2MB", response.json()["error"])

    def test_avatar_upload_accepts_supported_image_type(self):
        avatar = SimpleUploadedFile("avatar.png", b"fake-image", content_type="image/png")

        response = self.client.post("/api/profile/avatar/", data={"avatar": avatar})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["user"]["avatarUrl"])

    def test_password_change_requires_current_password(self):
        response = self.client.post(
            "/api/profile/password/",
            data={"currentPassword": "wrong", "newPassword": "NewPass123", "confirmPassword": "NewPass123"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("当前密码", response.json()["error"])

    def test_password_change_updates_password_and_keeps_session(self):
        response = self.client.post(
            "/api/profile/password/",
            data={"currentPassword": "UserPass123", "newPassword": "NewPass123", "confirmPassword": "NewPass123"},
            content_type="application/json",
        )
        me_response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass123"))
        self.assertEqual(me_response.status_code, 200)

    def test_builtin_admin_can_change_own_password_from_profile(self):
        admin = ensure_builtin_admin()
        self.client.force_login(admin)

        response = self.client.post(
            "/api/profile/password/",
            data={"currentPassword": "Admin@123456", "newPassword": "ChangedPass123", "confirmPassword": "ChangedPass123"},
            content_type="application/json",
        )
        ensure_builtin_admin()

        self.assertEqual(response.status_code, 200)
        admin.refresh_from_db()
        self.assertTrue(admin.check_password("ChangedPass123"))
        self.assertFalse(admin.check_password("Admin@123456"))


class TwoFactorLoginTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operator", password="UserPass123")
        grant_profile_permissions(self.user, "2fa_enable", "2fa_disable")

    def complete_slider(self) -> str:
        challenge_response = self.client.get("/api/auth/slider-challenge/")
        self.assertEqual(challenge_response.status_code, 200)
        challenge = challenge_response.json()
        verify_response = self.client.post(
            "/api/auth/slider-verify/",
            data={"challengeId": challenge["challengeId"], "offsetX": challenge["targetX"], "elapsedMs": 400},
            content_type="application/json",
        )
        self.assertEqual(verify_response.status_code, 200)
        return verify_response.json()["sliderToken"]

    def enable_two_factor(self):
        profile = UserProfile.objects.create(user=self.user, totp_secret=pyotp.random_base32(), totp_enabled=True)
        return profile

    def test_two_factor_setup_and_confirm_enable_login_protection(self):
        self.client.force_login(self.user)

        setup_response = self.client.post("/api/profile/2fa/setup/", data={}, content_type="application/json")
        self.assertEqual(setup_response.status_code, 200)
        secret = setup_response.json()["secret"]
        code = pyotp.TOTP(secret).now()
        confirm_response = self.client.post("/api/profile/2fa/confirm/", data={"code": code}, content_type="application/json")

        self.assertEqual(confirm_response.status_code, 200)
        self.assertTrue(confirm_response.json()["user"]["twoFactorEnabled"])

    def test_login_requires_two_factor_when_enabled(self):
        self.enable_two_factor()
        token = self.complete_slider()

        response = self.client.post(
            "/api/auth/login/",
            data={"account": "operator", "password": "UserPass123", "remember": True, "sliderToken": token},
            content_type="application/json",
        )
        me_response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["twoFactorRequired"])
        self.assertEqual(me_response.status_code, 401)

    def test_two_factor_login_completes_session(self):
        profile = self.enable_two_factor()
        token = self.complete_slider()
        login_response = self.client.post(
            "/api/auth/login/",
            data={"account": "operator", "password": "UserPass123", "remember": False, "sliderToken": token},
            content_type="application/json",
        )
        self.assertTrue(login_response.json()["twoFactorRequired"])

        verify_response = self.client.post(
            "/api/auth/login/2fa/",
            data={"code": pyotp.TOTP(profile.totp_secret).now()},
            content_type="application/json",
        )

        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(verify_response.json()["user"]["username"], "operator")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

    def test_required_two_factor_login_returns_setup_payload(self):
        UserProfile.objects.create(user=self.user, totp_required=True)
        token = self.complete_slider()

        response = self.client.post(
            "/api/auth/login/",
            data={"account": "operator", "password": "UserPass123", "remember": False, "sliderToken": token},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["twoFactorSetupRequired"])
        self.assertTrue(payload["secret"])
        self.assertTrue(payload["qrDataUrl"].startswith("data:image/png;base64,"))
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_two_factor_setup_login_completes_session(self):
        profile = UserProfile.objects.create(user=self.user, totp_required=True)
        token = self.complete_slider()
        login_response = self.client.post(
            "/api/auth/login/",
            data={"account": "operator", "password": "UserPass123", "remember": False, "sliderToken": token},
            content_type="application/json",
        )
        secret = login_response.json()["secret"]

        verify_response = self.client.post(
            "/api/auth/login/2fa/setup/",
            data={"code": pyotp.TOTP(secret).now()},
            content_type="application/json",
        )

        self.assertEqual(verify_response.status_code, 200)
        profile.refresh_from_db()
        self.assertTrue(profile.totp_enabled)
        self.assertFalse(profile.totp_required)
        self.assertEqual(profile.totp_secret, secret)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

    def test_legacy_reset_flag_is_treated_as_setup_required(self):
        old_secret = pyotp.random_base32()
        profile = UserProfile.objects.create(user=self.user, totp_secret=old_secret, totp_enabled=False, totp_reset_required=True)
        token = self.complete_slider()
        login_response = self.client.post(
            "/api/auth/login/",
            data={"account": "operator", "password": "UserPass123", "remember": False, "sliderToken": token},
            content_type="application/json",
        )

        self.assertTrue(login_response.json()["twoFactorSetupRequired"])
        self.assertNotEqual(login_response.json()["secret"], old_secret)
        profile.refresh_from_db()
        self.assertFalse(profile.totp_enabled)
        self.assertEqual(profile.two_factor_status, "required")

    def test_two_factor_disable_requires_password_and_code(self):
        profile = self.enable_two_factor()
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/profile/2fa/disable/",
            data={"password": "UserPass123", "code": pyotp.TOTP(profile.totp_secret).now()},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertFalse(profile.totp_enabled)
