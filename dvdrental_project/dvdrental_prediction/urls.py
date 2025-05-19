from django.urls import path 
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('movies/', views.movie_list, name='movie_list'),
    path('movies/<int:film_id>/', views.movie_detail, name='movie_detail'),
    path('search/', views.search_result, name='search_result' )
]
