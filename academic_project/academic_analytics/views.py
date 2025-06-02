from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Student, Course, Enrollment, Assessment, Attendance, Department, Instructor, CourseDifficulty
from .forms import GradePredictionForm, RecommendationForm, InstructorRecommendationForm, CourseRecommendationForm, RiskDropoutForm
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
import os
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib import messages
import pickle
import io
import base64
import matplotlib.pyplot as plt
import seaborn as sns

def prepare_input_data(stu_id, course_id, engine, le):
    # Query untuk rata-rata nilai sebelumnya
    avg_query = f"""
        SELECT AVG(grade) AS avg_prev_grade
        FROM enrollment
        WHERE stu_id = {stu_id} AND course_id <> {course_id}
    """
    avg_grade_df = pd.read_sql(avg_query, engine)
    avg_grade = avg_grade_df.iloc[0]['avg_prev_grade'] if not pd.isna(avg_grade_df.iloc[0]['avg_prev_grade']) else 0

    # Query untuk mendapatkan tingkat kesulitan course
    diff_query = f"""
        SELECT difficulty_level
        FROM course_difficulty
        WHERE course_id = {course_id}
    """
    difficulty = pd.read_sql(diff_query, engine).iloc[0]['difficulty_level']
    difficulty_encoded = le.transform([difficulty])[0]

    # Query untuk tingkat kelulusan course
    pass_rate_query = f"""
        SELECT COUNT(*) FILTER (WHERE grade >= 60) * 1.0 / NULLIF(COUNT(*), 0) AS pass_rate
        FROM enrollment
        WHERE course_id = {course_id}
    """
    pass_rate_result = pd.read_sql(pass_rate_query, engine)
    course_pass_rate = pass_rate_result.iloc[0]['pass_rate'] if not pd.isna(pass_rate_result.iloc[0]['pass_rate']) else 0

    # Query untuk memeriksa apakah mahasiswa pernah mengambil mata kuliah dengan tingkat kesulitan tersebut
    experience_query = f"""
        SELECT COUNT(*) AS course_count
        FROM enrollment e
        JOIN course_difficulty cd ON e.course_id = cd.course_id
        WHERE e.stu_id = {stu_id} AND cd.difficulty_level = '{difficulty}'
    """
    experience_result = pd.read_sql(experience_query, engine)
    has_experience = experience_result.iloc[0]['course_count'] > 0

    # Query untuk mendapatkan jumlah mata kuliah yang lulus untuk setiap tingkat kesulitan
    # Hanya jika mahasiswa memiliki pengalaman
    if has_experience:
        easy_passed_query = f"""
            SELECT COUNT(*) AS easy_passed_count
            FROM enrollment e
            JOIN course_difficulty cd ON e.course_id = cd.course_id
            WHERE e.stu_id = {stu_id} AND e.grade >= 60 AND cd.difficulty_level = 'Easy';
        """
        easy_passed = pd.read_sql(easy_passed_query, engine).iloc[0]['easy_passed_count']
        
        medium_passed_query = f"""
            SELECT COUNT(*) AS medium_passed_count
            FROM enrollment e
            JOIN course_difficulty cd ON e.course_id = cd.course_id
            WHERE e.stu_id = {stu_id} AND e.grade >= 60 AND cd.difficulty_level = 'Medium';
        """
        medium_passed = pd.read_sql(medium_passed_query, engine).iloc[0]['medium_passed_count']
        
        hard_passed_query = f"""
            SELECT COUNT(*) AS hard_passed_count
            FROM enrollment e
            JOIN course_difficulty cd ON e.course_id = cd.course_id
            WHERE e.stu_id = {stu_id} AND e.grade >= 60 AND cd.difficulty_level = 'Hard';
        """
        hard_passed = pd.read_sql(hard_passed_query, engine).iloc[0]['hard_passed_count']

        # Buat DataFrame untuk prediksi dengan semua fitur yang mungkin dibutuhkan
        input_data = pd.DataFrame([{
            'avg_prev_grade': avg_grade,
            'easy_passed_count': easy_passed,
            'medium_passed_count': medium_passed,
            'hard_passed_count': hard_passed,
            'course_pass_rate': course_pass_rate,
            'difficulty_level_encoded': difficulty_encoded
        }])
    else:
        # Jika tidak ada pengalaman, buat DataFrame kosong
        input_data = pd.DataFrame()
    
    return input_data, difficulty, course_pass_rate, has_experience

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
        'recommendation': None,
        'instructor': None,  # Added instructor prediction results
    }

    prediction_results = {
        'grade': None,
        'recommendation': None,
        'instructor': None,
        'dropout': None
    }
    
    # Inisialisasi form
    forms = {
        'grade_form': GradePredictionForm(),
        'recommendation_form': RecommendationForm(),
        'instructor_form': InstructorRecommendationForm(),  # Added instructor form
        'course_recommendation_form': CourseRecommendationForm(),
        'risk_dropout_form': RiskDropoutForm() 
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
            
        elif form_type == 'recommendation':
            form = RecommendationForm(request.POST)
            if form.is_valid():
                student = form.cleaned_data['student']
                course = form.cleaned_data['course']
                stu_id = student.stu_id
                course_id = course.course_id

                # Buat koneksi ke database
                engine = create_engine('postgresql://postgres:12345678@localhost:5432/final')

                # 🔍 Cek apakah course sudah pernah diambil
                taken_query = f"""
                    SELECT COUNT(*) AS taken_count
                    FROM enrollment
                    WHERE stu_id = {stu_id} AND course_id = {course_id}
                """
                taken_result = pd.read_sql(taken_query, engine)
                already_taken = taken_result.iloc[0]['taken_count'] > 0

                if already_taken:
                    prediction_results['recommendation'] = {
                        'stu_id': stu_id,
                        'course_id': course_id,
                        'warning': "⚠️ The Student Has Taken This Course."
                    }
                    forms['recommendation_form'] = form
                    context = {
                        'forms': forms,
                        'prediction_results': prediction_results
                    }
                    return render(request, 'academic_analytics/admin_panel.html', context)

                # Jika belum pernah ambil, lanjut proses prediksi
                BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                model_path = os.path.join(BASE_DIR, 'ml_model', 'course_recommendation_models.pkl')
                model_data = joblib.load(model_path)
                le = model_data['label_encoder']

                new_data, difficulty, pass_rate, has_experience = prepare_input_data(stu_id, course_id, engine, le)

                prediction_results['recommendation'] = {
                    'stu_id': stu_id,
                    'course_id': course_id,
                    'difficulty': difficulty,
                    'pass_rate': round(pass_rate * 100, 2),
                }

                if has_experience:
                    if difficulty == 'Easy':
                        model = model_data['easy_model']['model']
                        features = model_data['easy_model']['features']
                    elif difficulty == 'Medium':
                        model = model_data['medium_model']['model']
                        features = model_data['medium_model']['features']
                    else:
                        model = model_data['hard_model']['model']
                        features = model_data['hard_model']['features']

                    try:
                        new_data_filtered = new_data[features]
                        pred = model.predict(new_data_filtered)[0]
                        proba = model.predict_proba(new_data_filtered)[0][1]

                        prediction_results['recommendation'].update({
                            'probability': round(proba * 100, 2),
                            'recommended': "✅ Recommended" if pred == 1 else "❌ Not Recommended",
                            'top_recommendation': {
                            'course_id': course_id,
                            'course_name': course.course_name,
                            'probability': round(proba * 100, 2)
                        }
                        })
                        top_courses = get_top_courses_by_difficulty(stu_id, engine, le, model_data)
                        prediction_results['recommendation'].update({
                            'top_by_difficulty': top_courses
})
                    except KeyError:
                        prediction_results['recommendation'].update({
                            'warning': f"The Student Has Not Experience in This Level {difficulty}"
                        })
                else:
                    prediction_results['recommendation'].update({
                        'warning': f"The Student Has Not Experience in this level {difficulty}"
                    })

                forms['recommendation_form'] = form

                
        elif form_type == 'instructor':
            form = InstructorRecommendationForm(request.POST)
            if form.is_valid():
                course = form.cleaned_data['course']
                target_grade = form.cleaned_data['target_grade']
                student = form.cleaned_data['student']

                # Buat koneksi ke database
                engine = create_engine('postgresql://postgres:12345678@localhost:5432/final')

                # 🔍 Cek apakah mahasiswa sudah pernah mengambil course ini
                taken_query = f"""
                    SELECT COUNT(*) AS taken_count
                    FROM enrollment
                    WHERE stu_id = {student.stu_id} AND course_id = {course.course_id}
                """
                taken_result = pd.read_sql(taken_query, engine)
                already_taken = taken_result.iloc[0]['taken_count'] > 0

                if already_taken:
                    messages.warning(request, "⚠️ Mahasiswa sudah pernah mengambil mata kuliah ini.")
                    forms['instructor_form'] = form
                    context = {
                        'forms': forms,
                        'prediction_results': prediction_results
                    }
                    return render(request, 'academic_analytics/admin_panel.html', context)

                # Get the absolute path to the model file
                BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                model_path = os.path.join(BASE_DIR, 'ml_model', 'instructor_recommendation_models.pkl')

                # Check if model file exists
                if not os.path.exists(model_path):
                    messages.error(request, f"Model file not found at {model_path}")
                else:
                    try:
                        with open(model_path, 'rb') as file:
                            models_data = pickle.load(file)

                        recommendations = recommend_instructors_with_prediction(
                            model=models_data['model'],
                            data=models_data['data'],
                            instructor_metrics=models_data['instructor_metrics'],
                            courses=models_data['courses'],
                            course_name=course.course_name,
                            target_grade=target_grade,
                            student_id=student.stu_id,
                            top_n=3
                        )

                        if isinstance(recommendations, dict) and 'error' in recommendations:
                            messages.error(request, recommendations['error'])
                        else:
                            prediction_results['instructor'] = {
                                'course_name': course.course_name,
                                'target_grade': target_grade,
                                'recommendations': recommendations
                            }

                    except Exception as e:
                        import traceback
                        error_details = traceback.format_exc()
                        messages.error(request, f"Error generating instructor recommendations: {str(e)}")
                        print(f"Detailed error: {error_details}")

                forms['instructor_form'] = form


        elif form_type == 'course_recommendation':
            form = CourseRecommendationForm(request.POST)
            if form.is_valid():
                course_a = form.cleaned_data['course_a'].course_id
                course_b = form.cleaned_data['course_b'].course_id
                score_a = form.cleaned_data['score_a']
                score_b = form.cleaned_data['score_b']

                engine = create_engine('postgresql://postgres:12345678@localhost:5432/final')
                recommendation_result = prepare_course_recommendation(course_a, course_b, score_a, score_b, engine)

                prediction_results['course_recommendation'] = recommendation_result

                forms['course_recommendation_form'] = form
        elif form_type == 'dropout':
            form = RiskDropoutForm(request.POST)
            if form.is_valid():
                stu_id = form.cleaned_data['student'].stu_id

                BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                model_path = os.path.join(BASE_DIR, 'ml_model', 'student_segmentation_kmeans.pkl')

                with open(model_path, 'rb') as file:
                    model_data = pickle.load(file)

                engine = create_engine('postgresql://postgres:12345678@localhost:5432/final')
                input_data = prepare_dropout_risk_data(stu_id, engine)

                # Prediksi klaster
                scaled = model_data['scaler'].transform(input_data)
                cluster = model_data['model'].predict(scaled)[0]

                prediction_results['dropout'] = {
                    'stu_id': stu_id,
                    'cluster': cluster
                }

                forms['risk_dropout_form'] = form


    context = {
        'forms': forms,
        'prediction_results': prediction_results
    }
    return render(request, 'academic_analytics/admin_panel.html', context)

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

# Modified section from views.py for improved error handling
# Replace the corresponding part in your views.py file

def recommend_instructors_with_prediction(model, data, instructor_metrics, courses, course_name, target_grade, student_id, top_n=3):
    if course_name not in courses:
        return {"error": f"Course '{course_name}' not found in the dataset"}

    course_metrics = instructor_metrics[instructor_metrics['course_name'] == course_name]
    if len(course_metrics) == 0:
        return {"error": f"No instructor data available for course '{course_name}'"}

    try:
        student = Student.objects.select_related('dept').get(pk=student_id)
        enrollment = Enrollment.objects.filter(stu=student).select_related('course', 'semester').order_by('-semester__semester_id').first()

        semester_name = 'Semester 1'
        difficulty_level = 'Medium'
        assessment_type = 'Midterm'
        attendance_percentage = 85
        assessment_score = 80

        if enrollment:
            semester_name = enrollment.semester.semester_name
            difficulty = CourseDifficulty.objects.filter(course=enrollment.course).first()
            if difficulty:
                difficulty_level = difficulty.difficulty_level
            attendance = Attendance.objects.filter(enroll=enrollment).first()
            if attendance:
                attendance_percentage = attendance.attendance_percentage
            assessment = Assessment.objects.filter(enroll=enrollment).first()
            if assessment:
                assessment_type = assessment.assessment_type
                assessment_score = assessment.score

        student_profile = {
            'course_name': course_name,
            'semester_name': semester_name,
            'difficulty_level': difficulty_level,
            'assessment_type': assessment_type,
            'gender': student.gender,
            'student_department': student.dept.dept_name,
            'attendance_percentage': attendance_percentage,
            'assessment_score': assessment_score
        }

    except Student.DoesNotExist:
        return {"error": f"Student with ID {student_id} does not exist"}

    instructors_data = []

    for _, row in course_metrics.iterrows():
        instructor = row['instructor_name']
        avg_grade = row['avg_grade']
        std_grade = max(row['std_grade'], 1)
        count = row['count']

        if avg_grade >= target_grade:
            base_score = 1
        else:
            std_diff = (target_grade - avg_grade) / std_grade
            base_score = 1 + std_diff

        confidence_factor = min(1, count / 10)
        final_score = base_score / confidence_factor

        instructor_course_data = data[
            (data['instructor_name'] == instructor) & 
            (data['course_name'] == course_name)
        ]
        success_rate = len(instructor_course_data[instructor_course_data['grade'] >= target_grade]) / len(instructor_course_data)

        profile = student_profile.copy()
        profile['instructor_name'] = instructor
        profile_df = pd.DataFrame([profile])

        try:
            predicted_grade = model.predict(profile_df)[0]
        except Exception as e:
            print(f"Prediction error for instructor {instructor}: {e}")
            predicted_grade = avg_grade

        instructors_data.append({
            'instructor_name': instructor,
            'average_grade': round(avg_grade, 2),
            'success_rate': round(success_rate * 100, 2),
            'recommendation_score': round(final_score, 2),
            'student_count': count,
            'predicted_score': round(predicted_grade, 2),
            'match_score': round(100 - (final_score * 25), 1)
        })

    instructors_data.sort(key=lambda x: (-x['predicted_score'], x['recommendation_score']))
    return instructors_data[:top_n]


#Abella
def prepare_course_recommendation(course_a_id, course_b_id, score_a, score_b, engine, top_n=3):
    """
    Prepare course recommendations based on two previously taken courses.
    Uses association rules to recommend courses and predict grades.
    
    Parameters:
    - course_a_id: ID of the first course
    - course_b_id: ID of the second course
    - score_a: Grade earned in first course
    - score_b: Grade earned in second course
    - engine: SQLAlchemy database engine
    - top_n: Number of recommendations to return
    
    Returns:
    - Dictionary with recommendation results
    """
    try:
        # Get the absolute path to the model file
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(BASE_DIR, 'ml_model', 'course_association_model.pkl')
        
        # Check if model file exists
        if not os.path.exists(model_path):
            return {"error": "Model file not found"}
            
        # Load model
        with open(model_path, 'rb') as file:
            model_data = pickle.load(file)
            
        # Extract model components
        rules_sorted = model_data['association_rules']
        
        # Get recommendations based on courses taken
        filtered_rules = recommend_courses(rules_sorted, [course_a_id, course_b_id])
        
        # If no rules exist, return early
        if filtered_rules.empty:
            return {"error": "No course recommendations found for the selected courses combination"}
            
        # Get course predictions
        predictions_df = predict_top_3_scores(filtered_rules, course_a_id, course_b_id, score_a, score_b, engine)
        
        # Get course names for the input courses
        course_a_query = f"SELECT course_name FROM course WHERE course_id = {course_a_id}"
        course_b_query = f"SELECT course_name FROM course WHERE course_id = {course_b_id}"
        course_a_name = pd.read_sql(course_a_query, engine).iloc[0]['course_name'] if not pd.read_sql(course_a_query, engine).empty else f"Course {course_a_id}"
        course_b_name = pd.read_sql(course_b_query, engine).iloc[0]['course_name'] if not pd.read_sql(course_b_query, engine).empty else f"Course {course_b_id}"
        
        # Convert predictions to list of dictionaries for output
        recommendations = []
        for _, row in predictions_df.iterrows():
            course_id = row['course_id']
            predicted_score = row['predicted_score']
            
            # Get course name from database
            course_query = f"SELECT course_name FROM course WHERE course_id = {course_id}"
            course_name_df = pd.read_sql(course_query, engine)
            course_name = course_name_df.iloc[0]['course_name'] if not course_name_df.empty else f"Course {course_id}"
            
            recommendations.append({
                'course_id': course_id,
                'course_name': course_name,
                'predicted_score': predicted_score
            })
        
        # Return results dictionary
        return {
            'course_a': {
                'id': course_a_id,
                'name': course_a_name,
                'score': score_a
            },
            'course_b': {
                'id': course_b_id,
                'name': course_b_name,
                'score': score_b
            },
            'recommendations': recommendations
        }
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error generating course recommendations: {str(e)}")
        print(f"Detailed error: {error_details}")
        return {"error": f"Error generating recommendations: {str(e)}"}


def course_recommendation(request):
    """
    View function for processing course recommendation requests.
    """
    # Initialize result dictionary
    recommendation_result = None
    
    # Initialize form
    form = CourseRecommendationForm()
    
    if request.method == 'POST':
        form = CourseRecommendationForm(request.POST)
        if form.is_valid():
            course_a = form.cleaned_data['course_a'].course_id
            course_b = form.cleaned_data['course_b'].course_id
            score_a = form.cleaned_data['score_a']
            score_b = form.cleaned_data['score_b']
            
            # Create database connection
            engine = create_engine('postgresql://postgres:12345678@localhost:5432/final')
            
            # Get recommendation results
            recommendation_result = prepare_course_recommendation(
                course_a, course_b, score_a, score_b, engine
            )

    context = {
        'form': form,
        'recommendation_result': recommendation_result
    }
    return render(request, 'academic_analytics/course_recommendation.html', context)


# Helper functions needed for course recommendations
def recommend_courses(rules_df, input_courses, top_n=3):
    """Recommend courses based on association rules and student's current courses"""
    input_set = frozenset(input_courses)
    filtered = rules_df[
        rules_df['antecedents'].apply(lambda x: x.issubset(input_set))
    ].sort_values(by='confidence', ascending=False)

    return filtered.head(top_n)


def get_top_3_consequents(rules_df):
    """Extract the top 3 consequent courses from the rules dataframe"""
    top_3 = []
    for _, row in rules_df.iterrows():
        for course in row['consequents']:
            if course not in top_3:
                top_3.append(course)
            if len(top_3) == 3:
                return top_3
    return top_3


def get_training_data(course_a, course_b, target_course, engine):
    """Get training data for the linear regression model"""
    query = f"""
        SELECT
            s.stu_id,
            MAX(CASE WHEN e.course_id = {course_a} THEN e.grade END) AS score_a,
            MAX(CASE WHEN e.course_id = {course_b} THEN e.grade END) AS score_b,
            MAX(CASE WHEN e.course_id = {target_course} THEN e.grade END) AS score_target
        FROM enrollment e
        JOIN student s ON s.stu_id = e.stu_id
        WHERE e.course_id IN ({course_a}, {course_b}, {target_course})
        GROUP BY s.stu_id
        HAVING COUNT(DISTINCT e.course_id) = 3
    """
    df = pd.read_sql(query, engine)
    return df.dropna()


def train_model(df):
    """Train a linear regression model to predict target course score"""
    X = df[['score_a', 'score_b']]
    y = df['score_target']
    model = LinearRegression()
    model.fit(X, y)
    return model


def predict_score(model, input_score_a, input_score_b):
    """Predict a student's score in a target course"""
    return model.predict([[input_score_a, input_score_b]])[0]


def predict_top_3_scores(rules_df, course_a, course_b, score_a, score_b, engine):
    """Predict scores for top 3 recommended courses"""
    top_3_consequents = get_top_3_consequents(rules_df)
    predictions = []

    for z in top_3_consequents:
        df_train = get_training_data(course_a, course_b, z, engine)

        if not df_train.empty and len(df_train) >= 5:  # Ensure enough data for training
            model = train_model(df_train)
            predicted = predict_score(model, score_a, score_b)
            predictions.append({'course_id': z, 'predicted_score': round(predicted, 2)})
        else:
            predictions.append({'course_id': z, 'predicted_score': 'Insufficient Data'})

    return pd.DataFrame(predictions)

def prepare_dropout_risk_data(stu_id, engine):
    # Query nilai rata-rata dari grade
    avg_grade_query = f"""
        SELECT AVG(grade) AS avg_grade
        FROM enrollment
        WHERE stu_id = {stu_id}
    """
    avg_grade = pd.read_sql(avg_grade_query, engine).iloc[0]['avg_grade'] or 0

    # Query nilai rata-rata dari skor assessment
    avg_assessment_query = f"""
        SELECT AVG(a.score) AS avg_assessment
        FROM assessment a
        JOIN enrollment e ON a.enroll_id = e.enroll_id
        WHERE e.stu_id = {stu_id}
    """
    avg_assessment = pd.read_sql(avg_assessment_query, engine).iloc[0]['avg_assessment'] or 0

    # Query nilai rata-rata kehadiran
    avg_attendance_query = f"""
        SELECT AVG(at.attendance_percentage) AS avg_attendance
        FROM attendance at
        JOIN enrollment e ON at.enroll_id = e.enroll_id
        WHERE e.stu_id = {stu_id}
    """
    avg_attendance = pd.read_sql(avg_attendance_query, engine).iloc[0]['avg_attendance'] or 0

    # Jumlah mata kuliah yang pernah diambil
    num_courses_query = f"""
        SELECT COUNT(*) AS num_courses
        FROM enrollment
        WHERE stu_id = {stu_id}
    """
    num_courses = pd.read_sql(num_courses_query, engine).iloc[0]['num_courses'] or 0

    # Rata-rata skor tingkat kesulitan
    difficulty_query = f"""
        SELECT AVG(CASE 
            WHEN cd.difficulty_level = 'Easy' THEN 1
            WHEN cd.difficulty_level = 'Medium' THEN 2
            WHEN cd.difficulty_level = 'Hard' THEN 3
            ELSE NULL END
        ) AS avg_difficulty
        FROM enrollment e
        JOIN course_difficulty cd ON e.course_id = cd.course_id
        WHERE e.stu_id = {stu_id}
    """
    avg_difficulty = pd.read_sql(difficulty_query, engine).iloc[0]['avg_difficulty'] or 0

    # Ambil gender dari student
    gender_query = f"""
        SELECT gender FROM student WHERE stu_id = {stu_id}
    """
    gender = pd.read_sql(gender_query, engine).iloc[0]['gender']
    gender_encoded = 1 if gender == "Male" else 0

    # Bentuk DataFrame
    input_data = pd.DataFrame([{
        "avg_grade": avg_grade,
        "avg_assessment": avg_assessment,
        "avg_attendance": avg_attendance,
        "num_courses": num_courses,
        "avg_difficulty": avg_difficulty,
        "gender": gender_encoded
    }])

    return input_data

#Cecil
def dropout_risk_view(request):
    context = {}
    
    # Load your form here (assumed)
    # Example:
    # dropout_form = YourDropoutForm(request.POST or None)
    
    if request.method == 'POST' and request.POST.get('form_type') == 'dropout':
        student_id = request.POST.get('student')
        
        # Load the model and scaler
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ml_model', 'student_segmentation_kmeans.pkl')
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)

        model = model_data['model']
        scaler = model_data['scaler']
        features = model_data['features']

        # Prepare data for the specific student
        df_student = prepare_dropout_risk_data(student_id, engine)
        X_student = scaler.transform(df_student[features])
        assigned_cluster = model.predict(X_student)[0]

        # Load full data for visualization
        student_df, enrollment_df, assessment_df, attendance_df, difficulty_df = load_data()
        data_all = preprocess(student_df, enrollment_df, assessment_df, attendance_df, difficulty_df)

        # Make sure to drop NA for scaling consistency
        X_all = data_all[features].dropna()
        X_scaled = scaler.transform(X_all)
        labels = model.labels_

        # Find index of the selected student in the data_all dataframe
        student_indices = data_all.index[data_all['stu_id'] == int(student_id)].tolist()
        student_index = student_indices[0] if student_indices else None

        # Generate plot
        cluster_plot = generate_cluster_plot(X_scaled, labels, student_index=student_index)

        context = {
            'forms': {
                'risk_dropout_form': None,  # Replace with your actual form instance
            },
            'prediction_results': {
                'dropout': {
                    'stu_id': student_id,
                    'cluster': int(assigned_cluster),
                }
            },
            'cluster_plot': cluster_plot,
        }
    else:
        # GET or no form submitted: prepare empty form context or any defaults
        context = {
            'forms': {
                'risk_dropout_form': None,  # Replace with your actual empty form
            }
        }

    return render(request, 'admin_panel.html', context)


# --- Your helper functions ---

def prepare_dropout_risk_data(stu_id, engine):
    # Queries same as your existing function, trimmed here for brevity
    # Make sure to handle cases where stu_id may not be valid
    # ...
    # Your implementation copied here
    pass

def load_data():
    student_df = pd.read_sql("SELECT * FROM Student", engine)
    enrollment_df = pd.read_sql("SELECT * FROM Enrollment", engine)
    assessment_df = pd.read_sql("SELECT * FROM Assessment", engine)
    attendance_df = pd.read_sql("SELECT * FROM Attendance", engine)
    difficulty_df = pd.read_sql("SELECT * FROM Course_Difficulty", engine)
    return student_df, enrollment_df, assessment_df, attendance_df, difficulty_df

def preprocess(student_df, enrollment_df, assessment_df, attendance_df, difficulty_df):
    # Your preprocessing logic here
    pass

import os
import io
import base64
import pickle
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.decomposition import PCA
from sqlalchemy import create_engine

# DB connection (adjust as needed)
engine = create_engine('postgresql://postgres:12345678@localhost:5432/final')

def prepare_dropout_risk_data(stu_id, engine):
    avg_grade_query = f"""SELECT AVG(grade) AS avg_grade FROM enrollment WHERE stu_id = {stu_id}"""
    avg_assessment_query = f"""SELECT AVG(a.score) AS avg_assessment FROM assessment a JOIN enrollment e ON a.enroll_id = e.enroll_id WHERE e.stu_id = {stu_id}"""
    avg_attendance_query = f"""SELECT AVG(at.attendance_percentage) AS avg_attendance FROM attendance at JOIN enrollment e ON at.enroll_id = e.enroll_id WHERE e.stu_id = {stu_id}"""
    num_courses_query = f"""SELECT COUNT(*) AS num_courses FROM enrollment WHERE stu_id = {stu_id}"""
    difficulty_query = f"""
        SELECT AVG(CASE 
            WHEN cd.difficulty_level = 'Easy' THEN 1
            WHEN cd.difficulty_level = 'Medium' THEN 2
            WHEN cd.difficulty_level = 'Hard' THEN 3
            ELSE NULL END
        ) AS avg_difficulty
        FROM enrollment e
        JOIN course_difficulty cd ON e.course_id = cd.course_id
        WHERE e.stu_id = {stu_id}
    """
    gender_query = f"""SELECT gender FROM student WHERE stu_id = {stu_id}"""

    avg_grade = pd.read_sql(avg_grade_query, engine).iloc[0]['avg_grade'] or 0
    avg_assessment = pd.read_sql(avg_assessment_query, engine).iloc[0]['avg_assessment'] or 0
    avg_attendance = pd.read_sql(avg_attendance_query, engine).iloc[0]['avg_attendance'] or 0
    num_courses = pd.read_sql(num_courses_query, engine).iloc[0]['num_courses'] or 0
    avg_difficulty = pd.read_sql(difficulty_query, engine).iloc[0]['avg_difficulty'] or 0
    gender = pd.read_sql(gender_query, engine).iloc[0]['gender']
    gender_encoded = 1 if gender == "Male" else 0

    return pd.DataFrame([{
        "avg_grade": avg_grade,
        "avg_assessment": avg_assessment,
        "avg_attendance": avg_attendance,
        "num_courses": num_courses,
        "avg_difficulty": avg_difficulty,
        "gender": gender_encoded
    }])

def load_data():
    student_df = pd.read_sql("SELECT * FROM Student", engine)
    enrollment_df = pd.read_sql("SELECT * FROM Enrollment", engine)
    assessment_df = pd.read_sql("SELECT * FROM Assessment", engine)
    attendance_df = pd.read_sql("SELECT * FROM Attendance", engine)
    difficulty_df = pd.read_sql("SELECT * FROM Course_Difficulty", engine)
    return student_df, enrollment_df, assessment_df, attendance_df, difficulty_df

def preprocess(student_df, enrollment_df, assessment_df, attendance_df, difficulty_df):
    assessment_avg = assessment_df.groupby("enroll_id")["score"].mean().reset_index()
    assessment_avg.columns = ["enroll_id", "avg_assessment_score"]

    enrollment_df = enrollment_df.merge(assessment_avg, on="enroll_id", how="left")
    enrollment_df = enrollment_df.merge(attendance_df, on="enroll_id", how="left")
    enrollment_df = enrollment_df.merge(difficulty_df[['course_id', 'difficulty_level']], on="course_id", how="left")
    
    difficulty_map = {"Easy": 1, "Medium": 2, "Hard": 3}
    enrollment_df["difficulty_score"] = enrollment_df["difficulty_level"].map(difficulty_map)

    agg = enrollment_df.groupby("stu_id").agg({
        "grade": "mean",
        "avg_assessment_score": "mean",
        "attendance_percentage": "mean",
        "course_id": "count",
        "difficulty_score": "mean"
    }).reset_index()

    agg.columns = ["stu_id", "avg_grade", "avg_assessment", "avg_attendance", "num_courses", "avg_difficulty"]
    agg = agg.merge(student_df[['stu_id', 'gender']], on='stu_id', how='left')
    agg['gender'] = agg['gender'].map({"Male": 1, "Female": 0})

    return agg

def generate_cluster_plot(X_scaled, labels, student_index=None):
    pca = PCA(n_components=2)
    reduced = pca.fit_transform(X_scaled)

    df_plot = pd.DataFrame(reduced, columns=['PC1', 'PC2'])
    df_plot['Cluster'] = labels

    plt.figure(figsize=(8, 6))
    sns.scatterplot(data=df_plot, x='PC1', y='PC2', hue='Cluster', palette='Set1', s=100, alpha=0.7)

    if student_index is not None:
        plt.scatter(df_plot.loc[student_index, 'PC1'], df_plot.loc[student_index, 'PC2'], 
                    color='black', s=200, edgecolor='white', label='Selected Student', marker='X')

    plt.title('Student Clustering Visualization')
    plt.legend()
    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    buffer.close()
    plt.close()

    return image_base64


def main(student_id):
    # Load model + scaler + features
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ml_model', 'student_segmentation_kmeans.pkl')
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)

    model = model_data['model']
    scaler = model_data['scaler']
    features = model_data['features']

    # Prepare student data for prediction
    df_student = prepare_dropout_risk_data(student_id, engine)
    X_student = scaler.transform(df_student[features])
    assigned_cluster = model.predict(X_student)[0]

    print(f"Student ID: {student_id} assigned to cluster: {assigned_cluster}")

    # Load all data to visualize
    student_df, enrollment_df, assessment_df, attendance_df, difficulty_df = load_data()
    data_all = preprocess(student_df, enrollment_df, assessment_df, attendance_df, difficulty_df)

    X_all = data_all[features].dropna()
    X_scaled = scaler.transform(X_all)
    labels = model.labels_

    # Find the index of the student in the data_all dataframe for plotting
    student_indices = data_all.index[data_all['stu_id'] == int(student_id)].tolist()
    student_index = student_indices[0] if student_indices else None

    # --- Generate cluster plot base64 (optional) ---
    cluster_plot_base64 = generate_cluster_plot(X_scaled, labels, student_index=student_index)

    # --- Prepare PCA 2D data and labels for JS visualization ---
    pca = PCA(n_components=2)
    reduced = pca.fit_transform(X_scaled)
    pca_data = reduced.tolist()   # List of [PC1, PC2]
    labels_list = labels.tolist()

    # Optionally save base64 image locally for debug
    with open("cluster_plot.png", "wb") as img_file:
        img_file.write(base64.b64decode(cluster_plot_base64))
    print("Cluster plot saved as 'cluster_plot.png'.")

    # Return everything needed for frontend
    return {
        'cluster_plot_base64': cluster_plot_base64,
        'pca_data': pca_data,
        'labels': labels_list,
        'student_index': student_index,
        'assigned_cluster': assigned_cluster,
        'student_id': student_id
    }


if __name__ == "__main__":
    student_id = 123  # Replace with your target student ID
    result = main(student_id)
    print(result)


def your_view_function(request):
    context = {}

    if request.method == 'POST' and request.POST.get('form_type') == 'grade':
        # Extract form data
        student_id = request.POST.get('student')
        course_id = request.POST.get('course')
        attendance = float(request.POST.get('attendance', 0))
        midterm_score = float(request.POST.get('midterm_score', 0))
        project_score = float(request.POST.get('project_score', 0))

        # Predict grade logic here (replace with your real prediction)
        predicted_grade = your_grade_predictor(student_id, course_id, attendance, midterm_score, project_score)
        confidence = 85  # example confidence

        # Generate cluster plot base64 string for this student
        cluster_plot_base64 = main(student_id)  # Assuming main() from your earlier code returns base64 string

        # Pass results and cluster plot to context
        context['prediction_results'] = {
            'grade': {
                'predicted_grade': predicted_grade,
                'confidence': confidence,
            }
        }
        context['cluster_plot_base64'] = cluster_plot_base64

    # Add your forms to context as usual, e.g.:
    context['forms'] = {
        'grade_form': YourGradeForm(),
        # ... other forms
    }

    return render(request, 'admin_panel.html', context)


#Punya Standy
def get_top_courses_by_difficulty(student_id, engine, le, model_data):
    top_courses = {}

    # Ambil semua course dan tingkat kesulitan
    all_courses = pd.read_sql("SELECT course_id FROM course", engine)
    difficulties = ['Easy', 'Medium', 'Hard']

    for diff in difficulties:
        course_ids = pd.read_sql(f"""
            SELECT cd.course_id
            FROM course_difficulty cd
            WHERE cd.difficulty_level = '{diff}'
        """, engine)['course_id'].tolist()

        best_course = None
        best_proba = -1

        for cid in course_ids:
            new_data, _, pass_rate, has_experience = prepare_input_data(student_id, cid, engine, le)

            if not has_experience or new_data.empty:
                continue

            if diff == 'Easy':
                model = model_data['easy_model']['model']
                features = model_data['easy_model']['features']
            elif diff == 'Medium':
                model = model_data['medium_model']['model']
                features = model_data['medium_model']['features']
            else:
                model = model_data['hard_model']['model']
                features = model_data['hard_model']['features']

            try:
                new_data_filtered = new_data[features]
                proba = model.predict_proba(new_data_filtered)[0][1]

                if proba > best_proba:
                    course_name_df = pd.read_sql(f"SELECT course_name FROM course WHERE course_id = {cid}", engine)
                    course_name = course_name_df.iloc[0]['course_name'] if not course_name_df.empty else f"Course {cid}"
                    best_course = {
                        'course_id': cid,
                        'course_name': course_name,
                        'probability': round(proba * 100, 2)
                    }
                    best_proba = proba
            except Exception as e:
                continue

        if best_course:
            top_courses[diff] = best_course

    return top_courses
