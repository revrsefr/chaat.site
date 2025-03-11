from django.shortcuts import render
from django.core.paginator import Paginator
from django.utils.timezone import now
from accounts.models import CustomUser
from django.shortcuts import render, get_object_or_404
from datetime import timedelta

def community_membres(request):
    members = CustomUser.objects.all()

    # ✅ Filtering (Optional)
    gender = request.GET.get("gender")
    age_min = request.GET.get("age_min")
    age_max = request.GET.get("age_max")
    country = request.GET.get("country")

    if gender:
        members = members.filter(gender=gender)
    if age_min:
        members = members.filter(age__gte=age_min)
    if age_max:
        members = members.filter(age__lte=age_max)
    if country:
        members = members.filter(city__icontains=country)

    # ✅ Sorting
    order = request.GET.get("order", "last_active")
    if order == "oldest":
        members = members.order_by("date_joined")
    elif order == "popular":
        members = members.order_by("-popularity_score")  # If you have a popularity field
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

    return render(
        request,
        "community/membres.html",
        {"members": page_obj, "now": current_time, "active_threshold": active_threshold},
    )

def member_profile(request, username):
    member = get_object_or_404(CustomUser, username=username)
    return render(request, "accounts/profile.html", {"member": member})