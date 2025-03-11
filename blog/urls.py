from django.urls import path
from .views import blog_list, blog_detail, add_comment



app_name = "blog" 


urlpatterns = [
    path("", blog_list, name="blog_list"),
    path("<slug:slug>/", blog_detail, name="blog_detail"),
    path("<slug:slug>/comment/", add_comment, name="add_comment"), 
]
