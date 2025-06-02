from django.contrib import admin
from .models import ModelStandy, ModelCecil, ModelAbell, ModelInsan
from django.utils.html import format_html
from django.utils.timezone import now

@admin.register(ModelStandy)
class ModelInfo(admin.ModelAdmin):
    list_display = ('model_name', 'model_file', 'training_data', 'training_date', 'short_summary', 'retrain_button')
    search_fields = ('model_name',)  # 'ModelCecil' is not a searchable field unless it's a field on the model

    def short_summary(self, obj):
        return (obj.model_summary[:75] + '...') if obj.model_summary else '-'
    short_summary.short_description = 'Summary'

    def retrain_button(self, obj):
        return format_html('<a class="button" href="/admin/retrain/{}/">Retrain</a>', obj.pk)
    retrain_button.short_description = 'Retrain'

@admin.register(ModelCecil)
class ModelInfo(admin.ModelAdmin):
    list_display = ('model_name', 'model_file', 'training_data', 'training_date', 'short_summary', 'retrain_button')
    search_fields = ('model_name',)  # 'ModelCecil' is not a searchable field unless it's a field on the model

    def short_summary(self, obj):
        return (obj.model_summary[:75] + '...') if obj.model_summary else '-'
    short_summary.short_description = 'Summary'

    def retrain_button(self, obj):
        return format_html('<a class="button" href="/admin/retrain/{}/">Retrain</a>', obj.pk)
    retrain_button.short_description = 'Retrain'

@admin.register(ModelAbell)
class ModelInfo(admin.ModelAdmin):
    list_display = ('model_name', 'model_file', 'training_data', 'training_date', 'short_summary', 'retrain_button')
    search_fields = ('model_name',)  # 'ModelCecil' is not a searchable field unless it's a field on the model

    def short_summary(self, obj):
        return (obj.model_summary[:75] + '...') if obj.model_summary else '-'
    short_summary.short_description = 'Summary'

    def retrain_button(self, obj):
        return format_html('<a class="button" href="/admin/retrain/{}/">Retrain</a>', obj.pk)
    retrain_button.short_description = 'Retrain'

@admin.register(ModelInsan)
class ModelInfo(admin.ModelAdmin):
    list_display = ('model_name', 'model_file', 'training_data', 'training_date', 'short_summary', 'retrain_button')
    search_fields = ('model_name',)  # 'ModelCecil' is not a searchable field unless it's a field on the model

    def short_summary(self, obj):
        return (obj.model_summary[:75] + '...') if obj.model_summary else '-'
    short_summary.short_description = 'Summary'

    def retrain_button(self, obj):
        return format_html('<a class="button" href="/admin/retrain/{}/">Retrain</a>', obj.pk)
    retrain_button.short_description = 'Retrain'
# Register your models here.
