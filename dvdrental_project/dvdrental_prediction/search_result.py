from django.shortcuts import render
from .models import Movie
from .forms import MovieSearchForm

def search_result(request):
    form = MovieSearchForm(request.GET)
    search_results = Movie.objects.select_related('language').all()

    if form.is_valid():
        actor = form.cleaned_data.get('actor')
        category = form.cleaned_data.get('category')
        language = form.cleaned_data.get('language')

        if actor:
            search_results = search_results.filter(actors=actor)
        if category:
            search_results = search_results.filter(categories=category)
        if language:
            search_results = search_results.filter(language=language)

    return render(request, 'dvdrental_prediction/movie_search.html', {
        'form': form,
        'movies': search_results
    })
