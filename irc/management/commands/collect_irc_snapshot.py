from typing import List

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from irc.models import ChannelPeak, TelemetrySnapshot
from irc.rpc_client import RPCError
from irc.services import AnopeStatsService


class Command(BaseCommand):
    help = "Collects a telemetry snapshot from Anope RPC and stores it in the database."  # noqa: E501

    def add_arguments(self, parser):
        parser.add_argument(
            "--channel-limit",
            type=int,
            default=25,
            help="How many of the largest channels to persist per snapshot (default: 25)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch data but do not write to the database.",
        )

    def handle(self, *args, **options):
        channel_limit = max(1, min(int(options["channel_limit"]), 500))
        dry_run = options["dry_run"]

        service = AnopeStatsService()
        try:
            overview = service.network_overview()
        except RPCError as exc:
            raise CommandError(f"Failed to fetch network overview: {exc}") from exc

        counts = overview.get("counts") or {}
        snapshot_kwargs = {
            "user_count": int(counts.get("users", 0)),
            "channel_count": int(counts.get("channels", 0)),
            "server_count": int(counts.get("servers", 0)),
            "operator_count": int(counts.get("operators", 0)),
            "overview_payload": overview,
        }

        try:
            channels = service.channel_listing(limit=channel_limit)
        except RPCError as exc:
            raise CommandError(f"Failed to fetch channel listing: {exc}") from exc

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run complete. Would have stored snapshot %s with %s channels"
                    % (snapshot_kwargs, len(channels))
                )
            )
            return

        with transaction.atomic():
            snapshot = TelemetrySnapshot.objects.create(**snapshot_kwargs)
            peaks: List[ChannelPeak] = []
            for entry in channels:
                channel_name = (entry.get("name") or "").strip()
                if not channel_name:
                    continue
                peaks.append(
                    ChannelPeak(
                        snapshot=snapshot,
                        channel_name=channel_name,
                        topic=entry.get("topic_value") or "",
                        user_count=int(entry.get("user_count") or 0),
                        recorded_at=snapshot.recorded_at,
                    )
                )
            ChannelPeak.objects.bulk_create(peaks, ignore_conflicts=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Stored snapshot at {snapshot.recorded_at:%Y-%m-%d %H:%M:%S}"
                f" (users={snapshot.user_count}, channels={snapshot.channel_count})"  # pragma: no cover
            )
        )
