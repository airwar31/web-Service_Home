import os
import secrets
import tempfile

ALLOWED_EXTENSIONS = {"wav", "mp3", "ogg", "m4a", "webm"}

def allowed_file(filename: str) -> bool:
    """Проверка, что файл имеет допустимое расширение"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_ext(filename: str) -> str:
    """Получить расширение файла"""
    return filename.rsplit(".", 1)[1].lower() if "." in filename else ""

def temp_filepath(suffix: str = "") -> str:
    """Создать путь к временному файлу"""
    name = secrets.token_hex(8)
    directory = tempfile.gettempdir()
    return os.path.join(directory, f"{name}{suffix}")
