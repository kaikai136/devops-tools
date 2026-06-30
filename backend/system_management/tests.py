from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, TestCase
from django.utils import timezone
from unittest.mock import Mock, patch

from host_management.models import HostCredential, HostGroup, ManagedHost
from .models import LoginLog, SystemSetting
from .dashboard import parse_cip_output
from .services import (
    BUILTIN_ADMIN_EMAIL,
    BUILTIN_ADMIN_FIRST_NAME,
    BUILTIN_ADMIN_USERNAME,
    FEATURE_PERMISSION_CODE_BY_KEY,
    PAGE_ACTION_PERMISSION_CODE_BY_KEY,
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
        self.assertIn(FEATURE_PERMISSION_CODE_BY_KEY["dashboard"], codenames)
        self.assertIn(FEATURE_PERMISSION_CODE_BY_KEY["hosts"], codenames)
        self.assertIn(PAGE_ACTION_PERMISSION_CODE_BY_KEY[("hosts", "create")], codenames)
        self.assertTrue(all(item["isFeature"] for item in payload))
        self.assertTrue(any(item["permissionType"] == "page" and item["featureKey"] == "hosts" for item in payload))
        self.assertTrue(any(item["permissionType"] == "action" and item["featureKey"] == "hosts" and item["actionKey"] == "create" for item in payload))

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

    def test_existing_page_permission_inherits_new_action_permissions(self):
        ensure_feature_permissions()
        page_permission = Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["hosts"])
        action_permission = Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("hosts", "create")])
        role = Group.objects.create(name="Host viewer")
        role.permissions.add(page_permission)
        action_permission.delete()

        ensure_feature_permissions()

        action_permission = Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("hosts", "create")])
        self.assertTrue(role.permissions.filter(id=action_permission.id).exists())


class DashboardSummaryApiTests(TestCase):
    def setUp(self):
        ensure_feature_permissions()
        ManagedHost.objects.all().delete()
        HostCredential.objects.all().delete()
        HostGroup.objects.all().delete()
        LoginLog.objects.all().delete()
        self.dashboard_permission = Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["dashboard"])
        self.user = get_user_model().objects.create_user(username="viewer", password="pass")
        self.operator = get_user_model().objects.create_user(username="operator", password="pass", is_staff=True)
        self.admin = get_user_model().objects.create_superuser(username="root", password="pass")

    def test_dashboard_requires_login(self):
        response = self.client.get("/api/dashboard/summary/")

        self.assertEqual(response.status_code, 401)

    def test_dashboard_requires_access_permission(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/dashboard/summary/")

        self.assertEqual(response.status_code, 403)

    @patch("system_management.dashboard.get_egress_network")
    def test_dashboard_returns_summary_for_permitted_user(self, mock_egress):
        mock_egress.return_value = {
            "ip": "203.0.113.8",
            "location": "中国 江苏 南京",
            "isp": "电信",
            "url": "http://www.cip.cc/203.0.113.8",
            "raw": "",
            "checkedAt": timezone.now().isoformat(),
            "status": "ok",
            "error": "",
        }
        role = Group.objects.create(name="dashboard-viewer")
        role.permissions.add(self.dashboard_permission)
        self.user.groups.add(role)
        group = HostGroup.objects.create(name="生产", sort_order=1)
        ManagedHost.objects.create(name="linux-01", group=group, private_ip="192.168.1.10", cpu=4, memory=8, os="ubuntu", verified=True)
        ManagedHost.objects.create(name="win-01", group=group, private_ip="192.168.1.11", cpu=8, memory=16, os="windows", verify_status="failed")
        HostCredential.objects.create(name="root-key", username="root")
        LoginLog.objects.create(user=self.user, username="viewer", ip_address="10.0.0.8", status=LoginLog.STATUS_SUCCESS)
        LoginLog.objects.create(username="viewer", ip_address="10.0.0.9", status=LoginLog.STATUS_FAILED)
        self.client.force_login(self.user)

        response = self.client.get("/api/dashboard/summary/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["users"]["total"], 4)
        self.assertEqual(payload["assets"]["total"], 2)
        self.assertEqual(payload["assets"]["verified"], 1)
        self.assertEqual(payload["assets"]["failed"], 1)
        self.assertEqual(payload["assets"]["cpuCores"], 12)
        self.assertEqual(payload["assets"]["memoryGb"], 24)
        self.assertEqual(payload["assets"]["credentials"], 1)
        self.assertEqual(payload["egressNetwork"]["ip"], "203.0.113.8")
        self.assertEqual(len(payload["loginTrend"]), 7)
        self.assertTrue(any(item["label"] == "生产" and item["value"] == 2 for item in payload["groupRanking"]))

    @patch("system_management.dashboard.get_egress_network")
    def test_superuser_can_access_dashboard_without_role_permission(self, mock_egress):
        mock_egress.return_value = {"ip": "", "location": "", "isp": "", "url": "", "raw": "", "checkedAt": "", "status": "error", "error": ""}
        self.client.force_login(self.admin)

        response = self.client.get("/api/dashboard/summary/")

        self.assertEqual(response.status_code, 200)

    @patch("system_management.dashboard.subprocess.run")
    @patch("system_management.dashboard.cache")
    def test_egress_network_parses_cip_output(self, mock_cache, mock_run):
        from .dashboard import get_egress_network

        mock_cache.get.return_value = None
        mock_run.return_value = Mock(
            returncode=0,
            stdout="IP\t: 222.94.156.34\n地址\t: 中国 江苏 南京\n运营商\t: 电信\n\nURL\t: http://www.cip.cc/222.94.156.34\n",
            stderr="",
        )

        payload = get_egress_network()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["ip"], "222.94.156.34")
        self.assertEqual(payload["location"], "中国 江苏 南京")
        self.assertEqual(payload["isp"], "电信")

    @patch("system_management.dashboard.subprocess.run")
    @patch("system_management.dashboard.cache")
    def test_egress_network_handles_curl_failure(self, mock_cache, mock_run):
        from .dashboard import get_egress_network

        mock_cache.get.return_value = None
        mock_run.return_value = Mock(returncode=28, stdout="", stderr="operation timed out")

        payload = get_egress_network()

        self.assertEqual(payload["status"], "error")
        self.assertIn("timed out", payload["error"])

    def test_parse_cip_output_tolerates_missing_fields(self):
        parsed = parse_cip_output("地址\t: 中国 江苏 南京\n")

        self.assertEqual(parsed["ip"], "")
        self.assertEqual(parsed["location"], "中国 江苏 南京")


class SystemSettingsApiTests(TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_user(username="operator", password="pass", is_staff=True)
        self.user = get_user_model().objects.create_user(username="viewer", password="pass", is_staff=False)
        self.client.force_login(self.operator)

    def test_staff_can_create_update_and_read_watermark_setting(self):
        response = self.client.post(
            "/api/system/settings/",
            data={
                "key": "watermark",
                "label": "水印设置",
                "description": "页面水印配置",
                "value": {"enabled": True, "text": "CAPTAIN", "pages": ["ip", "webTerminal", "ip"]},
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["value"], {"enabled": True, "text": "CAPTAIN", "pages": ["ip", "webTerminal"]})

        update_response = self.client.put(
            "/api/system/settings/watermark/",
            data={"value": {"enabled": False, "text": "", "pages": ["hosts"]}},
            content_type="application/json",
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertFalse(update_response.json()["value"]["enabled"])

    def test_logged_in_user_can_read_watermark_but_cannot_write(self):
        SystemSetting.objects.create(key="watermark", value={"enabled": True, "text": "CAPTAIN", "pages": ["ip"]})
        self.client.force_login(self.user)

        read_response = self.client.get("/api/system/settings/watermark/")
        write_response = self.client.put(
            "/api/system/settings/watermark/",
            data={"value": {"enabled": False, "text": "", "pages": []}},
            content_type="application/json",
        )

        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.json()["value"]["text"], "CAPTAIN")
        self.assertEqual(write_response.status_code, 403)

    def test_anonymous_user_cannot_read_watermark(self):
        SystemSetting.objects.create(key="watermark", value={"enabled": True, "text": "CAPTAIN", "pages": ["ip"]})
        self.client.logout()

        response = self.client.get("/api/system/settings/watermark/")

        self.assertEqual(response.status_code, 401)

    def test_watermark_validation_rejects_empty_text_when_enabled(self):
        response = self.client.post(
            "/api/system/settings/",
            data={"key": "watermark", "value": {"enabled": True, "text": "", "pages": ["ip"]}},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_watermark_validation_rejects_unknown_page(self):
        response = self.client.post(
            "/api/system/settings/",
            data={"key": "watermark", "value": {"enabled": False, "text": "", "pages": ["unknown"]}},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)


class SystemUserLoginFlowTests(TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_user(username="operator", password="pass", is_staff=True)
        self.client.force_login(self.operator)

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
        slider_token = self.complete_slider()
        login_response = self.client.post(
            "/api/auth/login/",
            data={"account": "new-user", "password": "UserPass123", "remember": False, "sliderToken": slider_token},
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
