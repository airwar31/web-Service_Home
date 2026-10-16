# -*- coding: utf-8 -*-
"""
Command Parser Service - Сервис парсинга команд
"""

import re
from typing import Dict, Any

from app.models.command import Command, CommandAction


class CommandParserService:
    """Сервис для парсинга голосовых и текстовых команд"""
    
    ROOMS_MAP = {
        # кухня
        "кухне": "кухня", "кухня": "кухня",
        # спальня
        "спальне": "спальня", "спальня": "спальня",
        # гостиная / зал
        "гостиной": "гостиная", "гостиная": "гостиная", "зале": "зал", "зал": "зал",
        # ванная / санузел / туалет
        "ванной": "ванная", "ванна": "ванная", "санузле": "туалет", "санузел": "туалет", 
        "туалете": "туалет", "туалет": "туалет",
        # коридор / прихожая / холл
        "коридоре": "коридор", "коридор": "коридор", "прихожей": "прихожая", 
        "прихожая": "прихожая", "холле": "холл", "холл": "холл",
        # кабинет / офис
        "кабинете": "кабинет", "кабинет": "кабинет", "офисе": "офис", "офис": "офис",
        # детская / комната
        "детской": "детская", "детская": "детская", "комнате": "комната", "комната": "комната",
    }
    
    def normalize(self, text: str) -> str:
        """Нормализация текста команды"""
        return re.sub(r"\s+", " ", text.strip().lower())
    
    def _extract_room(self, text: str) -> str:
        """Извлечение комнаты из текста"""
        for variant, canonical in self.ROOMS_MAP.items():
            if variant in text:
                return canonical
        return "зал"  # по умолчанию
    
    def parse_command(self, text: str) -> Command:
        """Парсинг команды из текста"""
        t = self.normalize(text)
        
        # Свет (сначала проверяем более специфичные команды)
        if re.search(r"\bвключ(и|ить)\b.*\bсвет\b", t) and not re.search(r"\bтемператур[ауыи]*\b|\bвлажност[ьи]*\b", t):
            room = self._extract_room(t)
            return Command(CommandAction.TURN_ON_LIGHT, {"room": room}, text)
        
        if re.search(r"\bвыключ(и|ить)\b.*\bсвет\b", t) and not re.search(r"\bтемператур[ауыи]*\b|\bвлажност[ьи]*\b", t):
            room = self._extract_room(t)
            return Command(CommandAction.TURN_OFF_LIGHT, {"room": room}, text)
        
        # Таймер
        m = re.search(r"таймер.*?на\s+(\d+)\s+(секунд(?:у|ы|)|минут(?:у|ы|)|час(?:|а|ов))", t)
        if m:
            value = int(m.group(1))
            unit = m.group(2)
            return Command(CommandAction.SET_TIMER, {"value": value, "unit": unit}, text)
        
        # Шторы
        if re.search(r"\b(открой|открыть)\b.*\bштор[ыауе]?\b", t):
            room = self._extract_room(t)
            return Command(CommandAction.OPEN_CURTAIN, {"room": room}, text)
        
        if re.search(r"\b(закрой|закрыть)\b.*\bштор[ыауе]?\b", t):
            room = self._extract_room(t)
            return Command(CommandAction.CLOSE_CURTAIN, {"room": room}, text)
        
        # Пылесос
        if re.search(r"\b(запусти|включи|включить)\b.*\bпылесос\b", t):
            room = self._extract_room(t)
            return Command(CommandAction.START_VACUUM, {"room": room}, text)
        
        if re.search(r"\b(останови|выключи|выключить)\b.*\bпылесос\b", t):
            room = self._extract_room(t)
            return Command(CommandAction.STOP_VACUUM, {"room": room}, text)
        
        # Температура
        if re.search(r"\b(повысь|повысить|увеличь|увеличить)\b.*\bтемператур[ауыи]*\b", t):
            room = self._extract_room(t)
            return Command(CommandAction.INCREASE_TEMPERATURE, {"room": room}, text)
        
        if re.search(r"\b(понизь|понизить|сниз(ь|ить|и))\b.*\bтемператур[ауыи]*\b", t):
            room = self._extract_room(t)
            return Command(CommandAction.DECREASE_TEMPERATURE, {"room": room}, text)
        
        # Влажность
        if re.search(r"\b(повысь|повысить|увеличь|увеличить)\b.*\bвлажност[ьи]*\b", t):
            room = self._extract_room(t)
            return Command(CommandAction.INCREASE_HUMIDITY, {"room": room}, text)
        
        if re.search(r"\b(понизь|понизить|сниз(ь|ить|и))\b.*\bвлажност[ьи]*\b", t):
            room = self._extract_room(t)
            return Command(CommandAction.DECREASE_HUMIDITY, {"room": room}, text)
        
        # Установка температуры
        m = re.search(r'(установи|установить|поставь|измени|задать|сделай)? ?температур[ауыи]* ?(на|в)? ?([а-я]+)? ?(\d{1,2})', t)
        if m:
            value = int(m.group(4))
            room = self._extract_room(m.group(3) or t)
            return Command(CommandAction.SET_TEMPERATURE, {"room": room, "value": value}, text)
        
        # Установка влажности
        m = re.search(r'(установи|установить|поставь|измени|задать|сделай)? ?влажност[ьи]* ?(на|в)? ?([а-я]+)? ?(\d{1,2})', t)
        if m:
            value = int(m.group(4))
            room = self._extract_room(m.group(3) or t)
            return Command(CommandAction.SET_HUMIDITY, {"room": room, "value": value}, text)
        
        # Громкость
        m = re.search(r'\b(громкость|звук)\b.*?(\d{1,3})', t)
        if m:
            value = int(m.group(2))
            return Command(CommandAction.SET_VOLUME, {"value": value}, text)
        
        # Неизвестная команда
        return Command(CommandAction.UNKNOWN, {}, text)
