from django import forms
from .models import Actor, Category, Language

class MovieSearchForm(forms.Form):
    actor = forms.ModelChoiceField(queryset=Actor.objects.all(), required=False)
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False)
    language = forms.ModelChoiceField(queryset=Language.objects.all(), required=False)