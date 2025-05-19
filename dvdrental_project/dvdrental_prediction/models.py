from django.db import models

# Create your models here.
class Language(models.Model):
    language_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=20)

    class Meta:
        db_table = 'language'
        managed = False

    def __str__(self):
        return self.name


class Category(models.Model):
    category_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)

    class Meta:
        db_table = 'category'
        managed = False

    def __str__(self):
        return self.name
    
class Actor(models.Model):
    actor_id = models.IntegerField(primary_key=True)
    first_name = models.CharField(max_length=45)
    last_name = models.CharField(max_length=45)

    class Meta:
        db_table = 'actor'

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Movie(models.Model):
    film_id = models.IntegerField(primary_key=True)
    title = models.CharField(max_length=255)
    release_year = models.IntegerField()
    rating = models.CharField(max_length=5)
    language = models.ForeignKey(Language, on_delete=models.DO_NOTHING, db_column='language_id')
    actors = models.ManyToManyField(Actor, through='FilmActor')
    
    # Add many-to-many through relationship to Category
    categories = models.ManyToManyField(Category, through='FilmCategory')

    def __str__(self):
        return self.title

    class Meta:
        db_table = 'film'
        managed = False


class FilmCategory(models.Model):
    film = models.ForeignKey(Movie, on_delete=models.DO_NOTHING, db_column='film_id')
    category = models.ForeignKey(Category, on_delete=models.DO_NOTHING, db_column='category_id')

    class Meta:
        db_table = 'film_category'
        unique_together = ('film', 'category')
        managed = False

class FilmActor(models.Model):
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, db_column='actor_id')
    film = models.ForeignKey(Movie, on_delete=models.CASCADE, db_column='film_id')

    class Meta:
        db_table = 'film_actor'
        unique_together = ('film', 'actor')