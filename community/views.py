from __future__ import annotations

from datetime import date, timedelta

from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import now

from accounts.models import CustomUser
from blog.models import BlogPost


def _safe_birthdate_for_age(age_years: int) -> date:
    today = date.today()
    try:
        return date(today.year - age_years, today.month, today.day)
    except ValueError:
        # Handles Feb 29th on non-leap years.
        return date(today.year - age_years, today.month, 28)


def _age_years_from_birthdate(birthdate: date) -> int:
    today = date.today()
    years = today.year - birthdate.year
    if (today.month, today.day) < (birthdate.month, birthdate.day):
        years -= 1
    return max(years, 0)

def community_membres(request):
    members = CustomUser.objects.filter(public=True)

    # ✅ Filtering (Optional)
    gender = request.GET.get("gender")
    age_min = request.GET.get("age_min")
    age_max = request.GET.get("age_max")
    country = request.GET.get("country")

    gender_map = {
        "male": "M",
        "m": "M",
        "female": "F",
        "f": "F",
        "M": "M",
        "F": "F",
    }
    if gender:
        mapped_gender = gender_map.get(gender, gender)
        members = members.filter(gender=mapped_gender)

    # CustomUser.age is a birthdate (DateField). Filter by age in years.
    try:
        age_min_int = int(age_min) if age_min else None
    except (TypeError, ValueError):
        age_min_int = None

    try:
        age_max_int = int(age_max) if age_max else None
    except (TypeError, ValueError):
        age_max_int = None

    if age_min_int is not None:
        min_birthdate = _safe_birthdate_for_age(age_min_int)
        members = members.filter(age__lte=min_birthdate)
    if age_max_int is not None:
        max_birthdate = _safe_birthdate_for_age(age_max_int)
        members = members.filter(age__gte=max_birthdate)
    if country:
        members = members.filter(city__icontains=country)

    # ✅ Sorting
    order = request.GET.get("order", "last_active")
    if order == "oldest":
        members = members.order_by("date_joined")
    elif order == "popular":
        members = members.order_by("-popularity_score")
    elif order == "most_active":
        members = members.order_by("-last_login")
    else:
        members = members.order_by("-last_login")  # Default: Last Active

    # ✅ Pagination (10 per page)
    paginator = Paginator(members, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ✅ Get current time and threshold for active users (5 minutes)
    current_time = now()
    active_threshold = current_time - timedelta(minutes=5)

    ages = list(range(18, 81))
    gender_choices = list(CustomUser._meta.get_field("gender").choices)

    return render(
        request,
        "community/membres.html",
        {
            "members": page_obj,
            "order": order,
            "ages": ages,
            "gender_choices": gender_choices,
            "now": current_time,
            "active_threshold": active_threshold,
        },
    )

def member_profile(request, username):
    member = get_object_or_404(CustomUser, username=username)
    if not member.public:
        if not request.user.is_authenticated:
            raise Http404
        if request.user != member and not request.user.is_staff:
            raise Http404

    current_time = now()
    active_threshold = current_time - timedelta(minutes=5)

    member_age_years = _age_years_from_birthdate(member.age) if member.age else None

    recent_posts = (
        BlogPost.objects.filter(author=member, is_active=True, is_published=True)
        .order_by("-created_at")
        .only("title", "slug", "created_at")[:10]
    )

    recent_media_posts = (
        BlogPost.objects.filter(author=member, is_active=True, is_published=True)
        .order_by("-created_at")
        .only("title", "slug", "image")[:6]
    )

    newest_members = (
        CustomUser.objects.filter(public=True)
        .order_by("-date_joined")
        .only("username", "avatar", "last_login")[:5]
    )
    popular_members = (
        CustomUser.objects.filter(public=True)
        .order_by("-popularity_score")
        .only("username", "avatar", "last_login")[:5]
    )

    return render(
        request,
        "community/member_detail.html",
        {
            "member": member,
            "member_age_years": member_age_years,
            "recent_posts": recent_posts,
            "recent_media_posts": recent_media_posts,
            "newest_members": newest_members,
            "popular_members": popular_members,
            "now": current_time,
            "active_threshold": active_threshold,
        },
    )