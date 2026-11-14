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

    def test_completed_gigs_listed_for_site_owner_only(self):
        GigRating.objects.create(history=self.hist, rated_by=self.boss, stars=4)
        rows = self.api(self.boss).get("/api/contractor/completed-gigs/").json()
        self.assertEqual((len(rows), rows[0]["rating"]["stars"], rows[0]["worker_name"]), (1, 4, "Wanjiku Mason"))
        self.assertEqual(self.api(self.rival).get("/api/contractor/completed-gigs/").json(), [])

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


class JobPostTests(FeatureBase):
    def test_contractor_posts_fundis_see_owner_deletes(self):
        r = self.api(self.boss).post("/api/gigs-available/", {"organization": self.org.id, "title": "2 masons needed",
                                                              "county": "Nairobi", "constituency": "Westlands", "ward": "Parklands"})
        self.assertEqual(r.status_code, 201)
        pid = r.json()["id"]
        rows = self.api(self.fundi).get("/api/gigs-available/").json()
        self.assertEqual(rows[0]["organization_name"], "Site A")
        self.assertEqual(len(self.api(self.rival).get("/api/gigs-available/", {"mine": 1}).json()), 0)
        self.assertEqual(self.api(self.rival).post("/api/gigs-available/", {"organization": self.org.id, "title": "x",
                         "county": "a", "constituency": "b", "ward": "c"}).status_code, 403)
        self.assertEqual(self.api(self.rival).delete(f"/api/gigs-available/{pid}/").status_code, 403)
        self.assertEqual(self.api(self.boss).delete(f"/api/gigs-available/{pid}/").status_code, 204)


class HiringTests(FeatureBase):
    def setUp(self):
        super().setUp()
        from app.models import GigsAvailable
        self.post = GigsAvailable.objects.create(organization=self.org, title="Masons", county="Nairobi", constituency="W", ward="P")

    def test_apply_review_decide(self):
        self.assertEqual(self.api(self.boss).post(f"/api/gigs-available/{self.post.id}/apply/").status_code, 403)
        r = self.api(self.fundi).post(f"/api/gigs-available/{self.post.id}/apply/", {"message": "I'm free Monday"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.api(self.fundi).post(f"/api/gigs-available/{self.post.id}/apply/").status_code, 200)  # idempotent
        posts = self.api(self.fundi).get("/api/gigs-available/").json()
        self.assertEqual(posts[0]["my_application"]["status"], "pending")
        self.assertEqual(self.api(self.boss).get("/api/gigs-available/", {"mine": 1}).json()[0]["applications_count"], 1)
        self.assertEqual(self.api(self.rival).get(f"/api/gigs-available/{self.post.id}/applications/").status_code, 404)
        apps = self.api(self.boss).get(f"/api/gigs-available/{self.post.id}/applications/").json()
        self.assertEqual(apps[0]["worker"]["name"], "Wanjiku Mason")
        self.assertEqual(self.api(self.rival).post(f"/api/applications/{apps[0]['id']}/decide/", {"status": "accepted"}).status_code, 404)
        self.assertEqual(self.api(self.boss).post(f"/api/applications/{apps[0]['id']}/decide/", {"status": "accepted"}).json()["status"], "accepted")
        self.assertEqual(self.api(self.fundi).get("/api/my-applications/").json()[0]["status"], "accepted")


class CheckInTests(FeatureBase):
    def test_check_in_rules_and_on_site_list(self):
        from app.models import Gig
        gig = Gig.objects.create(worker=self.fundi, logged_by=self.fundi, organization=self.org, job_type=self.job,
                                 duration_value=3, duration_unit="days", county="Nairobi", constituency="W", ward="P")
        url = f"/api/gigs/{gig.id}/check-in/"
        self.assertEqual(self.api(self.fundi).post(url).status_code, 400)  # not verified yet
        gig.is_verified = True; gig.save()
        self.assertEqual(self.api(self.rival).post(url).status_code, 404)
        self.assertEqual(self.api(self.fundi).post(url).status_code, 201)
        self.assertEqual(self.api(self.fundi).post(url).status_code, 200)  # once a day
        self.assertEqual(self.api(self.fundi).get("/api/my-check-ins/today/").json(), [gig.id])
        rows = self.api(self.boss).get("/api/contractor/on-site-today/").json()
        self.assertEqual((len(rows), rows[0]["worker_name"]), (1, "Wanjiku Mason"))
        self.assertEqual(self.api(self.rival).get("/api/contractor/on-site-today/").json(), [])
