import os
from typing import Optional

from backend.fileutils import get_ext, temp_filepath

# Try to import heavy dependencies, but make them optional
try:
    from pydub import AudioSegment
    from pydub.utils import which
    from faster_whisper import WhisperModel  # type: ignore
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError as e:
    SPEECH_RECOGNITION_AVAILABLE = False
    print(f"Speech recognition dependencies not available: {e}")
    print("Speech recognition features will be disabled. Install faster-whisper and pydub to enable.")

class RecognitionError(Exception):
    pass

# Глобальная переменная для кэширования модели
_FW_MODEL = None

def _configure_ffmpeg() -> None:
    """Настройка FFmpeg для конвертации аудио"""
    if not SPEECH_RECOGNITION_AVAILABLE:
        raise RecognitionError("Speech recognition dependencies not available")
    
    # Позволяем указать путь к ffmpeg через переменную окружения
    custom_path = os.getenv("FFMPEG_PATH")
    if custom_path and os.path.exists(custom_path):
        AudioSegment.converter = custom_path  # type: ignore
        return
    
    # Иначе пытаемся найти ffmpeg в PATH
    found = which("ffmpeg")
    if found:
        AudioSegment.converter = found  # type: ignore
        return
    
    # Если не нашли — подскажем, что нужно установить
    raise RecognitionError(
        "FFmpeg не найден. Установите ffmpeg и добавьте в PATH, или укажите путь в переменной окружения FFMPEG_PATH"
    )

def _ensure_wav(input_path: str) -> str:
    """Конвертация аудио в WAV формат для Whisper"""
    ext = get_ext(input_path)
    if ext == "wav":
        return input_path

    _configure_ffmpeg()

    output_path = temp_filepath(".wav")
    try:
        fmt = ext if ext else None
        # Явные соответствия для webm/ogg
        if ext in ("webm", "ogg"):
            fmt = ext
        audio = AudioSegment.from_file(input_path, format=fmt)
    except Exception:
        # Последняя попытка — пусть pydub сам определит через ffmpeg
        try:
            audio = AudioSegment.from_file(input_path)
        except Exception as e:
            raise RecognitionError(f"Ошибка декодирования аудио: {e}. Проверьте, что формат поддерживается ffmpeg")

    # Нормализация аудио для Whisper
    audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
    try:
        audio.export(output_path, format="wav")
    except Exception as e:
        raise RecognitionError(f"Не удалось сконвертировать в WAV: {e}")
    return output_path

def _normalize_lang_for_whisper(language: Optional[str]) -> Optional[str]:
    """Нормализация языка для Whisper (ru-RU -> ru)"""
    if not language:
        return None
    # Expect values like "ru-RU"; Whisper prefers ISO 639-1 like "ru"
    return language.split("-")[0].lower()

def recognize_from_file(file_path: str, language: str = "ru-RU", timeout: Optional[float] = None) -> str:
    """
    Распознавание речи из аудиофайла
    
    Args:
        file_path: Путь к аудиофайлу
        language: Язык распознавания (по умолчанию ru-RU)
        timeout: Таймаут (не используется в текущей реализации)
    
    Returns:
        Распознанный текст
    
    Raises:
        RecognitionError: При ошибках распознавания
    """
    if not SPEECH_RECOGNITION_AVAILABLE:
        raise RecognitionError("Speech recognition dependencies not available. Install faster-whisper and pydub.")
    
    if not os.path.exists(file_path):
        raise RecognitionError("Файл не найден")

    # Ensure compatible PCM WAV for stable local transcription
    wav_path = _ensure_wav(file_path)

    lang = _normalize_lang_for_whisper(language)

    # Lazy-load and cache the faster-whisper model in memory
    global _FW_MODEL
    try:
        model_size = os.getenv("WHISPER_MODEL", "tiny")
        compute_type = os.getenv("WHISPER_COMPUTE", "int8").lower()

        if '_FW_MODEL' not in globals() or _FW_MODEL is None:
            _FW_MODEL = WhisperModel(model_size, device="cpu", compute_type=compute_type)

        segments, _info = _FW_MODEL.transcribe(
            wav_path,
            language=lang,
            vad_filter=True,
            beam_size=5,
        )
        parts = [seg.text for seg in segments]
        text = (" ".join(parts)).strip()
        if not text:
            raise RecognitionError("Не удалось распознать речь")
        return text
    except Exception as e:
        raise RecognitionError(f"Ошибка распознавания: {e}")
    finally:
        if wav_path != file_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass

def get_status() -> dict:
    """
    Получение статуса системы распознавания речи
    
    Returns:
        Словарь со статусом системы
    """
    return {
        "speech_recognition_available": SPEECH_RECOGNITION_AVAILABLE,
        "model_loaded": _FW_MODEL is not None,
        "whisper_model": "tiny",
        "ffmpeg_available": _check_ffmpeg_availability(),
        "supported_formats": ["wav", "mp3", "webm", "ogg", "m4a", "flac"],
        "supported_languages": ["ru"],
        "protocol": "https",
        "about": {
            "name": "Speech Recognition Service",
            "version": "1.0.0",
            "description": "Сервис распознавания речи на основе Whisper",
            "author": "Web Service Home Team"
        }
    }

def _check_ffmpeg_availability() -> bool:
    """Проверка доступности FFmpeg"""
    try:
        _configure_ffmpeg()
        return True
    except RecognitionError:
        return False