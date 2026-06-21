from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from .models import LoginLog
from .services import BUILTIN_ADMIN_EMAIL, BUILTIN_ADMIN_FIRST_NAME, BUILTIN_ADMIN_USERNAME, ensure_builtin_admin, record_login_log


class LoginLogTests(TestCase):
    def test_record_login_log_saves_request_metadata(self):
        user = get_user_model().objects.create_user(username="admin", password="pass")
        request = RequestFactory().post("/api/auth/login/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "unit-test"

        record_login_log(request, "admin", LoginLog.STATUS_SUCCESS, "登录成功", user)

        log = LoginLog.objects.get()
        self.assertEqual(log.user, user)
        self.assertEqual(log.username, "admin")
        self.assertEqual(str(log.ip_address), "127.0.0.1")
        self.assertEqual(log.user_agent, "unit-test")
        self.assertEqual(log.status, LoginLog.STATUS_SUCCESS)


class BuiltinAdminTests(TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_user(username="operator", password="pass", is_staff=True)
        self.client.force_login(self.operator)

    def test_system_user_list_creates_builtin_admin(self):
        response = self.client.get("/api/system/users/")

        self.assertEqual(response.status_code, 200)
        admin = get_user_model().objects.get(username=BUILTIN_ADMIN_USERNAME)
        self.assertEqual(admin.email, BUILTIN_ADMIN_EMAIL)
        self.assertEqual(admin.first_name, BUILTIN_ADMIN_FIRST_NAME)
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(any(item["username"] == BUILTIN_ADMIN_USERNAME and item["isBuiltinAdmin"] for item in response.json()))

    def test_builtin_admin_cannot_be_deleted(self):
        admin = ensure_builtin_admin()

        response = self.client.delete(f"/api/system/users/{admin.id}/")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(get_user_model().objects.filter(id=admin.id).exists())

    def test_builtin_admin_core_fields_stay_fixed_when_updated(self):
        admin = ensure_builtin_admin()

        response = self.client.put(
            f"/api/system/users/{admin.id}/",
            data={
                "username": "renamed",
                "email": "renamed@example.com",
                "firstName": "Renamed",
                "isActive": False,
                "isStaff": False,
                "roleIds": [],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        admin.refresh_from_db()
        self.assertEqual(admin.username, BUILTIN_ADMIN_USERNAME)
        self.assertEqual(admin.email, BUILTIN_ADMIN_EMAIL)
        self.assertEqual(admin.first_name, BUILTIN_ADMIN_FIRST_NAME)
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
