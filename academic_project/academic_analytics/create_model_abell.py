import pandas as pd
import pickle
import os
import sys
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
from django.utils.timezone import now

# Tambahkan root project ke sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DJANGO_SETTINGS_MODULE dan setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "academic_project.settings")  # Ganti dengan nama proyek Django-mu
import django
django.setup()

# Sekarang baru bisa import model
from academic_analytics.models import ModelAbell

# === STEP 1: Database connection === #
# Membuat koneksi ke database
engine = create_engine('postgresql://postgres:12345678@localhost:5051/final')
print("Database connection established")

# === STEP 2: Load and preprocess enrollment data === #
# Membaca data dari database menggunakan SQLAlchemy
query = "SELECT * FROM enrollment"
df = pd.read_sql(query, engine)
print(f"Data loaded: {df.shape[0]} rows")

# Group by student to form course "transactions"
transactions_df = df.groupby('stu_id')['course_id'].apply(list).reset_index()
transactions = transactions_df['course_id'].tolist()
print(f"Created {len(transactions)} student transaction records")

# Encode transactions
te = TransactionEncoder()
te_ary = te.fit(transactions).transform(transactions)
df_encoded = pd.DataFrame(te_ary, columns=te.columns_)
print(f"Encoded {len(te.columns_)} unique courses")

# Generate frequent itemsets and association rules
print("\nGenerating frequent itemsets...")
frequent_itemsets = apriori(df_encoded, min_support=0.05, use_colnames=True)
print(f"Found {len(frequent_itemsets)} frequent itemsets")

print("\nGenerating association rules...")
rules = association_rules(frequent_itemsets, metric="lift", min_threshold=1)
rules_sorted = rules.sort_values(by='confidence', ascending=False)
print(f"Generated {len(rules)} association rules, sorted by confidence")

# === STEP 3: Association Rule Recommendation Function === #
def recommend_courses(rules_df, input_courses, top_n=3):
    """Recommend courses based on association rules and student's current courses"""
    input_set = frozenset(input_courses)
    filtered = rules_df[
        rules_df['antecedents'].apply(lambda x: x.issubset(input_set))
    ].sort_values(by='confidence', ascending=False)

    return filtered[['consequents', 'support', 'confidence', 'lift']].head(top_n)

# === STEP 4: Training and prediction utilities === #
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

# === STEP 5: Prediction workflow === #
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

def predict_top_3_scores(rules_df, x, y, scoreX, scoreY, engine):
    """Predict scores for top 3 recommended courses"""
    top_3_consequents = get_top_3_consequents(rules_df)
    predictions = []

    for z in top_3_consequents:
        df_train = get_training_data(x, y, z, engine)

        if not df_train.empty and len(df_train) >= 5:  # Ensure enough data for training
            model = train_model(df_train)
            predicted = predict_score(model, scoreX, scoreY)
            predictions.append({'course_id': z, 'predicted_score': round(predicted, 2)})
        else:
            predictions.append({'course_id': z, 'predicted_score': 'Insufficient Data'})

    return pd.DataFrame(predictions)

# Membuat model dan menyimpannya
# Buat direktori ml_model jika belum ada
current_dir = os.path.dirname(os.path.abspath(__file__))
django_project_dir = os.path.abspath(os.path.join(current_dir, '..'))
ml_model_dir = os.path.join(django_project_dir, 'ml_model')

if not os.path.exists(ml_model_dir):
    os.makedirs(ml_model_dir)
    print(f"Created directory: {ml_model_dir}")

# Menyimpan model association rules ke file pickle
model_data = {
    'transaction_encoder': te,
    'frequent_itemsets': frequent_itemsets,
    'association_rules': rules_sorted
}

# Simpan model ke file .pkl
model_path = os.path.join(ml_model_dir, 'course_association_model.pkl')
with open(model_path, 'wb') as file:
    pickle.dump(model_data, file)
print(f"\nAssociation Rules model saved to {model_path}")

# Simpan metadata model ke database
model_info = ModelAbell.objects.create(
    model_name='CourseAssociationRulesModel',
    model_file='ml_model/course_association_model.pkl',
    training_data='from PostgreSQL: enrollment',
    training_date=now(),
    model_summary='Model uses association rule mining to recommend courses based on enrollment patterns and predicts grades using linear regression.'
)

print(f"Model info saved to DB: ID {model_info.id}")

# === STEP 6: Example demonstration === #
# This is just to demonstrate how the model works - could be removed in production
# print("\n=== DEMONSTRATION ===")
# # User input example
# x = 11  # Course A
# y = 13  # Course B
# scoreX = 85  # Score in Course A
# scoreY = 80  # Score in Course B

# Get relevant rules and predict scores
# print(f"\nFinding recommendations for students who took courses {x} and {y}...")
# filtered_rules = recommend_courses(rules_sorted, [x, y])
# print("\nRecommended course rules:")
# print(filtered_rules)

# print("\nPredicting scores for top recommended courses:")
# output_df = predict_top_3_scores(filtered_rules, x, y, scoreX, scoreY, engine)
# print(output_df)

print("\nModel creation complete!")