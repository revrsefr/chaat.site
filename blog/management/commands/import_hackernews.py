import io
import logging
import mimetypes
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.html import escape
from django.utils.text import slugify

from accounts.models import CustomUser
from blog.models import BlogPost
from PIL import Image, ImageDraw, ImageFont


logger = logging.getLogger(__name__)

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={item_id}"
USER_AGENT = "chaat.site/hn-importer (+https://chaat.site)"


class Command(BaseCommand):
    help = "Import Hacker News stories into BlogPost"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25)
        parser.add_argument("--author-username", default="Administrator")
        parser.add_argument("--category", default="Hacker News")
        parser.add_argument("--timeout", type=int, default=7)
        parser.add_argument("--refresh-existing", action="store_true")

    def handle(self, *args, **options):
        limit = max(options["limit"], 1)
        timeout = max(options["timeout"], 3)
        author = self._resolve_author(options["author_username"])
        category = options["category"]
        refresh_existing = options["refresh_existing"]

        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

        story_ids = self._fetch_json(session, f"{HN_API_BASE}/newstories.json", timeout)
        if not story_ids:
            self.stdout.write(self.style.WARNING("No HN stories returned."))
            return

        created = 0
        skipped = 0

        for item_id in story_ids[:limit]:
            item_id = str(item_id)
            existing_post = BlogPost.objects.filter(source_id=item_id).first()
            if existing_post and not refresh_existing:
                skipped += 1
                continue

            item = self._fetch_json(session, f"{HN_API_BASE}/item/{item_id}.json", timeout)
            if not item or item.get("type") != "story":
                skipped += 1
                continue

            title = (item.get("title") or "").strip()
            if not title:
                skipped += 1
                continue

            hn_link = HN_ITEM_URL.format(item_id=item_id)
            source_url = (item.get("url") or "").strip() or hn_link

            og_image, description = (None, "")
            if source_url and source_url != hn_link:
                og_image, description = self._extract_meta(session, source_url, timeout)

            summary = description or self._extract_text(item.get("text")) or ""
            content_html = self._build_content_html(summary, source_url, hn_link)

            image_content, image_name = self._resolve_image(
                session=session,
                item_id=item_id,
                og_image_url=og_image,
                timeout=timeout,
            )

            slug = self._build_slug(title, item_id)

            if existing_post:
                post = existing_post
                post.title = title
                post.content = content_html
                post.author = author
                post.category = category
                post.tags = "hacker news"
                post.keywords = "hacker news"
                post.source_url = source_url
                post.is_active = True
                post.is_published = True
            else:
                post = BlogPost(
                    title=title,
                    slug=slug,
                    content=content_html,
                    author=author,
                    category=category,
                    tags="hacker news",
                    keywords="hacker news",
                    source_id=item_id,
                    source_url=source_url,
                    is_active=True,
                    is_published=True,
                )

            post.image.save(image_name, image_content, save=False)
            post.save()
            if existing_post:
                skipped += 1
            else:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"HN import complete. Created: {created}, Skipped: {skipped}."
        ))

    def _resolve_author(self, username: str) -> CustomUser:
        user = CustomUser.objects.filter(username__iexact=username).first()
        if not user:
            user = CustomUser.objects.filter(is_superuser=True).order_by("id").first()
        if not user:
            user = CustomUser.objects.order_by("id").first()
        if not user:
            raise CommandError("No users found to assign as author.")
        return user

    def _fetch_json(self, session: requests.Session, url: str, timeout: int):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("HN fetch failed: %s", url)
            return None

    def _extract_meta(self, session: requests.Session, url: str, timeout: int):
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
        except Exception:
            logger.exception("Failed to fetch article: %s", url)
            return None, ""

        soup = BeautifulSoup(resp.text or "", "html.parser")
        og_image = self._find_meta(soup, ("og:image", "twitter:image"))
        if og_image:
            og_image = urljoin(url, og_image)

        description = self._find_meta(
            soup,
            ("description", "og:description", "twitter:description"),
        )
        if not description:
            first_p = soup.find("p")
            if first_p:
                description = " ".join(first_p.get_text(" ").split())

        return og_image, description or ""

    def _find_meta(self, soup: BeautifulSoup, keys):
        for key in keys:
            tag = soup.find("meta", attrs={"property": key})
            if not tag:
                tag = soup.find("meta", attrs={"name": key})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    def _extract_text(self, html_text: str) -> str:
        if not html_text:
            return ""
        soup = BeautifulSoup(html_text, "html.parser")
        return " ".join(soup.get_text(" ").split())

    def _build_content_html(self, summary: str, source_url: str, hn_link: str) -> str:
        summary_html = escape(summary) if summary else ""
        links = (
            f"<a href=\"{escape(source_url)}\" target=\"_blank\" rel=\"nofollow noopener\">Source</a>"
            f" | <a href=\"{escape(hn_link)}\" target=\"_blank\" rel=\"nofollow noopener\">Hacker News discussion</a>"
        )
        if summary_html:
            return f"<p>{summary_html}</p><p>{links}</p>"
        return f"<p>{links}</p>"

    def _build_slug(self, title: str, item_id: str) -> str:
        max_len = BlogPost._meta.get_field("slug").max_length or 50
        suffix = f"-{item_id}"
        base_len = max_len - len(suffix)
        base = slugify(title)[: max(base_len, 0)] or "hn"
        return f"{base}{suffix}"[:max_len]

    def _resolve_image(self, session: requests.Session, item_id: str, og_image_url: str, timeout: int):
        if og_image_url and og_image_url.startswith("data:"):
            og_image_url = None

        if og_image_url:
            try:
                resp = session.get(og_image_url, timeout=timeout)
                resp.raise_for_status()
                if resp.content:
                    ext = self._guess_ext(og_image_url, resp.headers.get("content-type"))
                    return ContentFile(resp.content), f"hn-{item_id}{ext}"
            except Exception:
                logger.exception("Failed to fetch og:image: %s", og_image_url)

        return self._placeholder_image(item_id)

    def _guess_ext(self, url: str, content_type: str | None):
        if content_type:
            ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
            if ext:
                return ext
        ext = mimetypes.guess_extension(url) or ".jpg"
        if not ext.startswith("."):
            ext = f".{ext}"
        return ext

    def _placeholder_image(self, item_id: str):
        width, height = 1200, 630
        img = Image.new("RGB", (width, height), color=(18, 18, 18))
        draw = ImageDraw.Draw(img)
        text = "Hacker News"
        font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        draw.text((x, y), text, fill=(255, 153, 0), font=font)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return ContentFile(buf.getvalue()), f"hn-{item_id}.jpg"
