# -*- coding: utf-8 -*-
"""
App Controller - Главный контроллер приложения
"""

import json
import queue
import threading
import time
from typing import Dict, Any, List, Optional

from app.controllers.device_controller import DeviceController
from app.services.speech_service import SpeechService
from app.services.command_parser_service import CommandParserService
from app.models.command import Command


class AppController:
    """Главный контроллер приложения"""
    
    def __init__(self):
        self.device_controller = DeviceController()
        self.speech_service = SpeechService()
        self.command_parser = CommandParserService()
        # Подключаем колбэк рассылки состояния для таймеров пылесоса
        self.device_controller.broadcast_callback = self.broadcast_state
        
        # SSE подписчики
        self.subscribers: List[queue.Queue] = []
        
        # Кэш устройств
        self.cached_devices = []
        self.cached_devices_timestamp = 0
        self.cache_ttl = 5
        
        # Кэш устройств по комнате и типу
        self.device_cache: Dict[tuple, Any] = {}
    
    def get_devices_snapshot(self) -> Dict[str, Any]:
        """Возвращает снимок состояния всех устройств"""
        snapshot = self.device_controller.get_devices_snapshot()
        # Всегда используем кэш устройств для быстрого ответа
        snapshot["devices"] = self.cached_devices
        return snapshot
    
    def invalidate_device_cache(self):
        """Инвалидирует кэш устройств"""
        self.cached_devices_timestamp = 0
    
    def broadcast_state(self):
        """Отправляет состояние всем подписчикам"""
        snapshot = self.get_devices_snapshot()
        data = json.dumps(snapshot, ensure_ascii=False)
        
        # Отправляем всем подписчикам
        for subscriber in self.subscribers[:]:
            try:
                subscriber.put_nowait(data)
            except queue.Full:
                # Удаляем подписчика, если очередь переполнена
                self.subscribers.remove(subscriber)
    
    def add_subscriber(self) -> queue.Queue:
        """Добавляет нового подписчика SSE"""
        subscriber_queue = queue.Queue(maxsize=10)
        self.subscribers.append(subscriber_queue)
        return subscriber_queue
    
    def remove_subscriber(self, subscriber_queue: queue.Queue):
        """Удаляет подписчика SSE"""
        if subscriber_queue in self.subscribers:
            self.subscribers.remove(subscriber_queue)
    
    def process_text_command(self, text: str) -> str:
        """Обрабатывает текстовую команду"""
        command = self.command_parser.parse_command(text)
        result = self.device_controller.apply_command(command)
        
        # Инвалидируем кэш и отправляем обновление
        self.invalidate_device_cache()
        self.broadcast_state()
        
        return result
    
    def process_speech_command(self, audio_path: str) -> str:
        """Обрабатывает голосовую команду"""
        try:
            # Распознаем речь
            text = self.speech_service.recognize_speech(audio_path)
            if not text:
                return "Не удалось распознать речь"
            
            # Парсим и выполняем команду
            command = self.command_parser.parse_command(text)
            result = self.device_controller.apply_command(command)
            
            # Инвалидируем кэш и отправляем обновление
            self.invalidate_device_cache()
            self.broadcast_state()
            
            return f"Распознано: '{text}'. {result}"
            
        except Exception as e:
            return f"Ошибка обработки голосовой команды: {str(e)}"
    
    def get_speech_status(self) -> Dict[str, Any]:
        """Возвращает статус распознавания речи"""
        return self.speech_service.get_status()
    
    def device_action(self, device_id: int, action: str, payload: Dict[str, Any] = None) -> str:
        """Выполняет действие с устройством"""
        if payload is None:
            payload = {}
        
        try:
            device = self.device_controller.db.get_device(device_id)
            if not device:
                return "Устройство не найдено"
            
            room = device['room']
            device_type = device['type']
            
            # Формируем команду
            command_text = ""
            if device_type == "light":
                command_text = f"{'включи' if action == 'on' else 'выключи'} свет в {room}"
            elif device_type == "thermometer":
                value = payload.get("value", 25)
                command_text = f"установи температуру {value} в {room}"
            elif device_type == "curtain":
                command_text = f"{'открой' if action == 'open' else 'закрой'} шторы в {room}"
            elif device_type == "vacuum":
                command_text = f"{'запусти' if action == 'start' else 'останови'} пылесос в {room}"
            
            if command_text:
                result = self.process_text_command(command_text)
                return result
            else:
                return "Неподдерживаемое действие для данного типа устройства"
                
        except Exception as e:
            return f"Ошибка выполнения действия: {str(e)}"
