import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    PORT = int(os.getenv('PORT', 5000))
    ALLOWED_LOCATIONS = os.getenv('ALLOWED_LOCATIONS', 'Москва,Санкт-Петербург').split(',')
    VOSK_MODEL_PATH = os.getenv('VOSK_MODEL_PATH', 'model')  # Path to Vosk model
    MODEL_PATH = os.getenv('MODEL_PATH', 'models/command_model.pkl')  # Path to sklearn model
