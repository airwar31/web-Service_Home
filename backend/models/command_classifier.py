import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
import os

class CommandClassifier:
    def __init__(self, model_path='models/command_model.pkl'):
        self.model_path = model_path
        self.pipeline = None
        self.load_or_train()

    def load_or_train(self):
        if os.path.exists(self.model_path):
            self.pipeline = joblib.load(self.model_path)
        else:
            self.train_model()

    def train_model(self):
        # Sample training data
        commands = [
            "включи свет",
            "выключи свет",
            "включи отопление",
            "выключи отопление",
            "установи температуру 25",
            "повысь температуру",
            "понизь температуру",
            "статус устройств"
        ]
        labels = [
            "turn_on_light",
            "turn_off_light",
            "turn_on_heating",
            "turn_off_heating",
            "set_temperature",
            "increase_temperature",
            "decrease_temperature",
            "get_status"
        ]

        # Create pipeline
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer()),
            ('clf', LogisticRegression(random_state=42))
        ])

        # Train
        self.pipeline.fit(commands, labels)

        # Save
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.pipeline, self.model_path)

    def predict(self, text):
        if self.pipeline:
            return self.pipeline.predict([text])[0]
        return None
