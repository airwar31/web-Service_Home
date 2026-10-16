# -*- coding: utf-8 -*-
"""
Speech Service - Сервис распознавания речи
"""

import os
from typing import Optional, Dict, Any

from app.utils.file_utils import get_ext, temp_filepath


class RecognitionError(Exception):
    """Ошибка распознавания речи"""
    pass


class SpeechService:
    """Сервис для распознавания речи"""
    
    def __init__(self):
        self._model = None
        self._available = False
        self._ffmpeg_available = False
        self._initialize()
    
    def _initialize(self):
        """Инициализация сервиса"""
        try:
            from pydub import AudioSegment
            from pydub.utils import which
            from faster_whisper import WhisperModel
            
            self._available = True
            self._configure_ffmpeg()
            self._load_model()
            
        except ImportError as e:
            print(f"Speech recognition dependencies not available: {e}")
            print("Speech recognition features will be disabled. Install faster-whisper and pydub to enable.")
            self._available = False
    
    def _configure_ffmpeg(self):
        """Настройка FFmpeg для конвертации аудио"""
        if not self._available:
            raise RecognitionError("Speech recognition dependencies not available")
        
        try:
            from pydub import AudioSegment
            from pydub.utils import which
            
            # Позволяем указать путь к ffmpeg через переменную окружения
            custom_path = os.getenv("FFMPEG_PATH")
            if custom_path and os.path.exists(custom_path):
                AudioSegment.converter = custom_path
                self._ffmpeg_available = True
                return
            
            # Иначе пытаемся найти ffmpeg в PATH
            found = which("ffmpeg")
            if found:
                AudioSegment.converter = found
                self._ffmpeg_available = True
                return
            
            self._ffmpeg_available = False
            
        except Exception:
            self._ffmpeg_available = False
    
    def _load_model(self):
        """Загрузка модели Whisper"""
        if not self._available:
            return
        
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel("tiny", device="cpu", compute_type="int8")
        except Exception as e:
            print(f"Failed to load Whisper model: {e}")
            self._model = None
    
    def _ensure_wav(self, input_path: str) -> str:
        """Конвертация аудио в WAV формат для Whisper"""
        if not self._available or not self._ffmpeg_available:
            raise RecognitionError("Speech recognition not available")
        
        ext = get_ext(input_path)
        if ext == "wav":
            return input_path
        
        try:
            from pydub import AudioSegment
            
            output_path = temp_filepath("wav")
            audio = AudioSegment.from_file(input_path)
            audio.export(output_path, format="wav")
            return output_path
        except Exception as e:
            raise RecognitionError(f"Failed to convert audio to WAV: {e}")
    
    def recognize_speech(self, audio_path: str) -> str:
        """Распознавание речи из аудиофайла"""
        if not self._available or not self._model:
            raise RecognitionError("Speech recognition not available")
        
        try:
            wav_path = self._ensure_wav(audio_path)
            segments, info = self._model.transcribe(wav_path, language="ru")
            
            # Объединяем все сегменты в один текст
            text = " ".join(segment.text for segment in segments)
            return text.strip()
            
        except Exception as e:
            raise RecognitionError(f"Speech recognition failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Возвращает статус сервиса распознавания речи"""
        return {
            "speech_recognition_available": self._available,
            "model_loaded": self._model is not None,
            "whisper_model": "tiny" if self._model else None,
            "ffmpeg_available": self._ffmpeg_available,
            "supported_formats": ["wav", "mp3", "m4a", "ogg", "flac"] if self._ffmpeg_available else [],
            "supported_languages": ["ru"],
            "protocol": "https",
            "about": {
                "name": "Smart Home Voice Control",
                "version": "2.0.0",
                "description": "Система голосового управления умным домом",
                "author": "ИИ-COPILOT",
                "features": [
                    "Распознавание голосовых команд",
                    "Управление освещением",
                    "Контроль температуры и влажности",
                    "Управление шторами и пылесосом"
                ]
            }
        }
