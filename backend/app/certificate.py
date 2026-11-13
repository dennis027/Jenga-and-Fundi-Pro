"""Verified work certificate: a shareable, signed, expiring summary of a fundi's record.

Only platform-verified facts are shown (verified/completed gigs, ratings, score,
identity status). No phone number, national ID or client details.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db.models import Avg, Count
from django.utils import timezone

from .models import Gig, GigHistory, GigRating

_SALT = "app.certificate"


def make_token(user):
    return signing.dumps({"u": user.pk}, salt=_SALT)


def load_user(token):
    """Return (user, issued_at) or raise signing.BadSignature / SignatureExpired."""
    max_age = timedelta(days=settings.CERTIFICATE_MAX_AGE_DAYS)
    data = signing.loads(token, salt=_SALT, max_age=max_age)
    issued = timezone.now()  # signature timestamp is verified by max_age above
    return get_user_model().objects.get(pk=data["u"]), issued


def _days(value, unit):
    return (value or 0) * (7 if unit == "weeks" else 1)


def summary(user):
    completed = GigHistory.objects.filter(worker=user, is_verified=True).select_related("job_type", "organization")
    ongoing = Gig.objects.filter(worker=user, is_verified=True).select_related("job_type", "organization")
    work = list(completed) + list(ongoing)
    ratings = GigRating.objects.filter(history__worker=user).aggregate(avg=Avg("stars"), n=Count("id"))
    trades = {}
    for g in work:
        name = g.job_type.name if g.job_type_id else "Other"
        trades[name] = trades.get(name, 0) + 1
    v = user.current_verification
    return {
        "name": user.full_name or user.username,
        "username": user.username,
        "identity_verified": bool(v and v.status == "approved"),
        "credit_score": user.credit_score or 0,
        "verified_gigs": len(work),
        "completed_gigs": len(completed),
        "days_worked": sum(_days(g.duration_value, g.duration_unit) for g in work),
        "trades": sorted(({"name": k, "gigs": c} for k, c in trades.items()), key=lambda t: -t["gigs"]),
        "sites": len({g.organization_id for g in work}),
        "counties": sorted({g.county for g in work if g.county}),
        "first_verified_work": min((g.start_date for g in work), default=None),
        "average_rating": round(ratings["avg"], 1) if ratings["avg"] else None,
        "ratings_count": ratings["n"],
        "member_since": user.date_joined.date(),
    }
