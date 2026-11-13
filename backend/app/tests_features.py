"""Work certificate, ratings, disputes, USSD, staff admin review."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from app.models import GigDispute, GigHistory, GigRating, JobType, Organization, VerificationRequest

User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class FeatureBase(TestCase):
    def setUp(self):
        mk = lambda n, t, **kw: User.objects.create_user(username=n, email=f"{n}@example.com", password="pw-12345678",
                                                         account_type=t, is_active=True, is_verified=True, **kw)
        self.boss = mk("boss", "02")
        self.rival = mk("rival", "02")
        self.fundi = mk("fundi", "01", full_name="Wanjiku Mason", phone="+254711222333", national_id="12345678")
        self.staff = mk("admin", "02", is_staff=True, is_superuser=True)
        self.org = Organization.objects.create(name="Site A", owner=self.boss, county="Nairobi",
                                               constituency="Westlands", ward="Parklands")
        self.job = JobType.objects.create(organization=self.org, name="Masonry X")
        self.hist = GigHistory.objects.create(worker=self.fundi, job_type=self.job, start_date=date(2026, 10, 1),
                                              duration_value=2, duration_unit="weeks", client_name="Site A",
                                              client_phone="0700", county="Nairobi", constituency="Westlands",
                                              ward="Parklands", is_verified=True, organization=self.org)

    def api(self, user=None):
        c = APIClient()
        if user:
            c.force_authenticate(user)
        return c


class CertificateTests(FeatureBase):
    def test_fundi_gets_link_and_public_page_shows_only_verified_facts(self):
        GigRating.objects.create(history=self.hist, rated_by=self.boss, stars=4)
        body = self.api(self.fundi).get("/api/certificate/link/").json()
        path = body["url"].split("testserver", 1)[1]
        page = self.client.get(path)
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("Wanjiku Mason", html)
        self.assertIn("<svg", html)  # QR code
        for secret in ("+254711222333", "12345678", "0700"):
            self.assertNotIn(secret, html)
        data = self.client.get(body["json_url"].split("testserver", 1)[1]).json()
        self.assertEqual((data["verified_gigs"], data["days_worked"], data["average_rating"]), (1, 14, 4.0))

    def test_tampered_or_expired_link_is_404(self):
        path = self.api(self.fundi).get("/api/certificate/link/").json()["url"].split("testserver", 1)[1]
        self.assertEqual(self.client.get(path[:-3] + "xyz/").status_code, 404)
        with self.settings(CERTIFICATE_MAX_AGE_DAYS=-1):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_only_fundis_get_certificates(self):
        self.assertEqual(self.api(self.boss).get("/api/certificate/link/").status_code, 403)


class RatingTests(FeatureBase):
    def url(self):
        return f"/api/gig-history/{self.hist.id}/rate/"

    def test_only_site_contractor_rates_and_can_update(self):
        self.assertEqual(self.api(self.rival).post(self.url(), {"stars": 1}).status_code, 403)
        self.assertEqual(self.api(self.fundi).post(self.url(), {"stars": 5}).status_code, 403)
        self.assertEqual(self.api(self.boss).post(self.url(), {"stars": 4, "comment": "Neat"}).status_code, 201)
        self.assertEqual(self.api(self.boss).post(self.url(), {"stars": 5}).status_code, 200)
        self.assertEqual(GigRating.objects.get().stars, 5)

    def test_stars_validated(self):
        self.assertEqual(self.api(self.boss).post(self.url(), {"stars": 9}).status_code, 400)


class DisputeTests(FeatureBase):
    def test_worker_disputes_own_gig_staff_resolves(self):
        self.assertEqual(self.api(self.rival).post("/api/disputes/", {"history": self.hist.id, "reason": "x"})
                         .status_code, 403)
        r = self.api(self.fundi).post("/api/disputes/", {"history": self.hist.id, "reason": "Rating unfair"})
        self.assertEqual(r.status_code, 201)
        did = r.json()["id"]
        self.assertEqual(len(self.api(self.boss).get("/api/disputes/").json()), 1)  # site owner sees it
        self.assertEqual(len(self.api(self.rival).get("/api/disputes/").json()), 0)
        self.assertEqual(self.api(self.boss).post(f"/api/disputes/{did}/resolve/", {"status": "resolved"})
                         .status_code, 403)
        r = self.api(self.staff).post(f"/api/disputes/{did}/resolve/", {"status": "resolved", "resolution": "Fixed"})
        self.assertEqual(r.json()["status"], "resolved")
        self.assertEqual(GigDispute.objects.get().resolved_by, self.staff)


@override_settings(USSD_CALLBACK_TOKEN="ussd-secret")
class UssdTests(FeatureBase):
    def ussd(self, text, phone="+254711222333", token="ussd-secret"):
        return self.client.post(f"/ussd/?token={token}", {"sessionId": "s", "serviceCode": "*384#",
                                                          "phoneNumber": phone, "text": text})

    def test_menu_and_answers(self):
        self.assertTrue(self.ussd("").content.decode().startswith("CON"))
        self.assertIn("credit score 0/100", self.ussd("1").content.decode())
        self.assertIn("Masonry X", self.ussd("2").content.decode())
        self.assertIn("not submitted", self.ussd("3").content.decode())

    def test_local_phone_format_and_unknown_number(self):
        self.assertIn("credit score", self.ussd("1", phone="0711222333").content.decode())
        self.assertIn("not linked", self.ussd("1", phone="+254799999999").content.decode())

    def test_requires_token(self):
        self.assertEqual(self.ussd("1", token="wrong").status_code, 403)
        with self.settings(USSD_CALLBACK_TOKEN=""):
            self.assertEqual(self.ussd("1").status_code, 403)


class AdminReviewTests(FeatureBase):
    def test_staff_approve_action_in_admin(self):
        vr = VerificationRequest.objects.create(user=self.fundi, status="pending", id_front="MEDIA/x.jpg")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(f"/admin/app/verificationrequest/{vr.id}/change/").status_code, 200)
        r = self.client.post("/admin/app/verificationrequest/", {"action": "approve_selected",
                                                                 "_selected_action": [vr.id]})
        self.assertEqual(r.status_code, 302)
        self.fundi.refresh_from_db()
        self.assertEqual((self.fundi.current_verification_id, self.fundi.credit_score), (vr.id, 20))

    def test_admin_pages_load(self):
        self.client.force_login(self.staff)
        for m in ("user", "gig", "gighistory", "gigdispute", "creditscorehistory", "mpesanewtransaction",
                  "organization", "gigrating"):
            self.assertEqual(self.client.get(f"/admin/app/{m}/").status_code, 200, m)
