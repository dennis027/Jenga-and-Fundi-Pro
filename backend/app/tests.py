import json
import os
import tempfile
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
AT_OK = {"SMSMessageData": {"Message": "Sent to 1/1", "Recipients": [
    {"status": "Success", "statusCode": 101, "messageId": "ATXid_1", "cost": "KES 0.8"}]}}
PHONE = "+254700000001"


def _sent_code(send_mock):
    return send_mock.call_args.args[0].rsplit(" ", 1)[-1]


@override_settings(CACHES=LOCMEM, OTP_RETURN_CODE_IN_RESPONSE=False)
class OTPTests(TestCase):
    def setUp(self):
        cache.clear()

    def post(self, url, data, **extra):
        return self.client.post(url, json.dumps(data), content_type="application/json", **extra)

    @mock.patch("app.views.sms.send", return_value=AT_OK)
    def test_code_is_not_returned_and_verifies_once(self, send):
        r = self.post("/send-otp/", {"phone": PHONE})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "success")
        self.assertNotIn("otp", body)
        self.assertNotIn("debug_info", body)
        self.assertNotIn("at_response", body)
        code = _sent_code(send)
        self.assertRegex(code, r"^\d{6}$")

        self.assertEqual(self.post("/verify-otp/", {"phone": PHONE, "otp": code}).json()["verified"], True)
        # single use
        self.assertEqual(self.post("/verify-otp/", {"phone": PHONE, "otp": code}).status_code, 400)

    @mock.patch("app.views.sms.send", return_value=AT_OK)
    def test_wrong_code_then_lockout(self, send):
        self.post("/send-otp/", {"phone": PHONE})
        code = _sent_code(send)
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.post("/verify-otp/", {"phone": PHONE, "otp": wrong}).status_code, 400)
        self.assertEqual(self.post("/verify-otp/", {"phone": PHONE, "otp": code}).status_code, 429)

    @mock.patch("app.views.sms.send", return_value=AT_OK)
    def test_resend_cooldown(self, send):
        self.assertEqual(self.post("/send-otp/", {"phone": PHONE}).status_code, 200)
        r = self.post("/send-otp/", {"phone": PHONE})
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r)
        self.assertEqual(send.call_count, 1)

    @mock.patch("app.views.sms.send", side_effect=RuntimeError("gateway down"))
    def test_send_failure_does_not_leak_code(self, send):
        r = self.post("/send-otp/", {"phone": PHONE})
        self.assertEqual(r.status_code, 502)
        self.assertNotIn(_sent_code(send), r.content.decode())
        # failed send lifts the cooldown so the user can retry
        send.side_effect, send.return_value = None, AT_OK
        self.assertEqual(self.post("/send-otp/", {"phone": PHONE}).status_code, 200)

    @override_settings(OTP_RETURN_CODE_IN_RESPONSE=True)
    @mock.patch("app.views.sms.send", return_value=AT_OK)
    def test_legacy_flag_returns_code(self, send):
        self.assertEqual(self.post("/send-otp/", {"phone": PHONE}).json()["otp"], _sent_code(send))

    def test_phone_required(self):
        self.assertEqual(self.post("/send-otp/", {}).status_code, 400)


@override_settings(CACHES=LOCMEM)
class MpesaTokenCacheTests(TestCase):
    def setUp(self):
        cache.clear()

    @mock.patch("app.views.requests.get")
    def test_token_fetched_once_then_cached(self, get):
        from app.views import get_access_token
        get.return_value.json.return_value = {"access_token": "tok", "expires_in": "3599"}
        self.assertEqual(get_access_token(), "tok")
        self.assertEqual(get_access_token(), "tok")
        self.assertEqual(get.call_count, 1)


class HealthAndMediaTests(TestCase):
    def test_healthz(self):
        r = self.client.get("/healthz/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["checks"]["database"], "ok")

    def test_source_files_are_not_served(self):
        for path in ("/project/settings.py", "/manage.py", "/.env", "/requirements.txt"):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_uploaded_media_is_served(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "MEDIA", "profiles"))
            with open(os.path.join(root, "MEDIA", "profiles", "a.txt"), "w") as fh:
                fh.write("img")
            with self.settings(MEDIA_ROOT=root):
                r = self.client.get("/MEDIA/profiles/a.txt")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(b"".join(r.streaming_content), b"img")


class ClientIPTests(TestCase):
    def ip(self, **meta):
        from django.test import RequestFactory
        from app.views import _client_ip
        return _client_ip(RequestFactory().post("/", **meta))

    def test_remote_addr_by_default(self):
        self.assertEqual(self.ip(REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="1.1.1.1"), "10.0.0.9")

    @override_settings(USE_X_FORWARDED_FOR=True, XFF_CLIENT_POSITION="last")
    def test_xff_last_for_own_proxy(self):
        self.assertEqual(self.ip(HTTP_X_FORWARDED_FOR="6.6.6.6, 2.2.2.2"), "2.2.2.2")

    @override_settings(USE_X_FORWARDED_FOR=True, XFF_CLIENT_POSITION="first")
    def test_xff_first_for_render(self):
        self.assertEqual(self.ip(HTTP_X_FORWARDED_FOR="3.3.3.3, 10.1.1.1"), "3.3.3.3")

    @override_settings(CLIENT_IP_HEADER="HTTP_TRUE_CLIENT_IP", USE_X_FORWARDED_FOR=True)
    def test_edge_header_wins(self):
        self.assertEqual(self.ip(HTTP_TRUE_CLIENT_IP="4.4.4.4", HTTP_X_FORWARDED_FOR="5.5.5.5"), "4.4.4.4")
