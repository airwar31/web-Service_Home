from flask import Flask, request, jsonify
from flask_cors import CORS
from vosk import Model, KaldiRecognizer
import wave
import json
import os
from config import Config
from models.command_classifier import CommandClassifier
from utils.device_manager import DeviceManager

app = Flask(__name__)
CORS(app)
config = Config()

# Initialize components
device_manager = DeviceManager()
classifier = CommandClassifier(config.MODEL_PATH)

# Vosk model
vosk_model = None
try:
    vosk_model = Model(config.VOSK_MODEL_PATH)
except Exception as e:
    print(f"Vosk model not found: {e}. Speech processing disabled.")

@app.route('/process_speech', methods=['POST'])
def process_speech():
    if not vosk_model:
        return jsonify({"error": "Vosk model not available"}), 500

    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Save temp file
    temp_path = 'temp.wav'
    audio_file.save(temp_path)

    # Transcribe
    wf = wave.open(temp_path, "rb")
    rec = KaldiRecognizer(vosk_model, wf.getframerate())
    text = ""
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            text += res.get("text", "")

    res = json.loads(rec.FinalResult())
    text += res.get("text", "")

    os.remove(temp_path)

    if not text:
        return jsonify({"error": "No speech detected"}), 400

    # Classify command
    intent = classifier.predict(text)

    # Execute action
    response = execute_command(intent, text)

    return jsonify({"transcription": text, "intent": intent, "response": response})

@app.route('/command', methods=['POST'])
def command():
    data = request.get_json()
    text = data.get('text', '')
    if not text:
        return jsonify({"error": "No text provided"}), 400

    intent = classifier.predict(text)
    response = execute_command(intent, text)

    return jsonify({"intent": intent, "response": response})

@app.route('/devices', methods=['GET'])
def devices():
    status = device_manager.get_status()
    return jsonify(status)

def execute_command(intent, text):
    if intent == "turn_on_light":
        return device_manager.turn_on_light()
    elif intent == "turn_off_light":
        return device_manager.turn_off_light()
    elif intent == "turn_on_heating":
        return device_manager.turn_on_heating()
    elif intent == "turn_off_heating":
        return device_manager.turn_off_heating()
    elif intent == "set_temperature":
        # Extract number from text, simple way
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            return device_manager.set_temperature(numbers[0])
        return "Не удалось извлечь температуру"
    elif intent == "increase_temperature":
        return device_manager.increase_temperature()
    elif intent == "decrease_temperature":
        return device_manager.decrease_temperature()
    elif intent == "get_status":
        return device_manager.get_status()
    else:
        return "Команда не распознана"

if __name__ == '__main__':
    app.run(debug=config.DEBUG, port=config.PORT)
