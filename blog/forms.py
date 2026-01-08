from django import forms

from .models import BlogPost, Comment


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["content"]


class BlogPostForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = [
            "title",
            "content",
            "image",
            "category",
            "tags",
            "keywords",
            "is_published",
        ]
