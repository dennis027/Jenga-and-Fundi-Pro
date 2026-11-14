"""Inbox, work profile, alerts, saved posts, invitations, crew, two-way ratings, incidents,
reject / bulk verify, attendance, payroll, budgets, activity, statement, data export, account deletion."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from app.models import (ActivityLog, CrewMember, Gig, GigHistory, GigsAvailable, JobAlert, JobApplication, JobType,
                        Notification, Organization, SafetyIncident, SiteCheckIn, SiteRating)

User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"], SMS_NOTIFICATIONS=False)
class Base(TestCase):
    def setUp(self):
        mk = lambda n, t, **kw: User.objects.create_user(username=n, email=f"{n}@example.com", password="pw-12345678",
                                                         account_type=t, is_active=True, **kw)
        self.boss = mk("boss", "02", full_name="Boss Man")
        self.rival = mk("rival", "02")
        self.fundi = mk("fundi", "01", full_name="Wanjiku Mason", phone="+254711222333", county="Nairobi",
                        skills="Masonry, Tiling")
        self.other = mk("other", "01", county="Kiambu", skills="Welding")
        self.org = Organization.objects.create(name="Site A", owner=self.boss, county="Nairobi", constituency="W", ward="P")
        self.rival_org = Organization.objects.create(name="Site R", owner=self.rival, county="Nairobi", constituency="W", ward="P")
        self.job, _ = JobType.objects.get_or_create(organization=self.org, name="Masonry")
        self.today = timezone.localdate()

    def api(self, user=None):
        c = APIClient()
        if user:
            c.force_authenticate(user)
        return c

    def gig(self, worker=None, verified=False, days_ago=1, pay=1000, org=None):
        org = org or self.org
        job = self.job if org == self.org else JobType.objects.get_or_create(organization=org, name="Other")[0]
        w = worker or self.fundi
        return Gig.objects.create(worker=w, logged_by=w, organization=org, job_type=job,
                                  start_date=self.today - timedelta(days=days_ago), duration_value=2, duration_unit="days",
                                  county="Nairobi", constituency="W", ward="P", amount_paid=Decimal(pay), is_verified=verified)

    def history(self, worker=None, pay=5000):
        return GigHistory.objects.create(worker=worker or self.fundi, job_type=self.job, start_date=self.today - timedelta(days=10),
                                         duration_value=1, duration_unit="weeks", client_name="Site A", client_phone="0700",
                                         county="Nairobi", constituency="W", ward="P", is_verified=True,
                                         organization=self.org, amount_paid=Decimal(pay))

    def post(self, **kw):
        return GigsAvailable.objects.create(organization=self.org, title=kw.pop("title", "Mason needed"),
                                            county="Nairobi", constituency="W", ward="P", **kw)


class InboxTests(Base):
    def test_verify_creates_notification_and_activity_and_read_marks(self):
        g = self.gig()
        self.assertEqual(self.api(self.boss).post(f"/api/gigs/verify/{g.id}/").status_code, 200)
        body = self.api(self.fundi).get("/api/notifications/").json()
        self.assertEqual(body["unread"], 1)
        self.assertIn("verified your Masonry", body["items"][0]["title"])
        self.assertTrue(ActivityLog.objects.filter(organization=self.org, action="gig_verified").exists())
        self.api(self.fundi).post("/api/notifications/read/", {}, format="json")
        self.assertEqual(self.api(self.fundi).get("/api/notifications/").json()["unread"], 0)

    def test_cannot_read_or_mark_others_notifications(self):
        n = Notification.objects.create(user=self.fundi, kind="x", title="secret")
        self.assertEqual(self.api(self.other).get("/api/notifications/").json()["items"], [])
        self.api(self.other).post("/api/notifications/read/", {"ids": [n.id]}, format="json")
        n.refresh_from_db()
        self.assertFalse(n.is_read)


class WorkProfileTests(Base):
    def test_update_and_find_by_skill(self):
        r = self.api(self.fundi).patch("/api/me/work-profile/", {"skills": "Masonry,  Plastering, Masonry",
                                                                  "day_rate": 1500, "years_experience": 8}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["skills"], "Masonry, Plastering")
        found = self.api(self.boss).get("/api/workers/available/?trade=plaster&county=Nairobi").json()
        self.assertEqual([w["username"] for w in found], ["fundi"])
        self.assertEqual(found[0]["day_rate"], 1500)
        self.assertEqual(self.api(self.fundi).get("/api/workers/available/").status_code, 403)

    def test_busy_workers_hidden_when_filtering_available(self):
        self.api(self.fundi).patch("/api/me/work-profile/", {"is_available": False,
                                                              "available_from": str(self.today + timedelta(days=5))}, format="json")
        found = self.api(self.boss).get("/api/workers/available/?available=1&trade=masonry").json()
        self.assertEqual(found, [])


class AlertsAndSavedTests(Base):
    def test_matching_alert_notifies_on_new_post(self):
        JobAlert.objects.create(user=self.fundi, keyword="mason", county="Nairobi")
        JobAlert.objects.create(user=self.other, keyword="mason", county="Kiambu")
        r = self.api(self.boss).post("/api/gigs-available/", {"organization": self.org.id, "title": "2 masons needed",
                                                               "county": "Nairobi", "constituency": "W", "ward": "P"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(Notification.objects.filter(user=self.fundi, kind="job_alert").exists())
        self.assertFalse(Notification.objects.filter(user=self.other, kind="job_alert").exists())

    def test_alert_needs_keyword_or_county_and_contractor_cannot(self):
        self.assertEqual(self.api(self.fundi).post("/api/job-alerts/", {}, format="json").status_code, 400)
        self.assertEqual(self.api(self.boss).post("/api/job-alerts/", {"keyword": "x"}, format="json").status_code, 403)
        a = self.api(self.fundi).post("/api/job-alerts/", {"keyword": "tiles"}, format="json").json()
        self.assertEqual(self.api(self.other).delete(f"/api/job-alerts/{a['id']}/").status_code, 404)
        self.assertEqual(self.api(self.fundi).delete(f"/api/job-alerts/{a['id']}/").status_code, 204)

    def test_save_toggle(self):
        p = self.post()
        self.assertTrue(self.api(self.fundi).post(f"/api/gigs-available/{p.id}/save/").json()["saved"])
        self.assertEqual([x["id"] for x in self.api(self.fundi).get("/api/saved-posts/").json()], [p.id])
        self.assertTrue(self.api(self.fundi).get("/api/gigs-available/").json()[0]["saved"])
        self.assertFalse(self.api(self.fundi).post(f"/api/gigs-available/{p.id}/save/").json()["saved"])


class HiringTests(Base):
    def test_withdraw_only_pending_and_reapply(self):
        p = self.post()
        app_id = self.api(self.fundi).post(f"/api/gigs-available/{p.id}/apply/", {}, format="json").json()["id"]
        self.assertTrue(Notification.objects.filter(user=self.boss, kind="new_applicant").exists())
        self.assertEqual(self.api(self.other).post(f"/api/applications/{app_id}/withdraw/").status_code, 404)
        self.assertEqual(self.api(self.fundi).post(f"/api/applications/{app_id}/withdraw/").json()["status"], "withdrawn")
        self.assertEqual(self.api(self.fundi).post(f"/api/gigs-available/{p.id}/apply/", {}, format="json").json()["status"], "pending")

    def test_invite_accept_fills_and_closes_post(self):
        p = self.post(positions=1)
        self.assertEqual(self.api(self.rival).post(f"/api/gigs-available/{p.id}/invite/", {"username": "fundi"}).status_code, 404)
        app = self.api(self.boss).post(f"/api/gigs-available/{p.id}/invite/", {"username": "fundi"}).json()
        self.assertEqual(app["status"], "invited")
        self.assertTrue(Notification.objects.filter(user=self.fundi, kind="invitation").exists())
        self.assertEqual(self.api(self.other).post(f"/api/applications/{app['id']}/respond/", {"accept": True}, format="json").status_code, 404)
        r = self.api(self.fundi).post(f"/api/applications/{app['id']}/respond/", {"accept": True}, format="json")
        self.assertEqual(r.json()["status"], "accepted")
        p.refresh_from_db()
        self.assertFalse(p.is_open)
        self.assertEqual(self.api(self.other).get("/api/gigs-available/").json(), [])
        self.assertEqual(self.api(self.other).post(f"/api/gigs-available/{p.id}/apply/", {}, format="json").status_code, 404)

    def test_accepting_applicants_closes_when_positions_filled(self):
        p = self.post(positions=2)
        a1 = JobApplication.objects.create(post=p, worker=self.fundi)
        a2 = JobApplication.objects.create(post=p, worker=self.other)
        self.api(self.boss).post(f"/api/applications/{a1.id}/decide/", {"status": "accepted"}, format="json")
        p.refresh_from_db(); self.assertTrue(p.is_open)
        self.api(self.boss).post(f"/api/applications/{a2.id}/decide/", {"status": "accepted"}, format="json")
        p.refresh_from_db(); self.assertFalse(p.is_open)

    def test_toggle_and_positions(self):
        p = self.post()
        self.assertEqual(self.api(self.rival).post(f"/api/gigs-available/{p.id}/toggle/", {}).status_code, 404)
        r = self.api(self.boss).post(f"/api/gigs-available/{p.id}/toggle/", {"positions": 3}, format="json").json()
        self.assertEqual((r["positions"], r["is_open"]), (3, False))
        self.assertEqual(self.api(self.boss).post(f"/api/gigs-available/{p.id}/toggle/", {"positions": 99}, format="json").status_code, 400)


class RejectAndBulkTests(Base):
    def test_reject_needs_reason_owner_and_unverified(self):
        g = self.gig()
        self.assertEqual(self.api(self.boss).post(f"/api/gigs/{g.id}/reject/", {"reason": ""}).status_code, 400)
        self.assertEqual(self.api(self.rival).post(f"/api/gigs/{g.id}/reject/", {"reason": "never here"}).status_code, 404)
        self.assertEqual(self.api(self.boss).post(f"/api/gigs/{g.id}/reject/", {"reason": "Never worked here"}).status_code, 200)
        self.assertFalse(Gig.objects.filter(pk=g.id).exists())
        n = Notification.objects.get(user=self.fundi, kind="gig_rejected")
        self.assertIn("Never worked here", n.body)
        v = self.gig(verified=True)
        self.assertEqual(self.api(self.boss).post(f"/api/gigs/{v.id}/reject/", {"reason": "changed mind"}).status_code, 400)

    def test_bulk_verify_only_own_sites(self):
        mine, mine2, theirs = self.gig(), self.gig(worker=self.other), self.gig(org=self.rival_org)
        r = self.api(self.boss).post("/api/gigs/verify-bulk/", {"ids": [mine.id, mine2.id, theirs.id]}, format="json").json()
        self.assertEqual(r["verified"], 2)
        theirs.refresh_from_db(); self.assertFalse(theirs.is_verified)
        self.fundi.refresh_from_db(); self.assertEqual(self.fundi.credit_score, 5)


class CrewTests(Base):
    def test_add_list_remove(self):
        self.assertEqual(self.api(self.boss).post("/api/crew/", {"username": "fundi", "note": "good"}).status_code, 201)
        self.assertEqual(self.api(self.boss).post("/api/crew/", {"username": "rival"}).status_code, 404)
        self.assertEqual([c["username"] for c in self.api(self.boss).get("/api/crew/").json()], ["fundi"])
        self.assertTrue(self.api(self.boss).get("/api/workers/search/?q=fundi").json()["in_crew"])
        self.assertEqual(self.api(self.boss).delete("/api/crew/fundi/").status_code, 204)
        self.assertEqual(self.api(self.fundi).get("/api/crew/").status_code, 403)


class SiteRatingTests(Base):
    def test_worker_rates_site_once(self):
        h = self.history()
        self.assertEqual(self.api(self.other).post(f"/api/gig-history/{h.id}/rate-site/", {"stars": 5}).status_code, 404)
        r = self.api(self.fundi).post(f"/api/gig-history/{h.id}/rate-site/", {"stars": 4, "paid_on_time": True}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.api(self.fundi).post(f"/api/gig-history/{h.id}/rate-site/", {"stars": 1}).status_code, 400)
        mine = self.api(self.boss).get("/api/contractor/site-ratings/").json()
        self.assertEqual((mine[0]["avg"], mine[0]["paid_on_time_pct"]), (4.0, 100))
        self.post()
        self.assertEqual(self.api(self.other).get("/api/gigs-available/").json()[0]["site_rating"]["avg"], 4.0)
        self.assertEqual(self.api(self.fundi).get("/api/fundi/completed/").json()[0]["my_site_rating"]["stars"], 4)


class IncidentTests(Base):
    def test_only_workers_at_site_can_report_and_owner_resolves(self):
        payload = {"organization": self.org.id, "kind": "near_miss", "severity": "high",
                   "description": "Scaffold plank slipped on floor 3"}
        self.assertEqual(self.api(self.other).post("/api/incidents/", payload).status_code, 403)
        self.gig()
        r = self.api(self.fundi).post("/api/incidents/", payload)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(Notification.objects.filter(user=self.boss, kind="incident").exists())
        self.assertEqual(len(self.api(self.boss).get("/api/incidents/").json()), 1)
        self.assertEqual(self.api(self.rival).get("/api/incidents/").json(), [])
        iid = r.json()["id"]
        self.assertEqual(self.api(self.fundi).post(f"/api/incidents/{iid}/resolve/", {}).status_code, 404)
        self.assertTrue(self.api(self.boss).post(f"/api/incidents/{iid}/resolve/", {"resolution": "Clamped"}).json()["is_resolved"])

    def test_validation(self):
        self.gig()
        bad = {"organization": self.org.id, "kind": "fire", "severity": "low", "description": "long enough text"}
        self.assertEqual(self.api(self.fundi).post("/api/incidents/", bad).status_code, 400)
        future = {"organization": self.org.id, "kind": "hazard", "description": "long enough text",
                  "occurred_on": str(self.today + timedelta(days=2))}
        self.assertEqual(self.api(self.fundi).post("/api/incidents/", future).status_code, 400)


class ReportsTests(Base):
    def test_attendance_payroll_and_csv(self):
        g = self.gig(verified=True, pay=2400)
        SiteCheckIn.objects.create(gig=g, worker=self.fundi, date=self.today)
        self.history(pay=5000)
        SiteCheckIn.objects.create(gig=self.gig(org=self.rival_org, verified=True), worker=self.other, date=self.today)
        att = self.api(self.boss).get("/api/contractor/attendance/").json()
        self.assertEqual((att["worker_days"], att["rows"][0]["username"]), (1, "fundi"))
        csv = self.api(self.boss).get("/api/contractor/attendance/?csv=1")
        self.assertEqual(csv["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Wanjiku Mason", csv.content.decode())
        pay = self.api(self.boss).get(f"/api/contractor/payroll/?from={self.today - timedelta(days=30)}").json()
        self.assertEqual(Decimal(pay["total"]), Decimal("7400"))
        self.assertEqual(pay["rows"][0]["days_on_site"], 1)
        self.assertEqual(self.api(self.boss).get("/api/contractor/payroll/?from=2026-13-01").status_code, 400)
        self.assertEqual(self.api(self.fundi).get("/api/contractor/payroll/").status_code, 403)

    def test_budgets(self):
        self.gig(pay=3000); self.history(pay=2000)
        self.assertEqual(self.api(self.boss).post("/api/contractor/budgets/", {"organization": self.rival_org.id,
                                                                               "labour_budget": 1}).status_code, 404)
        self.api(self.boss).post("/api/contractor/budgets/", {"organization": self.org.id, "labour_budget": "10000"})
        b = self.api(self.boss).get("/api/contractor/budgets/").json()[0]
        self.assertEqual((Decimal(b["spent"]), b["pct"], Decimal(b["remaining"])), (Decimal("5000"), 50, Decimal("5000")))

    def test_activity_only_mine(self):
        ActivityLog.objects.create(actor=self.rival, organization=self.rival_org, action="x", summary="theirs")
        ActivityLog.objects.create(actor=self.boss, organization=self.org, action="x", summary="mine")
        self.assertEqual([a["summary"] for a in self.api(self.boss).get("/api/activity/").json()], ["mine"])

    def test_completing_copies_pay_and_statement(self):
        g = self.gig(verified=True, pay=4200)
        self.api(self.fundi).post(f"/api/gigs/{g.id}/complete/")
        self.assertEqual(GigHistory.objects.get(worker=self.fundi).amount_paid, Decimal("4200"))
        self.gig(pay=999)  # pending: listed but not counted
        st = self.api(self.fundi).get("/api/fundi/statement/").json()
        self.assertEqual((st["summary"]["verified_gigs"], Decimal(str(st["summary"]["verified_pay"]))), (1, Decimal("4200")))
        csv = self.api(self.fundi).get("/api/fundi/statement/?csv=1").content.decode()
        self.assertIn("Verified agreed pay (KSh),4200.00", csv)


class YourDataTests(Base):
    def test_export_contains_own_data_only(self):
        self.gig(pay=1234)
        r = self.api(self.fundi).get("/api/account/export/")
        self.assertIn("attachment", r["Content-Disposition"])
        data = r.json()
        self.assertEqual(data["account"]["phone"], "+254711222333")
        self.assertEqual(len(data["gigs"]), 1)

    def test_delete_account_erases_personal_data_keeps_work(self):
        self.history()
        CrewMember.objects.create(contractor=self.boss, worker=self.fundi)
        self.assertEqual(self.api(self.fundi).post("/api/account/delete/", {"password": "wrong"}).status_code, 403)
        self.assertEqual(self.api(self.fundi).post("/api/account/delete/", {"password": "pw-12345678"}).status_code, 200)
        u = User.objects.get(pk=self.fundi.pk)
        self.assertEqual((u.is_active, u.phone, u.full_name, u.national_id), (False, None, "Deleted user", ""))
        self.assertFalse(u.has_usable_password())
        self.assertEqual(GigHistory.objects.filter(worker=u).count(), 1)
        self.assertFalse(CrewMember.objects.exists())
        self.assertEqual(self.client.post("/api/login/", {"username": "fundi", "password": "pw-12345678"}).status_code // 100, 4)
