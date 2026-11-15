"""A large, realistic showcase dataset (safe to run on the live database, and removable).

    python manage.py seed_showcase            # add (refuses if already present)
    python manage.py seed_showcase --reset    # remove, then add again
    python manage.py seed_showcase --remove   # remove everything it added

Builds around the README test accounts (jenga-pro contractor, fundi-pro worker):
4 contractors, 12 sites across 7 counties, ~45 fundis with work profiles, ~120 days
of gigs (pending, verified, completed) with check-ins, ratings both ways, job posts
with applications and invitations, crews, safety incidents, disputes, budgets,
M-Pesa payments, notifications and an activity log.

How it stays safe and removable:
- every showcase user has an email at DEMO_EMAIL_DOMAIN; app.notify never texts them;
- showcase sites are owned by showcase contractors, or by jenga-pro with a name from SITES;
- --remove deletes those users and sites (cascading their gigs, posts, etc.), the
  showcase M-Pesa rows and the test accounts' notifications, then rebuilds fundi-pro's
  score history from what is left.
Uses bulk inserts so it finishes in a few minutes against a remote database.
"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from app.models import (ActivityLog, CreditScoreHistory, CrewMember, Gig, GigDispute, GigHistory, GigRating,
                        GigsAvailable, JobAlert, JobApplication, JobType, MpesaNewTransaction, Notification,
                        Organization, SafetyIncident, SavedPost, SiteCheckIn, SiteRating, VerificationRequest)
from app.notify import DEMO_EMAIL_DOMAIN

DAYS = 120
DEMO_PASSWORD = "DemoFundi2026!"

# (username, full name, phone, company-ish note)
CONTRACTORS = [
    ("achieng.construction", "Achieng Otieno", "0711000201"),
    ("rift.builders", "Kipchumba Rotich", "0711000202"),
    ("coastline.dev", "Fatma Abdalla", "0711000203"),
]
# (owner key, name, description, county, constituency, ward, phone)  owner "boss" = jenga-pro
SITES = [
    ("boss", "Kilimani Heights", "8-storey residential block, Argwings Kodhek Rd", "Nairobi", "Dagoretti North", "Kilimani", "0711000101"),
    ("boss", "Ruaka Gardens", "48 townhouses, phase 2", "Kiambu", "Kiambaa", "Ndenderu", "0711000102"),
    ("boss", "Syokimau Court", "Gated maisonettes off Mombasa Rd", "Machakos", "Mavoko", "Syokimau/Mulolongo", "0711000103"),
    ("boss", "Kitengela Villas", "3-bedroom bungalows, 30 units", "Kajiado", "Kajiado East", "Kitengela", "0711000104"),
    ("boss", "Roysambu Plaza", "Mixed-use, 5 floors retail and offices", "Nairobi", "Roysambu", "Roysambu", "0711000105"),
    ("boss", "Nyali Beach Apartments", "12-storey apartments, sea-facing", "Mombasa", "Nyali", "Frere Town", "0711000106"),
    ("achieng.construction", "Milimani Residences", "Apartments near Kisumu CBD", "Kisumu", "Kisumu Central", "Milimani", "0711000201"),
    ("achieng.construction", "Kondele Market Upgrade", "County market stalls and drainage", "Kisumu", "Kisumu Central", "Kondele", "0711000201"),
    ("rift.builders", "Milimani Estate Nakuru", "Townhouses, 24 units", "Nakuru", "Nakuru Town East", "Biashara", "0711000202"),
    ("rift.builders", "Naivasha Lakeview Lodge", "Hotel extension, 40 rooms", "Nakuru", "Naivasha", "Lake View", "0711000202"),
    ("coastline.dev", "Bamburi Heights", "Apartments, 6 floors", "Mombasa", "Kisauni", "Bamburi", "0711000203"),
    ("coastline.dev", "Mtwapa Creek Homes", "Holiday homes, phase 1", "Kilifi", "Kilifi South", "Mtwapa", "0711000203"),
]
TRADES = ["Masonry", "Plastering", "Block laying", "Concrete works", "Tiling", "Plumbing", "Electrical", "Carpentry",
          "Painting", "Welding", "Steel fixing", "Roofing", "Glazing", "General labour"]
FIRST = ["Wanjiru", "Brian", "Amina", "Samuel", "Peter", "Grace", "Kevin", "Mercy", "Joseph", "Faith", "Dennis", "Esther",
         "John", "Lucy", "Collins", "Mary", "Hassan", "Janet", "Victor", "Caroline", "Moses", "Ann", "George", "Purity",
         "Felix", "Rose", "Tom", "Beatrice", "Isaac", "Nancy", "Daniel", "Joy", "Omar", "Cynthia", "Patrick", "Irene",
         "Stephen", "Lilian", "Erick", "Agnes", "Kennedy", "Winnie", "Simon", "Diana", "Paul"]
LAST = ["Mwangi", "Otieno", "Hassan", "Kiptoo", "Kamau", "Njeri", "Ochieng", "Wambui", "Mutua", "Chebet", "Kariuki",
        "Akinyi", "Mohamed", "Wanjala", "Kipruto", "Nduta", "Barasa", "Atieno", "Kimani", "Juma", "Odhiambo", "Mumbua",
        "Korir", "Waweru", "Omondi", "Muthoni", "Ruto", "Adhiambo", "Ndungu", "Mwende", "Langat", "Wafula", "Ali",
        "Nyambura", "Kirui", "Moraa", "Gitau", "Anyango", "Kibet", "Wairimu", "Owino", "Nekesa", "Macharia", "Jeptoo", "Opiyo"]
BIOS = ["Own tools, reliable and on time.", "Foreman experience on multi-storey builds.", "Neat finishing, references available.",
        "Worked with NCA-registered contractors for years.", "Quick learner, happy to travel.", "Specialise in finishing works.", ""]
POSTS = [
    ("Kilimani Heights", "2 masons for block work, 3 weeks", "Floors 7-8. KSh 1,300/day. Start Monday 7am.", 2),
    ("Kilimani Heights", "Electrician, 2 weeks", "Second-fix wiring for 16 units. Own tools.", 1),
    ("Ruaka Gardens", "Tiler for bathrooms", "24 bathrooms, ceramic tiles. Pay per m², negotiable.", 2),
    ("Ruaka Gardens", "Painters, 4 needed", "Interior emulsion, townhouses 13-24.", 4),
    ("Syokimau Court", "Plumber for first fix", "PPR piping, 10 maisonettes. 3 weeks.", 1),
    ("Kitengela Villas", "Roofers, ridge and tiles", "Concrete tiles, 6 units. KSh 1,400/day.", 3),
    ("Roysambu Plaza", "Steel fixers for slab", "4th floor slab. Start Wednesday.", 3),
    ("Roysambu Plaza", "Glazier for shopfronts", "Aluminium and glass, ground floor.", 1),
    ("Nyali Beach Apartments", "Plasterers, 2 weeks", "External plaster floors 5-8.", 2),
    ("Nyali Beach Apartments", "Welder for balcony rails", "Stainless rails, 24 balconies.", 1),
    ("Milimani Residences", "Carpenter for formwork", "Columns and beams, 2 weeks.", 2),
    ("Kondele Market Upgrade", "General labourers", "Drainage trenching. KSh 800/day.", 6),
    ("Milimani Estate Nakuru", "Masons, 1 month", "Block work, townhouses 9-16.", 3),
    ("Naivasha Lakeview Lodge", "Tilers, porcelain floors", "40 rooms, 600x600 porcelain.", 2),
    ("Bamburi Heights", "Electrician, conduits", "First fix, floors 1-3.", 1),
    ("Mtwapa Creek Homes", "Roofer, makuti and tiles", "Phase 1, 8 homes.", 2),
    ("Kitengela Villas", "Painter for exterior", "Weathercoat, 10 bungalows.", 2),
    ("Syokimau Court", "Block layers", "Boundary wall, 200 m.", 2),
]
INCIDENTS = [
    ("near_miss", "high", "Scaffold plank on floor 5 slipped while carrying blocks. Nobody hurt."),
    ("injury", "medium", "Cut on the hand from a tile cutter. First aid given, worker back next day."),
    ("hazard", "medium", "Exposed live cable near the bathroom block."),
    ("hazard", "low", "Rubble blocking the fire exit stairs on floor 2."),
    ("near_miss", "medium", "Bag of cement fell from the hoist. Area was clear."),
    ("injury", "high", "Fall from a ladder, ankle sprain. Taken to clinic."),
    ("hazard", "high", "No guard rails on the open slab edge, floor 4."),
    ("other", "low", "Water tank leaking onto the walkway, slippery surface."),
    ("hazard", "medium", "Trench left uncovered overnight near the gate."),
    ("near_miss", "low", "Wheelbarrow tipped on the ramp, no injuries."),
    ("injury", "low", "Dust in the eye while chasing walls. Goggles issued."),
    ("hazard", "medium", "Loose roofing sheets after strong wind."),
]
COMMENTS = ["Neat, on time.", "Good finish.", "Reliable.", "Fast and careful.", "Needs supervision on levels.", "Excellent work.", "", ""]
SITE_COMMENTS = ["Paid every Friday.", "Good site, safe scaffolds.", "Supervisor is fair.", "Pay came a week late.",
                 "Water and shade provided.", "Long hours but paid on time.", ""]


class Command(BaseCommand):
    help = "Add (or remove) a large showcase dataset. Safe for the live database."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Remove the showcase data, then add it again.")
        parser.add_argument("--remove", action="store_true", help="Remove the showcase data only.")

    def handle(self, *args, reset=False, remove=False, **opts):
        User = get_user_model()
        self.User = User
        boss = User.objects.filter(username="jenga-pro").first()
        me = User.objects.filter(username="fundi-pro").first()
        if not boss or not me:
            call_command("seed_test_users", stdout=self.stdout)
            boss, me = User.objects.get(username="jenga-pro"), User.objects.get(username="fundi-pro")
        self.boss, self.me = boss, me
        present = self._showcase_orgs().exists()
        if remove or reset:
            self._remove()
            self.stdout.write("Showcase data removed.")
            if remove:
                return
        elif present:
            raise CommandError("Showcase data already present. Use --reset to rebuild or --remove to delete it.")
        self._build()

    # ------------------------------------------------------------------ helpers
    def _showcase_orgs(self):
        names = [s[1] for s in SITES if s[0] == "boss"]
        return Organization.objects.filter(Q(owner__email__endswith=DEMO_EMAIL_DOMAIN)
                                           | Q(owner=self.boss, name__in=names))

    def _at(self, day, hour=None):
        """Aware datetime on `day` (a date) at a working hour, never in the future."""
        h = hour if hour is not None else self.rnd.randint(7, 17)
        ts = timezone.make_aware(datetime.combine(day, time(h, self.rnd.randint(0, 59))))
        return self._past(ts)

    def _past(self, ts):
        now = timezone.now()
        return ts if ts < now else now - timedelta(minutes=self.rnd.randint(10, 240))

    @transaction.atomic
    def _remove(self):
        orgs = self._showcase_orgs()
        GigDispute.objects.filter(Q(gig__organization__in=orgs) | Q(history__organization__in=orgs)).delete()
        orgs.delete()
        self.User.objects.filter(email__endswith=DEMO_EMAIL_DOMAIN).delete()
        MpesaNewTransaction.objects.filter(checkout_request_id__startswith="showcase-").delete()
        Notification.objects.filter(user__in=[self.boss, self.me]).delete()
        CrewMember.objects.filter(contractor=self.boss).delete()
        JobAlert.objects.filter(user=self.me).delete()
        SavedPost.objects.filter(user=self.me).delete()
        showcase_ids = VerificationRequest.objects.filter(user=self.me, id_front__startswith="MEDIA/verifications/id_front/showcase_")
        if self.me.current_verification_id in set(showcase_ids.values_list("id", flat=True)):
            self.User.objects.filter(pk=self.me.pk).update(current_verification=None)
            self.me.current_verification = None
        showcase_ids.delete()
        self._rebuild_score(self.me)

    def _rebuild_score(self, u):
        """Recreate a user's score history from the verified facts that remain."""
        CreditScoreHistory.objects.filter(user=u).delete()
        events = []
        v = u.current_verification
        if v and v.status == "approved":
            events.append((v.created_at, "approve_verification", 20))
        for g in Gig.objects.filter(worker=u, is_verified=True):
            events.append((g.created_at, "verify_gig", 5))
        for h in GigHistory.objects.filter(worker=u, is_verified=True):
            events += [(h.created_at, "verify_gig", 5), (h.created_at, "complete_gig", 5)]
        self._write_history(u, events)

    def _write_history(self, u, events):
        score, rows = 0, []
        for ts, action, pts in sorted(events, key=lambda e: e[0]):
            new = max(0, min(100, score + pts))
            rows.append(CreditScoreHistory(user=u, change=new - score, new_score=new, action=action))
            rows[-1]._ts = ts
            score = new
        made = CreditScoreHistory.objects.bulk_create(rows)
        for r, src in zip(made, rows):
            r.timestamp = src._ts
        CreditScoreHistory.objects.bulk_update(made, ["timestamp"], batch_size=500)
        self.User.objects.filter(pk=u.pk).update(credit_score=score)

    # ------------------------------------------------------------------ build
    @transaction.atomic
    def _build(self):
        rnd = self.rnd = random.Random(2026)
        today = timezone.localdate()
        start = today - timedelta(days=DAYS)
        pw = make_password(DEMO_PASSWORD)
        boss, me = self.boss, self.me
        acts, notes = [], []  # (ts, org, actor, action, summary) / (ts, user, kind, title, body, link, read)

        # people ---------------------------------------------------------------
        boss.full_name = boss.full_name or "Dennis Macharia"
        boss.save(update_fields=["full_name"])
        owners = {"boss": boss}
        for uname, name, phone in CONTRACTORS:
            u = self.User(username=uname, email=f"{uname}{DEMO_EMAIL_DOMAIN}", full_name=name, phone=phone,
                          account_type="02", is_active=True, is_verified=True, password=pw)
            u.save()
            owners[uname] = u

        sites = {}
        for owner, name, desc, county, cons, ward, phone in SITES:
            o = Organization.objects.create(name=name, description=desc, owner=owners[owner], county=county,
                                            constituency=cons, ward=ward, phone_number=phone)
            Organization.objects.filter(pk=o.pk).update(created_at=self._at(start - timedelta(days=rnd.randint(5, 40))))
            sites[name] = o
        org_list = list(sites.values())

        counties = [s[3] for s in SITES]
        fundis = []
        used = set()
        for i in range(45):
            first, last = FIRST[i], LAST[(i * 7) % len(LAST)]
            uname = f"{first.lower()}.{last.lower()}"
            while uname in used:
                uname += str(i)
            used.add(uname)
            home = rnd.choice(SITES)
            skills = rnd.sample(TRADES[:-1], rnd.choice([1, 2, 2, 3]))
            rate = rnd.choice([800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1800])
            avail = rnd.random() < 0.75
            u = self.User(username=uname, email=f"{uname}{DEMO_EMAIL_DOMAIN}", full_name=f"{first} {last}",
                          phone=f"07{rnd.randint(10, 99)}{rnd.randint(100000, 999999)}", account_type="01",
                          is_active=True, is_verified=True, password=pw, county=home[3], constituency=home[4], ward=home[5],
                          national_id=str(rnd.randint(22000000, 39999999)), skills=", ".join(skills),
                          years_experience=rnd.randint(1, 20), day_rate=rate, bio=rnd.choice(BIOS), is_available=avail,
                          available_from=None if avail else today + timedelta(days=rnd.randint(3, 25)))
            u.save()
            self.User.objects.filter(pk=u.pk).update(date_joined=self._at(start - timedelta(days=rnd.randint(1, 60))))
            fundis.append(u)
        me.full_name = me.full_name or "Wanjiku Kamau"
        me.skills, me.years_experience, me.day_rate = "Masonry, Plastering, Block laying", 9, 1200
        me.bio, me.is_available, me.available_from = "Block work and plastering on multi-storey sites. Own tools.", True, None
        me.save(update_fields=["full_name", "skills", "years_experience", "day_rate", "bio", "is_available", "available_from"])
        workers = fundis + [me]

        # ID verification -------------------------------------------------------
        score_events = {u.pk: [] for u in workers}
        for u in workers:
            r = rnd.random()
            if u == me and me.current_verification_id:
                continue
            status = "approved" if (u == me or r < 0.7) else ("pending" if r < 0.85 else ("rejected" if r < 0.92 else None))
            if not status:
                continue
            vr = VerificationRequest.objects.create(user=u, status=status, id_front=f"MEDIA/verifications/id_front/showcase_{u.username}.jpg",
                                                    rejection_reason="Photo too blurry." if status == "rejected" else None)
            ts = self._at(start + timedelta(days=rnd.randint(0, 30)))
            VerificationRequest.objects.filter(pk=vr.pk).update(created_at=ts)
            if status == "approved":
                self.User.objects.filter(pk=u.pk).update(current_verification=vr)
                score_events[u.pk].append((ts, "approve_verification", 20))
        me.refresh_from_db()

        # job types per site ---------------------------------------------------
        jt = {}
        for o in org_list:
            have = {j.name.lower(): j for j in JobType.objects.filter(organization=o)}
            for t in TRADES:
                j = have.get(t.lower()) or JobType.objects.create(organization=o, name=t)
                jt[(o.pk, t)] = j

        # gigs over the period ---------------------------------------------------
        gigs, hists, hist_meta, checkins = [], [], [], []
        boss_sites_all = [o for o in org_list if o.owner == boss]
        for u in workers:
            local = boss_sites_all if u == me else ([o for o in org_list if o.county == u.county] or org_list)
            # past gigs back to back, then (for most workers) one gig running now
            plan, day = [], start + timedelta(days=rnd.randint(0, 20))
            n = 10 if u == me else rnd.randint(3, 7)
            while len(plan) < n and day < today - timedelta(days=12):
                unit = "weeks" if rnd.random() < 0.35 else "days"
                val = rnd.randint(1, 3) if unit == "weeks" else rnd.randint(2, 10)
                plan.append((day, unit, val))
                day += timedelta(days=(val * 7 if unit == "weeks" else val) + rnd.randint(1, 8))
            if u == me or rnd.random() < 0.75:
                cur = max(day, today - timedelta(days=rnd.randint(0, 9)))
                if cur <= today:
                    unit = "weeks" if rnd.random() < 0.4 else "days"
                    plan.append((cur, unit, rnd.randint(1, 3) if unit == "weeks" else rnd.randint(4, 12)))
            for day, unit, val in plan:
                o = rnd.choice(local if rnd.random() < 0.75 else org_list)
                trade = rnd.choice(u.skills.split(", ")) if u.skills else "General labour"
                length = val * 7 if unit == "weeks" else val
                end = day + timedelta(days=length - 1)
                pay = Decimal((u.day_rate or 1000) * length)
                logged = self._at(day + timedelta(days=rnd.randint(0, 1)))
                owner = o.owner
                common = dict(worker=u, job_type=jt[(o.pk, trade)], start_date=day, duration_value=val, duration_unit=unit,
                              client_name=o.name, client_phone=o.phone_number or "", county=o.county,
                              constituency=o.constituency, ward=o.ward)
                verify_ts = self._past(logged + timedelta(hours=rnd.randint(3, 40)))
                if end < today - timedelta(days=3) and rnd.random() < 0.92:
                    done_ts = self._at(min(end + timedelta(days=rnd.randint(1, 3)), today))
                    hists.append(GigHistory(**common, is_verified=True, organization=o, amount_paid=pay))
                    hist_meta.append((done_ts, o, u, trade, verify_ts))
                    score_events[u.pk] += [(verify_ts, "verify_gig", 5), (done_ts, "complete_gig", 5)]
                    acts.append((verify_ts, o, owner, "gig_verified", f"Verified {u.full_name}'s {trade} gig"))
                    acts.append((done_ts, o, u, "gig_completed", f"{u.full_name} completed {trade}"))
                    continue
                if end < today - timedelta(days=3):
                    verified = True                      # finished but not marked complete yet
                elif day >= today - timedelta(days=2):
                    verified = rnd.random() < 0.35       # just logged: mostly waiting for the contractor
                else:
                    verified = rnd.random() < 0.85
                g = Gig(**common, logged_by=u, organization=o, amount_paid=pay, is_verified=verified,
                        verified_by=owner if verified else None)
                g._ts = logged
                gigs.append(g)
                if verified:
                    score_events[u.pk].append((verify_ts, "verify_gig", 5))
                    acts.append((verify_ts, o, owner, "gig_verified", f"Verified {u.full_name}'s {trade} gig"))
                    g._checkin = (max(day, verify_ts.date()), min(end, today))
                    if u == me:
                        notes.append((verify_ts, me, "gig_verified", f"{o.name} verified your {trade}",
                                      "+5 points. Mark it complete when done.", "/main-menu/gig-summary",
                                      verify_ts < timezone.now() - timedelta(days=2)))
                elif o.owner == boss:
                    notes.append((logged, boss, "gig_logged", f"{u.full_name} logged {trade}", f"{o.name} · waiting for you",
                                  "/main-menu/verify-gigs", False))

        made = Gig.objects.bulk_create(gigs, batch_size=500)
        for g, src in zip(made, gigs):
            g.created_at = src._ts
            if getattr(src, "_checkin", None):
                d0, d1 = src._checkin
                d = d0
                while d <= d1:
                    if (d.weekday() != 6 or d == today) and rnd.random() < (0.95 if d == today else 0.85):
                        checkins.append(SiteCheckIn(gig=g, worker=g.worker, date=d))
                    d += timedelta(days=1)
        Gig.objects.bulk_update(made, ["created_at"], batch_size=500)
        cmade = SiteCheckIn.objects.bulk_create(checkins, batch_size=1000)
        for c in cmade:
            c.checked_in_at = self._past(timezone.make_aware(datetime.combine(c.date, time(rnd.randint(6, 9), rnd.randint(0, 59)))))
        SiteCheckIn.objects.bulk_update(cmade, ["checked_in_at"], batch_size=1000)

        hmade = GigHistory.objects.bulk_create(hists, batch_size=500)
        ratings, site_ratings = [], []
        for h, (ts, o, u, trade, _) in zip(hmade, hist_meta):
            h.created_at = ts
            if rnd.random() < 0.8:
                ratings.append(GigRating(history=h, rated_by=o.owner, stars=rnd.choice([3, 4, 4, 5, 5, 5]), comment=rnd.choice(COMMENTS)))
            if rnd.random() < 0.55:
                s = rnd.choice([3, 4, 4, 5, 5])
                site_ratings.append(SiteRating(history=h, organization=o, rated_by=u, stars=s, paid_on_time=rnd.random() < (0.9 if s >= 4 else 0.5),
                                               comment=rnd.choice(SITE_COMMENTS)))
                if o.owner == boss and ts > timezone.now() - timedelta(days=10):
                    notes.append((ts + timedelta(hours=3), boss, "site_rated", f"{u.full_name} rated {o.name} {s}★",
                                  site_ratings[-1].comment, "/main-menu/workforce?tab=ratings", True))
        GigHistory.objects.bulk_update(hmade, ["created_at"], batch_size=500)
        recent = timezone.now() - timedelta(days=21)
        for h, (ts, o, u, trade, vts) in zip(hmade, hist_meta):
            if u == me and vts > recent:
                notes.append((vts, me, "gig_verified", f"{o.name} verified your {trade}", "+5 points. Mark it complete when done.",
                              "/main-menu/gig-summary", True))
            if o.owner == boss and ts > recent:
                notes.append((ts, boss, "gig_completed", f"{u.full_name} completed {trade}", f"{o.name} · KSh {h.amount_paid:,.0f}",
                              "/main-menu/all-gigs", ts < timezone.now() - timedelta(days=2)))
        GigRating.objects.bulk_create(ratings, batch_size=500)
        SiteRating.objects.bulk_create(site_ratings, batch_size=500)

        for u in fundis:
            self._write_history(u, score_events[u.pk])
        me.refresh_from_db()
        self._rebuild_score(me)

        # job posts, applications, invitations ------------------------------------
        crew_pool = rnd.sample(fundis, 10)
        CrewMember.objects.bulk_create([
            CrewMember(contractor=boss, worker=w, note=rnd.choice(["Best mason on Kilimani", "Reliable, tidy work", "Call first for tiling",
                                                                    "Good foreman", "", ""])) for w in crew_pool])
        apps = []
        for i, (site, title, desc, positions) in enumerate(POSTS):
            o = sites[site]
            posted = self._at(today - timedelta(days=rnd.randint(0, 28)))
            p = GigsAvailable.objects.create(organization=o, title=title, description=desc, county=o.county,
                                             constituency=o.constituency, ward=o.ward, positions=positions)
            GigsAvailable.objects.filter(pk=p.pk).update(created_at=posted)
            acts.append((posted, o, o.owner, "job_posted", f"Posted job '{title}'"))
            pool = [f for f in fundis if any(t.lower() in title.lower() or t.lower() in desc.lower() for t in f.skills.split(", "))] or fundis
            applicants = rnd.sample(pool, min(len(pool), rnd.randint(2, 7)))
            closed = i % 3 == 2
            accepted = 0
            for j, w in enumerate(applicants):
                ts = self._past(posted + timedelta(hours=rnd.randint(2, 96)))
                if closed and accepted < positions:
                    st = "accepted"
                elif j == len(applicants) - 1 and o.owner == boss and w in crew_pool:
                    st = "invited"
                else:
                    st = rnd.choice(["pending", "pending", "pending", "declined", "accepted", "withdrawn"])
                    if st == "accepted" and accepted + 1 >= positions:
                        st = "pending"
                accepted += st == "accepted"
                a = JobApplication(post=p, worker=w, status=st, message=rnd.choice(
                    ["I can start Monday.", "10 years experience, own tools.", "Available immediately.",
                     "I worked on a similar site in Westlands.", "", ""]) if st != "invited" else "")
                a._ts, a._post = ts, p
                apps.append(a)
                if st == "accepted":
                    acts.append((ts + timedelta(hours=5), o, o.owner, "hired", f"Hired {w.full_name} for '{title}'"))
                if st == "invited":
                    acts.append((ts, o, o.owner, "invited", f"Invited {w.full_name} to '{title}'"))
                if o.owner == boss and st == "pending" and ts > timezone.now() - timedelta(days=4):
                    notes.append((ts, boss, "new_applicant", f"{w.full_name} applied", f"For '{title}'", "/main-menu/job-posts",
                                  ts < timezone.now() - timedelta(days=1)))
            if closed:
                GigsAvailable.objects.filter(pk=p.pk).update(is_open=False)
                acts.append((posted + timedelta(days=3), o, o.owner, "job_closed", f"Closed job '{title}'"))
        amade = JobApplication.objects.bulk_create(apps, batch_size=500)
        for a, src in zip(amade, apps):
            a.created_at = src._ts
            a.decided_at = src._ts + timedelta(hours=5) if src.status in ("accepted", "declined", "withdrawn") else None
        JobApplication.objects.bulk_update(amade, ["created_at", "decided_at"], batch_size=500)

        # fundi-pro: an application, an invitation, an alert, saved jobs
        open_posts = list(GigsAvailable.objects.filter(organization__in=org_list, is_open=True).order_by("id"))
        JobApplication.objects.get_or_create(post=open_posts[0], worker=me, defaults={"status": "pending", "message": "I can start Monday."})
        JobApplication.objects.get_or_create(post=open_posts[3], worker=me, defaults={"status": "invited"})
        notes.append((timezone.now() - timedelta(hours=3), me, "invitation", f"{open_posts[3].organization.name} invited you",
                      f"Job: '{open_posts[3].title}'. Accept or decline.", "/main-menu/search-gigs", False))
        JobAlert.objects.bulk_create([JobAlert(user=me, keyword="mason", county="Nairobi"), JobAlert(user=me, keyword="plaster")]
                                     + [JobAlert(user=f, keyword=f.skills.split(", ")[0].lower(), county=f.county, sms=rnd.random() < 0.3)
                                        for f in rnd.sample(fundis, 15)])
        SavedPost.objects.bulk_create([SavedPost(user=me, post=p) for p in open_posts[1:3]]
                                      + [SavedPost(user=f, post=rnd.choice(open_posts)) for f in rnd.sample(fundis, 20)], ignore_conflicts=True)

        # incidents ------------------------------------------------------------------
        boss_sites = [o for o in org_list if o.owner == boss]
        for i, (kind, sev, desc) in enumerate(INCIDENTS):
            o = boss_sites[i % len(boss_sites)] if i < 9 else org_list[6 + i % 6]
            day = today - timedelta(days=rnd.randint(0, 60) if i > 1 else i)
            rep = rnd.choice([g.worker for g in made if g.organization_id == o.pk] or fundis)
            resolved = i > 2 and rnd.random() < 0.7
            inc = SafetyIncident.objects.create(organization=o, reported_by=rep, kind=kind, severity=sev, description=desc,
                                                occurred_on=day, is_resolved=resolved,
                                                resolution=rnd.choice(["Fixed the same day.", "Area cordoned off and repaired.",
                                                                       "Toolbox talk held with the crew.", "Guard rails installed."]) if resolved else "",
                                                resolved_at=self._at(day + timedelta(days=1)) if resolved else None)
            ts = self._at(day)
            SafetyIncident.objects.filter(pk=inc.pk).update(created_at=ts)
            label = dict(SafetyIncident.KINDS)[kind]
            acts.append((ts, o, rep, "incident_reported", f"{label} ({sev}) reported by {rep.full_name}"))
            if resolved:
                acts.append((ts + timedelta(days=1), o, o.owner, "incident_resolved", f"Resolved a {kind.replace('_', ' ')} report"))
            if o.owner == boss and day > today - timedelta(days=7):
                notes.append((ts, boss, "incident", f"{label} reported at {o.name}", desc[:200], "/main-menu/safety", resolved))

        # disputes, rejections, budgets, payments --------------------------------------
        boss_hist = [h for h in hmade if h.organization_id in {o.pk for o in boss_sites}]
        for h in rnd.sample(boss_hist, min(4, len(boss_hist))):
            d = GigDispute.objects.create(history=h, raised_by=h.worker, reason=rnd.choice(
                ["The days worked were 10, not 8.", "Rating does not match the work done.", "Pay agreed was higher than recorded."]))
            if rnd.random() < 0.5:
                GigDispute.objects.filter(pk=d.pk).update(status="resolved", resolution="Records corrected after a call with the site.",
                                                          resolved_at=timezone.now() - timedelta(days=rnd.randint(1, 10)))
        for _ in range(8):
            o, w = rnd.choice(boss_sites), rnd.choice(fundis)
            ts = self._at(today - timedelta(days=rnd.randint(1, 50)))
            acts.append((ts, o, boss, "gig_rejected", f"Rejected {w.full_name}'s gig: " + rnd.choice(
                ["not on site these dates", "wrong site", "duration is wrong, please log 3 days", "logged twice"])))
        for o in org_list:
            spent = sum((g.amount_paid for g in made if g.organization_id == o.pk), Decimal(0)) + \
                sum((h.amount_paid for h in hmade if h.organization_id == o.pk), Decimal(0))
            budget = (spent / Decimal(rnd.choice([0.45, 0.6, 0.72, 0.85, 0.93, 1.08]))).quantize(Decimal("1000"))
            Organization.objects.filter(pk=o.pk).update(labour_budget=max(budget, Decimal(50000)))
            acts.append((self._at(start + timedelta(days=rnd.randint(0, 10))), o, o.owner, "budget_set",
                         f"Labour budget for {o.name} set to KSh {max(budget, Decimal(50000)):,.0f}"))
        payments = []
        for i in range(30):
            ts = self._at(today - timedelta(days=rnd.randint(0, 90)))
            payments.append(MpesaNewTransaction(
                user=boss, phone_number="2547" + str(rnd.randint(10000000, 99999999)), amount=Decimal(rnd.choice([2400, 3600, 5200, 7500, 9000, 12000, 18000, 24000])),
                mpesa_receipt_number=f"T{rnd.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rnd.randint(10, 99)}SC{rnd.randint(100000, 999999)}",
                transaction_date=ts, merchant_request_id=f"showcase-m{i}", checkout_request_id=f"showcase-c{i}",
                result_code=0, result_desc="The service request is processed successfully.", raw_callback={"showcase": True}))
        MpesaNewTransaction.objects.bulk_create(payments)
        for pmt in payments:
            if pmt.transaction_date > timezone.now() - timedelta(days=14):
                notes.append((pmt.transaction_date, boss, "payment", f"M-Pesa payment of KSh {pmt.amount:,.0f} confirmed",
                              f"Receipt {pmt.mpesa_receipt_number}", "/main-menu/MPESA-Payments", True))

        # notifications and activity ----------------------------------------------------
        now = timezone.now()
        notes += [
            (now - timedelta(days=20), me, "id_approved", "Your ID is verified", "+20 points added to your credit score.", "/main-menu/credit-score", True),
            (now - timedelta(hours=6), me, "job_alert", f"New job: {open_posts[0].title}", f"{open_posts[0].organization.name} · {open_posts[0].county}", "/main-menu/search-gigs", False),
            (now - timedelta(days=1, hours=2), me, "application_accepted", f"{open_posts[1].organization.name} accepted you", f"For '{open_posts[1].title}'.", "/main-menu/search-gigs", True),
        ]
        nrows = [Notification(user=u, kind=k, title=t[:200], body=(b or "")[:300], link=l, is_read=r) for ts, u, k, t, b, l, r in notes if ts <= now]
        nmade = Notification.objects.bulk_create(nrows)
        for n, src in zip(nmade, [x for x in notes if x[0] <= now]):
            n.created_at = src[0]
        Notification.objects.bulk_update(nmade, ["created_at"], batch_size=500)

        arows, ats = [], []
        for ts, o, actor, action, summary in acts:
            if ts <= now:
                arows.append(ActivityLog(actor=actor, organization=o, action=action, summary=summary[:300]))
                ats.append(ts)
        amade2 = ActivityLog.objects.bulk_create(arows, batch_size=1000)
        for a, ts in zip(amade2, ats):
            a.created_at = ts
        ActivityLog.objects.bulk_update(amade2, ["created_at"], batch_size=1000)

        self.stdout.write(self.style.SUCCESS(
            f"Showcase: {len(CONTRACTORS) + 1} contractors, {len(org_list)} sites, {len(workers)} fundis, "
            f"{len(made)} open gigs, {len(hmade)} completed, {len(checkins)} check-ins, {len(ratings)} ratings, "
            f"{len(site_ratings)} site ratings, {len(POSTS)} job posts, {len(amade)} applications, {len(INCIDENTS)} incidents, "
            f"{len(payments)} payments, {len(nmade)} notifications, {len(amade2)} activity entries. "
            f"Showcase logins use password {DEMO_PASSWORD}."))
