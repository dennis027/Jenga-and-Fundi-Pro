"""Private ID documents, identity vs email verification, phone tokens, background email."""
import json
import os
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from app.models import VerificationRequest

User = get_user_model()
FAST = ["django.contrib.auth.hashers.MD5PasswordHasher"]
LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def user(name, **kw):
    kw.setdefault("account_type", "01")
    return User.objects.create_user(username=name, email=f"{name}@example.com", password="pw-12345678",
                                    is_active=True, is_verified=True, **kw)


@override_settings(PASSWORD_HASHERS=FAST)
class PrivateMediaTests(TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        for rel in ("MEDIA/verifications/id_front/a.jpg", "MEDIA/profiles/p.jpg"):
            os.makedirs(os.path.dirname(os.path.join(self.root, rel)), exist_ok=True)
            with open(os.path.join(self.root, rel), "wb") as fh:
                fh.write(b"img")
        self.owner = user("owner")
        self.vr = VerificationRequest.objects.create(user=self.owner, status="pending",
                                                     id_front="MEDIA/verifications/id_front/a.jpg")

    def get(self, client, url):
        with self.settings(MEDIA_ROOT=self.root):
            return client.get(url)

    def test_id_documents_not_public_profile_photos_are(self):
        self.assertEqual(self.get(self.client, "/MEDIA/verifications/id_front/a.jpg").status_code, 404)
        self.assertEqual(self.get(self.client, "/MEDIA/profiles/p.jpg").status_code, 200)

    def test_staff_session_can_view(self):
        staff = user("staff", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.get(self.client, "/MEDIA/verifications/id_front/a.jpg").status_code, 200)

    def test_owner_gets_working_signed_link_from_api(self):
        api = APIClient()
        api.force_authenticate(self.owner)
        url = api.get("/api/verification/latest/").json()["id_front"]
        self.assertIn("sig=", url)
        path = url.split("testserver", 1)[-1]
        self.assertEqual(self.get(self.client, path).status_code, 200)
        self.assertEqual(self.get(self.client, path.replace("sig=", "sig=x")).status_code, 404)

    def test_signed_link_expires(self):
        from app.media import signed_media_url
        url = signed_media_url(self.vr.id_front)
        with self.settings(PRIVATE_MEDIA_URL_MAX_AGE=-1):
            self.assertEqual(self.get(self.client, url).status_code, 404)


@override_settings(PASSWORD_HASHERS=FAST)
class IdentityVerificationStatusTests(TestCase):
    def setUp(self):
        self.fundi = user("fundi")
        self.staff = user("staff", is_staff=True)
        self.vr = VerificationRequest.objects.create(user=self.fundi, status="pending", id_front="MEDIA/x.jpg")
        self.api = APIClient()
        self.api.force_authenticate(self.staff)

    def test_rejection_does_not_lock_user_out(self):
        self.api.post(f"/api/verification/{self.vr.id}/action/", {"action": "reject", "reason": "blurry"},
                      format="json")
        self.fundi.refresh_from_db()
        self.assertTrue(self.fundi.is_verified)  # email flag untouched -> can still log in
        r = APIClient().post("/api/login/", {"username": "fundi", "password": "pw-12345678"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_id_verified_follows_approval(self):
        me = APIClient()
        me.force_authenticate(self.fundi)
        self.assertFalse(me.get("/api/user/").json().get("id_verified", me.get("/api/user/").json()
                                                         .get("user", {}).get("id_verified")))
        self.api.post(f"/api/verification/{self.vr.id}/action/", {"action": "approve"}, format="json")
        me.force_authenticate(User.objects.get(pk=self.fundi.pk))  # real requests reload the user
        body = me.get("/api/user/").json()
        self.assertTrue(body.get("id_verified", body.get("user", {}).get("id_verified")))


@override_settings(PASSWORD_HASHERS=FAST, CACHES=LOCMEM, REQUIRE_PHONE_OTP=True)
class PhoneTokenTests(TestCase):
    AT_OK = {"SMSMessageData": {"Recipients": [{"status": "Success", "statusCode": 101, "messageId": "1"}]}}

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.me = user("fundi", phone="0711000009")
        self.api = APIClient()
        self.api.force_authenticate(self.me)

    def test_changing_phone_needs_token(self):
        r = self.api.put("/api/profile/", {"phone": "+254722000000"}, format="multipart")
        self.assertEqual(r.status_code, 400)
        with mock.patch("app.views.sms.send", return_value=self.AT_OK) as send:
            self.client.post("/send-otp/", json.dumps({"phone": "+254722000000"}), content_type="application/json")
            code = send.call_args.args[0].rsplit(" ", 1)[-1]
        token = self.client.post("/verify-otp/", json.dumps({"phone": "+254722000000", "otp": code}),
                                 content_type="application/json").json()["phone_token"]
        r = self.api.put("/api/profile/", {"phone": "+254722000000", "phone_token": token}, format="multipart")
        self.assertEqual(r.status_code, 200)
        # token is bound to that number
        r = self.api.put("/api/profile/", {"phone": "+254733000000", "phone_token": token}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_unchanged_phone_needs_no_token(self):
        self.assertEqual(self.api.put("/api/profile/", {"phone": "0711000009", "full_name": "X"},
                                      format="multipart").status_code, 200)


class AsyncMailTests(TestCase):
    @override_settings(EMAIL_ASYNC=False)
    def test_inline_when_disabled(self):
        from app.mail import send_mail_async
        send_mail_async("Hi", "body", "a@example.com", ["b@example.com"])
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(EMAIL_ASYNC=True)
    def test_background_send_does_not_raise(self):
        from app import mail as m
        with mock.patch.object(m, "send_mail", side_effect=OSError("smtp down")) as sm:
            m.send_mail_async("Hi", "body", "a@example.com", ["b@example.com"])
            m._executor.submit(lambda: None).result(timeout=5)  # drain queue
        sm.assert_called_once()
