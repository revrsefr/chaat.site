import os
import tempfile
import zipfile
from typing import Iterable

import requests
from django.core.management.base import BaseCommand

from locations.models import City


class Command(BaseCommand):
    help = "Load French cities from the GeoNames country dump (FR.zip), filtering populated places."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default=os.environ.get("GEONAMES_DUMP_URL")
            or "http://download.geonames.org/export/dump/FR.zip",
            help="GeoNames country dump URL (default: FR.zip).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="How many rows to bulk-insert per batch.",
        )
        parser.add_argument(
            "--max-rows",
            type=int,
            default=0,
            help="Stop after inserting this many rows (0 = no limit).",
        )
        parser.add_argument(
            "--keep-zip",
            action="store_true",
            help="Keep the downloaded zip file (for debugging).",
        )

    def _iter_geonames_rows(self, txt_path: str) -> Iterable[tuple[str, float | None, float | None]]:
        # GeoNames dump format:
        # geonameid, name, asciiname, alternatenames, latitude, longitude,
        # feature class, feature code, country code, ... (tab-separated)
        with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 9:
                    continue

                name = (parts[1] or "").strip()
                if not name:
                    continue

                lat_s = parts[4]
                lng_s = parts[5]
                feature_class = parts[6]
                country_code = parts[8]

                if country_code != "FR":
                    continue
                if feature_class != "P":
                    continue

                try:
                    lat = float(lat_s) if lat_s else None
                except ValueError:
                    lat = None
                try:
                    lng = float(lng_s) if lng_s else None
                except ValueError:
                    lng = None

                yield name, lat, lng

    def handle(self, *args, **kwargs):
        url: str = kwargs["url"]
        batch_size: int = max(1, kwargs["batch_size"])
        max_rows: int = max(0, kwargs["max_rows"])
        keep_zip: bool = bool(kwargs["keep_zip"])

        self.stdout.write(self.style.NOTICE(f"Downloading GeoNames dump: {url}"))

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "FR.zip")

            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(zip_path, "wb") as out:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            out.write(chunk)

            self.stdout.write(self.style.SUCCESS("✅ Downloaded dump"))

            with zipfile.ZipFile(zip_path) as zf:
                candidates = [n for n in zf.namelist() if n.lower().endswith(".txt")]
                if not candidates:
                    raise RuntimeError("No .txt found in zip")
                # Usually it's FR.txt
                txt_name = sorted(candidates, key=len)[0]
                txt_path = os.path.join(tmpdir, os.path.basename(txt_name))
                zf.extract(txt_name, tmpdir)
                # If extracted into nested directories
                extracted = os.path.join(tmpdir, txt_name)
                if extracted != txt_path and os.path.exists(extracted):
                    os.replace(extracted, txt_path)

            self.stdout.write(self.style.NOTICE(f"Parsing {os.path.basename(txt_path)} and inserting cities..."))

            inserted_attempted = 0
            batch: list[City] = []
            batch_seen: set[str] = set()

            for name, lat, lng in self._iter_geonames_rows(txt_path):
                if name in batch_seen:
                    continue
                batch_seen.add(name)
                batch.append(City(name=name, latitude=lat, longitude=lng))

                if len(batch) >= batch_size:
                    City.objects.bulk_create(batch, ignore_conflicts=True)
                    inserted_attempted += len(batch)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Inserted batch (attempted={len(batch)}), total_attempted={inserted_attempted}"
                        )
                    )
                    batch.clear()
                    batch_seen.clear()

                    if max_rows and inserted_attempted >= max_rows:
                        self.stdout.write(self.style.WARNING(f"⚠️ Reached --max-rows={max_rows}, stopping."))
                        break

            if batch and (not max_rows or inserted_attempted < max_rows):
                City.objects.bulk_create(batch, ignore_conflicts=True)
                inserted_attempted += len(batch)

            self.stdout.write(self.style.SUCCESS(f"Done. total_attempted={inserted_attempted}"))

            if keep_zip:
                kept = os.path.join(os.getcwd(), "FR.zip")
                os.replace(zip_path, kept)
                self.stdout.write(self.style.WARNING(f"Kept zip at {kept}"))
