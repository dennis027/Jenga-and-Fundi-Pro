"""Realistic demo data for local development and UI work.

    docker compose exec backend python manage.py seed_demo_data [--reset]

Builds on the seed_test_users accounts (jenga-pro contractor, fundi-pro worker):
two sites, six fundis, ~15 gigs over the last six weeks (pending, verified and
completed), contractor ratings, ID reviews, M-Pesa payments and a dispute. Scores
are produced by the real scoring rules. Refuses to run in production mode.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from app import identity
from app.models import (CreditScoreHistory, Gig, GigDispute, GigHistory, GigRating, JobType, MpesaNewTransaction,
                        Organization, VerificationRequest)
from app.scoring import apply_score_change

SITES = [
    ("Kilimani Heights", "8-storey residential block, Argwings Kodhek Rd", "Nairobi", "Dagoretti North", "Kilimani", "0711000101"),
    ("Ruaka Gardens", "Townhouses phase 2", "Kiambu", "Kiambaa", "Ndenderu", "0711000102"),
]
FUNDIS = [
    # username, full name, phone, county, constituency, ward, id status
    ("fundi-pro", "Wanjiku Kamau", "0712345678", "Nairobi", "Westlands", "Parklands", "approved"),
    ("otieno.mason", "Brian Otieno", "0722456789", "Nairobi", "Kibra", "Makina", "approved"),
    ("amina.tiles", "Amina Hassan", "0733567890", "Kiambu", "Kiambaa", "Ndenderu", "pending"),
    ("kiptoo.weld", "Samuel Kiptoo", "0767890123", "Nairobi", "Embakasi East", "Utawala", None),
    ("mwangi.wire", "Peter Mwangi", "0745678901", "Kiambu", "Ruiru", "Gitothua", "approved"),
    ("njeri.paint", "Grace Njeri", "0756789012", "Nairobi", "Dagoretti North", "Kilimani", None),
]
DEMO_MARK = "[demo]"


class Command(BaseCommand):
    help = "Create realistic demo data (local only)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete previous demo data first.")

    @transaction.atomic
    def handle(self, *args, reset=False, **options):
        if getattr(settings, "SECURE_SSL_REDIRECT", False) or not (settings.DEBUG or settings.ALLOWED_HOSTS):
            raise CommandError("Refusing to create demo data in production mode.")
        User = get_user_model()
        call_command("seed_test_users", stdout=self.stdout)
        boss = User.objects.get(username="jenga-pro")
        boss.full_name = "Dennis Macharia"
        boss.save(update_fields=["full_name"])

        if Organization.objects.filter(owner=boss, description__startswith=DEMO_MARK).exists():
            if not reset:
                self.stdout.write("Demo data already present (use --reset to rebuild).")
                return
        self._reset(boss)

        rnd = random.Random(42)
        orgs = [Organization.objects.create(name=n, description=f"{DEMO_MARK} {d}", owner=boss, county=c,
                                            constituency=k, ward=w, phone_number=p) for n, d, c, k, w, p in SITES]
        fundis = []
        for uname, name, phone, county, cons, ward, id_status in FUNDIS:
            u, _ = User.objects.get_or_create(username=uname, defaults={"email": f"{uname}@example.com", "account_type": "01"})
            u.full_name, u.phone, u.county, u.constituency, u.ward = name, phone, county, cons, ward
            u.account_type, u.is_active, u.is_verified, u.credit_score = "01", True, True, 0
            u.national_id = str(28100000 + rnd.randint(1000, 9999))
            if uname != "fundi-pro":
                u.set_password("DemoFundi2026!")
            u.save()
            CreditScoreHistory.objects.filter(user=u).delete()
            if id_status:
                vr = VerificationRequest.objects.create(user=u, status="pending",
                                                        id_front=f"MEDIA/verifications/id_front/demo_{uname}.jpg")
                if id_status == "approved":
                    identity.approve(vr)
            fundis.append(u)

        today = timezone.localdate()
        trades = ["Masonry", "Plumbing", "Tiling", "Welding", "Electrical", "Painting", "Carpentry", "Plastering"]
        plan = [  # (fundi idx, site idx, trade, days ago, duration, unit, pay, state)
            (0, 0, "Masonry", 40, 2, "weeks", 18000, "completed"), (0, 1, "Plastering", 24, 6, "days", 7200, "completed"),
            (0, 0, "Masonry", 9, 1, "weeks", 9000, "verified"), (0, 1, "Block Laying", 2, 3, "days", 3600, "pending"),
            (1, 0, "Masonry", 35, 3, "weeks", 27000, "completed"), (1, 0, "Concrete Works", 6, 4, "days", 5200, "pending"),
            (2, 1, "Tiling", 20, 10, "days", 15000, "completed"), (2, 1, "Tiling", 3, 5, "days", 7500, "pending"),
            (3, 0, "Welding", 15, 1, "weeks", 10500, "verified"), (3, 1, "Welding", 1, 2, "days", 3000, "pending"),
            (4, 0, "Electrical", 28, 2, "weeks", 22400, "completed"), (4, 1, "Electrical", 5, 4, "days", 6400, "verified"),
            (5, 1, "Painting", 12, 1, "weeks", 8400, "completed"), (5, 0, "Painting", 0, 2, "days", 2400, "pending"),
        ]
        for fi, si, trade, ago, dur, unit, pay, state in plan:
            org, worker = orgs[si], fundis[fi]
            job = JobType.objects.filter(organization=org, name=trade).first() or \
                JobType.objects.create(organization=org, name=trade)
            gig = Gig.objects.create(worker=worker, logged_by=worker, organization=org, job_type=job,
                                     start_date=today - timedelta(days=ago), duration_value=dur, duration_unit=unit,
                                     client_name=org.name, client_phone=org.phone_number, county=org.county,
                                     constituency=org.constituency, ward=org.ward, amount_paid=Decimal(pay))
            Gig.objects.filter(pk=gig.pk).update(created_at=timezone.now() - timedelta(days=ago, hours=rnd.randint(1, 9)))
            if state in ("verified", "completed"):
                gig.is_verified, gig.verified_by = True, boss
                gig.save(update_fields=["is_verified", "verified_by"])
                apply_score_change(worker, "verify_gig")
            if state == "completed":
                hist = GigHistory.objects.create(worker=worker, job_type=job, start_date=gig.start_date,
                                                 duration_value=dur, duration_unit=unit, client_name=org.name,
                                                 client_phone=org.phone_number or "", county=org.county,
                                                 constituency=org.constituency, ward=org.ward, is_verified=True,
                                                 organization=org, amount_paid=Decimal(pay))
                apply_score_change(worker, "complete_gig")
                gig.delete()
                GigRating.objects.create(history=hist, rated_by=boss, stars=rnd.choice([4, 5, 5, 3]),
                                         comment=rnd.choice(["Neat, on time.", "Good finish.", "Reliable.", ""]))

        for i, (amount, days_ago) in enumerate([(18000, 30), (27000, 20), (15000, 14), (22400, 8), (8400, 3)]):
            MpesaNewTransaction.objects.create(
                user=boss, phone_number="254711000101", amount=amount, mpesa_receipt_number=f"TJD{i}DEMO{rnd.randint(100, 999)}",
                transaction_date=timezone.now() - timedelta(days=days_ago), merchant_request_id=f"demo-m{i}",
                checkout_request_id=f"demo-c{i}", result_code=0, result_desc="The service request is processed successfully.",
                raw_callback={"demo": True})

        from app.models import GigsAvailable
        for org, title, desc in [
            (orgs[0], "2 masons for block work, 3 weeks", "Floors 5-6. KSh 1,200/day. Start Monday 7am."),
            (orgs[0], "Electrician, 1 week", "Wiring for 4 units. Bring your own tools."),
            (orgs[1], "Tiler for bathrooms", "12 bathrooms, ceramic tiles. Pay per m², negotiable."),
        ]:
            GigsAvailable.objects.create(organization=org, title=title, description=desc, county=org.county,
                                         constituency=org.constituency, ward=org.ward)

        from app.models import JobApplication, SiteCheckIn
        posts = list(GigsAvailable.objects.filter(organization__in=orgs).order_by("id"))
        JobApplication.objects.create(post=posts[0], worker=fundis[1], message="I can start Monday, 12 years in block work.")
        JobApplication.objects.create(post=posts[0], worker=fundis[3], message="Available for 3 weeks.")
        JobApplication.objects.create(post=posts[2], worker=fundis[2], message="I did the tiling at Ruaka phase 1.")
        for g in Gig.objects.filter(organization__in=orgs, is_verified=True).exclude(worker__username="fundi-pro"):
            SiteCheckIn.objects.get_or_create(gig=g, date=today, defaults={"worker": g.worker})

        hist = GigHistory.objects.filter(worker=fundis[2]).first()
        if hist:
            GigDispute.objects.create(history=hist, raised_by=fundis[2], reason="The days worked were 10, not 8.")

        self._workforce(boss, orgs, fundis, posts, today, rnd)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data: {len(orgs)} sites, {len(fundis)} fundis, {Gig.objects.filter(organization__in=orgs).count()} open gigs, "
            f"{GigHistory.objects.filter(organization__in=orgs).count()} completed. Other fundis' password: DemoFundi2026!"))

    def _workforce(self, boss, orgs, fundis, posts, today, rnd):
        """Work profiles, crew, alerts, site ratings, incidents, budgets, inbox and activity."""
        from app.inbox import log, push
        from app.models import ActivityLog, CrewMember, JobAlert, Notification, SafetyIncident, SiteRating
        profiles = {
            "fundi-pro": ("Masonry, Plastering, Block laying", 9, 1200, "Block work and plastering on multi-storey sites. Own tools.", True),
            "otieno.mason": ("Masonry, Concrete works", 12, 1300, "Foreman experience on 6+ storey builds.", True),
            "amina.tiles": ("Tiling", 6, 1500, "Bathrooms and kitchens, ceramic and porcelain.", False),
            "kiptoo.weld": ("Welding, Steel fixing", 7, 1400, "", True),
            "mwangi.wire": ("Electrical", 10, 1600, "Wiring, DBs and testing. KPLC-ready installs.", True),
            "njeri.paint": ("Painting", 4, 1000, "", True),
        }
        for u in fundis:
            sk, yrs, rate, bio, avail = profiles[u.username]
            u.skills, u.years_experience, u.day_rate, u.bio, u.is_available = sk, yrs, rate, bio, avail
            u.available_from = None if avail else today + timedelta(days=9)
            u.save(update_fields=["skills", "years_experience", "day_rate", "bio", "is_available", "available_from"])
        for u, note in [(fundis[1], "Best mason on Kilimani"), (fundis[4], "Reliable, tidy wiring"), (fundis[2], "")]:
            CrewMember.objects.get_or_create(contractor=boss, worker=u, defaults={"note": note})
        JobAlert.objects.get_or_create(user=fundis[0], keyword="mason", county="Nairobi")
        for i, h in enumerate(GigHistory.objects.filter(organization__in=orgs).order_by("id")[:4]):
            SiteRating.objects.get_or_create(history=h, defaults={"organization": h.organization, "rated_by": h.worker,
                                                                   "stars": [5, 4, 4, 3][i], "paid_on_time": i != 3,
                                                                   "comment": ["Paid every Friday.", "Good site, safe scaffolds.", "", "Pay came a week late."][i]})
        orgs[0].labour_budget, orgs[1].labour_budget = Decimal("120000"), Decimal("45000")
        for o in orgs:
            o.save(update_fields=["labour_budget"])
        SafetyIncident.objects.create(organization=orgs[0], reported_by=fundis[1], kind="near_miss", severity="high",
                                      description="Scaffold plank on floor 5 slipped while carrying blocks. Nobody hurt.",
                                      occurred_on=today - timedelta(days=1))
        SafetyIncident.objects.create(organization=orgs[1], reported_by=fundis[2], kind="hazard", severity="medium",
                                      description="Exposed wiring near the bathroom block, phase 2.", occurred_on=today - timedelta(days=6),
                                      is_resolved=True, resolution="Electrician isolated and taped the cable.",
                                      resolved_at=timezone.now() - timedelta(days=5))
        if posts:
            posts[0].positions = 2
            posts[0].save(update_fields=["positions"])
        Notification.objects.filter(user__in=[boss, *fundis]).delete()
        push(fundis[0], "gig_verified", "Kilimani Heights verified your Masonry", "+5 points. Mark it complete when done.", "/main-menu/gig-summary")
        push(fundis[0], "job_alert", "New job: 2 masons for block work, 3 weeks", "Kilimani Heights · Kilimani, Nairobi", "/main-menu/search-gigs")
        push(fundis[0], "id_approved", "Your ID is verified", "+20 points added to your credit score.", "/main-menu/credit-score")
        Notification.objects.filter(user=fundis[0], kind="id_approved").update(is_read=True)
        push(boss, "incident", "Near miss reported at Kilimani Heights", "Scaffold plank on floor 5 slipped while carrying blocks.", "/main-menu/safety")
        push(boss, "new_applicant", "Brian Otieno applied", "For '2 masons for block work, 3 weeks'", "/main-menu/job-posts")
        push(boss, "site_rated", "Wanjiku Kamau rated Kilimani Heights 5★", "Paid every Friday.", "/main-menu/workforce?tab=ratings")
        ActivityLog.objects.filter(organization__in=orgs).delete()
        for o, action, text, ago in [
            (orgs[0], "job_posted", "Posted job '2 masons for block work, 3 weeks'", 3),
            (orgs[0], "gig_verified", "Verified Wanjiku Kamau's Masonry gig", 2),
            (orgs[1], "gig_rejected", "Rejected Peter Mwangi's Plumbing gig: not on site these dates", 2),
            (orgs[1], "hired", "Hired Amina Hassan for 'Tiler for bathrooms'", 1),
            (orgs[0], "incident_reported", "Near miss (high) reported by Brian Otieno", 1),
            (orgs[0], "budget_set", "Labour budget for Kilimani Heights set to KSh 120,000", 0),
        ]:
            a = log(boss, o, action, text)
            ActivityLog.objects.filter(pk=a.pk).update(created_at=timezone.now() - timedelta(days=ago, hours=rnd.randint(1, 6)))

    def _reset(self, boss):
        orgs = Organization.objects.filter(owner=boss)
        GigDispute.objects.filter(history__organization__in=orgs).delete()
        GigDispute.objects.filter(gig__organization__in=orgs).delete()
        orgs.delete()  # cascades gigs, history, ratings, job types
        MpesaNewTransaction.objects.filter(user=boss, checkout_request_id__startswith="demo-").delete()
        from app.models import CrewMember, JobAlert
        CrewMember.objects.filter(contractor=boss).delete()
        User = get_user_model()
        for uname, *_ in FUNDIS:
            u = User.objects.filter(username=uname).first()
            if u:
                VerificationRequest.objects.filter(user=u).delete()
                JobAlert.objects.filter(user=u).delete()
                u.current_verification = None
                u.save(update_fields=["current_verification"])
