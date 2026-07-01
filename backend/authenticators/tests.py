from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase

from system_management.services import FEATURE_PERMISSION_CODE_BY_KEY, PAGE_ACTION_PERMISSION_CODE_BY_KEY, ensure_feature_permissions

from .models import AuthenticatorEntry


def grant_auth_permissions(user, *actions):
    ensure_feature_permissions()
    role = Group.objects.create(name=f"auth-permissions-{user.id}-{Group.objects.count()}")
    permissions = [Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["auth"])]
    permissions.extend(Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("auth", action)]) for action in actions)
    role.permissions.add(*permissions)
    user.groups.add(role)


class AuthenticatorEntryIsolationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="operator", password="UserPass123")
        self.other_user = User.objects.create_user(username="viewer", password="UserPass123")
        grant_auth_permissions(self.user, "create", "edit", "delete", "clear")
        grant_auth_permissions(self.other_user, "create", "edit", "delete", "clear")

    def test_authenticator_entries_are_scoped_to_current_user(self):
        AuthenticatorEntry.objects.create(created_by=self.user, issuer="GitHub", account_name="operator", secret="JBSWY3DPEHPK3PXP")
        AuthenticatorEntry.objects.create(created_by=self.other_user, issuer="GitHub", account_name="viewer", secret="JBSWY3DPEHPK3PXQ")

        self.client.force_login(self.user)
        response = self.client.get("/api/authenticators/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["account_name"], "operator")

    def test_authenticator_delete_does_not_affect_other_users_entries(self):
        other_entry = AuthenticatorEntry.objects.create(created_by=self.other_user, issuer="GitHub", account_name="viewer", secret="JBSWY3DPEHPK3PXQ")

        self.client.force_login(self.user)
        response = self.client.delete(f"/api/authenticators/{other_entry.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(AuthenticatorEntry.objects.filter(id=other_entry.id, created_by=self.other_user).exists())

    def test_same_authenticator_entry_can_exist_for_different_users(self):
        payload = {
            "issuer": "GitHub",
            "account_name": "shared",
            "secret": "JBSWY3DPEHPK3PXP",
            "digits": 6,
            "period": 30,
            "algorithm": "SHA1",
        }

        self.client.force_login(self.user)
        first_response = self.client.post("/api/authenticators/", data=payload, content_type="application/json")
        self.client.force_login(self.other_user)
        second_response = self.client.post("/api/authenticators/", data=payload, content_type="application/json")

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        self.assertEqual(AuthenticatorEntry.objects.count(), 2)

