from __future__ import annotations

from django.core.management.base import BaseCommand

from irc.tasks import enqueue_refresh_network_overview_cache, refresh_network_overview_cache


class Command(BaseCommand):
    help = "Refresh IRC network overview cache."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run refresh synchronously without enqueuing.",
        )

    def handle(self, *args, **options):
        if options.get("sync"):
            refresh_network_overview_cache()
            self.stdout.write(self.style.SUCCESS("IRC stats cache refreshed."))
            return

        job_id = enqueue_refresh_network_overview_cache()
        self.stdout.write(self.style.SUCCESS(f"Enqueued IRC stats refresh job: {job_id}"))
