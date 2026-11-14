"""Identity (national ID + selfie) review, shared by the API and the Django admin."""
from django.db import transaction

from .scoring import apply_score_change


def approve(verification):
    """Approve; points are awarded only the first time. Returns True if newly approved."""
    with transaction.atomic():
        first = verification.status != "approved"
        verification.status = "approved"
        verification.save(update_fields=["status"])
        user = verification.user
        user.current_verification = verification
        user.save(update_fields=["current_verification"])
        if first:
            apply_score_change(user, "approve_verification")
    if first:
        from .notify import sms
        sms(verification.user, "Your ID is verified. +20 points added to your credit score.")
    return first


def reject(verification, reason=""):
    # is_verified is the email flag used by login; never touched by ID review.
    with transaction.atomic():
        verification.status = "rejected"
        verification.rejection_reason = reason
        verification.save(update_fields=["status", "rejection_reason"])
        user = verification.user
        if user.current_verification_id == verification.id:
            user.current_verification = None
            user.save(update_fields=["current_verification"])
    from .notify import sms
    sms(verification.user, "We could not verify your ID. Please upload clearer photos in the app.")
