import os
import sys
import pickle
import pandas as pd
from sqlalchemy import create_engine
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split

from django.utils.timezone import now

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "academic_project.settings")  # Ganti dengan nama proyek Django-mu
import django
django.setup()

from academic_analytics.models import ModelInsan

engine = create_engine('postgresql://postgres:12345678@localhost:5051/final')

# SQL query
query = """
SELECT
    s.stu_id,
    s.gender,
    d.dept_name AS student_department,
    c.course_name,
    ci.instructor_id,
    i.instructor_name,
    sem.semester_name,
    cd.difficulty_level,
    att.attendance_percentage,
    a.assessment_type,
    a.score AS assessment_score,
    e.grade
FROM enrollment e
JOIN student s ON e.stu_id = s.stu_id
JOIN course c ON e.course_id = c.course_id
JOIN department d ON s.dept_id = d.dept_id
JOIN semester sem ON e.semester_id = sem.semester_id
JOIN course_difficulty cd ON e.course_id = cd.course_id
JOIN course_instructor ci ON ci.course_id = e.course_id AND ci.semester_id = e.semester_id
JOIN instructor i ON ci.instructor_id = i.instructor_id
LEFT JOIN assessment a ON a.enroll_id = e.enroll_id
LEFT JOIN attendance att ON att.enroll_id = e.enroll_id
ORDER BY s.stu_id, c.course_name, sem.semester_name;
"""

# Load data into DataFrame
data_df = pd.read_sql_query(query, con=engine)

# Drop rows with missing grades
data_df = data_df.dropna(subset=['grade'])

# Calculate instructor performance metrics
instructor_metrics = data_df.groupby(['instructor_name', 'course_name']).agg({
    'grade': ['mean', 'median', 'std', 'count']
}).reset_index()

instructor_metrics.columns = ['instructor_name', 'course_name', 'avg_grade', 'median_grade', 'std_grade', 'count']

# Extract unique courses and instructors
courses = sorted(data_df['course_name'].unique())
instructors = sorted(data_df['instructor_name'].unique())

# Define features for the model
categorical_features = ['course_name', 'instructor_name', 'semester_name',
                        'difficulty_level', 'assessment_type', 'gender', 'student_department']

preprocessor = ColumnTransformer(
    transformers=[
        ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
    ],
    remainder='passthrough'
)

# Prepare data for model training
X = data_df.drop(['grade', 'stu_id', 'instructor_id'], axis=1)
y = data_df['grade']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Create and train model
model = Pipeline([
    ('preprocessor', preprocessor),
    ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))
])

model.fit(X_train, y_train)

# Evaluate model
train_score = model.score(X_train, y_train)
test_score = model.score(X_test, y_test)

print(f"Model R² on training data: {train_score:.4f}")
print(f"Model R² on test data: {test_score:.4f}")

# Function to recommend instructors
def recommend_instructors(course_name, target_grade, top_n=3):
    if course_name not in courses:
        return {"error": f"Course '{course_name}' not found in the dataset"}

    course_metrics = instructor_metrics[instructor_metrics['course_name'] == course_name]

    if len(course_metrics) == 0:
        return {"error": f"No instructor data available for course '{course_name}'"}

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

        instructor_course_data = data_df[
            (data_df['instructor_name'] == instructor) &
            (data_df['course_name'] == course_name)
        ]

        success_rate = len(instructor_course_data[instructor_course_data['grade'] >= target_grade]) / len(instructor_course_data)
        
        # Get predicted score for this instructor using our trained model
        predicted_score = predict_student_score(course_name, instructor)

        instructors_data.append({
            'instructor_name': instructor,
            'average_grade': round(avg_grade, 2),
            'median_grade': round(row['median_grade'], 2),
            'std_dev': round(std_grade, 2),
            'student_count': count,
            'success_rate': round(success_rate * 100, 2),
            'recommendation_score': round(final_score, 2),
            'match_score': round(100 - (final_score * 25), 1),
            'predicted_score': round(predicted_score, 2)
        })

    instructors_data.sort(key=lambda x: x['recommendation_score'])
    return instructors_data[:top_n]

# Function to predict student score with a specific instructor
def predict_student_score(course_name, instructor_name):
    """
    Predict the expected score for an average student taking the course with the specified instructor.
    
    Parameters:
    - course_name: The name of the course
    - instructor_name: The name of the instructor
    
    Returns:
    - Predicted grade for an average student
    """
    # Get most common values for categorical features to represent an average student
    avg_student = {
        'course_name': course_name,
        'instructor_name': instructor_name,
        'semester_name': data_df['semester_name'].mode()[0],
        'difficulty_level': data_df['difficulty_level'].mode()[0],
        'assessment_type': data_df['assessment_type'].mode()[0],
        'gender': data_df['gender'].mode()[0],
        'student_department': data_df['student_department'].mode()[0],
        'attendance_percentage': data_df['attendance_percentage'].median(),
        'assessment_score': data_df['assessment_score'].median()
    }
    
    # Create DataFrame with input data
    input_df = pd.DataFrame([avg_student])
    
    # Make prediction
    try:
        predicted_grade = model.predict(input_df)[0]
        return predicted_grade
    except Exception as e:
        print(f"Prediction error: {str(e)}")
        return data_df['grade'].mean()  # Return average grade if prediction fails

# Function to get instructor-course details
def get_instructor_course_details(instructor_name, course_name):
    instructor_data = data_df[
        (data_df['instructor_name'] == instructor_name) &
        (data_df['course_name'] == course_name)
    ]

    if len(instructor_data) == 0:
        return {"error": f"No data found for instructor {instructor_name} teaching {course_name}"}

    return {
        'grade_distribution': instructor_data['grade'].describe().to_dict(),
        'difficulty_distribution': instructor_data['difficulty_level'].value_counts().to_dict(),
        'semester_distribution': instructor_data['semester_name'].value_counts().to_dict(),
        'assessment_distribution': instructor_data['assessment_type'].value_counts().to_dict(),
        'grade_by_difficulty': instructor_data.groupby('difficulty_level')['grade'].mean().to_dict(),
        'grade_by_assessment': instructor_data.groupby('assessment_type')['grade'].mean().to_dict(),
        'sample_size': len(instructor_data)
    }

def recommend_instructors_with_model(course_name, student_features, top_n=3):
    """
    Recommend instructors for a given course using the trained prediction model.
    
    Parameters:
    - course_name (str): The course to find instructors for.
    - student_features (dict): Dictionary containing values for the model's features:
        - 'semester_name', 'difficulty_level', 'assessment_type', 'gender', 'student_department'
    - top_n (int): Number of top instructors to recommend.
    
    Returns:
    - List of dicts with instructor name and predicted grade.
    """
    if course_name not in courses:
        return {"error": f"Course '{course_name}' not found in the dataset"}

    # Filter instructors teaching the course
    course_instructors = instructor_metrics[instructor_metrics['course_name'] == course_name]['instructor_name'].unique()

    predictions = []

    for instructor in course_instructors:
        # Prepare a single-row DataFrame with all required features for prediction
        input_dict = {
            'course_name': course_name,
            'instructor_name': instructor,
            'semester_name': student_features.get('semester_name', data_df['semester_name'].mode()[0]),
            'difficulty_level': student_features.get('difficulty_level', data_df['difficulty_level'].mode()[0]),
            'assessment_type': student_features.get('assessment_type', data_df['assessment_type'].mode()[0]),
            'gender': student_features.get('gender', data_df['gender'].mode()[0]),
            'student_department': student_features.get('student_department', data_df['student_department'].mode()[0]),
            'attendance_percentage': student_features.get('attendance_percentage', data_df['attendance_percentage'].median()),
            'assessment_score': student_features.get('assessment_score', data_df['assessment_score'].median())
        }

        input_df = pd.DataFrame([input_dict])

        try:
            predicted_grade = model.predict(input_df)[0]
        except Exception as e:
            return {"error": f"Prediction error: {str(e)}"}

        predictions.append({
            'instructor_name': instructor,
            'predicted_grade': round(predicted_grade, 2)
        })

    # Sort instructors by predicted grade descending
    predictions = sorted(predictions, key=lambda x: x['predicted_grade'], reverse=True)

    return predictions[:top_n]

# Save the model
current_dir = os.path.dirname(os.path.abspath(__file__))
django_project_dir = os.path.abspath(os.path.join(current_dir, '..'))
ml_model_dir = os.path.join(django_project_dir, 'ml_model')

if not os.path.exists(ml_model_dir):
    os.makedirs(ml_model_dir)
    print(f"Created directory: {ml_model_dir}")


models_data = {
    'model': model,
    'preprocessor': preprocessor,
    'courses': courses,
    'instructors': instructors,
    'instructor_metrics': instructor_metrics,
    'data': data_df,
}

# Save model to .pkl file
model_path = os.path.join(ml_model_dir, 'instructor_recommendation_models.pkl')
with open(model_path, 'wb') as file:
    pickle.dump(models_data, file)
print(f"\nModels saved to {model_path}")

print("\nModel creation complete!")

model_info = ModelInsan.objects.create(
    model_name='RandomForestInstructorRecommendation',
    model_file='ml_model/instructor_recommendation_models.pkl',
    training_data='from PostgreSQL: enrollment + grade',
    training_date=now(),
    model_summary='Model includes assessment, instructorID, and courseName.'
)

# Example usage:
# recommended = recommend_instructors('Database Systems', 85, top_n=3)
# print(recommended)
# 
# details = get_instructor_course_details('Dr. Smith', 'Database Systems')
# print(details)