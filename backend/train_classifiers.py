import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

df = pd.read_csv("../data/docs/training_data.csv")
print(f"Loaded {len(df)} examples")

# Sentiment classifier
sentiment_pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
    ("clf", LogisticRegression(max_iter=1000)),
])
sentiment_pipeline.fit(df["text"], df["sentiment"])
joblib.dump(sentiment_pipeline, "app/ml/sentiment_model.pkl")
print("Sentiment model trained and saved")

# Complaint category classifier
category_pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
    ("clf", LogisticRegression(max_iter=1000)),
])
category_pipeline.fit(df["text"], df["category"])
joblib.dump(category_pipeline, "app/ml/category_model.pkl")
print("Category model trained and saved")

# Quick sanity check
test_texts = [
    "my earbuds wont pair with my phone",
    "thank you so much that solved it",
    "i want my money back this is defective",
]
for t in test_texts:
    sentiment = sentiment_pipeline.predict([t])[0]
    category = category_pipeline.predict([t])[0]
    print(f"'{t}' -> sentiment={sentiment}, category={category}")
