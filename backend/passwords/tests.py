from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase

from system_management.services import FEATURE_PERMISSION_CODE_BY_KEY, PAGE_ACTION_PERMISSION_CODE_BY_KEY, ensure_feature_permissions

from .models import PasswordRecord


def grant_password_permissions(user, *actions):
    ensure_feature_permissions()
    role = Group.objects.create(name=f"password-permissions-{user.id}-{Group.objects.count()}")
    permissions = [Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["password"])]
    permissions.extend(Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("password", action)]) for action in actions)
    role.permissions.add(*permissions)
    user.groups.add(role)


class PasswordRecordIsolationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="operator", password="UserPass123")
        self.other_user = User.objects.create_user(username="viewer", password="UserPass123")
        grant_password_permissions(self.user, "generate", "delete", "clear", "import")
        grant_password_permissions(self.other_user, "generate", "delete", "clear", "import")

    def test_password_history_is_scoped_to_current_user(self):
        PasswordRecord.objects.create(created_by=self.user, project_name="operator", password="UserPass123!")
        PasswordRecord.objects.create(created_by=self.other_user, project_name="viewer", password="ViewerPass123!")

        self.client.force_login(self.user)
        response = self.client.get("/api/passwords/history/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["project_name"], "operator")

    def test_password_generate_creates_record_for_current_user(self):
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/passwords/generate/",
            data={"project_name": "operator", "length": 16, "include_uppercase": True, "include_lowercase": True, "include_numbers": True},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        record = PasswordRecord.objects.get(id=response.json()["id"])
        self.assertEqual(record.created_by, self.user)

    def test_password_delete_does_not_affect_other_users_records(self):
        other_record = PasswordRecord.objects.create(created_by=self.other_user, project_name="viewer", password="ViewerPass123!")

        self.client.force_login(self.user)
        response = self.client.delete(f"/api/passwords/history/{other_record.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(PasswordRecord.objects.filter(id=other_record.id, created_by=self.other_user).exists())

    def test_password_clear_deletes_only_current_users_records(self):
        PasswordRecord.objects.create(created_by=self.user, project_name="operator", password="UserPass123!")
        PasswordRecord.objects.create(created_by=self.other_user, project_name="viewer", password="ViewerPass123!")

        self.client.force_login(self.user)
        response = self.client.delete("/api/passwords/history/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PasswordRecord.objects.filter(created_by=self.user).exists())
        self.assertTrue(PasswordRecord.objects.filter(created_by=self.other_user).exists())

