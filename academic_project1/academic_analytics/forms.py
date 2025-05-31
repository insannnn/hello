from django import forms
from .models import Student, Course, Enrollment, Instructor


class GradePredictionForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), required=True)
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=True)
    attendance = forms.IntegerField(min_value=0, max_value=100, required=True)
    midterm_score = forms.IntegerField(min_value=0, max_value=100, required=True)
    project_score = forms.IntegerField(min_value=0, max_value=100, required=True)


# Form prediksi baru 1: Risiko DO
class DropoutRiskForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), required=True)
    attendance = forms.IntegerField(min_value=0, max_value=100, required=True)
    average_grade = forms.IntegerField(min_value=0, max_value=100, required=True)
    failed_courses = forms.IntegerField(min_value=0, max_value=10, required=True)


# Form prediksi baru 2: Kelulusan Mata Kuliah
class CourseSuccessForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), required=True)
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=True)
    attendance = forms.IntegerField(min_value=0, max_value=100, required=True)
    previous_gpa = forms.FloatField(min_value=0, max_value=4.0, required=True)


# Form prediksi baru 3: Rekomendasi Waktu Belajar
class StudyTimeForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), required=True)
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=True)
    target_grade = forms.IntegerField(min_value=0, max_value=100, required=True)
    current_grade = forms.IntegerField(min_value=0, max_value=100, required=True)


# Form prediksi baru 4: Instruktur Terbaik
class BestInstructorForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), required=True)
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=True)
    learning_style = forms.ChoiceField(choices=[
        ('visual', 'Visual'),
        ('auditory', 'Auditory'),
        ('kinesthetic', 'Kinesthetic')
    ], required=True)