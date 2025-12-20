import os
import time

import requests
from django.core.management.base import BaseCommand

from locations.models import City


class Command(BaseCommand):
    help = "Fetch and store French cities using the GeoNames API (paginated)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=os.environ.get("GEONAMES_USERNAME") or "reverse",
            help="GeoNames username (or set GEONAMES_USERNAME env var).",
        )
        parser.add_argument(
            "--page-size",
            type=int,
            default=1000,
            help="GeoNames maxRows per request (max 1000).",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.2,
            help="Seconds to sleep between page requests.",
        )
        parser.add_argument(
            "--max-rows",
            type=int,
            default=0,
            help="Stop after inserting this many rows (0 = no limit).",
        )

    def handle(self, *args, **kwargs):
        username: str = kwargs["username"]
        page_size: int = min(max(kwargs["page_size"], 1), 1000)
        sleep_s: float = max(kwargs["sleep"], 0.0)
        max_rows: int = max(kwargs["max_rows"], 0)

        base_url = "http://api.geonames.org/searchJSON"
        inserted_total = 0
        start_row = 0

        self.stdout.write(
            self.style.NOTICE(
                f"Fetching GeoNames cities for FR (username={username}, page_size={page_size})"
            )
        )

        session = requests.Session()

        while True:
            params = {
                "country": "FR",
                "featureClass": "P",
                "maxRows": page_size,
                "startRow": start_row,
                "username": username,
            }
            try:
                response = session.get(base_url, params=params, timeout=30)
            except requests.RequestException as exc:
                self.stderr.write(self.style.ERROR(f"❌ GeoNames request failed: {exc}"))
                break

            if response.status_code != 200:
                self.stderr.write(
                    self.style.ERROR(
                        f"❌ GeoNames error HTTP {response.status_code}: {response.text[:200]}"
                    )
                )
                break

            data = response.json()
            rows = data.get("geonames", [])

            if not rows:
                self.stdout.write(self.style.SUCCESS("✅ No more cities to fetch."))
                break

            batch = []
            for row in rows:
                name = (row.get("name") or "").strip()
                if not name:
                    continue
                try:
                    lat = float(row.get("lat")) if row.get("lat") is not None else None
                except (TypeError, ValueError):
                    lat = None
                try:
                    lng = float(row.get("lng")) if row.get("lng") is not None else None
                except (TypeError, ValueError):
                    lng = None
                batch.append(City(name=name, latitude=lat, longitude=lng))

            if batch:
                City.objects.bulk_create(batch, ignore_conflicts=True)
                inserted_total += len(batch)

            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Page startRow={start_row}: processed={len(rows)} (attempted_insert={len(batch)}), total_attempted={inserted_total}"
                )
            )

            if max_rows and inserted_total >= max_rows:
                self.stdout.write(self.style.WARNING(f"⚠️ Reached --max-rows={max_rows}, stopping."))
                break

            start_row += page_size
            if sleep_s:
                time.sleep(sleep_s)

        self.stdout.write(self.style.SUCCESS("Done."))
