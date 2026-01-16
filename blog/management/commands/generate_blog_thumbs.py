from django.core.management.base import BaseCommand

from blog.models import BlogPost


class Command(BaseCommand):
    help = "Generate blog post image thumbnails (WebP/JPEG fallback) for existing posts."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        limit = int(options.get("limit") or 0)

        qs = BlogPost.objects.all().only("id", "image")
        if limit > 0:
            qs = qs[:limit]

        processed = 0
        for post in qs.iterator(chunk_size=100):
            try:
                if hasattr(post, "ensure_image_thumbs"):
                    post.ensure_image_thumbs()
                processed += 1
            except Exception as exc:
                self.stderr.write(f"post_id={post.id}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Done. Processed {processed} posts."))
