"""Single place where credit scores change.

Every change is clamped to 0..MAX_SCORE, applied under a row lock (safe when
two requests race), and recorded in CreditScoreHistory with the delta that was
actually applied.
"""
from django.contrib.auth import get_user_model
from django.db import transaction

MAX_SCORE = 100

POINTS = {
    "verify_gig": 5,
    "complete_gig": 5,
    "approve_verification": 20,
}


def apply_score_change(user, action, delta=None):
    """Apply ``delta`` (default: POINTS[action]) to ``user`` and return the new score."""
    from .models import CreditScoreHistory

    delta = POINTS[action] if delta is None else delta
    User = get_user_model()
    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)
        old = locked.credit_score or 0
        new = max(0, min(MAX_SCORE, old + delta))
        locked.credit_score = new
        locked.save(update_fields=["credit_score"])
        CreditScoreHistory.objects.create(user=locked, change=new - old, new_score=new, action=action)
    user.credit_score = new
    return new
