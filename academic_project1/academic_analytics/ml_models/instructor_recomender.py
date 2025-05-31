import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sqlalchemy import create_engine
import os
import pickle

class InstructorRecommender:
    """A model to recommend instructors based on desired grades for specific courses."""

    def __init__(self, data_path=None, data_df=None):
        """
        Initialize the recommender with either a path to a CSV file or a DataFrame.

        Args:
            data_path (str, optional): Path to the CSV file containing student data.
            data_df (DataFrame, optional): Pandas DataFrame containing student data.
        """
        if data_df is not None:
            self.data = data_df
        elif data_path is not None:
            self.data = pd.read_csv(data_path)
        else:
            raise ValueError("Either data_path or data_df must be provided")

        # Drop rows with missing grades
        self.data = self.data.dropna(subset=['grade'])

        self.model = None
        self.preprocessor = None
        self.courses = sorted(self.data['course_name'].unique())
        self.instructors = sorted(self.data['instructor_name'].unique())
        self._process_data()
        self._train_model()

    def _process_data(self):
        """Preprocess the data for model training."""
        # Calculate instructor performance metrics
        instructor_metrics = self.data.groupby(['instructor_name', 'course_name']).agg({
            'grade': ['mean', 'median', 'std', 'count']
        }).reset_index()

        instructor_metrics.columns = ['instructor_name', 'course_name', 'avg_grade', 'median_grade', 'std_grade', 'count']
        self.instructor_metrics = instructor_metrics

        # Define features for the model
        categorical_features = ['course_name', 'instructor_name', 'semester_name',
                                'difficulty_level', 'assessment_type', 'gender', 'student_department']

        self.preprocessor = ColumnTransformer(
            transformers=[
                ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
            ],
            remainder='passthrough'
        )

    def _train_model(self):
        """Train the prediction model."""
        X = self.data.drop(['grade', 'stu_id', 'instructor_id'], axis=1)
        y = self.data['grade']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.model = Pipeline([
            ('preprocessor', self.preprocessor),
            ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))
        ])

        self.model.fit(X_train, y_train)

        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)

        print(f"Model R² on training data: {train_score:.4f}")
        print(f"Model R² on test data: {test_score:.4f}")

    def recommend_instructors(self, course_name, target_grade, top_n=3):
        if course_name not in self.courses:
            return {"error": f"Course '{course_name}' not found in the dataset"}

        course_metrics = self.instructor_metrics[self.instructor_metrics['course_name'] == course_name]

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

            instructor_course_data = self.data[
                (self.data['instructor_name'] == instructor) &
                (self.data['course_name'] == course_name)
            ]

            success_rate = len(instructor_course_data[instructor_course_data['grade'] >= target_grade]) / len(instructor_course_data)

            instructors_data.append({
                'instructor_name': instructor,
                'average_grade': round(avg_grade, 2),
                'median_grade': round(row['median_grade'], 2),
                'std_dev': round(std_grade, 2),
                'student_count': count,
                'success_rate': round(success_rate * 100, 2),
                'recommendation_score': round(final_score, 2)
            })

        instructors_data.sort(key=lambda x: x['recommendation_score'])

        return instructors_data[:top_n]

    def get_courses(self):
        return self.courses

    def get_instructor_course_details(self, instructor_name, course_name):
        instructor_data = self.data[
            (self.data['instructor_name'] == instructor_name) &
            (self.data['course_name'] == course_name)
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


# === RUNNING SCRIPT ===
if __name__ == "__main__":
    from sqlalchemy import create_engine

    # PostgreSQL connection
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

    # Handle any missing 'grade'
    data_df = data_df.dropna(subset=['grade'])

    # Initialize the model
    recommender = InstructorRecommender(data_df=data_df)

    if not os.path.exists(ml_model_dir):
        os.makedirs(ml_model_dir)
        print(f"Created directory: {ml_model_dir}")
        models_data = {
        'model': easy_model,
        'features': easy_features}
# Simpan model ke file .pkl
    model_path = os.path.join(ml_model_dir, 'course_recommendation_models.pkl')
    with open(model_path, 'wb') as file:
        pickle.dump(models_data, file)
    print(f"\nModels saved to {model_path}")

    print("\nModel creation complete!")