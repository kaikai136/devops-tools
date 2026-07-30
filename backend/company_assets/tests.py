from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase

from system_management.services import (
    FEATURE_PERMISSION_CODE_BY_KEY,
    PAGE_ACTION_PERMISSION_CODE_BY_KEY,
    ensure_feature_permissions,
)

from .models import CompanyDevice


def grant_company_device_permissions(user, *actions, access=True):
    ensure_feature_permissions()
    role = Group.objects.create(name=f"company-device-permissions-{user.id}-{Group.objects.count()}")
    permissions = []
    if access:
        permissions.append(Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["companyDevices"]))
    permissions.extend(
        Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("companyDevices", action)])
        for action in actions
    )
    role.permissions.add(*permissions)
    user.groups.add(role)


class CompanyDeviceApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.viewer = User.objects.create_user(username="viewer", password="pass", is_staff=False)

    def test_staff_can_create_list_update_and_delete_company_devices(self):
        self.client.force_login(self.staff)

        create_response = self.client.post(
            "/api/company-devices/",
            data={
                "name": "笔记本",
                "category": "固定资产",
                "code": "NB-001",
                "spec": "i7/32GB/1TB",
                "status": "using",
                "user": "张三",
                "brand": "ThinkPad",
                "purchaseTime": "2026-07-20",
                "remark": "研发使用",
            },
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["name"], "笔记本")
        self.assertEqual(created["purchaseTime"], "2026-07-20")
        self.assertEqual(created["createdBy"], "staff")
        self.assertTrue(CompanyDevice.objects.filter(code="NB-001", created_by=self.staff).exists())

        list_response = self.client.get("/api/company-devices/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()[0]["code"], "NB-001")

        update_response = self.client.put(
            f"/api/company-devices/{created['id']}/",
            data={
                "name": "笔记本 Pro",
                "category": "固定资产",
                "code": "NB-001",
                "spec": "i9/64GB/2TB",
                "status": "repair",
                "user": "李四",
                "brand": "ThinkPad",
                "purchaseTime": None,
                "remark": "返修中",
            },
            content_type="application/json",
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["name"], "笔记本 Pro")
        self.assertEqual(update_response.json()["purchaseTime"], None)
        self.assertEqual(update_response.json()["status"], "repair")

        delete_response = self.client.delete(f"/api/company-devices/{created['id']}/")

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json(), {"deleted": True})
        self.assertFalse(CompanyDevice.objects.filter(id=created["id"]).exists())

    def test_company_device_create_requires_name(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            "/api/company-devices/",
            data={"name": "", "category": "固定资产", "status": "using"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("资产名称", response.json()["error"])

    def test_company_device_category_and_status_choices_are_enforced(self):
        self.client.force_login(self.staff)

        scrapped_response = self.client.post(
            "/api/company-devices/",
            data={"name": "报废打印机", "category": "耗材", "status": "scrapped"},
            content_type="application/json",
        )
        invalid_category_response = self.client.post(
            "/api/company-devices/",
            data={"name": "其他资产", "category": "其他", "status": "using"},
            content_type="application/json",
        )
        invalid_status_response = self.client.post(
            "/api/company-devices/",
            data={"name": "未知状态资产", "category": "固定资产", "status": "lost"},
            content_type="application/json",
        )

        self.assertEqual(scrapped_response.status_code, 201)
        self.assertEqual(scrapped_response.json()["status"], "scrapped")
        self.assertEqual(scrapped_response.json()["category"], "耗材")
        self.assertEqual(invalid_category_response.status_code, 400)
        self.assertIn("资产类别", invalid_category_response.json()["error"])
        self.assertEqual(invalid_status_response.status_code, 400)
        self.assertIn("资产状态", invalid_status_response.json()["error"])

    def test_company_device_action_permissions_are_enforced(self):
        self.client.force_login(self.viewer)

        denied_list = self.client.get("/api/company-devices/")
        self.assertEqual(denied_list.status_code, 403)

        grant_company_device_permissions(self.viewer)

        allowed_list = self.client.get("/api/company-devices/")
        denied_create = self.client.post(
            "/api/company-devices/",
            data={"name": "台式机", "category": "固定资产", "status": "using"},
            content_type="application/json",
        )

        self.assertEqual(allowed_list.status_code, 200)
        self.assertEqual(denied_create.status_code, 403)

        grant_company_device_permissions(self.viewer, "create")
        create_response = self.client.post(
            "/api/company-devices/",
            data={"name": "台式机", "category": "固定资产", "status": "idle"},
            content_type="application/json",
        )
        device_id = create_response.json()["id"]

        denied_edit = self.client.put(
            f"/api/company-devices/{device_id}/",
            data={"name": "台式机 A", "category": "固定资产", "status": "using"},
            content_type="application/json",
        )
        denied_delete = self.client.delete(f"/api/company-devices/{device_id}/")

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(denied_edit.status_code, 403)
        self.assertEqual(denied_delete.status_code, 403)

        grant_company_device_permissions(self.viewer, "edit", "delete")

        allowed_edit = self.client.put(
            f"/api/company-devices/{device_id}/",
            data={"name": "台式机 A", "category": "固定资产", "status": "using"},
            content_type="application/json",
        )
        allowed_delete = self.client.delete(f"/api/company-devices/{device_id}/")

        self.assertEqual(allowed_edit.status_code, 200)
        self.assertEqual(allowed_delete.status_code, 200)
