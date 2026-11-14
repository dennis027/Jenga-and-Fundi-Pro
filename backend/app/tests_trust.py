"""Who may change credit scores, see whose data, and record payments."""
import io
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from app.models import (CreditScoreHistory, Gig, JobType, MpesaNewTransaction, Organization,
                        UserPaymentSession, VerificationRequest)

User = get_user_model()


def make_user(username, account_type="01", **extra):
    return User.objects.create_user(username=username, email=f"{username}@example.com", password="pw-12345678",
                                    account_type=account_type, is_active=True, is_verified=False, **extra)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TrustBase(TestCase):
    def setUp(self):
        self.contractor = make_user("boss", "02")
        self.other_contractor = make_user("rival", "02")
        self.fundi = make_user("fundi", "01", phone="0711000001")
        self.other_fundi = make_user("fundi2", "01", phone="0711000002")
        self.staff = make_user("admin", "02", is_staff=True)
        self.org = Organization.objects.create(name="Site A", owner=self.contractor, county="Nairobi",
                                               constituency="Westlands", ward="Parklands", phone_number="0700111222")
        self.other_org = Organization.objects.create(name="Site B", owner=self.other_contractor, county="Meru",
                                                     constituency="Tigania", ward="Kianjai")
        self.job = JobType.objects.create(organization=self.org, name="Masonry Test")
        self.gig = self.new_gig()

    def new_gig(self, worker=None, org=None, **kw):
        worker = worker or self.fundi
        return Gig.objects.create(worker=worker, logged_by=worker, organization=org or self.org, job_type=self.job,
                                  duration_value=2, duration_unit="days", county="Nairobi", constituency="Westlands",
                                  ward="Parklands", client_name="Site A", client_phone="0700111222",
                                  amount_paid=Decimal("1500.00"), **kw)

    def api(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def score(self, user):
        user.refresh_from_db()
        return user.credit_score


class ProfileTrustFieldsTests(TrustBase):
    def test_user_cannot_set_own_score_or_verified_flag(self):
        r = self.api(self.fundi).put("/api/profile/", {"credit_score": 100, "is_verified": "true",
                                                       "full_name": "Real Name"}, format="multipart")
        self.assertEqual(r.status_code, 200)
        self.fundi.refresh_from_db()
        self.assertEqual(self.fundi.credit_score, 0)
        self.assertFalse(self.fundi.is_verified)
        self.assertEqual(self.fundi.full_name, "Real Name")  # normal fields still editable


class VerifyGigTests(TrustBase):
    def url(self, gig=None):
        return f"/api/gigs/verify/{(gig or self.gig).id}/"

    def test_other_fundi_cannot_verify(self):
        self.assertEqual(self.api(self.other_fundi).post(self.url()).status_code, 403)
        self.assertEqual(self.score(self.fundi), 0)

    def test_other_sites_contractor_cannot_verify(self):
        self.assertEqual(self.api(self.other_contractor).post(self.url()).status_code, 403)

    def test_site_owner_verifies_once(self):
        c = self.api(self.contractor)
        self.assertEqual(c.post(self.url()).status_code, 200)
        self.assertEqual(c.post(self.url()).status_code, 200)  # idempotent
        self.assertEqual(self.score(self.fundi), 5)
        self.assertEqual(CreditScoreHistory.objects.filter(user=self.fundi, action="verify_gig").count(), 1)

    def test_contractor_cannot_verify_own_gig_on_own_site(self):
        gig = self.new_gig(worker=self.contractor)
        self.assertEqual(self.api(self.contractor).post(self.url(gig)).status_code, 403)


class CompleteGigTests(TrustBase):
    def url(self):
        return f"/api/gigs/{self.gig.id}/complete/"

    def test_unverified_cannot_complete(self):
        self.assertEqual(self.api(self.fundi).post(self.url()).status_code, 400)

    def test_stranger_cannot_complete(self):
        self.gig.is_verified = True
        self.gig.save()
        self.assertEqual(self.api(self.other_fundi).post(self.url()).status_code, 403)
        self.assertEqual(self.api(self.other_contractor).post(self.url()).status_code, 403)

    def test_worker_completes_verified_gig_once(self):
        self.api(self.contractor).post(f"/api/gigs/verify/{self.gig.id}/")
        r = self.api(self.fundi).post(self.url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.score(self.fundi), 10)
        self.assertFalse(Gig.objects.filter(id=self.gig.id).exists())
        self.assertEqual(self.api(self.fundi).post(self.url()).status_code, 404)  # can't farm twice


class IdentityVerificationTests(TrustBase):
    def setUp(self):
        super().setUp()
        self.vr = VerificationRequest.objects.create(user=self.fundi, status="pending", id_front="MEDIA/x.jpg")

    def url(self):
        return f"/api/verification/{self.vr.id}/action/"

    def test_users_cannot_approve_verifications(self):
        for u in (self.fundi, self.contractor):
            self.assertEqual(self.api(u).post(self.url(), {"action": "approve"}, format="json").status_code, 403)
        self.fundi.refresh_from_db()
        self.assertIsNone(self.fundi.current_verification_id)

    def test_staff_approval_awards_points_once(self):
        c = self.api(self.staff)
        c.post(self.url(), {"action": "approve"}, format="json")
        c.post(self.url(), {"action": "approve"}, format="json")
        self.fundi.refresh_from_db()
        self.assertEqual(self.fundi.current_verification_id, self.vr.id)  # identity verified
        self.assertFalse(self.fundi.is_verified)  # email flag is not touched by ID review
        self.assertEqual(self.fundi.credit_score, 20)


class ScoreCapTests(TrustBase):
    def test_score_is_capped_and_history_records_applied_delta(self):
        from app.scoring import apply_score_change
        self.fundi.credit_score = 98
        self.fundi.save()
        self.assertEqual(apply_score_change(self.fundi, "verify_gig"), 100)
        self.assertEqual(CreditScoreHistory.objects.filter(user=self.fundi).last().change, 2)


class DataExposureTests(TrustBase):
    def test_user_list_is_staff_only(self):
        self.assertEqual(self.api(self.fundi).get("/api/list-users/").status_code, 403)
        self.assertEqual(self.api(self.staff).get("/api/list-users/").status_code, 200)

    def test_gig_search_hides_private_fields_of_others(self):
        rows = self.api(self.other_fundi).get("/api/search-gigs/", {"county": "Nairobi"}).json()
        self.assertEqual(len(rows), 1)
        self.assertNotIn("client_phone", rows[0])
        self.assertNotIn("amount_paid", rows[0])
        own = self.api(self.fundi).get("/api/search-gigs/", {"county": "Nairobi"}).json()
        self.assertEqual(own[0]["client_phone"], "0700111222")

    def test_org_gigs_owner_only(self):
        url = f"/api/organizations/{self.org.id}/gigs/"
        self.assertEqual(self.api(self.other_contractor).get(url).status_code, 403)
        self.assertEqual(self.api(self.contractor).get(url).status_code, 200)

    def test_job_types_only_on_own_sites(self):
        c = self.api(self.other_contractor)
        self.assertEqual(c.post("/api/job-types/", {"name": "Hack", "organization": self.org.id}).status_code, 403)
        self.assertEqual(c.delete(f"/api/job-types/{self.job.id}/").status_code, 403)
        self.assertEqual(self.api(self.contractor).post(
            "/api/job-types/", {"name": "Tiling X", "organization": self.org.id}).status_code, 201)

    def test_worker_search_hides_other_sites_private_fields(self):
        self.new_gig(org=self.other_org)  # same fundi, rival's site
        body = self.api(self.contractor).get("/api/workers/search/", {"q": "fundi"}).json()
        by_site = {g["organization"]: g for g in body["gigs"]}
        self.assertEqual(by_site[self.org.id]["client_phone"], "0700111222")
        self.assertNotIn("client_phone", by_site[self.other_org.id])
        self.assertIn("rating_avg", body)

    def test_worker_search_contractors_only(self):
        self.assertEqual(self.api(self.other_fundi).get("/api/workers/search/", {"q": "fundi"}).status_code, 403)
        self.assertEqual(self.api(self.contractor).get("/api/workers/search/", {"q": "fundi"}).status_code, 200)

    def test_platform_reports_staff_only(self):
        for path in ("weekly-workers", "weekly-gigs", "job-type-distribution", "org-performance", "verification-impact"):
            self.assertEqual(self.api(self.contractor).get(f"/api/reports/{path}/").status_code, 403, path)

    def test_mpesa_messages_scoped_to_user(self):
        MpesaNewTransaction.objects.create(user=self.other_contractor, phone_number="254700", amount=10,
                                           mpesa_receipt_number="R1", transaction_date="2026-11-01T10:00:00Z",
                                           merchant_request_id="m", checkout_request_id="c1", result_code=0,
                                           result_desc="ok", raw_callback={})
        body = self.api(self.contractor).get("/api/mpesa-messages/").json()
        self.assertEqual(body["count"], 0)


@override_settings(MPESA_CALLBACK_TOKEN="s3cret")
class MpesaCallbackTests(TrustBase):
    def setUp(self):
        super().setUp()
        UserPaymentSession.objects.create(user=self.contractor, phone_number="254700000000",
                                          checkout_request_id="ws_CO_1", merchant_request_id="m1", amount=100)

    def callback(self, checkout="ws_CO_1", amount=100, code=0, token="s3cret", receipt="QAB123XYZ"):
        body = {"Body": {"stkCallback": {
            "MerchantRequestID": "m1", "CheckoutRequestID": checkout, "ResultCode": code, "ResultDesc": "x",
            "CallbackMetadata": {"Item": [{"Name": "Amount", "Value": amount},
                                          {"Name": "MpesaReceiptNumber", "Value": receipt},
                                          {"Name": "TransactionDate", "Value": 20261114101010},
                                          {"Name": "PhoneNumber", "Value": 254700000000}]}}}}
        q = f"?token={token}" if token is not None else ""
        return APIClient().post("/api/stk-new-callback/" + q, json.dumps(body), content_type="application/json")

    def test_rejects_missing_or_wrong_token(self):
        self.assertEqual(self.callback(token=None).status_code, 403)
        self.assertEqual(self.callback(token="nope").status_code, 403)
        self.assertEqual(MpesaNewTransaction.objects.count(), 0)

    def test_ignores_unknown_checkout(self):
        self.assertEqual(self.callback(checkout="forged").status_code, 200)
        self.assertEqual(MpesaNewTransaction.objects.count(), 0)

    def test_records_once_and_checks_amount(self):
        self.assertEqual(self.callback(amount=50000).status_code, 400)
        self.assertEqual(self.callback().status_code, 200)
        self.assertEqual(self.callback().json()["status"], "duplicate")
        txn = MpesaNewTransaction.objects.get()
        self.assertEqual(txn.user, self.contractor)

    def test_two_failed_payments_do_not_crash(self):
        UserPaymentSession.objects.create(user=self.contractor, phone_number="254700000000",
                                          checkout_request_id="ws_CO_2", merchant_request_id="m2", amount=100)
        self.assertEqual(self.callback(code=1032).status_code, 200)
        self.assertEqual(self.callback(checkout="ws_CO_2", code=1032).status_code, 200)
        self.assertEqual(MpesaNewTransaction.objects.count(), 2)


class AuditCommandTests(TrustBase):
    def test_finds_and_fixes_scores_without_history(self):
        User.objects.filter(pk=self.fundi.pk).update(credit_score=100)  # as the old profile bug allowed
        out = io.StringIO()
        call_command("audit_credit_scores", "--fix", stdout=out)
        self.assertIn("1 mismatch", out.getvalue())
        self.assertEqual(self.score(self.fundi), 0)
