import joblib

_sentiment_model = None
_category_model = None


def get_sentiment_model():
    global _sentiment_model
    if _sentiment_model is None:
        _sentiment_model = joblib.load("app/ml/sentiment_model.pkl")
    return _sentiment_model


def get_category_model():
    global _category_model
    if _category_model is None:
        _category_model = joblib.load("app/ml/category_model.pkl")
    return _category_model


def classify(text: str):
    """Returns (sentiment, category) for a piece of support text."""
    sentiment = get_sentiment_model().predict([text])[0]
    category = get_category_model().predict([text])[0]
    return sentiment, category
