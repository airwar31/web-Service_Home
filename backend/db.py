import os
import sqlite3
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "devices.sqlite3")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
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


def list_devices() -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT id, name, room, type, is_on FROM devices ORDER BY id ASC")
        return [dict(row) | {"is_on": bool(row["is_on"])} for row in cur.fetchall()]
    finally:
        conn.close()


def get_device_by_room_and_type(room: str, type_: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT id, name, room, type, is_on FROM devices WHERE room = ? AND type = ? LIMIT 1",
            (room, type_),
        )
        row = cur.fetchone()
        return (dict(row) | {"is_on": bool(row["is_on"])}) if row else None
    finally:
        conn.close()


def create_device(name: str, room: Optional[str], type_: str, is_on: bool = False) -> Dict[str, Any]:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO devices(name, room, type, is_on) VALUES(?,?,?,?)",
            (name, room, type_, 1 if is_on else 0),
        )
        conn.commit()
        device_id = cur.lastrowid
        return get_device(device_id)  # type: ignore
    finally:
        conn.close()


def get_device(device_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT id, name, room, type, is_on FROM devices WHERE id=?", (device_id,))
        row = cur.fetchone()
        return (dict(row) | {"is_on": bool(row["is_on"])}) if row else None
    finally:
        conn.close()


def update_device_state(device_id: int, is_on: bool) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        conn.execute("UPDATE devices SET is_on=? WHERE id=?", (1 if is_on else 0, device_id))
        conn.commit()
        return get_device(device_id)
    finally:
        conn.close()


def delete_device(device_id: int) -> bool:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM devices WHERE id=?", (device_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


