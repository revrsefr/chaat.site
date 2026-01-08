from django.urls import path
from .views import add_comment, blog_detail, blog_list, create_post, delete_comment



app_name = "blog" 


urlpatterns = [
    path("", blog_list, name="blog_list"),
    path("new/", create_post, name="blog_create"),
    path("<slug:slug>/", blog_detail, name="blog_detail"),
    path("<slug:slug>/comment/", add_comment, name="add_comment"), 
    path("<slug:slug>/comment/<int:comment_id>/delete/", delete_comment, name="delete_comment"),
]
