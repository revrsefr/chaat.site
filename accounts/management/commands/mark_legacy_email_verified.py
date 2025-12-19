from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Mark legacy users as email_verified=True. "
        "Legacy here means: email_verified is False, email_verification_sent_at is NULL, "
        "and last_login is NOT NULL (they have logged in successfully before verification was introduced)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write changes to the database (default is dry-run).",
        )
        parser.add_argument(
            "--username",
            action="append",
            default=[],
            help="Only update the specified username(s). Can be provided multiple times.",
        )

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model

        apply_changes: bool = options["apply"]
        usernames: list[str] = options["username"] or []

        User = get_user_model()

        qs = User.objects.filter(
            email_verified=False,
            email_verification_sent_at__isnull=True,
            last_login__isnull=False,
        )
        if usernames:
            qs = qs.filter(username__in=usernames)

        count = qs.count()
        self.stdout.write(f"Eligible legacy users: {count}")

        if count == 0:
            return

        preview = list(qs.values_list("id", "username", "email", "last_login")[:50])
        for row in preview:
            self.stdout.write(f"- id={row[0]} username={row[1]!r} email={row[2]!r} last_login={row[3]}")
        if count > len(preview):
            self.stdout.write(f"... and {count - len(preview)} more")

        if not apply_changes:
            self.stdout.write(self.style.WARNING("Dry-run only. Re-run with --apply to persist."))
            return

        now = timezone.now()
        with transaction.atomic():
            updated = qs.update(email_verified=True)

        self.stdout.write(self.style.SUCCESS(f"Updated {updated} user(s) at {now.isoformat()}"))
