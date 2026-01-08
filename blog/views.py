from django.shortcuts import render, get_object_or_404, redirect
from .models import BlogPost, Comment
from .forms import BlogPostForm, CommentForm
from accounts.utils import verify_recaptcha
from django.db.models import Count
from django.db.models import Q
from django.conf import settings
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required

def blog_list(request):
    query = request.GET.get("q", "")  # Get search query from URL
    selected_category = (request.GET.get("category") or "").strip()

    posts = (
        BlogPost.objects.filter(is_active=True, is_published=True)
        .select_related("author")
        .order_by("-created_at")
    )

    if selected_category:
        posts = posts.filter(category__iexact=selected_category)

    if query:
        posts = posts.filter(
            Q(title__icontains=query) | Q(content__icontains=query) | Q(tags__icontains=query)
        )

    categories = (
        BlogPost.objects.filter(is_active=True, is_published=True)
        .exclude(category="")
        .values("category")
        .annotate(count=Count("id"))
        .order_by("-count", "category")
    )

    recent_posts = (
        BlogPost.objects.filter(is_active=True, is_published=True)
        .only("title", "slug", "created_at", "image")
        .order_by("-created_at")[:5]
    )

    return render(request, "blog/blog.html", {
        "posts": posts,
        "query": query,  # Keep search term in input field
        "categories": categories,
        "recent_posts": recent_posts,
        "selected_category": selected_category,
    })


@login_required(login_url="login")
def create_post(request):
    if request.method == "POST":
        form = BlogPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect("blog:blog_detail", slug=post.slug)
    else:
        form = BlogPostForm()

    return render(request, "blog/blog-create.html", {
        "form": form,
    })

def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)
    comments = post.comments.order_by("-created_at")
    post_tags = post.tags.split(",") if post.tags else []
    all_posts = (
        BlogPost.objects.filter(is_active=True, is_published=True)
        .only("title", "slug", "created_at", "image")
        .order_by("-created_at")[:5]
    )
    categories = (
        BlogPost.objects.filter(is_active=True, is_published=True)
        .exclude(category="")
        .values("category")
        .annotate(count=Count("id"))
        .order_by("-count", "category")
    )

    form = CommentForm()

    # Comment creation is handled by add_comment() so this view can remain idempotent.
    # If a POST lands here for legacy reasons, bounce to the proper endpoint.
    if request.method == "POST":
        return redirect("blog:add_comment", slug=post.slug)

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
        if not request.user.is_authenticated:
            return redirect("login")

        form = CommentForm(request.POST)
        recaptcha_token = request.POST.get("g-recaptcha-response")

        # ✅ Validate reCAPTCHA
        recaptcha_success, recaptcha_error = verify_recaptcha(recaptcha_token)
        if not recaptcha_success:
            return redirect("blog:blog_detail", slug=post.slug)

        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post

            # Use authenticated user identity as requested.
            comment.name = getattr(request.user, "username", "") or str(request.user)
            comment.email = getattr(request.user, "email", "")

            comment.save()
            return redirect("blog:blog_detail", slug=post.slug)
    return redirect("blog:blog_detail", slug=post.slug)


def delete_comment(request, slug, comment_id: int):
    post = get_object_or_404(BlogPost, slug=slug)

    if request.method != "POST":
        return redirect("blog:blog_detail", slug=post.slug)

    if not request.user.is_authenticated:
        return redirect("login")

    if request.user.pk != post.author_id:
        return HttpResponseForbidden("You are not allowed to delete comments on this post.")

    comment = get_object_or_404(Comment, pk=comment_id, post=post)
    comment.delete()
    return redirect("blog:blog_detail", slug=post.slug)