# -*- coding: utf-8 -*-
"""
Device Model - Модель устройства
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class DeviceType(Enum):
    """Типы устройств"""
    LIGHT = "light"
    THERMOMETER = "thermometer"
    CURTAIN = "curtain"
    VACUUM = "vacuum"


class DeviceState(Enum):
    """Состояния устройств"""
    ON = "on"
    OFF = "off"
    OPEN = "open"
    CLOSED = "closed"
    RUNNING = "running"
    STOPPED = "stopped"


@dataclass
class Device:
    """Модель устройства"""
    id: int
    name: str
    room: Optional[str]
    type_: DeviceType
    is_on: bool
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Device':
        """Создает устройство из словаря"""
        return cls(
            id=data['id'],
            name=data['name'],
            room=data.get('room'),
            type_=DeviceType(data['type']),
            is_on=data['is_on']
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует устройство в словарь"""
        return {
            'id': self.id,
            'name': self.name,
            'room': self.room,
            'type': self.type_.value,
            'is_on': self.is_on
        }


@dataclass
class ThermometerData:
    """Данные термометра"""
    temperature: float
    humidity: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует данные в словарь"""
        return {
            'temperature': self.temperature,
            'humidity': self.humidity
        }


@dataclass
class DeviceState:
    """Состояние всех устройств"""
    lights: Dict[str, bool]  # room -> is_on
    thermometers: Dict[str, ThermometerData]  # room -> data
    curtains: Dict[str, str]  # room -> state
    vacuums: Dict[str, str]  # room -> state
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует состояние в словарь"""
        return {
            'lights': self.lights,
            'thermometers': {room: data.to_dict() for room, data in self.thermometers.items()},
            'curtains': self.curtains,
            'vacuums': self.vacuums
        }
