# -*- coding: utf-8 -*-
"""
Command Model - Модель команд
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class CommandAction(Enum):
    """Действия команд"""
    TURN_ON_LIGHT = "turn_on_light"
    TURN_OFF_LIGHT = "turn_off_light"
    SET_TIMER = "set_timer"
    OPEN_CURTAIN = "open_curtain"
    CLOSE_CURTAIN = "close_curtain"
    START_VACUUM = "start_vacuum"
    STOP_VACUUM = "stop_vacuum"
    INCREASE_TEMPERATURE = "increase_temperature"
    DECREASE_TEMPERATURE = "decrease_temperature"
    INCREASE_HUMIDITY = "increase_humidity"
    DECREASE_HUMIDITY = "decrease_humidity"
    SET_TEMPERATURE = "set_temperature"
    SET_HUMIDITY = "set_humidity"
    SET_VOLUME = "set_volume"
    UNKNOWN = "unknown"


@dataclass
class Command:
    """Модель команды"""
    action: CommandAction
    params: Dict[str, Any]
    raw: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Command':
        """Создает команду из словаря"""
        return cls(
            action=CommandAction(data.get('action', 'unknown')),
            params=data.get('params', {}),
            raw=data.get('raw', '')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует команду в словарь"""
        return {
            'action': self.action.value,
            'params': self.params,
            'raw': self.raw
        }
    
    @property
    def room(self) -> Optional[str]:
        """Возвращает комнату из параметров"""
        return self.params.get('room')
    
    @property
    def value(self) -> Optional[Any]:
        """Возвращает значение из параметров"""
        return self.params.get('value')
    
    def has_room(self) -> bool:
        """Проверяет, есть ли комната в команде"""
        return self.room is not None
    
    def requires_room(self) -> bool:
        """Проверяет, требует ли команда указания комнаты"""
        room_required_actions = {
            CommandAction.TURN_ON_LIGHT,
            CommandAction.TURN_OFF_LIGHT,
            CommandAction.OPEN_CURTAIN,
            CommandAction.CLOSE_CURTAIN,
            CommandAction.START_VACUUM,
            CommandAction.STOP_VACUUM,
            CommandAction.INCREASE_TEMPERATURE,
            CommandAction.DECREASE_TEMPERATURE,
            CommandAction.INCREASE_HUMIDITY,
            CommandAction.DECREASE_HUMIDITY,
            CommandAction.SET_TEMPERATURE,
            CommandAction.SET_HUMIDITY,
        }
        return self.action in room_required_actions
