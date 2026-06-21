from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from .models import LoginLog
from .services import record_login_log


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
