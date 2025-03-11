from django.core.paginator import Paginator
from django.shortcuts import render
from accounts.models import CustomUser  # Your custom user model

def community_membres(request):
    members = CustomUser.objects.all().order_by("-date_joined")

    # ✅ Filtering (Optional)
    gender = request.GET.get("gender")
    age_min = request.GET.get("age_min")
    age_max = request.GET.get("age_max")
    country = request.GET.get("country")

    if gender:
        members = members.filter(gender=gender)
    if country:
        members = members.filter(city=country)
    
    # ✅ Pagination (10 users per page)
    paginator = Paginator(members, 10)
    page = request.GET.get("page")
    members = paginator.get_page(page)

    return render(request, "community/membres.html", {"members": members})
