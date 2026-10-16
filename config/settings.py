# -*- coding: utf-8 -*-
"""
Settings - Настройки приложения
"""

import os
from typing import List


class Settings:
    """Настройки приложения"""
    
    # Основные настройки
    APP_NAME = "Smart Home Web Service"
    APP_VERSION = "2.0.0"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # Сервер
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5443"))
    
    # SSL
    SSL_CERT_PATH = os.getenv("SSL_CERT_PATH", "cert.pem")
    SSL_KEY_PATH = os.getenv("SSL_KEY_PATH", "key.pem")
    USE_SSL = os.getenv("USE_SSL", "True").lower() == "true"
    
    # База данных
    DATABASE_PATH = os.getenv("DATABASE_PATH", "backend/devices.sqlite3")
    
    # Комнаты
    ROOMS: List[str] = ["зал", "кухня", "комната", "ванная"]
    
    # Распознавание речи
    WHISPER_MODEL = "tiny"
    SUPPORTED_LANGUAGES = ["ru"]
    SUPPORTED_AUDIO_FORMATS = ["wav", "mp3", "m4a", "ogg", "flac"]
    
    # Кэширование
    CACHE_TTL = 5  # секунды
    
    # SSE
    SSE_RETRY_TIMEOUT = 30000  # миллисекунды
    
    @classmethod
    def get_database_url(cls) -> str:
        """Возвращает URL базы данных"""
        return f"sqlite:///{cls.DATABASE_PATH}"
    
    @classmethod
    def get_ssl_context(cls):
        """Возвращает SSL контекст"""
        if not cls.USE_SSL:
            return None
        
        # Если сертификаты отсутствуют — используем 'adhoc', Flask сам сгенерирует временные ключи
        cert_exists = os.path.exists(cls.SSL_CERT_PATH)
        key_exists = os.path.exists(cls.SSL_KEY_PATH)
        if not (cert_exists and key_exists):
            # Сообщим в stdout, чтобы было видно причину
            print(
                f"SSL: certificates not found, enabling adhoc SSL (will generate temp keys). "
                f"Expected cert='{cls.SSL_CERT_PATH}', key='{cls.SSL_KEY_PATH}'"
            )
            return 'adhoc'
        
        import ssl
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cls.SSL_CERT_PATH, cls.SSL_KEY_PATH)
        return context
