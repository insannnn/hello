from django.shortcuts import render
from .models import Movie
from  .forms import MovieSearchForm


# Create your views here.
def home(request):
    return render(request, 'dvdrental_prediction/home.html')
def about(request):
    return render(request, 'dvdrental_prediction/about.html')
def movie_list(request):
    movies = Movie.objects.prefetch_related('categories').all()
    form = MovieSearchForm()
    return render(request, 'dvdrental_prediction/movie_list.html', {'movies': movies, 'form': form})
def movie_detail(request, film_id):
    movie = Movie.objects.get(film_id=film_id)
    actors = movie.actors.all()
    return render(request, 'dvdrental_prediction/movie_detail.html', {'movie':movie, 'actors':actors})
def search_result(request):
    form = MovieSearchForm(request.GET)
    movies = Movie.objects.select_related('language').prefetch_related('actors', 'categories').all()

    if form.is_valid():
        actor = form.cleaned_data.get('actor')
        category = form.cleaned_data.get('category')
        language = form.cleaned_data.get('language')

        if actor:
            movies = movies.filter(actors=actor)
        if category:
            movies = movies.filter(categories=category)
        if language:
            movies = movies.filter(language=language)

    return render(request, 'dvdrental_prediction/movie_search.html', {
        'form': form,
        'movies': movies
    })
