from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Student, Course, Enrollment, Assessment, Attendance, Department, Instructor
from .forms import GradePredictionForm, DropoutRiskForm, CourseSuccessForm, StudyTimeForm, BestInstructorForm
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib import messages

def index(request):
    return render(request, 'academic_analytics/index.html')

def home(request):
    # Hitung statistik dasar untuk halaman beranda
    student_count = Student.objects.count()
    course_count = Course.objects.count()
    enrollment_count = Enrollment.objects.count()
   
    context = {
        'student_count': student_count,
        'course_count': course_count,
        'enrollment_count': enrollment_count
    }
    return render(request, 'academic_analytics/home.html', context)


def about(request):
    return render(request, 'academic_analytics/about.html')


def dashboard(request):
    # Dapatkan semua departemen
    departments = Department.objects.all()
   
    # Jumlah siswa per departemen
    dept_student_counts = []
    for dept in departments:
        count = Student.objects.filter(dept=dept).count()
        dept_student_counts.append({'name': dept.dept_name, 'count': count})
   
    # Rata-rata nilai per departemen
    dept_avg_grades = []
    for dept in departments:
        students = Student.objects.filter(dept=dept)
        enrollments = Enrollment.objects.filter(stu__in=students)
        # Hanya ambil yang tidak kosong
        valid_grades = [e.grade for e in enrollments if e.grade is not None]
        if valid_grades:
            avg_grade = sum(valid_grades) / len(valid_grades)
        else:
            avg_grade = 0
        dept_avg_grades.append({'name': dept.dept_name, 'avg_grade': avg_grade})
   
    context = {
        'dept_student_counts': dept_student_counts,
        'dept_avg_grades': dept_avg_grades
    }
    return render(request, 'academic_analytics/dashboard.html', context)




def admin_panel(request):
    # Inisialisasi hasil prediksi
    prediction_results = {
        'grade': None,
        'dropout': None,
        'success': None,
        'study_time': None,
        'instructor': None,
    }
   
    # Inisialisasi form
    forms = {
        'grade_form': GradePredictionForm(),
        'dropout_form': DropoutRiskForm(),
        'success_form': CourseSuccessForm(),
        'study_time_form': StudyTimeForm(),
        'instructor_form': BestInstructorForm(),
    }
   
    # Periksa jenis form yang dikirimkan
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
       
        if form_type == 'grade':
            form = GradePredictionForm(request.POST)
            if form.is_valid():
                student = form.cleaned_data['student']
                course = form.cleaned_data['course']
                attendance = form.cleaned_data['attendance']
                midterm_score = form.cleaned_data['midterm_score']
                project_score = form.cleaned_data['project_score']
               
                prediction_results['grade'] = predict_grade(student, course, attendance, midterm_score, project_score)
                forms['grade_form'] = form
               
        elif form_type == 'dropout':
            form = DropoutRiskForm(request.POST)
            if form.is_valid():
                student = form.cleaned_data['student']
                attendance = form.cleaned_data['attendance']
                average_grade = form.cleaned_data['average_grade']
                failed_courses = form.cleaned_data['failed_courses']
               
                prediction_results['dropout'] = predict_dropout_risk(student, attendance, average_grade, failed_courses)
                forms['dropout_form'] = form
               
        elif form_type == 'success':
            form = CourseSuccessForm(request.POST)
            if form.is_valid():
                student = form.cleaned_data['student']
                course = form.cleaned_data['course']
                attendance = form.cleaned_data['attendance']
                previous_gpa = form.cleaned_data['previous_gpa']
               
                prediction_results['success'] = predict_course_success(student, course, attendance, previous_gpa)
                forms['success_form'] = form
               
        elif form_type == 'study_time':
            form = StudyTimeForm(request.POST)
            if form.is_valid():
                student = form.cleaned_data['student']
                course = form.cleaned_data['course']
                target_grade = form.cleaned_data['target_grade']
                current_grade = form.cleaned_data['current_grade']
               
                prediction_results['study_time'] = predict_study_time(student, course, target_grade, current_grade)
                forms['study_time_form'] = form
               
        elif form_type == 'instructor':
            form = BestInstructorForm(request.POST)
            if form.is_valid():
                student = form.cleaned_data['student']
                course = form.cleaned_data['course']
                learning_style = form.cleaned_data['learning_style']
               
                prediction_results['instructor'] = predict_best_instructor(student, course, learning_style)
                forms['instructor_form'] = form
   
    context = {
        'forms': forms,
        'prediction_results': prediction_results
    }
    return render(request, 'academic_analytics/admin_panel.html', context)


# Fungsi predict_grade tetap sama...


def predict_dropout_risk(student, attendance, average_grade, failed_courses):
    # Simulasi model prediksi risiko DO
    # Dalam implementasi nyata, gunakan model ML yang dilatih dengan data yang tepat
   
    # Hitung skor risiko berdasarkan parameter
    risk_score = (100 - attendance) * 0.4 + (100 - average_grade) * 0.3 + failed_courses * 10
   
    # Normalisasi skor ke persentase
    risk_percentage = min(max(risk_score, 0), 100)
   
    # Tentukan kategori risiko
    if risk_percentage < 30:
        risk_category = 'Low'
    elif risk_percentage < 70:
        risk_category = 'Medium'
    else:
        risk_category = 'High'
   
    # Buat rekomendasi berdasarkan faktor risiko tertinggi
    if (100 - attendance) > 40:
        recommendation = 'Improve attendance'
    elif (100 - average_grade) > 30:
        recommendation = 'Focus on academic performance'
    elif failed_courses > 1:
        recommendation = 'Retake failed courses and seek tutoring'
    else:
        recommendation = 'Continue with current study habits'
   
    return {
        'risk_percentage': round(risk_percentage, 2),
        'risk_category': risk_category,
        'recommendation': recommendation,
        'confidence': 85  # Confidence tetap untuk simulasi
    }


def predict_course_success(student, course, attendance, previous_gpa):
    # Simulasi model prediksi keberhasilan kursus
   
    # Konversi GPA ke skala 100
    gpa_scale = previous_gpa * 25
   
    # Hitung probabilitas kelulusan
    success_probability = (attendance * 0.6 + gpa_scale * 0.4)
   
    # Normalisasi ke persentase
    success_percentage = min(max(success_probability, 0), 100)
   
    # Tentukan status lulus/tidak
    if success_percentage >= 60:
        status = 'Pass'
    else:
        status = 'Fail'
   
    # Buat rekomendasi
    if attendance < 80:
        recommendation = 'Improve attendance to increase success chance'
    elif previous_gpa < 3.0:
        recommendation = 'Consider additional study support or tutoring'
    else:
        recommendation = 'Continue with current study habits'
   
    return {
        'success_percentage': round(success_percentage, 2),
        'status': status,
        'recommendation': recommendation,
        'confidence': 82  # Confidence tetap untuk simulasi
    }


def predict_study_time(student, course, target_grade, current_grade):
    # Simulasi model prediksi waktu belajar
   
    # Hitung gap antara nilai target dan nilai saat ini
    grade_gap = max(target_grade - current_grade, 0)
   
    # Estimasi waktu belajar per minggu (dalam jam)
    # Asumsi: setiap poin kenaikan membutuhkan sekitar 0.5 jam per minggu
    weekly_hours = grade_gap * 0.5
   
    # Tentukan tingkat kesulitan kursus (simulasi)
    course_difficulty = 1.2  # Faktor pengali (lebih tinggi = lebih sulit)
   
    # Sesuaikan waktu belajar berdasarkan kesulitan
    adjusted_hours = weekly_hours * course_difficulty
   
    # Buat rekomendasi jadwal
    if adjusted_hours < 5:
        schedule = 'Recommended: 1 hour per day, 5 days a week'
    elif adjusted_hours < 10:
        schedule = 'Recommended: 2 hours per day, 5 days a week'
    else:
        schedule = 'Recommended: 2-3 hours per day, 7 days a week'
   
    return {
        'recommended_hours': round(adjusted_hours, 1),
        'weekly_schedule': schedule,
        'expected_improvement': min(grade_gap, 20),  # Batasi peningkatan yang diharapkan
        'confidence': 75  # Confidence tetap untuk simulasi
    }


def predict_best_instructor(student, course, learning_style):
    # Simulasi model rekomendasi instruktur
   
    # Dalam implementasi nyata, model ini akan:
    # 1. Mendapatkan data tentang instruktur dan gaya mengajar mereka
    # 2. Mendapatkan data tentang kinerja siswa dengan instruktur tersebut
    # 3. Mencocokkan gaya belajar siswa dengan gaya mengajar instruktur
   
    # Untuk simulasi, kita hanya akan membuat rekomendasi palsu
    instructors = list(Instructor.objects.all())
   
    if not instructors:
        return {
            'no_instructors': True
        }
   
    # Pilih instruktur secara "acak" berdasarkan gaya belajar
    instructor_index = hash(f"{student.name}_{course.course_name}_{learning_style}") % len(instructors)
    recommended_instructor = instructors[instructor_index]
   
    # Buat alasan rekomendasi berdasarkan gaya belajar
    if learning_style == 'visual':
        reason = f"{recommended_instructor.instructor_name} uses visual teaching methods that match your learning style"
    elif learning_style == 'auditory':
        reason = f"{recommended_instructor.instructor_name} emphasizes discussions and lectures that suit your auditory learning preferences"
    else:  # kinesthetic
        reason = f"{recommended_instructor.instructor_name} incorporates hands-on activities that align with your kinesthetic learning style"
   
    # Simulasi kompatibilitas
    compatibility = hash(f"{student.stu_id}_{recommended_instructor.instructor_id}") % 40 + 60  # 60-99%
   
    return {
        'instructor': recommended_instructor,
        'compatibility': compatibility,
        'reason': reason,
        'confidence': 78  # Confidence tetap untuk simulasi
    }


def predict_grade(student, course, attendance, midterm_score, project_score):
    # Dapatkan data untuk training
    enrollments = Enrollment.objects.all()
    data = []
   
    for enrollment in enrollments:
        # Dapatkan nilai ujian jika ada
        midterm = Assessment.objects.filter(enroll=enrollment, assessment_type='Midterm').first()
        final = Assessment.objects.filter(enroll=enrollment, assessment_type='Final').first()
        project = Assessment.objects.filter(enroll=enrollment, assessment_type='Project').first()
       
        # Dapatkan kehadiran jika ada
        attend = Attendance.objects.filter(enroll=enrollment).first()
       
        # Hanya tambahkan jika semua data tersedia dan nilai akhir (grade) tidak null
        if midterm and final and project and attend and enrollment.grade is not None:
            data.append({
                'midterm_score': midterm.score,
                'final_score': final.score,
                'project_score': project.score,
                'attendance': attend.attendance_percentage,
                'grade': enrollment.grade
            })
   
    # Jika tidak ada data yang cukup
    if len(data) < 10:
        return {
            'predicted_grade': 'Not enough data for prediction',
            'confidence': 0
        }
   
    # Convert ke DataFrame
    df = pd.DataFrame(data)
   
    # Pisahkan fitur dan target
    X = df[['midterm_score', 'project_score', 'attendance']]
    y = df['grade']
   
    # Train test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
   
    # Standardisasi fitur
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
   
    # Buat dan latih model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train_scaled, y_train)
   
    # Input untuk prediksi
    input_data = np.array([[midterm_score, project_score, attendance]])
    input_data_scaled = scaler.transform(input_data)
   
    # Prediksi
    predicted_grade = model.predict(input_data_scaled)[0]
   
    # Hitung confidence (bisa menggunakan std dev dari prediksi ensemble)
    predictions = []
    for estimator in model.estimators_:
        predictions.append(estimator.predict(input_data_scaled)[0])
   
    confidence = 1 - (np.std(predictions) / 100)  # Penskalaan sederhana
   
    return {
        'predicted_grade': round(predicted_grade, 2),
        'confidence': round(confidence * 100, 2)
    }

def signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']  
        email = request.POST['email'] 
        studentid = request.POST['studentid']    

        myuser = User.objects.create_user(username, email, studentid)
        myuser.first_name = first_name
        myuser.last_name = last_name
        myuser.save()

        return redirect('signin')
    
    # Handle GET request (show the signup form)
    return render(request, 'academic_analytics/signup.html')


def signin(request):
    if request.method == 'POST':
        email = request.POST['email']
        studentid = request.POST['studentid']

        try:
            student = Student.objects.get(email=email, stu_id=studentid)
            # Log the student in using session
            request.session['student_id'] = student.stu_id
            return redirect('home')  # Ensure 'home' exists in your urls.py
        except Student.DoesNotExist:
            messages.error(request, "Invalid username or student ID.")

    return render(request, 'academic_analytics/signin.html')