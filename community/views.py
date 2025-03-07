from django.shortcuts import render

def community(request):
    return render(request, 'community/community.html')  # Ensure correct path
