"""Job applications (hiring from job posts) and daily site check-ins."""
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Gig, GigHistory, GigsAvailable, JobApplication, SiteCheckIn
from ..permissions import CONTRACTOR, FUNDI, owns_organization


def _app_row(a, with_worker=False):
    row = {"id": a.id, "post": a.post_id, "post_title": a.post.title, "site": a.post.organization.name,
           "site_phone": a.post.organization.phone_number, "status": a.status, "message": a.message,
           "created_at": a.created_at, "decided_at": a.decided_at}
    if with_worker:
        w = a.worker
        v = w.current_verification
        row["worker"] = {"username": w.username, "name": w.full_name or w.username, "phone": w.phone,
                         "credit_score": w.credit_score or 0, "id_verified": bool(v and v.status == "approved"),
                         "completed_gigs": GigHistory.objects.filter(worker=w, is_verified=True).count()}
    return row


class ApplyView(APIView):
    """POST {"message": "..."}: a fundi says they're interested in a job post (once per post)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.account_type != FUNDI:
            return Response({"detail": "Only fundi accounts can apply."}, status=status.HTTP_403_FORBIDDEN)
        post = GigsAvailable.objects.select_related("organization").filter(
            pk=pk, organization__is_active=True, is_open=True).first()
        if not post:
            return Response({"detail": "This job is no longer open."}, status=status.HTTP_404_NOT_FOUND)
        message = (request.data.get("message") or "")[:300]
        app, created = JobApplication.objects.get_or_create(post=post, worker=request.user, defaults={"message": message})
        if not created and app.status in ("withdrawn", "invited"):
            app.status, app.message = "pending", message or app.message
            app.save(update_fields=["status", "message"])
            created = True
        if created:
            from ..inbox import push
            push(post.organization.owner, "new_applicant",
                 f"{request.user.full_name or request.user.username} applied", f"For '{post.title[:80]}'", "/main-menu/job-posts")
        return Response(_app_row(app), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class MyApplicationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        apps = JobApplication.objects.filter(worker=request.user).select_related("post__organization")
        return Response([_app_row(a) for a in apps])


class PostApplicationsView(APIView):
    """GET: applicants for one of your job posts, with their verified record."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        post = GigsAvailable.objects.select_related("organization").filter(pk=pk).first()
        if not post or not owns_organization(request.user, post.organization):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        apps = post.applications.select_related("worker__current_verification", "post__organization")
        return Response([_app_row(a, with_worker=True) for a in apps])


class DecideApplicationView(APIView):
    """POST {"status": "accepted" | "declined"}: the post's owner decides."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        app = JobApplication.objects.select_related("post__organization", "worker").filter(pk=pk).first()
        if not app or not owns_organization(request.user, app.post.organization):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        new = request.data.get("status")
        if new not in ("accepted", "declined"):
            return Response({"detail": "status must be accepted or declined"}, status=status.HTTP_400_BAD_REQUEST)
        if app.status not in ("pending", "invited") and app.status != new:
            return Response({"detail": f"This application is {app.status}."}, status=status.HTTP_400_BAD_REQUEST)
        app.status, app.decided_at = new, timezone.now()
        app.save(update_fields=["status", "decided_at"])
        from ..inbox import log, push
        who = app.worker.full_name or app.worker.username
        if new == "accepted":
            phone = app.post.organization.phone_number or (app.post.organization.owner.phone or "")
            push(app.worker, "application_accepted", f"{app.post.organization.name} accepted you",
                 f"For '{app.post.title[:80]}'." + (f" Call {phone} to agree the start." if phone else ""),
                 "/main-menu/search-gigs",
                 sms_text=f"{app.post.organization.name} accepted you for '{app.post.title[:60]}'."
                          + (f" Call {phone} to agree the start." if phone else ""))
            log(request.user, app.post.organization, "hired", f"Hired {who} for '{app.post.title}'")
            close_if_filled(app.post)
        else:
            push(app.worker, "application_declined", f"{app.post.organization.name} chose someone else",
                 f"For '{app.post.title[:80]}'. Keep applying.", "/main-menu/search-gigs")
        return Response(_app_row(app, with_worker=True))


def close_if_filled(post):
    """Close a job post once its positions are filled. Returns True if it was closed now."""
    if post.is_open and post.applications.filter(status="accepted").count() >= post.positions:
        post.is_open = False
        post.save(update_fields=["is_open"])
        return True
    return False


class CheckInView(APIView):
    """POST: the gig's worker checks in for today (verified, unfinished gigs; once a day)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, gig_id):
        gig = Gig.objects.select_related("organization").filter(pk=gig_id, worker=request.user).first()
        if not gig:
            return Response({"detail": "Gig not found."}, status=status.HTTP_404_NOT_FOUND)
        if not gig.is_verified:
            return Response({"detail": "You can check in once the contractor has verified this gig."}, status=status.HTTP_400_BAD_REQUEST)
        today = timezone.localdate()
        if gig.start_date > today:
            return Response({"detail": "This gig has not started yet."}, status=status.HTTP_400_BAD_REQUEST)
        ci, created = SiteCheckIn.objects.get_or_create(gig=gig, date=today, defaults={"worker": request.user})
        return Response({"gig": gig.id, "date": today, "checked_in_at": ci.checked_in_at, "new": created},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class MyCheckInsTodayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(list(SiteCheckIn.objects.filter(worker=request.user, date=timezone.localdate())
                             .values_list("gig_id", flat=True)))


class OnSiteTodayView(APIView):
    """GET: who checked in today at the signed-in contractor's sites."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = SiteCheckIn.objects.filter(date=timezone.localdate()).select_related("worker", "gig__organization", "gig__job_type")
        if not request.user.is_staff:
            qs = qs.filter(gig__organization__owner=request.user)
        return Response([{"worker_name": c.worker.full_name or c.worker.username, "worker_username": c.worker.username,
                          "phone": c.worker.phone, "site": c.gig.organization.name, "organization": c.gig.organization_id,
                          "trade": c.gig.job_type.name if c.gig.job_type_id else None, "checked_in_at": c.checked_in_at}
                         for c in qs])
