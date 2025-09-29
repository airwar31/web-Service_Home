import os
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from backend.fileutils import allowed_file, temp_filepath
from backend.speech_recognizer import recognize_from_file, RecognitionError
from backend.command_parser import parse_command, ROOMS_MAP
from dotenv import load_dotenv
from flask_cors import CORS
from flask import Response
import json
import queue
import threading
from backend import db
import random
from flask import url_for
from flask import send_from_directory

load_dotenv()
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB лимит на аплоад

# DB init
db.init_db()

ROOMS = ["зал", "кухня", "комната", "ванная"]

# --- ДОБАВЛЯЕМ ТЕРМОМЕТРЫ В БД ПРИ СТАРТЕ ---
for room in ROOMS:
    dev = db.get_device_by_room_and_type(room, "thermometer")
    if not dev:
        db.create_device(name=f"thermometer:{room}", room=room, type_="thermometer", is_on=True)

# --- ДОБАВЛЯЕМ СВЕТ В КАЖДУЮ КОМНАТУ ПРИ СТАРТЕ ---
for room in ROOMS:
    dev = db.get_device_by_room_and_type(room, "light")
    if not dev:
        is_on = bool(random.getrandbits(1))
        db.create_device(name=f"light:{room}", room=room, type_="light", is_on=is_on)

DEVICE_STATE = {
    "lights": {},  # room -> bool (mirrors DB for SSE speed)
    "thermometers": {},  # room -> {"temperature": float, "humidity": float}
}

def _update_thermometers():
    for room in ROOMS:
        # Температура: 18-28, влажность: 30-70
        DEVICE_STATE["thermometers"][room] = {
            "temperature": round(random.uniform(18, 28), 1),
            "humidity": round(random.uniform(30, 70), 1),
        }

# Инициализация термометров при старте
_update_thermometers()

_SUBSCRIBERS = []  # list[queue.Queue]
_STATE_LOCK = threading.Lock()

def _get_devices_snapshot() -> dict:
    with _STATE_LOCK:
        snapshot = json.loads(json.dumps(DEVICE_STATE))
        # Добавляем устройства из базы
        try:
            snapshot["devices"] = db.list_devices()
        except Exception:
            snapshot["devices"] = []
        return snapshot

def _broadcast_state():
    snapshot = json.dumps(_get_devices_snapshot())
    dead = []
    for q in list(_SUBSCRIBERS):
        try:
            q.put_nowait(snapshot)
        except Exception:
            dead.append(q)
    if dead:
        for q in dead:
            try:
                _SUBSCRIBERS.remove(q)
            except ValueError:
                pass

def _apply_command(parsed: dict):
    action = parsed.get("action")
    params = parsed.get("params", {})
    room = params.get("room")

    if action == "turn_on_light" and room:
        # ensure device exists in DB
        dev = db.get_device_by_room_and_type(room, "light")
        if not dev:
            db.create_device(name=f"light:{room}", room=room, type_="light", is_on=True)
        else:
            db.update_device_state(dev["id"], True)
        with _STATE_LOCK:
            DEVICE_STATE.setdefault("lights", {})[room] = True
        _broadcast_state()
    elif action == "turn_off_light" and room:
        dev = db.get_device_by_room_and_type(room, "light")
        if not dev:
            db.create_device(name=f"light:{room}", room=room, type_="light", is_on=False)
        else:
            db.update_device_state(dev["id"], False)
        with _STATE_LOCK:
            DEVICE_STATE.setdefault("lights", {})[room] = False
        _broadcast_state()
    elif action == "decrease_temperature" and room:
        with _STATE_LOCK:
            t = DEVICE_STATE["thermometers"].setdefault(room, {"temperature": 22.0, "humidity": 50.0})
            t["temperature"] = max(10, t["temperature"] - 1)
        _broadcast_state()
    elif action == "decrease_humidity" and room:
        with _STATE_LOCK:
            t = DEVICE_STATE["thermometers"].setdefault(room, {"temperature": 22.0, "humidity": 50.0})
            t["humidity"] = max(20, t["humidity"] - 1)
        _broadcast_state()
    elif action == "set_temperature" and room and "value" in params:
        with _STATE_LOCK:
            t = DEVICE_STATE["thermometers"].setdefault(room, {"temperature": 22.0, "humidity": 50.0})
            t["temperature"] = max(10, min(40, float(params["value"])))
        _broadcast_state()
    elif action == "set_humidity" and room and "value" in params:
        with _STATE_LOCK:
            t = DEVICE_STATE["thermometers"].setdefault(room, {"temperature": 22.0, "humidity": 50.0})
            t["humidity"] = max(20, min(90, float(params["value"])))
        _broadcast_state()
def _format_response(parsed: dict) -> str:
    action = parsed.get("action")
    params = parsed.get("params", {})
    room = params.get("room")

    if action == "turn_on_light":
        return f"Свет{_in_room(room)} включен" if room else "Свет включен"
    if action == "turn_off_light":
        return f"Свет{_in_room(room)} выключен" if room else "Свет выключен"
    if action == "set_timer":
        value = params.get("value")
        unit = params.get("unit")
        return f"Таймер установлен на {value} {unit}" if value and unit else "Таймер установлен"
    if action == "open_app":
        target = params.get("target")
        return f"Открываю {target}" if target else "Открываю"
    if action == "set_volume":
        value = params.get("value")
        return f"Громкость установлена на {value}%" if value is not None else "Громкость изменена"
    if action == "decrease_temperature":
        return f"Температура{_in_room(room)} снижена" if room else "Температура снижена"
    if action == "decrease_humidity":
        return f"Влажность{_in_room(room)} снижена" if room else "Влажность снижена"
    if action == "set_temperature":
        value = params.get("value")
        return f"Температура{_in_room(room)} установлена на {value}°C" if room and value is not None else "Температура установлена"
    if action == "set_humidity":
        value = params.get("value")
        return f"Влажность{_in_room(room)} установлена на {value}💧" if room and value is not None else "Влажность установлена"
    return "Извините, не понял команду"


def _in_room(room: str | None) -> str:
    if not room:
        return ""
    # Предлоги по падежам: "на кухне", "в спальне", "в гостиной", "в зале" и т.п.
    # Используем простое правило
    if room in {"кухня"}:
        return " на кухне"
    return f" в {room}"


def _canonicalize_room(room: str) -> str:
    r = (room or "").strip().lower()
    # если уже каноническая форма
    if r in ROOMS_MAP.values():
        return r
    # попытка по словарю форм
    return ROOMS_MAP.get(r, r)

@app.route("/")
def root():
    return send_from_directory("frontend", "index.html")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory("frontend", path)

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/api/devices", methods=["GET"])
def devices():
    # Prefer DB as source of truth
    try:
        devices = db.list_devices()
        return jsonify({"devices": devices})
    except Exception as e:
        return jsonify({"error": f"db error: {e}"}), 500

@app.route("/api/devices", methods=["POST"])
def devices_create():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        name = payload.get("name")
        room = payload.get("room")
        type_ = payload.get("type", "light")
        is_on = bool(payload.get("is_on", False))
        if not name:
            return jsonify({"error": "name is required"}), 400
        dev = db.create_device(name=name, room=room, type_=type_, is_on=is_on)
        # mirror to memory for SSE fast path if light
        if dev and dev.get("type") == "light" and dev.get("room"):
            DEVICE_STATE.setdefault("lights", {})[dev["room"]] = bool(dev["is_on"])  # type: ignore
            _broadcast_state()
        return jsonify(dev), 201
    except Exception as e:
        return jsonify({"error": f"db error: {e}"}), 500

@app.route("/api/devices/<int:device_id>", methods=["PATCH"])
def devices_update(device_id: int):
    try:
        payload = request.get_json(force=True, silent=True) or {}
        if "is_on" not in payload:
            return jsonify({"error": "is_on required"}), 400
        dev = db.update_device_state(device_id, bool(payload["is_on"]))
        if not dev:
            return jsonify({"error": "not found"}), 404
        if dev.get("type") == "light" and dev.get("room"):
            DEVICE_STATE.setdefault("lights", {})[dev["room"]] = bool(dev["is_on"])  # type: ignore
            _broadcast_state()
        return jsonify(dev)
    except Exception as e:
        return jsonify({"error": f"db error: {e}"}), 500

@app.route("/api/devices/stream", methods=["GET"])
def devices_stream():
    def event_stream(q: queue.Queue):
        # сразу отправим текущее состояние
        first = json.dumps(_get_devices_snapshot())
        yield f"data: {first}\n\n"
        try:
            while True:
                data = q.get()
                yield f"data: {data}\n\n"
        except GeneratorExit:
            pass

    q: queue.Queue = queue.Queue(maxsize=10)
    _SUBSCRIBERS.append(q)
    return Response(event_stream(q), mimetype="text/event-stream")

@app.route("/api/routes", methods=["GET"])
def api_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "endpoint": rule.endpoint,
            "methods": list(rule.methods),
            "rule": str(rule)
        })
    return jsonify(routes)

@app.route("/api/speech_to_action", methods=["POST"])
def api_speech_to_action():
    # Ожидаем form-data с полем "audio"
    audio = request.files.get("audio")
    if not audio or audio.filename == "":
        return jsonify({"error": "Файл не найден"}), 400

    if not allowed_file(audio.filename):
        return jsonify({"error": "Неподдерживаемый формат файла"}), 415

    # Сохраняем во временный файл
    safe_name = secure_filename(audio.filename)
    suffix = os.path.splitext(safe_name)[1].lower()
    temp_path = temp_filepath(suffix)

    try:
        audio.save(temp_path)
    except Exception:
        return jsonify({"error": "Не удалось сохранить файл"}), 500

    try:
        text = recognize_from_file(temp_path, language="ru-RU")
        parsed = parse_command(text)
        # Нормализация комнаты на случай устаревшей версии парсера/кэширования
        try:
            room = parsed.get("params", {}).get("room")
            if room:
                can = _canonicalize_room(room)
                parsed.setdefault("params", {})["room"] = can
        except Exception:
            pass

        # Формируем понятный ответ пользователю
        response_text = _format_response(parsed)

        # Применяем команду к состоянию устройств и рассылаем обновление
        _apply_command(parsed)

        return jsonify({
            "text": text,
            "parsed": parsed,
            "response": response_text
        })
    except RecognitionError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        return jsonify({"error": f"Внутренняя ошибка: {e}"}), 500
    finally:
        # Чистим временный файл
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass

@app.route("/api/text_command", methods=["POST"])
def api_text_command():
    payload = request.get_json(force=True, silent=True) or {}
    text = payload.get("text", "").strip()
    if not text:
        return jsonify({"error": "Текст команды пуст"}), 400
    parsed = parse_command(text)
    try:
        room = parsed.get("params", {}).get("room")
        if room:
            can = _canonicalize_room(room)
            parsed.setdefault("params", {})["room"] = can
    except Exception:
        pass
    response_text = _format_response(parsed)
    _apply_command(parsed)
    return jsonify({
        "text": text,
        "parsed": parsed,
        "response": response_text
    })

if __name__ == "__main__":
    # Для доступа из локальной сети — host="0.0.0.0"
    app.run(debug=False, host="0.0.0.0", port=5000)
