import pandas as pd
import pickle
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sqlalchemy import create_engine
import joblib
import sys


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DJANGO_SETTINGS_MODULE dan setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "academic_project.settings")  # Ganti dengan nama proyek Django-mu
import django
django.setup()

from academic_analytics.models import ModelStandy
# Script untuk membuat model dan menyimpannya ke dalam file .pkl

engine = create_engine('postgresql://postgres:12345678@localhost:5051/final')

query = """
SELECT
    e.stu_id,
    c.course_id,
    cd.difficulty_level,
    (
        SELECT AVG(e2.grade)
        FROM enrollment e2
        WHERE e2.stu_id = e.stu_id AND e2.course_id <> c.course_id
    ) AS avg_prev_grade,
    (
        SELECT COUNT(*)
        FROM enrollment e3
        JOIN course_difficulty cd3 ON e3.course_id = cd3.course_id
        WHERE e3.stu_id = e.stu_id AND e3.grade >= 60 AND cd3.difficulty_level = 'Easy'
    ) AS easy_passed_count,
    (
        SELECT COUNT(*)
        FROM enrollment e3
        JOIN course_difficulty cd3 ON e3.course_id = cd3.course_id
        WHERE e3.stu_id = e.stu_id AND e3.grade >= 60 AND cd3.difficulty_level = 'Medium'
    ) AS medium_passed_count,
    (
        SELECT COUNT(*)
        FROM enrollment e3
        JOIN course_difficulty cd3 ON e3.course_id = cd3.course_id
        WHERE e3.stu_id = e.stu_id AND e3.grade >= 60 AND cd3.difficulty_level = 'Hard'
    ) AS hard_passed_count,
    (
        SELECT COUNT(*) FILTER (WHERE grade >= 60) * 1.0 / COUNT(*)
        FROM enrollment
        WHERE course_id = c.course_id
    ) AS course_pass_rate,
    CASE WHEN e.grade >= 60 THEN 1 ELSE 0 END AS label
FROM enrollment e
JOIN course c ON e.course_id = c.course_id
JOIN course_difficulty cd ON c.course_id = cd.course_id
"""

df = pd.read_sql(query, engine)
print(f"Data loaded: {df.shape[0]} rows")

df.dropna(inplace=True)
print(f"Data after removing NaN: {df.shape[0]} rows")

# Encoding 
le = LabelEncoder()
df['difficulty_level_encoded'] = le.fit_transform(df['difficulty_level'])

difficulty_mapping = dict(zip(le.classes_, le.transform(le.classes_)))
print(f"\nMapping tingkat kesulitan: {difficulty_mapping}")

df_easy = df[df['difficulty_level'] == 'Easy']
df_medium = df[df['difficulty_level'] == 'Medium']
df_hard = df[df['difficulty_level'] == 'Hard']

print(f"\nJumlah data Easy: {len(df_easy)}")
print(f"Jumlah data Medium: {len(df_medium)}")
print(f"Jumlah data Hard: {len(df_hard)}")

def train_difficulty_model(df_subset, difficulty_name):
    # Untuk tiap tingkat kesulitan, gunakan fitur passed_count yang sesuai
    if difficulty_name == 'Easy':
        X = df_subset[['avg_prev_grade', 'easy_passed_count', 'course_pass_rate', 'difficulty_level_encoded']]
        features = ['avg_prev_grade', 'easy_passed_count', 'course_pass_rate', 'difficulty_level_encoded']
    elif difficulty_name == 'Medium':
        X = df_subset[['avg_prev_grade', 'medium_passed_count', 'course_pass_rate', 'difficulty_level_encoded']]
        features = ['avg_prev_grade', 'medium_passed_count', 'course_pass_rate', 'difficulty_level_encoded']
    else: # Hard
        X = df_subset[['avg_prev_grade', 'hard_passed_count', 'course_pass_rate', 'difficulty_level_encoded']]
        features = ['avg_prev_grade', 'hard_passed_count', 'course_pass_rate', 'difficulty_level_encoded']
    
    y = df_subset['label']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"\nTraining set {difficulty_name}: {X_train.shape[0]} samples")
    print(f"Testing set {difficulty_name}: {X_test.shape[0]} samples")
    
    # Train model
    model = RandomForestClassifier(n_estimators=1000, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluasi model
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\nHasil evaluasi model untuk tingkat kesulitan {difficulty_name}:")
    print(f"Model accuracy: {accuracy:.4f}")
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    print("Classification Report:")
    print(classification_report(y_test, y_pred))
    
    return model, features

# Melatih model untuk masing-masing tingkat kesulitan
print("\nMelatih model untuk setiap tingkat kesulitan...")
easy_model, easy_features = train_difficulty_model(df_easy, 'Easy')
medium_model, medium_features = train_difficulty_model(df_medium, 'Medium')
hard_model, hard_features = train_difficulty_model(df_hard, 'Hard')

from django.utils.timezone import now

# Simpan metadata model ke database
model_info = ModelStandy.objects.create(
    model_name='RandomForestCourseRecommendationModel',
    model_file='ml_model/course_recommendation_models.pkl',
    training_data='from PostgreSQL: enrollment + course_difficulty',
    training_date=now(),
    model_summary='Model includes Easy, Medium, and Hard difficulty classifiers with avg_prev_grade, passed_count, and pass_rate features.'
)

print(f"Model info saved to DB: ID {model_info.id}")

# Buat direktori ml_model jika belum ada
current_dir = os.path.dirname(os.path.abspath(__file__))
django_project_dir = os.path.abspath(os.path.join(current_dir, '..'))
ml_model_dir = os.path.join(django_project_dir, 'ml_model')

if not os.path.exists(ml_model_dir):
    os.makedirs(ml_model_dir)
    print(f"Created directory: {ml_model_dir}")

# Menyimpan model untuk setiap tingkat kesulitan ke file pickle
models_data = {
    'easy_model': {
        'model': easy_model,
        'features': easy_features
    },
    'medium_model': {
        'model': medium_model,
        'features': medium_features
    },
    'hard_model': {
        'model': hard_model,
        'features': hard_features
    },
    'label_encoder': le
}

model_path = os.path.join(ml_model_dir, 'course_recommendation_models.pkl')
with open(model_path, 'wb') as file:
    pickle.dump(models_data, file)
print(f"\nModels saved to {model_path}")

print("\nModel creation complete!")