"""Create (or reset) the shared test accounts for the two portals.

    docker compose exec backend python manage.py seed_test_users

Idempotent: re-running resets the passwords and flags below. Refuses to run
in HTTPS production mode (SECURE_SSL_REDIRECT) unless --force is given,
because these credentials are published in the README.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

TEST_USERS = [
    # username, password, account_type, full name, portal
    ("jenga-pro", "JengaPro2026!", "02", "Jenga Pro Test Contractor", "Jenga Pro (contractor)"),
    ("fundi-pro", "FundiPro2026!", "01", "Fundi Pro Test Worker", "Fundi Pro (worker)"),
]


class Command(BaseCommand):
    help = "Create or reset the jenga-pro / fundi-pro test accounts."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Allow running in HTTPS production mode.")

    def handle(self, *args, force=False, **options):
        if getattr(settings, "SECURE_SSL_REDIRECT", False) and not force:
            raise CommandError("Refusing to seed publicly documented test accounts in "
                               "production mode. Use --force if you really mean it.")

        User = get_user_model()
        for username, password, account_type, full_name, portal in TEST_USERS:
            user, created = User.objects.update_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "account_type": account_type,
                    "full_name": full_name,
                    "is_active": True,
                    "is_verified": True,
                },
            )
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"{'Created' if created else 'Reset'} {username} ({portal}, account_type={account_type})"))
