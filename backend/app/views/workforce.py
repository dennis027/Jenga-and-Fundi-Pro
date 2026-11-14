"""Workforce features: inbox, work profile, job alerts, saved posts, invitations, crew, two-way
ratings, safety incidents, bulk verify / reject, attendance, payroll, budgets, activity log,
statements and personal-data export / account deletion."""
import csv
import io
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..inbox import log, push
from ..models import (ActivityLog, CrewMember, Gig, GigHistory, GigRating, GigsAvailable, JobAlert, JobApplication,
                      Notification, Organization, SafetyIncident, SavedPost, SiteCheckIn, SiteRating)
from ..permissions import CONTRACTOR, FUNDI, IsContractorOrStaff, owns_organization
from ..serializers import GigsAvailableSerializer
from .gigs import verify_gig
from .hiring import _app_row, close_if_filled

User = get_user_model()


def _bad(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": msg}, status=code)


def _name(u):
    return (u.full_name or u.username) if u else ""


def _date_range(request, default_days=30):
    """?from=YYYY-MM-DD&to=YYYY-MM-DD (inclusive); defaults to the last `default_days` days."""
    today = timezone.localdate()
    try:
        end = date.fromisoformat(request.query_params.get("to")) if request.query_params.get("to") else today
        start = (date.fromisoformat(request.query_params.get("from")) if request.query_params.get("from")
                 else end - timedelta(days=default_days - 1))
    except ValueError:
        return None, None
    if start > end or (end - start).days > 366:
        return None, None
    return start, end


def _csv(filename, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        # neutralise spreadsheet formulas in user-entered text
        w.writerow([("'" + c) if isinstance(c, str) and c[:1] in ("=", "+", "-", "@") else c for c in r])
    resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _my_orgs(user, org_id=None):
    qs = Organization.objects.all() if user.is_staff else Organization.objects.filter(owner=user)
    if org_id:
        qs = qs.filter(pk=org_id)
    return qs


def _days(value, unit):
    return (value or 0) * (7 if unit == "weeks" else 1)


# --------------------------------------------------------------------------- inbox (1)

def _note(n):
    return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
            "is_read": n.is_read, "created_at": n.created_at}


class NotificationListView(APIView):
    """GET: latest 50 notifications and the unread count."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user)
        return Response({"unread": qs.filter(is_read=False).count(), "items": [_note(n) for n in qs[:50]]})


class NotificationReadView(APIView):
    """POST {"ids": [..]} marks those read; with no ids marks everything read."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        qs = Notification.objects.filter(user=request.user, is_read=False)
        ids = request.data.get("ids")
        if ids:
            qs = qs.filter(id__in=[i for i in ids if str(i).isdigit()])
        return Response({"marked": qs.update(is_read=True)})


# --------------------------------------------------------------------------- work profile + availability (2, 3)

class WorkProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["skills", "years_experience", "day_rate", "bio", "is_available", "available_from"]

    def validate_skills(self, v):
        parts = [p.strip()[:40] for p in v.split(",") if p.strip()]
        return ", ".join(dict.fromkeys(parts))[:300]

    def validate_years_experience(self, v):
        if v is not None and v > 60:
            raise serializers.ValidationError("Enter 0 to 60 years.")
        return v

    def validate_day_rate(self, v):
        if v is not None and v > 100000:
            raise serializers.ValidationError("That day rate looks too high.")
        return v

    def validate(self, attrs):
        if attrs.get("is_available") is True:
            attrs["available_from"] = None
        return attrs


class WorkProfileView(APIView):
    """GET / PATCH the signed-in fundi's skills, experience, day rate, bio and availability."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(WorkProfileSerializer(request.user).data)

    def patch(self, request):
        s = WorkProfileSerializer(request.user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)


def _worker_card(w, contractor=None):
    v = w.current_verification
    agg = GigRating.objects.filter(history__worker=w).aggregate(avg=Avg("stars"), n=Count("id"))
    card = {"username": w.username, "name": _name(w), "county": w.county, "ward": w.ward,
            "credit_score": w.credit_score or 0, "id_verified": bool(v and v.status == "approved"),
            "skills": [s.strip() for s in (w.skills or "").split(",") if s.strip()],
            "years_experience": w.years_experience, "day_rate": w.day_rate, "bio": w.bio,
            "is_available": w.is_available, "available_from": w.available_from,
            "completed_gigs": GigHistory.objects.filter(worker=w, is_verified=True).count(),
            "rating_avg": round(agg["avg"], 1) if agg["avg"] else None, "ratings_count": agg["n"]}
    if contractor is not None:
        card["in_crew"] = CrewMember.objects.filter(contractor=contractor, worker=w).exists()
    return card


class AvailableWorkersView(APIView):
    """GET ?trade=&county=&available=1: find fundis by skill and area (contractors)."""
    permission_classes = [IsContractorOrStaff]

    def get(self, request):
        qs = User.objects.filter(account_type=FUNDI, is_active=True).select_related("current_verification")
        trade, county = request.query_params.get("trade", "").strip(), request.query_params.get("county", "").strip()
        if trade:
            qs = qs.filter(skills__icontains=trade)
        if county:
            qs = qs.filter(county__iexact=county)
        if request.query_params.get("available"):
            today = timezone.localdate()
            qs = qs.filter(Q(is_available=True) | Q(available_from__lte=today))
        qs = qs.order_by("-credit_score", "id")[:50]
        return Response([_worker_card(w, request.user) for w in qs])


# --------------------------------------------------------------------------- job alerts (4)

class JobAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobAlert
        fields = ["id", "keyword", "county", "sms", "created_at"]

    def validate(self, attrs):
        if not (attrs.get("keyword", "").strip() or attrs.get("county", "").strip()):
            raise serializers.ValidationError("Give a trade/keyword, a county, or both.")
        return attrs


class JobAlertListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(JobAlertSerializer(JobAlert.objects.filter(user=request.user), many=True).data)

    def post(self, request):
        if request.user.account_type != FUNDI:
            return _bad("Only fundi accounts can set job alerts.", status.HTTP_403_FORBIDDEN)
        if JobAlert.objects.filter(user=request.user).count() >= 10:
            return _bad("You can keep up to 10 job alerts.")
        s = JobAlertSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save(user=request.user, keyword=s.validated_data.get("keyword", "").strip(),
               county=s.validated_data.get("county", "").strip())
        return Response(s.data, status=status.HTTP_201_CREATED)


class JobAlertDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        deleted, _ = JobAlert.objects.filter(pk=pk, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT if deleted else status.HTTP_404_NOT_FOUND)


# --------------------------------------------------------------------------- saved posts (5)

class SavePostView(APIView):
    """POST toggles saving a job post. Returns {"saved": bool}."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = GigsAvailable.objects.filter(pk=pk).first()
        if not post:
            return _bad("Not found.", status.HTTP_404_NOT_FOUND)
        obj, created = SavedPost.objects.get_or_create(user=request.user, post=post)
        if not created:
            obj.delete()
        return Response({"saved": created})


class SavedPostsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        posts = [s.post for s in SavedPost.objects.filter(user=request.user).select_related("post__organization")]
        return Response(GigsAvailableSerializer(posts, many=True, context={"request": request}).data)


# --------------------------------------------------------------------------- withdraw / invitations (6, 16)

class WithdrawApplicationView(APIView):
    """POST: the fundi withdraws a pending application."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        app = JobApplication.objects.select_related("post__organization").filter(pk=pk, worker=request.user).first()
        if not app:
            return _bad("Not found.", status.HTTP_404_NOT_FOUND)
        if app.status != "pending":
            return _bad(f"You can only withdraw a pending application (this one is {app.status}).")
        app.status, app.decided_at = "withdrawn", timezone.now()
        app.save(update_fields=["status", "decided_at"])
        return Response(_app_row(app))


class InviteWorkerView(APIView):
    """POST {"username": "..."}: invite a fundi to one of your open job posts."""
    permission_classes = [IsContractorOrStaff]

    def post(self, request, pk):
        post = GigsAvailable.objects.select_related("organization").filter(pk=pk).first()
        if not post or not owns_organization(request.user, post.organization):
            return _bad("Not found.", status.HTTP_404_NOT_FOUND)
        if not post.is_open:
            return _bad("This job post is closed. Reopen it first.")
        worker = User.objects.filter(username=request.data.get("username"), account_type=FUNDI, is_active=True).first()
        if not worker:
            return _bad("Worker not found.", status.HTTP_404_NOT_FOUND)
        app, created = JobApplication.objects.get_or_create(post=post, worker=worker, defaults={"status": "invited"})
        if not created:
            if app.status in ("accepted", "pending", "invited"):
                return Response(_app_row(app, with_worker=True))
            app.status, app.decided_at = "invited", None
            app.save(update_fields=["status", "decided_at"])
        push(worker, "invitation", f"{post.organization.name} invited you", f"Job: '{post.title[:80]}'. Accept or decline.",
             "/main-menu/search-gigs",
             sms_text=f"{post.organization.name} invited you for '{post.title[:60]}'. Open Fundi Pro to accept.")
        log(request.user, post.organization, "invited", f"Invited {_name(worker)} to '{post.title}'")
        return Response(_app_row(app, with_worker=True), status=status.HTTP_201_CREATED)


class RespondInvitationView(APIView):
    """POST {"accept": true|false}: the fundi answers an invitation."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        app = JobApplication.objects.select_related("post__organization__owner").filter(pk=pk, worker=request.user).first()
        if not app:
            return _bad("Not found.", status.HTTP_404_NOT_FOUND)
        if app.status != "invited":
            return _bad("This invitation has already been answered.")
        accept = bool(request.data.get("accept"))
        post = app.post
        if accept and not post.is_open:
            return _bad("Sorry, this job has been filled.")
        app.status, app.decided_at = ("accepted" if accept else "declined"), timezone.now()
        app.save(update_fields=["status", "decided_at"])
        who = _name(request.user)
        if accept:
            push(post.organization.owner, "invitation_accepted", f"{who} accepted your invitation",
                 f"For '{post.title[:80]}'. Call them to agree the start.", "/main-menu/job-posts",
                 sms_text=f"{who} accepted your invitation for '{post.title[:60]}'.")
            log(request.user, post.organization, "hired", f"{who} accepted the invitation for '{post.title}'")
            close_if_filled(post)
        else:
            push(post.organization.owner, "invitation_declined", f"{who} declined your invitation",
                 f"For '{post.title[:80]}'.", "/main-menu/job-posts")
        return Response(_app_row(app))


class ToggleJobPostView(APIView):
    """POST {"is_open"?: bool, "positions"?: int}: close/reopen a job post or change its positions."""
    permission_classes = [IsContractorOrStaff]

    def post(self, request, pk):
        post = GigsAvailable.objects.select_related("organization").filter(pk=pk).first()
        if not post or not owns_organization(request.user, post.organization):
            return _bad("Not found.", status.HTTP_404_NOT_FOUND)
        if "positions" in request.data:
            try:
                n = int(request.data["positions"])
            except (TypeError, ValueError):
                return _bad("positions must be a number.")
            if not 1 <= n <= 50:
                return _bad("positions must be between 1 and 50.")
            post.positions = n
        post.is_open = bool(request.data["is_open"]) if "is_open" in request.data else not post.is_open
        post.save(update_fields=["positions", "is_open"])
        log(request.user, post.organization, "job_reopened" if post.is_open else "job_closed",
            f"{'Reopened' if post.is_open else 'Closed'} job '{post.title}'")
        return Response(GigsAvailableSerializer(post, context={"request": request}).data)


# --------------------------------------------------------------------------- two-way ratings (8)

class FundiCompletedView(APIView):
    """GET: the fundi's completed gigs, with whether they've rated the site and the site's rating of them."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (GigHistory.objects.filter(worker=request.user).select_related("organization", "job_type")
              .order_by("-start_date"))
        out = []
        for h in qs:
            sr = getattr(h, "site_rating", None)
            gr = getattr(h, "rating", None)
            out.append({"id": h.id, "site": h.organization.name if h.organization_id else h.client_name,
                        "trade": h.job_type.name if h.job_type_id else "", "start_date": h.start_date,
                        "duration_value": h.duration_value, "duration_unit": h.duration_unit,
                        "amount_paid": h.amount_paid, "is_verified": h.is_verified,
                        "my_site_rating": {"stars": sr.stars, "paid_on_time": sr.paid_on_time} if sr else None,
                        "contractor_rating": gr.stars if gr else None})
        return Response(out)


class RateSiteView(APIView):
    """POST {"stars": 1-5, "paid_on_time": bool|null, "comment": ""}: the worker rates the site (once)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, history_id):
        h = GigHistory.objects.select_related("organization").filter(pk=history_id, worker=request.user).first()
        if not h or not h.organization_id:
            return _bad("Not found.", status.HTTP_404_NOT_FOUND)
        if not h.is_verified:
            return _bad("Only verified work can be rated.")
        if SiteRating.objects.filter(history=h).exists():
            return _bad("You have already rated this site for this gig.")
        try:
            stars = int(request.data.get("stars"))
        except (TypeError, ValueError):
            stars = 0
        if not 1 <= stars <= 5:
            return _bad("stars must be 1 to 5.")
        pot = request.data.get("paid_on_time")
        r = SiteRating.objects.create(history=h, organization=h.organization, rated_by=request.user, stars=stars,
                                      paid_on_time=None if pot is None else bool(pot),
                                      comment=(request.data.get("comment") or "")[:300])
        push(h.organization.owner, "site_rated", f"{_name(request.user)} rated {h.organization.name} {stars}★",
             r.comment[:200], "/main-menu/add-sites")
        return Response({"id": r.id, "stars": r.stars, "paid_on_time": r.paid_on_time}, status=status.HTTP_201_CREATED)


class SiteRatingsView(APIView):
    """GET: ratings your sites received from workers (contractor)."""
    permission_classes = [IsContractorOrStaff]

    def get(self, request):
        out = []
        for org in _my_orgs(request.user):
            rs = org.site_ratings.select_related("rated_by").order_by("-created_at")
            agg = rs.aggregate(avg=Avg("stars"), n=Count("id"))
            paid = rs.exclude(paid_on_time=None)
            out.append({"organization": org.id, "name": org.name,
                        "avg": round(agg["avg"], 1) if agg["avg"] else None, "count": agg["n"],
                        "paid_on_time_pct": round(100 * paid.filter(paid_on_time=True).count() / paid.count())
                        if paid.exists() else None,
                        "recent": [{"stars": r.stars, "comment": r.comment, "by": _name(r.rated_by),
                                    "paid_on_time": r.paid_on_time, "created_at": r.created_at} for r in rs[:5]]})
        return Response(out)


# --------------------------------------------------------------------------- safety incidents (12)

def _incident(i):
    return {"id": i.id, "organization": i.organization_id, "site": i.organization.name, "kind": i.kind,
            "severity": i.severity, "description": i.description, "occurred_on": i.occurred_on,
            "reported_by": _name(i.reported_by), "is_resolved": i.is_resolved, "resolution": i.resolution,
            "resolved_at": i.resolved_at, "created_at": i.created_at}


class IncidentListCreateView(APIView):
    """GET: incidents you reported, plus (contractors) those at your sites. POST: report one."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        qs = SafetyIncident.objects.select_related("organization", "reported_by")
        if not u.is_staff:
            qs = qs.filter(Q(reported_by=u) | Q(organization__owner=u))
        return Response([_incident(i) for i in qs[:200]])

    def post(self, request):
        u, d = request.user, request.data
        org = Organization.objects.filter(pk=d.get("organization")).first()
        if not org:
            return _bad("Choose a site.")
        worked_there = (Gig.objects.filter(worker=u, organization=org).exists()
                        or GigHistory.objects.filter(worker=u, organization=org).exists())
        if not (owns_organization(u, org) or worked_there):
            return _bad("You can only report incidents at sites you work at.", status.HTTP_403_FORBIDDEN)
        kind, sev = d.get("kind"), d.get("severity") or "low"
        if kind not in dict(SafetyIncident.KINDS) or sev not in dict(SafetyIncident.SEVERITY):
            return _bad("Choose what happened and how serious it is.")
        desc = (d.get("description") or "").strip()
        if len(desc) < 10:
            return _bad("Describe what happened (at least 10 characters).")
        try:
            occurred = date.fromisoformat(d.get("occurred_on")) if d.get("occurred_on") else timezone.localdate()
        except ValueError:
            return _bad("Invalid date.")
        if occurred > timezone.localdate():
            return _bad("The date cannot be in the future.")
        i = SafetyIncident.objects.create(organization=org, reported_by=u, kind=kind, severity=sev,
                                          description=desc[:1000], occurred_on=occurred)
        label = dict(SafetyIncident.KINDS)[kind]
        if org.owner_id != u.id:
            push(org.owner, "incident", f"{label} reported at {org.name}", desc[:200], "/main-menu/safety",
                 sms_text=f"{sev.upper()} {label.lower()} reported at {org.name} by {_name(u)}. Check Jenga Pro."
                 if sev == "high" else None)
        log(u, org, "incident_reported", f"{label} ({sev}) reported by {_name(u)}")
        return Response(_incident(i), status=status.HTTP_201_CREATED)


class ResolveIncidentView(APIView):
    """POST {"resolution": "..."}: the site's contractor marks an incident resolved."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        i = SafetyIncident.objects.select_related("organization", "reported_by").filter(pk=pk).first()
        if not i or not owns_organization(request.user, i.organization):
            return _bad("Not found.", status.HTTP_404_NOT_FOUND)
        i.is_resolved, i.resolution, i.resolved_at = True, (request.data.get("resolution") or "")[:500], timezone.now()
        i.save(update_fields=["is_resolved", "resolution", "resolved_at"])
        if i.reported_by_id != request.user.id:
            push(i.reported_by, "incident_resolved", f"Your report at {i.organization.name} was resolved",
                 i.resolution[:200], "/main-menu/safety")
        log(request.user, i.organization, "incident_resolved", f"Resolved a {i.kind.replace('_', ' ')} report")
        return Response(_incident(i))


# --------------------------------------------------------------------------- reject + bulk verify (9, 10)

class RejectGigView(APIView):
    """POST {"reason": "..."}: the site's contractor rejects an unverified gig (it's removed; the worker is told why)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, gig_id):
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 5:
            return _bad("Give the worker a reason (at least 5 characters).")
        with transaction.atomic():
            gig = Gig.objects.select_for_update().select_related("organization", "job_type", "worker").filter(pk=gig_id).first()
            if not gig or not owns_organization(request.user, gig.organization):
                return _bad("Not found.", status.HTTP_404_NOT_FOUND)
            if gig.is_verified:
                return _bad("This gig is already verified. Raise a dispute instead.")
            worker, org, trade = gig.worker, gig.organization, gig.job_type.name if gig.job_type_id else "gig"
            gig.delete()
        push(worker, "gig_rejected", f"{org.name} did not verify your {trade}", f"Reason: {reason[:240]}",
             "/main-menu/gig-summary",
             sms_text=f"{org.name} did not verify your {trade} gig. Reason: {reason[:80]}")
        log(request.user, org, "gig_rejected", f"Rejected {_name(worker)}'s {trade} gig: {reason[:120]}")
        return Response({"rejected": gig_id})


class BulkVerifyView(APIView):
    """POST {"ids": [..]} (max 100): verify several gigs; returns per-gig results."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids or len(ids) > 100:
            return _bad("Send 1 to 100 gig ids.")
        results = []
        for gid in ids:
            try:
                gid = int(gid)
            except (TypeError, ValueError):
                results.append({"id": gid, "ok": False, "detail": "bad id"})
                continue
            code, body = verify_gig(request.user, gid)
            results.append({"id": gid, "ok": code == 200, "detail": body.get("message") or body.get("detail")})
        return Response({"verified": sum(r["ok"] for r in results), "results": results})


# --------------------------------------------------------------------------- crew (15)

class CrewListView(APIView):
    """GET: your crew. POST {"username", "note"?}: add a worker."""
    permission_classes = [IsContractorOrStaff]

    def get(self, request):
        crew = CrewMember.objects.filter(contractor=request.user).select_related("worker__current_verification")
        return Response([{**_worker_card(c.worker), "note": c.note, "added_at": c.created_at} for c in crew])

    def post(self, request):
        w = User.objects.filter(username=request.data.get("username"), account_type=FUNDI).first()
        if not w:
            return _bad("Worker not found.", status.HTTP_404_NOT_FOUND)
        c, created = CrewMember.objects.get_or_create(contractor=request.user, worker=w,
                                                      defaults={"note": (request.data.get("note") or "")[:200]})
        return Response({**_worker_card(w), "note": c.note}, status=status.HTTP_201_CREATED if created else 200)


class CrewDeleteView(APIView):
    permission_classes = [IsContractorOrStaff]

    def delete(self, request, username):
        deleted, _ = CrewMember.objects.filter(contractor=request.user, worker__username=username).delete()
        return Response(status=status.HTTP_204_NO_CONTENT if deleted else status.HTTP_404_NOT_FOUND)


# --------------------------------------------------------------------------- attendance / payroll / budgets (13, 14, 15)

class AttendanceView(APIView):
    """GET ?from&to&org[&csv=1]: daily site check-ins at your sites."""
    permission_classes = [IsContractorOrStaff]

    def get(self, request):
        start, end = _date_range(request)
        if not start:
            return _bad("Invalid date range (max 366 days).")
        orgs = _my_orgs(request.user, request.query_params.get("org"))
        qs = (SiteCheckIn.objects.filter(gig__organization__in=orgs, date__range=(start, end))
              .select_related("worker", "gig__organization", "gig__job_type").order_by("-date", "gig__organization__name"))
        rows = [{"date": c.date, "worker": _name(c.worker), "username": c.worker.username, "phone": c.worker.phone,
                 "site": c.gig.organization.name, "trade": c.gig.job_type.name if c.gig.job_type_id else "",
                 "checked_in_at": timezone.localtime(c.checked_in_at).strftime("%H:%M")} for c in qs]
        if request.query_params.get("csv"):
            return _csv(f"attendance_{start}_{end}.csv", ["Date", "Worker", "Username", "Phone", "Site", "Trade", "Checked in"],
                        [[r["date"].isoformat(), r["worker"], r["username"], r["phone"] or "", r["site"], r["trade"],
                          r["checked_in_at"]] for r in rows])
        return Response({"from": start, "to": end, "rows": rows,
                         "workers": len({r["username"] for r in rows}), "worker_days": len(rows)})


class PayrollView(APIView):
    """GET ?from&to&org[&csv=1]: per worker per site — days checked in, gig days and agreed pay for gigs starting in range."""
    permission_classes = [IsContractorOrStaff]

    def get(self, request):
        start, end = _date_range(request, default_days=7)
        if not start:
            return _bad("Invalid date range (max 366 days).")
        orgs = list(_my_orgs(request.user, request.query_params.get("org")))
        lines = {}

        def line(worker, org):
            return lines.setdefault((worker.id, org.id), {
                "worker": _name(worker), "username": worker.username, "phone": worker.phone, "site": org.name,
                "organization": org.id, "gigs": 0, "gig_days": 0, "days_on_site": 0, "agreed_pay": Decimal("0"),
                "verified": True})

        for g in Gig.objects.filter(organization__in=orgs, start_date__range=(start, end)).select_related("worker", "organization"):
            ln = line(g.worker, g.organization)
            ln["gigs"] += 1
            ln["gig_days"] += _days(g.duration_value, g.duration_unit)
            ln["agreed_pay"] += g.amount_paid or 0
            ln["verified"] = ln["verified"] and g.is_verified
        for h in GigHistory.objects.filter(organization__in=orgs, start_date__range=(start, end)).select_related("worker", "organization"):
            ln = line(h.worker, h.organization)
            ln["gigs"] += 1
            ln["gig_days"] += _days(h.duration_value, h.duration_unit)
            ln["agreed_pay"] += h.amount_paid or 0
        for row in (SiteCheckIn.objects.filter(gig__organization__in=orgs, date__range=(start, end))
                    .values("worker", "gig__organization").annotate(n=Count("date", distinct=True))):
            w = User.objects.get(pk=row["worker"])
            o = next(o for o in orgs if o.id == row["gig__organization"])
            line(w, o)["days_on_site"] += row["n"]
        rows = sorted(lines.values(), key=lambda r: (r["site"], r["worker"]))
        total = sum((r["agreed_pay"] for r in rows), Decimal("0"))
        if request.query_params.get("csv"):
            return _csv(f"payroll_{start}_{end}.csv",
                        ["Worker", "Username", "Phone", "Site", "Gigs", "Gig days", "Days checked in", "Agreed pay (KSh)"],
                        [[r["worker"], r["username"], r["phone"] or "", r["site"], r["gigs"], r["gig_days"],
                          r["days_on_site"], f"{r['agreed_pay']:.2f}"] for r in rows] + [["TOTAL", "", "", "", "", "", "", f"{total:.2f}"]])
        return Response({"from": start, "to": end, "rows": rows, "total": total})


class BudgetsView(APIView):
    """GET: each site's labour budget against agreed pay so far (open + completed gigs).
    POST {"organization", "labour_budget"}: set a budget (null clears it)."""
    permission_classes = [IsContractorOrStaff]

    def get(self, request):
        out = []
        for org in _my_orgs(request.user).order_by("name"):
            open_pay = org.gigs.aggregate(s=Sum("amount_paid"))["s"] or Decimal("0")
            done_pay = org.gig_histories.aggregate(s=Sum("amount_paid"))["s"] or Decimal("0")
            spent = open_pay + done_pay
            budget = org.labour_budget
            out.append({"organization": org.id, "name": org.name, "is_active": org.is_active, "budget": budget,
                        "spent": spent, "committed_open": open_pay, "paid_completed": done_pay,
                        "pct": round(float(spent) * 100 / float(budget)) if budget else None,
                        "remaining": (budget - spent) if budget is not None else None})
        return Response(out)

    def post(self, request):
        org = _my_orgs(request.user, request.data.get("organization")).first()
        if not org:
            return _bad("Not found.", status.HTTP_404_NOT_FOUND)
        raw = request.data.get("labour_budget")
        try:
            org.labour_budget = None if raw in (None, "") else Decimal(str(raw))
        except Exception:
            return _bad("Enter an amount in KSh.")
        if org.labour_budget is not None and not (0 <= org.labour_budget < Decimal("10000000000")):
            return _bad("Enter an amount in KSh.")
        org.save(update_fields=["labour_budget"])
        log(request.user, org, "budget_set", f"Labour budget for {org.name} set to "
                                             + (f"KSh {org.labour_budget:,.0f}" if org.labour_budget is not None else "none"))
        return Response({"organization": org.id, "labour_budget": org.labour_budget})


# --------------------------------------------------------------------------- activity log (18)

class ActivityView(APIView):
    """GET ?org=: the latest 100 events at your sites."""
    permission_classes = [IsContractorOrStaff]

    def get(self, request):
        qs = ActivityLog.objects.select_related("actor", "organization")
        if not request.user.is_staff:
            qs = qs.filter(Q(organization__owner=request.user) | Q(organization__isnull=True, actor=request.user))
        if request.query_params.get("org"):
            qs = qs.filter(organization_id=request.query_params["org"])
        return Response([{"id": a.id, "action": a.action, "summary": a.summary, "actor": _name(a.actor),
                          "site": a.organization.name if a.organization_id else None, "created_at": a.created_at}
                         for a in qs[:100]])


# --------------------------------------------------------------------------- earnings statement (7)

class FundiStatementView(APIView):
    """GET ?from&to[&csv=1]: the fundi's work and agreed pay in a period (for lenders, SACCOs, landlords)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start, end = _date_range(request, default_days=90)
        if not start:
            return _bad("Invalid date range (max 366 days).")
        u = request.user
        rows = []
        for g in Gig.objects.filter(worker=u, start_date__range=(start, end)).select_related("organization", "job_type"):
            rows.append({"date": g.start_date, "site": g.organization.name, "trade": g.job_type.name if g.job_type_id else "",
                         "days": _days(g.duration_value, g.duration_unit), "amount": g.amount_paid,
                         "status": "verified" if g.is_verified else "pending"})
        for h in GigHistory.objects.filter(worker=u, start_date__range=(start, end)).select_related("organization", "job_type"):
            rows.append({"date": h.start_date, "site": h.organization.name if h.organization_id else h.client_name,
                         "trade": h.job_type.name if h.job_type_id else "", "days": _days(h.duration_value, h.duration_unit),
                         "amount": h.amount_paid, "status": "completed" if h.is_verified else "unverified"})
        rows.sort(key=lambda r: r["date"])
        counted = [r for r in rows if r["status"] in ("verified", "completed")]
        summary = {"gigs": len(rows), "verified_gigs": len(counted), "verified_days": sum(r["days"] for r in counted),
                   "verified_pay": sum((r["amount"] or 0 for r in counted), Decimal("0"))}
        if request.query_params.get("csv"):
            body = [[r["date"].isoformat(), r["site"], r["trade"], r["days"], f"{r['amount'] or 0:.2f}", r["status"]] for r in rows]
            body += [[], ["Name", _name(u)], ["Credit score", u.credit_score or 0],
                     ["Verified gigs", summary["verified_gigs"]], ["Verified days", summary["verified_days"]],
                     ["Verified agreed pay (KSh)", f"{summary['verified_pay']:.2f}"],
                     ["Generated", timezone.localtime().strftime("%Y-%m-%d %H:%M")]]
            return _csv(f"fundi_statement_{start}_{end}.csv", ["Start date", "Site", "Trade", "Days", "Agreed pay (KSh)", "Status"], body)
        return Response({"from": start, "to": end, "rows": rows, "summary": summary})


# --------------------------------------------------------------------------- your data (19, 20)

class ExportMyDataView(APIView):
    """GET: everything we hold about you, as a JSON download (Kenya Data Protection Act, s.26)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        import json
        from django.core.serializers.json import DjangoJSONEncoder
        from ..models import CreditScoreHistory, MpesaNewTransaction, VerificationRequest
        u = request.user
        data = {
            "exported_at": timezone.now(),
            "account": {f: getattr(u, f) for f in ("username", "email", "full_name", "phone", "national_id", "county",
                                                    "constituency", "ward", "account_type", "credit_score", "date_joined",
                                                    "skills", "years_experience", "day_rate", "bio", "is_available")},
            "gigs": list(Gig.objects.filter(worker=u).values("start_date", "duration_value", "duration_unit",
                                                             "organization__name", "job_type__name", "amount_paid", "is_verified")),
            "completed_gigs": list(GigHistory.objects.filter(worker=u).values("start_date", "duration_value", "duration_unit",
                                                                              "organization__name", "job_type__name", "amount_paid")),
            "credit_score_history": list(CreditScoreHistory.objects.filter(user=u).values("action", "change", "new_score", "timestamp")),
            "id_verifications": list(VerificationRequest.objects.filter(user=u).values("status", "rejection_reason", "created_at")),
            "applications": list(JobApplication.objects.filter(worker=u).values("post__title", "status", "message", "created_at")),
            "check_ins": list(SiteCheckIn.objects.filter(worker=u).values("date", "gig__organization__name")),
            "ratings_received": list(GigRating.objects.filter(history__worker=u).values("stars", "comment", "created_at")),
            "site_ratings_given": list(SiteRating.objects.filter(rated_by=u).values("organization__name", "stars", "comment")),
            "job_alerts": list(JobAlert.objects.filter(user=u).values("keyword", "county", "sms")),
            "sites": list(Organization.objects.filter(owner=u).values("name", "county", "constituency", "ward", "created_at")),
            "mpesa_payments": list(MpesaNewTransaction.objects.filter(user=u).values("amount", "mpesa_receipt_number", "transaction_date")),
            "notifications": list(Notification.objects.filter(user=u).values("title", "body", "created_at")),
        }
        resp = HttpResponse(json.dumps(data, cls=DjangoJSONEncoder, indent=2), content_type="application/json")
        resp["Content-Disposition"] = f'attachment; filename="my-data-{u.username}.json"'
        return resp


class DeleteAccountView(APIView):
    """POST {"password": "..."}: close the account. Personal details are erased; verified work stays
    on contractors' records under "Deleted user" so their books still add up."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        u = request.user
        if not u.check_password(request.data.get("password") or ""):
            return _bad("Password is incorrect.", status.HTTP_403_FORBIDDEN)
        if u.is_staff:
            return _bad("Staff accounts are closed by an administrator.", status.HTTP_403_FORBIDDEN)
        with transaction.atomic():
            for m in (Notification, JobAlert, SavedPost):
                m.objects.filter(user=u).delete()
            CrewMember.objects.filter(Q(contractor=u) | Q(worker=u)).delete()
            JobApplication.objects.filter(worker=u, status__in=("pending", "invited")).delete()
            Organization.objects.filter(owner=u).update(is_active=False)
            if u.profile_pic:
                u.profile_pic.delete(save=False)
            u.username, u.email = f"deleted-{u.pk}", f"deleted-{u.pk}@deleted.invalid"
            u.full_name, u.first_name, u.last_name = "Deleted user", "", ""
            u.phone, u.national_id, u.bio, u.skills = None, "", "", ""
            u.county = u.constituency = u.ward = ""
            u.day_rate = u.years_experience = None
            u.is_active, u.is_available = False, False
            u.set_unusable_password()
            u.save()
        try:  # sign out everywhere
            from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
            for t in OutstandingToken.objects.filter(user=u):
                BlacklistedToken.objects.get_or_create(token=t)
        except Exception:
            pass
        return Response({"deleted": True})
