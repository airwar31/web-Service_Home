# -*- coding: utf-8 -*-
"""
Device Controller - Контроллер устройств
"""

import threading
import random
import time
from typing import Dict, Any, List, Optional, Callable

from app.models.device import Device, DeviceState, ThermometerData, DeviceType
from app.models.database import DatabaseModel
from app.services.command_parser_service import CommandParserService
from app.models.command import Command, CommandAction


class DeviceController:
    """Контроллер для управления устройствами"""
    
    def __init__(self):
        self.db = DatabaseModel()
        self.command_parser = CommandParserService()
        self.device_state = DeviceState(
            lights={},
            thermometers={},
            curtains={},
            vacuums={}
        )
        # Колбэк для рассылки обновлений состояния (устанавливается снаружи)
        self.broadcast_callback: Optional[Callable[[], None]] = None
        self.rooms = ["зал", "кухня", "комната", "ванная"]
        self.vacuum_progress = {}
        self.vacuum_timers = {}
        self.state_lock = threading.Lock()
        
        # Инициализация
        self._initialize_devices()
        self._update_thermometers()
    
    def _initialize_devices(self):
        """Инициализация устройств в базе данных"""
        # Термометры
        for room in self.rooms:
            dev = self.db.get_device_by_room_and_type(room, "thermometer")
            if not dev:
                self.db.create_device(name=f"thermometer:{room}", room=room, type_="thermometer", is_on=True)
        
        # Свет: при старте ВСЕГДА выключен
        for room in self.rooms:
            dev = self.db.get_device_by_room_and_type(room, "light")
            if not dev:
                # создаем выключенный свет
                self.db.create_device(name=f"light:{room}", room=room, type_="light", is_on=False)
                self.device_state.lights[room] = False
            else:
                # если в БД был включен — выключаем и синхронизируем
                if bool(dev.get("is_on", False)):
                    try:
                        self.db.update_device_state(dev["id"], False)
                    except Exception:
                        pass
                self.device_state.lights[room] = False

        # Начальные состояния штор и пылесоса
        for room in self.rooms:
            if room not in self.device_state.curtains:
                self.device_state.curtains[room] = "closed"
            if room not in self.device_state.vacuums:
                self.device_state.vacuums[room] = "stopped"
    
    def _update_thermometers(self):
        """Обновление данных термометров"""
        with self.state_lock:
            # Базовые значения и гарантированные небольшие сдвиги для уникальности между комнатами
            base_temp = random.uniform(18.0, 26.0)
            base_hum = random.uniform(35.0, 60.0)
            for idx, room in enumerate(self.rooms):
                # Уникальный сдвиг для каждой комнаты
                temp_offset = (idx * 0.3) + random.uniform(0.0, 1.2)
                hum_offset = (idx * 0.6) + random.uniform(0.0, 2.5)
                t = max(18.0, min(28.0, base_temp + temp_offset))
                h = max(30.0, min(70.0, base_hum + hum_offset))
                self.device_state.thermometers[room] = ThermometerData(
                    temperature=round(t, 1),
                    humidity=round(h, 1)
                )
    
    def get_devices_snapshot(self) -> Dict[str, Any]:
        """Возвращает снимок состояния всех устройств"""
        # Создаем быструю копию без блокировки для чтения
        # Упрощаем, чтобы не зависать
        snapshot = {
            'lights': self.device_state.lights.copy(),
            'thermometers': {room: {'temperature': data.temperature, 'humidity': data.humidity} 
                           for room, data in self.device_state.thermometers.items()},
            'curtains': self.device_state.curtains.copy(),
            'vacuums': self.device_state.vacuums.copy(),
            'vacuum_progress': self.vacuum_progress.copy()
        }
        return snapshot
    
    def apply_command(self, command: Command) -> str:
        """Применяет команду к устройствам"""
        try:
            if command.action == CommandAction.TURN_ON_LIGHT:
                return self._turn_on_light(command.room)
            elif command.action == CommandAction.TURN_OFF_LIGHT:
                return self._turn_off_light(command.room)
            elif command.action == CommandAction.OPEN_CURTAIN:
                return self._open_curtain(command.room)
            elif command.action == CommandAction.CLOSE_CURTAIN:
                return self._close_curtain(command.room)
            elif command.action == CommandAction.START_VACUUM:
                return self._start_vacuum(command.room)
            elif command.action == CommandAction.STOP_VACUUM:
                return self._stop_vacuum(command.room)
            elif command.action == CommandAction.INCREASE_TEMPERATURE:
                return self._increase_temperature(command.room)
            elif command.action == CommandAction.DECREASE_TEMPERATURE:
                return self._decrease_temperature(command.room)
            elif command.action == CommandAction.INCREASE_HUMIDITY:
                return self._increase_humidity(command.room)
            elif command.action == CommandAction.DECREASE_HUMIDITY:
                return self._decrease_humidity(command.room)
            elif command.action == CommandAction.SET_TEMPERATURE:
                return self._set_temperature(command.room, command.value)
            elif command.action == CommandAction.SET_HUMIDITY:
                return self._set_humidity(command.room, command.value)
            elif command.action == CommandAction.SET_VOLUME:
                return self._set_volume(command.value)
            else:
                return "Неизвестная команда"
        except Exception as e:
            return f"Ошибка выполнения команды: {str(e)}"
    
    def _turn_on_light(self, room: str) -> str:
        """Включить свет"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        
        with self.state_lock:
            self.device_state.lights[room] = True
        return f"Свет в {room} включен"
    
    def _turn_off_light(self, room: str) -> str:
        """Выключить свет"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        
        with self.state_lock:
            self.device_state.lights[room] = False
        return f"Свет в {room} выключен"
    
    def _open_curtain(self, room: str) -> str:
        """Открыть шторы"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        
        with self.state_lock:
            self.device_state.curtains[room] = "open"
        return f"Шторы в {room} открыты"
    
    def _close_curtain(self, room: str) -> str:
        """Закрыть шторы"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        
        with self.state_lock:
            self.device_state.curtains[room] = "closed"
        return f"Шторы в {room} закрыты"
    
    def _start_vacuum(self, room: str) -> str:
        """Запустить пылесос"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        
        with self.state_lock:
            self.device_state.vacuums[room] = "running"
            self.vacuum_progress[room] = 0
        
        # Запускаем таймер для прогресса пылесоса
        self._start_vacuum_timer(room)
        return f"Пылесос в {room} запущен"
    
    def _stop_vacuum(self, room: str) -> str:
        """Остановить пылесос"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        
        with self.state_lock:
            self.device_state.vacuums[room] = "stopped"
            if room in self.vacuum_progress:
                del self.vacuum_progress[room]
        
        # Останавливаем таймер
        if room in self.vacuum_timers:
            self.vacuum_timers[room].cancel()
            del self.vacuum_timers[room]
        
        return f"Пылесос в {room} остановлен"
    
    def _start_vacuum_timer(self, room: str):
        """Запуск таймера для прогресса пылесоса"""
        def update_progress():
            with self.state_lock:
                if room in self.vacuum_progress:
                    # Увеличиваем прогресс и останавливаем на 100%
                    self.vacuum_progress[room] = min(100, self.vacuum_progress[room] + 5)
                    if self.vacuum_progress[room] >= 100:
                        self.device_state.vacuums[room] = "stopped"
                        del self.vacuum_progress[room]
                        if room in self.vacuum_timers:
                            del self.vacuum_timers[room]
                        # Рассылаем финальное состояние
                        if self.broadcast_callback:
                            try:
                                self.broadcast_callback()
                            except Exception:
                                pass
                        return
            # Рассылаем промежуточное состояние
            if self.broadcast_callback:
                try:
                    self.broadcast_callback()
                except Exception:
                    pass
            
            # Планируем следующее обновление
            if room in self.vacuum_progress:
                timer = threading.Timer(2.0, update_progress)
                self.vacuum_timers[room] = timer
                timer.start()
        
        timer = threading.Timer(2.0, update_progress)
        self.vacuum_timers[room] = timer
        timer.start()
    
    def _increase_temperature(self, room: str) -> str:
        """Увеличить температуру"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        
        with self.state_lock:
            if room not in self.device_state.thermometers:
                self.device_state.thermometers[room] = ThermometerData(22.0, 50.0)
            self.device_state.thermometers[room].temperature = min(40, self.device_state.thermometers[room].temperature + 1)
        return f"Температура в {room} повышена"
    
    def _decrease_temperature(self, room: str) -> str:
        """Уменьшить температуру"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        
        with self.state_lock:
            if room not in self.device_state.thermometers:
                self.device_state.thermometers[room] = ThermometerData(22.0, 50.0)
            self.device_state.thermometers[room].temperature = max(10, self.device_state.thermometers[room].temperature - 1)
        return f"Температура в {room} снижена"
    
    def _increase_humidity(self, room: str) -> str:
        """Увеличить влажность"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        
        with self.state_lock:
            if room not in self.device_state.thermometers:
                self.device_state.thermometers[room] = ThermometerData(22.0, 50.0)
            self.device_state.thermometers[room].humidity = min(90, self.device_state.thermometers[room].humidity + 1)
        return f"Влажность в {room} повышена"
    
    def _decrease_humidity(self, room: str) -> str:
        """Уменьшить влажность"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        
        with self.state_lock:
            if room not in self.device_state.thermometers:
                self.device_state.thermometers[room] = ThermometerData(22.0, 50.0)
            self.device_state.thermometers[room].humidity = max(20, self.device_state.thermometers[room].humidity - 1)
        return f"Влажность в {room} снижена"
    
    def _set_temperature(self, room: str, value: int) -> str:
        """Установить температуру"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        if value is None:
            raise ValueError("Необходимо указать значение температуры")
        
        with self.state_lock:
            if room not in self.device_state.thermometers:
                self.device_state.thermometers[room] = ThermometerData(22.0, 50.0)
            self.device_state.thermometers[room].temperature = max(10, min(40, float(value)))
        return f"Температура в {room} установлена на {value}°C"
    
    def _set_humidity(self, room: str, value: int) -> str:
        """Установить влажность"""
        if not room:
            raise ValueError("Необходимо указать комнату для команды")
        if value is None:
            raise ValueError("Необходимо указать значение влажности")
        
        with self.state_lock:
            if room not in self.device_state.thermometers:
                self.device_state.thermometers[room] = ThermometerData(22.0, 50.0)
            self.device_state.thermometers[room].humidity = max(20, min(90, float(value)))
        return f"Влажность в {room} установлена на {value}%"
    
    def _set_volume(self, value: int) -> str:
        """Установить громкость"""
        if value is None:
            raise ValueError("Необходимо указать значение громкости")
        return f"Громкость установлена на {value}%"
