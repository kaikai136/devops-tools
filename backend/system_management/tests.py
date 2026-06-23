from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, TestCase

from .models import LoginLog
from .services import (
    BUILTIN_ADMIN_EMAIL,
    BUILTIN_ADMIN_FIRST_NAME,
    BUILTIN_ADMIN_USERNAME,
    FEATURE_PERMISSION_CODE_BY_KEY,
    ensure_builtin_admin,
    ensure_feature_permissions,
    record_login_log,
)


class LoginLogTests(TestCase):
    def test_record_login_log_saves_request_metadata(self):
        user = ensure_builtin_admin()
        request = RequestFactory().post("/api/auth/login/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "unit-test"

        record_login_log(request, "admin", LoginLog.STATUS_SUCCESS, "登录成功", user)

        log = LoginLog.objects.get()
        self.assertEqual(log.user, user)
        self.assertEqual(log.username, BUILTIN_ADMIN_USERNAME)
        self.assertEqual(str(log.ip_address), "127.0.0.1")
        self.assertEqual(log.user_agent, "unit-test")
        self.assertEqual(log.status, LoginLog.STATUS_SUCCESS)


class LoginLogApiTests(TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_user(username="operator", password="pass", is_staff=True)
        self.client.force_login(self.operator)
        LoginLog.objects.create(
            user=self.operator,
            username="admin",
            ip_address="1.1.1.1",
            user_agent="PC / Windows 10 / Edge 149.0.0",
            status=LoginLog.STATUS_SUCCESS,
        )
        LoginLog.objects.create(
            username="admin",
            ip_address="1.1.1.1",
            user_agent="PC / Mac OS X 10.15.7 / Edge 149.0.0",
            status=LoginLog.STATUS_FAILED,
            message="用户名或密码错误，连续多次错误账户将会被禁用",
        )
        LoginLog.objects.create(
            username="guest",
            ip_address="2.2.2.2",
            user_agent="PC / Mac OS X 10.15.7 / Chrome 119.0.0",
            status=LoginLog.STATUS_SUCCESS,
        )

    def test_login_log_api_filters_and_paginates(self):
        response = self.client.get(
            "/api/system/login-logs/",
            {"username": "admin", "ip": "1.1", "status": LoginLog.STATUS_FAILED, "page": 1, "pageSize": 10},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["pageSize"], 10)
        self.assertEqual(data["results"][0]["username"], "admin")
        self.assertEqual(data["results"][0]["status"], LoginLog.STATUS_FAILED)
        self.assertEqual(data["results"][0]["ipAddress"], "1.1.1.1")

    def test_login_log_api_returns_requested_page(self):
        response = self.client.get("/api/system/login-logs/", {"page": 2, "pageSize": 2})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["results"]), 1)


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


class FeaturePermissionTests(TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_user(username="operator", password="pass", is_staff=True)
        self.client.force_login(self.operator)

    def test_permission_api_returns_feature_permissions(self):
        response = self.client.get("/api/system/permissions/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        codenames = {item["codename"] for item in payload}
        self.assertIn(FEATURE_PERMISSION_CODE_BY_KEY["hosts"], codenames)
        self.assertTrue(all(item["isFeature"] for item in payload))

    def test_role_can_store_feature_permissions(self):
        ensure_feature_permissions()
        permission = Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["hosts"])

        response = self.client.post(
            "/api/system/roles/",
            data={"name": "主机操作员", "permissionIds": [permission.id]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        role = Group.objects.get(name="主机操作员")
        self.assertTrue(role.permissions.filter(id=permission.id).exists())


class SystemUserLoginFlowTests(TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_user(username="operator", password="pass", is_staff=True)
        self.client.force_login(self.operator)

    def test_created_system_user_can_login_with_initial_password(self):
        response = self.client.post(
            "/api/system/users/",
            data={
                "username": "new-user",
                "firstName": "新用户",
                "email": "new-user@example.com",
                "password": "UserPass123",
                "isActive": True,
                "isStaff": False,
                "roleIds": [],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["canLogin"])

        user = get_user_model().objects.get(username="new-user")
        self.assertTrue(user.is_active)
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.check_password("UserPass123"))

        self.client.logout()
        login_response = self.client.post(
            "/api/auth/login/",
            data={"account": "new-user", "password": "UserPass123", "remember": False},
            content_type="application/json",
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["user"]["username"], "new-user")

    def test_create_system_user_rejects_weak_password(self):
        response = self.client.post(
            "/api/system/users/",
            data={
                "username": "weak-user",
                "password": "password",
                "isActive": True,
                "isStaff": False,
                "roleIds": [],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("大写字母", response.json()["error"])
