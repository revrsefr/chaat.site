from django.shortcuts import render, get_object_or_404, redirect
from .models import BlogPost, Comment
from .forms import CommentForm
from accounts.utils import verify_recaptcha
from django.db.models import Count
from django.db.models import Q
from django.http import JsonResponse
from django.conf import settings

def blog_list(request):
    query = request.GET.get("q", "")  # Get search query from URL
    posts = BlogPost.objects.all()

    if query:
        posts = posts.filter(
            Q(title__icontains=query) | Q(content__icontains=query) | Q(tags__icontains=query)
        )

    return render(request, "blog/blog.html", {
        "posts": posts,
        "query": query,  # Keep search term in input field
    })

def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)
    comments = Comment.objects.filter(post=post).order_by("-created_at")
    post_tags = post.tags.split(",") if post.tags else []
    all_posts = BlogPost.objects.all().order_by("-created_at")[:5]
    categories = BlogPost.objects.values("category").annotate(count=Count("category")).order_by("-count")

    form = CommentForm()

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            token = request.POST.get("g-recaptcha-response")
            recaptcha_valid, recaptcha_error = verify_recaptcha(token)

            if recaptcha_valid:
                comment = form.save(commit=False)
                comment.post = post
                comment.save()
                return redirect("blog_detail", slug=post.slug)
            else:
                form.add_error(None, recaptcha_error)

    return render(request, "blog/blog-single.html", {
        "post": post,
        "post_tags": post_tags,
        "recent_posts": all_posts,
        "categories": categories,
        "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY, 
        "comments": comments,
        "form": form,
    })

def add_comment(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)

    if request.method == "POST":
        form = CommentForm(request.POST)
        recaptcha_token = request.POST.get("g-recaptcha-response")

        # ✅ Validate reCAPTCHA
        recaptcha_success, recaptcha_error = verify_recaptcha(recaptcha_token)
        if not recaptcha_success:
            return redirect("blog_detail", slug=post.slug)

        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.save()
            return redirect("blog_detail", slug=post.slug)

    return redirect("blog_detail", slug=post.slug)