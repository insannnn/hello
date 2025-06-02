# academic_analytics/forms.py
from django import forms
from .models import Student, Course, Enrollment, Instructor


class GradePredictionForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), required=True)
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=True)
    attendance = forms.IntegerField(min_value=0, max_value=100, required=True)
    midterm_score = forms.IntegerField(min_value=0, max_value=100, required=True)
    project_score = forms.IntegerField(min_value=0, max_value=100, required=True)

class RecommendationForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), required=True)
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=True)

class InstructorRecommendationForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), required=True)
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=True)
    target_grade = forms.IntegerField(min_value=0, max_value=100, required=True)
     

class CourseRecommendationForm(forms.Form):
    course_a = forms.ModelChoiceField(
        queryset=Course.objects.all(), 
        required=True,
        label="Course A",
        help_text="Select the first course the student has completed"
    )
    
    course_b = forms.ModelChoiceField(
        queryset=Course.objects.all(), 
        required=True,
        label="Course B",
        help_text="Select the second course the student has completed"
    )
    
    score_a = forms.IntegerField(
        min_value=0, 
        max_value=100, 
        required=True,
        label="Score for Course A",
        help_text="The student's grade for Course A"
    )
    
    score_b = forms.IntegerField(
        min_value=0, 
        max_value=100, 
        required=True,
        label="Score for Course B",
        help_text="The student's grade for Course B"
    )

class RiskDropoutForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=True,
        label="Select Student",
        help_text="Choose a student to analyze dropout risk using clustering"
    )