import os
from typing import Optional
from pydub import AudioSegment
from pydub.utils import which
from faster_whisper import WhisperModel  # type: ignore

from backend.fileutils import get_ext, temp_filepath


class RecognitionError(Exception):
    pass


def _configure_ffmpeg() -> None:
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

    audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
    try:
        audio.export(output_path, format="wav")
    except Exception as e:
        raise RecognitionError(f"Не удалось сконвертировать в WAV: {e}")
    return output_path


def _normalize_lang_for_whisper(language: Optional[str]) -> Optional[str]:
    if not language:
        return None
    # Expect values like "ru-RU"; Whisper prefers ISO 639-1 like "ru"
    return language.split("-")[0].lower()


def recognize_from_file(file_path: str, language: str = "ru-RU", timeout: Optional[float] = None) -> str:
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
