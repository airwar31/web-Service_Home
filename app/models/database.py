# -*- coding: utf-8 -*-
"""
Database Model - Модель для работы с базой данных
"""

import os
import sqlite3
from typing import List, Dict, Any, Optional


class DatabaseModel:
    """Модель для работы с базой данных устройств"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Используем правильный путь к базе данных
            db_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend", "devices.sqlite3")
        self.db_path = db_path
    
    def _connect(self) -> sqlite3.Connection:
        """Создает подключение к базе данных"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self) -> None:
        """Инициализирует базу данных"""
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    room TEXT,
                    type TEXT NOT NULL,
                    is_on INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()
        finally:
            conn.close()
    
    def list_devices(self) -> List[Dict[str, Any]]:
        """Возвращает список всех устройств"""
        conn = self._connect()
        try:
            cur = conn.execute("SELECT id, name, room, type, is_on FROM devices ORDER BY id ASC")
            return [dict(row) | {"is_on": bool(row["is_on"])} for row in cur.fetchall()]
        finally:
            conn.close()
    
    def get_device_by_room_and_type(self, room: str, type_: str) -> Optional[Dict[str, Any]]:
        """Возвращает устройство по комнате и типу"""
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT id, name, room, type, is_on FROM devices WHERE room = ? AND type = ? LIMIT 1",
                (room, type_),
            )
            row = cur.fetchone()
            return (dict(row) | {"is_on": bool(row["is_on"])}) if row else None
        finally:
            conn.close()
    
    def create_device(self, name: str, room: Optional[str], type_: str, is_on: bool = False) -> Dict[str, Any]:
        """Создает новое устройство"""
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO devices(name, room, type, is_on) VALUES(?,?,?,?)",
                (name, room, type_, 1 if is_on else 0),
            )
            conn.commit()
            device_id = cur.lastrowid
            return self.get_device(device_id)  # type: ignore
        finally:
            conn.close()
    
    def get_device(self, device_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает устройство по ID"""
        conn = self._connect()
        try:
            cur = conn.execute("SELECT id, name, room, type, is_on FROM devices WHERE id=?", (device_id,))
            row = cur.fetchone()
            return (dict(row) | {"is_on": bool(row["is_on"])}) if row else None
        finally:
            conn.close()
    
    def update_device_state(self, device_id: int, is_on: bool) -> Optional[Dict[str, Any]]:
        """Обновляет состояние устройства"""
        conn = self._connect()
        try:
            conn.execute("UPDATE devices SET is_on=? WHERE id=?", (1 if is_on else 0, device_id))
            conn.commit()
            return self.get_device(device_id)
        finally:
            conn.close()
    
    def delete_device(self, device_id: int) -> bool:
        """Удаляет устройство"""
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM devices WHERE id=?", (device_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
