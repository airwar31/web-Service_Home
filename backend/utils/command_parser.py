import pickle
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB

# Обучающие данные
TRAINING_DATA = [
    ("включи лампу на кухне", "turn_on_lamp_kitchen"),
    ("выключи свет в спальне", "turn_off_light_bedroom"),
    ("включи чайник в гостиной", "turn_on_kettle_livingroom"),
    ("выключи розетку в ванной", "turn_off_socket_bathroom"),
    ("включи свет в коридоре", "turn_on_light_hallway"),
    ("выключи лампу в кабинете", "turn_off_lamp_office")
]

MODEL_PATH = "model.pkl"
VECTORIZER_PATH = "vectorizer.pkl"

def train_model():
    try:
        texts, labels = zip(*TRAINING_DATA)
        vectorizer = CountVectorizer()
        X = vectorizer.fit_transform(texts)

        model = MultinomialNB()
        model.fit(X, labels)

        with open(MODEL_PATH, "wb") as f:
            pickle.dump(model, f)
        with open(VECTORIZER_PATH, "wb") as f:
            pickle.dump(vectorizer, f)

        print("[ML] ✅ Модель обучена и сохранена.")
    except Exception as e:
        print("[ML] ❌ Ошибка при обучении:", e)

def load_model():
    try:
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        with open(VECTORIZER_PATH, "rb") as f:
            vectorizer = pickle.load(f)
        return model, vectorizer
    except Exception as e:
        print("[ML] ❌ Ошибка при загрузке модели:", e)
        return None, None

def predict_command(text):
    model, vectorizer = load_model()
    if not model or not vectorizer:
        return {"error": "Модель не загружена"}

    X_test = vectorizer.transform([text])
    label = model.predict(X_test)[0]
    parts = label.split('_')
    return {
        "action": parts[0] + "_" + parts[1],
        "device": parts[2],
        "location": parts[3]
    }

# Запуск обучения и теста
if __name__ == "__main__":
    train_model()
    test_text = "включи лампу на кухне"
    result = predict_command(test_text)
    print("[ML] 🔍 Предсказание:", result)
