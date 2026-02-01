from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.files.storage import default_storage

from blog.models import BlogPost


class Command(BaseCommand):
    help = "Delete blog posts older than a specified number of days to free up database storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Number of days to keep (default: 90). Posts older than this will be deleted.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting.",
        )

    def handle(self, *args, **options):
        days = int(options.get("days") or 90)
        dry_run = options.get("dry_run", False)

        cutoff_date = timezone.now().date() - timedelta(days=days)

        # Query posts older than cutoff_date
        old_posts = BlogPost.objects.filter(created_at__lt=cutoff_date)

        post_count = old_posts.count()
        if post_count == 0:
            self.stdout.write(self.style.SUCCESS("No old posts to delete."))
            return

        # Calculate storage space that will be freed (approximate)
        deleted_images = 0
        deleted_thumbs = 0

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would delete {post_count} posts older than {cutoff_date}"
                )
            )
            for post in old_posts.iterator(chunk_size=100):
                self.stdout.write(
                    f"  - {post.id}: '{post.title}' (created: {post.created_at})"
                )
        else:
            self.stdout.write(
                f"Deleting {post_count} posts older than {cutoff_date}..."
            )

            # Delete associated image files and thumbnails
            for post in old_posts.iterator(chunk_size=100):
                try:
                    # Delete main image
                    if post.image and post.image.name:
                        if default_storage.exists(post.image.name):
                            default_storage.delete(post.image.name)
                            deleted_images += 1

                        # Delete associated thumbnails
                        for size in [326, 652]:
                            thumb_name = post._image_thumb_storage_name(size)
                            if thumb_name and default_storage.exists(thumb_name):
                                default_storage.delete(thumb_name)
                                deleted_thumbs += 1
                            
                            # Try JPEG fallback
                            jpg_name = thumb_name[:-5] + ".jpg" if thumb_name else ""
                            if jpg_name and default_storage.exists(jpg_name):
                                default_storage.delete(jpg_name)
                                deleted_thumbs += 1
                except Exception as exc:
                    self.stderr.write(f"Error deleting images for post {post.id}: {exc}")

            # Delete posts from database
            deleted_db_count, _ = old_posts.delete()

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully deleted {post_count} blog posts\n"
                    f"  - Database records: {post_count}\n"
                    f"  - Image files: {deleted_images}\n"
                    f"  - Thumbnail files: {deleted_thumbs}"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nPosts created before {cutoff_date} have been removed."
                )
            )
