from django.urls import path
from . import views

app_name = 'helpdocs'

urlpatterns = [
    path('', views.help_index, name='help_index'),
    path('ircd/', views.ircd, name='ircd'),
    path('nickserv/', views.nickserv, name='nickserv'),
    path('chanserv/', views.chanserv, name='chanserv'),
    path('memoserv/', views.memoserv, name='memoserv'),
    path('operserv/', views.operserv, name='operserv'),
]
