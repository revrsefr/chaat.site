# chaat.site

chaat.site is a Django-based IRC community website with webchat access, member profiles, blog, and community pages.

## Features
- IRC webchat entry flow
- Member profiles and community pages
- Blog with categories/tags and comments
- Daily Hacker News import into blog posts
- Sitemap + SEO helpers

## Tech stack
- Django 6.x
- Python 3.13
- Redis (cache)
- PostgreSQL/MySQL (database configured via settings)

## Local setup
1. Create a virtual environment and install dependencies:
	- `python -m venv .env`
	- `source .env/bin/activate`
	- `pip install -r requirements.txt`
2. Configure environment variables (see the local `env` file for examples).
3. Run migrations:
	- `python manage.py migrate`
4. Start the server:
	- `python manage.py runserver`

## Management commands
- `python manage.py import_hackernews` (imports HN stories)
- `python manage.py collect_irc_snapshot` (IRC telemetry snapshot)
- `python manage.py generate_blog_thumbs` (generate blog thumbnails)

## Systemd timers
See the unit files in [deploy/systemd](deploy/systemd) for scheduled jobs.

## Project layout
- Django project: [manage.py](manage.py)
- Main app views: [main/views.py](main/views.py)
- Blog app: [blog](blog)
