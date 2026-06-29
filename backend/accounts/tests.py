from django.contrib.auth import get_user_model
from django.test import TestCase

from .views import SLIDER_CHALLENGE_SESSION_KEY


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
