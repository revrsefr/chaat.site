from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Generate avatar thumbnails (WebP/JPEG fallback) for existing users."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        User = get_user_model()
        limit = int(options.get("limit") or 0)

        qs = User.objects.all().only("id", "avatar")
        if limit > 0:
            qs = qs[:limit]

        processed = 0
        for user in qs.iterator(chunk_size=200):
            try:
                if hasattr(user, "ensure_avatar_thumbs"):
                    user.ensure_avatar_thumbs()
                processed += 1
            except Exception as exc:
                self.stderr.write(f"user_id={user.id}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Done. Processed {processed} users."))
