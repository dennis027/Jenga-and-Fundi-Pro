"""Find credit scores that do not match the recorded score history.

    python manage.py audit_credit_scores          # report only
    python manage.py audit_credit_scores --fix    # reset mismatches to the history total

Scores could previously be edited directly through /api/profile/; such changes
left no CreditScoreHistory entry, so they show up here as mismatches.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Sum

from app.scoring import MAX_SCORE, apply_score_change


class Command(BaseCommand):
    help = "Compare each user's credit score with the sum of their score history."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Reset mismatched scores to the history total.")

    def handle(self, *args, fix=False, **options):
        User = get_user_model()
        mismatches = 0
        for user in User.objects.annotate(history_total=Sum("score_history__change")).order_by("id"):
            expected = max(0, min(MAX_SCORE, user.history_total or 0))
            if (user.credit_score or 0) == expected:
                continue
            mismatches += 1
            line = f"user {user.id} ({user.username}): score {user.credit_score}, history total {expected}"
            if fix:
                apply_score_change(user, "adjustment", expected - (user.credit_score or 0))
                line += " -> fixed"
            self.stdout.write(line)
        self.stdout.write(self.style.SUCCESS(f"{mismatches} mismatch(es) found" + (" and fixed" if fix and mismatches else "")))
