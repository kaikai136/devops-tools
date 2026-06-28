from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import SecurityCommandRecord, SecurityCommandRule
from .services import match_security_command


class SecurityCommandRuleApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operator", password="pass")
        self.client.force_login(self.user)

    def test_command_rules_require_login(self):
        self.client.logout()

        response = self.client.get("/api/security/command-rules/")

        self.assertEqual(response.status_code, 401)

    def test_create_update_toggle_delete_command_rule(self):
        create_response = self.client.post(
            "/api/security/command-rules/",
            data={
                "name": " risk_command ",
                "matchType": "command",
                "content": " rm\nreboot ",
                "ignoreCase": True,
                "action": "block",
                "enabled": True,
                "remark": " dangerous ",
            },
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 201)
        payload = create_response.json()
        self.assertEqual(payload["name"], "risk_command")
        self.assertEqual(payload["content"], "rm\nreboot")
        self.assertEqual(payload["remark"], "dangerous")
        self.assertTrue(payload["enabled"])

        rule_id = payload["id"]
        update_response = self.client.put(
            f"/api/security/command-rules/{rule_id}/",
            data={"name": "warn rm", "matchType": "command", "content": "rm", "action": "warn", "enabled": True},
            content_type="application/json",
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["action"], "warn")

        toggle_response = self.client.post(f"/api/security/command-rules/{rule_id}/toggle/", data={}, content_type="application/json")

        self.assertEqual(toggle_response.status_code, 200)
        self.assertFalse(toggle_response.json()["enabled"])

        delete_response = self.client.delete(f"/api/security/command-rules/{rule_id}/")

        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(SecurityCommandRule.objects.filter(id=rule_id).exists())

    def test_rejects_missing_required_fields_and_missing_rule(self):
        response = self.client.post(
            "/api/security/command-rules/",
            data={"name": "", "content": " "},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

        missing_response = self.client.put(
            "/api/security/command-rules/999/",
            data={"name": "missing"},
            content_type="application/json",
        )

        self.assertEqual(missing_response.status_code, 404)

    def test_rejects_invalid_regex(self):
        response = self.client.post(
            "/api/security/command-rules/",
            data={"name": "bad regex", "matchType": "regex", "content": "rm(", "action": "block"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_command_records_list(self):
        rule = SecurityCommandRule.objects.create(name="rm", content="rm", action="block")
        SecurityCommandRecord.objects.create(
            user=self.user,
            rule=rule,
            rule_name=rule.name,
            command="rm -rf /tmp",
            action="block",
            blocked=True,
            message="blocked",
        )

        response = self.client.get("/api/security/command-records/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["command"], "rm -rf /tmp")
        self.assertEqual(response.json()[0]["ruleName"], "rm")


class SecurityCommandMatchingTests(TestCase):
    def test_command_match_hits_command_boundary_only(self):
        SecurityCommandRule.objects.create(name="rm", match_type="command", content="rm", action="block", enabled=True)

        self.assertIsNotNone(match_security_command("rm -rf /tmp"))
        self.assertIsNotNone(match_security_command(" rm "))
        self.assertIsNone(match_security_command("rmdir /tmp"))

    def test_regex_match_and_ignore_case(self):
        SecurityCommandRule.objects.create(
            name="shutdown",
            match_type="regex",
            content=r"shutdown\s+-h",
            ignore_case=True,
            action="warn",
            enabled=True,
        )

        match = match_security_command("SHUTDOWN -h now")

        self.assertIsNotNone(match)
        self.assertFalse(match.blocked)

    def test_disabled_rule_is_ignored(self):
        SecurityCommandRule.objects.create(name="reboot", content="reboot", enabled=False)

        self.assertIsNone(match_security_command("reboot"))
