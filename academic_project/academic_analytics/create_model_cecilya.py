import os
import pickle
import pandas as pd
from sqlalchemy import create_engine
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from django.utils.timezone import now

# Setup Django
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "academic_project.settings")  # Ganti sesuai nama proyek Django kamu
import django
django.setup()

from academic_analytics.models import ModelCecil  # Ganti sesuai lokasi ModelCecil kamu

# Koneksi ke database
engine = create_engine('postgresql://postgres:12345678@localhost:5051/final')

# Load data dari database
def load_data():
    student_df = pd.read_sql("SELECT * FROM Student", engine)
    enrollment_df = pd.read_sql("SELECT * FROM Enrollment", engine)
    assessment_df = pd.read_sql("SELECT * FROM Assessment", engine)
    attendance_df = pd.read_sql("SELECT * FROM Attendance", engine)
    difficulty_df = pd.read_sql("SELECT * FROM Course_Difficulty", engine)
    return student_df, enrollment_df, assessment_df, attendance_df, difficulty_df

# Preprocessing data
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

# Load n proses data
student_df, enrollment_df, assessment_df, attendance_df, difficulty_df = load_data()
data = preprocess(student_df, enrollment_df, assessment_df, attendance_df, difficulty_df)

features = ["avg_grade", "avg_assessment", "avg_attendance", "num_courses", "avg_difficulty", "gender"]
X = data[features].dropna()

# Scaling dan clustering
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

kmeans = KMeans(n_clusters=3, random_state=42)
kmeans.fit(X_scaled)

model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ml_model')
os.makedirs(model_dir, exist_ok=True)
model_path = os.path.join(model_dir, 'student_segmentation_kmeans.pkl')

with open(model_path, 'wb') as f:
    pickle.dump({
        'model': kmeans,
        'scaler': scaler,
        'features': features
    }, f)

model_info = ModelCecil.objects.create(
    model_name='KMeansStudentSegmentation',
    model_file='ml_model/student_segmentation_kmeans.pkl',
    training_data='from PostgreSQL: Student, Enrollment, Assessment, Attendance, Course_Difficulty',
    training_date=now(),
    model_summary='KMeans clustering with 3 clusters on student behavior features including attendance, grade, etc.'
)

print(f"Model disimpan dan metadata dimasukkan ke DB dengan ID: {model_info.id}")
