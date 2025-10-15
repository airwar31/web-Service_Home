import os
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from backend.fileutils import allowed_file, temp_filepath
from dotenv import load_dotenv
from flask_cors import CORS
from flask import Response
import json
import queue
import threading
from backend import db
from backend.command_parser import parse_command
from backend.speech_recognizer import recognize_from_file, RecognitionError
import random
from flask import make_response, send_from_directory
import subprocess
import shlex
import requests

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
    "curtains": {},  # room -> "open" | "closed"
    "vacuums": {},  # room -> "running" | "stopped"
}

# Словарь комнат для канонизации
ROOMS_MAP = {
    "зал": "зал",
    "кухня": "кухня", 
    "комната": "комната",
    "ванная": "ванная",
    "ванная комната": "ванная",
    "спальня": "комната",
    "гостиная": "зал"
}

# Прогресс пылесоса
VACUUM_PROGRESS = {}  # room -> progress_percent
VACUUM_TIMERS = {}  # room -> Timer

# Threading lock for state synchronization
_STATE_LOCK = threading.Lock()

def _update_thermometers():
    with _STATE_LOCK:
        DEVICE_STATE.setdefault("thermometers", {})
        for room in ROOMS:
            # Температура: 18-28, влажность: 30-70
            DEVICE_STATE["thermometers"][room] = {
                "temperature": round(random.uniform(18, 28), 1),
                "humidity": round(random.uniform(30, 70), 1),
            }

def _update_vacuum_progress(vacuum_key: str):
    with _STATE_LOCK:
        current_progress = VACUUM_PROGRESS.get(vacuum_key, 0)
        if current_progress < 100:
            VACUUM_PROGRESS[vacuum_key] = min(100, current_progress + random.randint(2, 4))  # +2-4%
            _broadcast_state()
            # Schedule next update every 1 second
            VACUUM_TIMERS[vacuum_key] = threading.Timer(1, _update_vacuum_progress, args=[vacuum_key])
            VACUUM_TIMERS[vacuum_key].start()
        else:
            # Reset if 100% reached
            VACUUM_PROGRESS[vacuum_key] = 0
            _broadcast_state()
            if vacuum_key in VACUUM_TIMERS:
                VACUUM_TIMERS[vacuum_key].cancel()
                del VACUUM_TIMERS[vacuum_key]

# Инициализация всех секций DEVICE_STATE при старте
with _STATE_LOCK:
    DEVICE_STATE.setdefault("lights", {})
    DEVICE_STATE.setdefault("thermometers", {})
    DEVICE_STATE.setdefault("curtains", {})
    DEVICE_STATE.setdefault("vacuums", {})

_update_thermometers()

_SUBSCRIBERS = []  # list[queue.Queue]

def _get_devices_snapshot() -> dict:
    with _STATE_LOCK:
        snapshot = json.loads(json.dumps(DEVICE_STATE))
        # Добавляем прогресс пылесоса
        snapshot["vacuum_progress"] = json.loads(json.dumps(VACUUM_PROGRESS))
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
    try:
        action = parsed.get("action")
        params = parsed.get("params", {})
        room = params.get("room")
        
        print(f"Applying command: action={action}, room={repr(room)}, params={params}")
        print(f"Room type: {type(room)}, Room value: {repr(room)}")

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
        elif action == "open_curtain" and room:
            dev = db.get_device_by_room_and_type(room, "curtain")
            if not dev:
                db.create_device(name=f"curtain:{room}", room=room, type_="curtain", is_on=True)
            else:
                db.update_device_state(dev["id"], True)
            with _STATE_LOCK:
                DEVICE_STATE.setdefault("curtains", {})[room] = "open"
            _broadcast_state()
        elif action == "close_curtain" and room:
            dev = db.get_device_by_room_and_type(room, "curtain")
            if not dev:
                db.create_device(name=f"curtain:{room}", room=room, type_="curtain", is_on=False)
            else:
                db.update_device_state(dev["id"], False)
            with _STATE_LOCK:
                DEVICE_STATE.setdefault("curtains", {})[room] = "closed"
            _broadcast_state()
        elif action == "start_vacuum":
            print(f"Starting vacuum for room: {repr(room)}")
            # Пылесос логически не привязан к комнате, но если указана — учитываем
            dev = db.get_device_by_room_and_type(room, "vacuum")
            print(f"Found device: {dev}")
            if not dev:
                print(f"Creating new vacuum device for room: {room}")
                db.create_device(name=f"vacuum:{room}", room=room, type_="vacuum", is_on=True)
            else:
                print(f"Updating existing device {dev['id']}")
                db.update_device_state(dev["id"], True)
            print(f"Updating DEVICE_STATE for room: {room or 'global'}")
            with _STATE_LOCK:
                DEVICE_STATE.setdefault("vacuums", {})[room or "global"] = "running"
                VACUUM_PROGRESS.setdefault(room or "global", 0)  # Reset progress on start
            print("Broadcasting state...")
            _broadcast_state()
            # Start progress updates
            vacuum_key = room or "global"
            print(f"Starting vacuum progress updates for key: {vacuum_key}")
            if vacuum_key in VACUUM_TIMERS:
                VACUUM_TIMERS[vacuum_key].cancel()
            VACUUM_TIMERS[vacuum_key] = threading.Timer(1, _update_vacuum_progress, args=[vacuum_key])
            VACUUM_TIMERS[vacuum_key].start()
            print("Vacuum started successfully!")
        elif action == "stop_vacuum":
            dev = db.get_device_by_room_and_type(room, "vacuum")
            if not dev:
                db.create_device(name=f"vacuum:{room}", room=room, type_="vacuum", is_on=False)
            else:
                db.update_device_state(dev["id"], False)
            with _STATE_LOCK:
                DEVICE_STATE.setdefault("vacuums", {})[room or "global"] = "stopped"
                vacuum_key = room or "global"
                if vacuum_key in VACUUM_TIMERS:
                    VACUUM_TIMERS[vacuum_key].cancel()
                    del VACUUM_TIMERS[vacuum_key]
                VACUUM_PROGRESS.setdefault(vacuum_key, 0)  # Reset progress on stop
            _broadcast_state()
    except Exception as e:
        print(f"Error in _apply_command: {e}")
        import traceback
        traceback.print_exc()
        raise e

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
    if action == "open_curtain":
        return f"Шторы{_in_room(room)} открыты" if room else "Шторы открыты"
    if action == "close_curtain":
        return f"Шторы{_in_room(room)} закрыты" if room else "Шторы закрыты"
    if action == "start_vacuum":
        return f"Пылесос запущен{_in_room(room)}" if room else "Пылесос запущен"
    if action == "stop_vacuum":
        return f"Пылесос остановлен{_in_room(room)}" if room else "Пылесос остановлен"
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
    try:
        payload = request.get_json(force=True, silent=True) or {}
        text = payload.get("text", "").strip()
        if not text:
            return jsonify({"error": "Текст команды пуст"}), 400
        
        print(f"Получена команда: {text}")
        parsed = parse_command(text)
        print(f"Распарсено: {parsed}")
        
        try:
            room = parsed.get("params", {}).get("room")
            if room:
                can = _canonicalize_room(room)
                parsed.setdefault("params", {})["room"] = can
        except Exception as e:
            print(f"Ошибка канонизации комнаты: {e}")
            pass
        
        response_text = _format_response(parsed)
        print(f"Ответ: {response_text}")
        
        try:
            _apply_command(parsed)
            print("Команда применена успешно")
        except Exception as e:
            print(f"Ошибка применения команды: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"Ошибка применения команды: {e}"}), 500
        
        return jsonify({
            "text": text,
            "parsed": parsed,
            "response": response_text
        })
    except Exception as e:
        print(f"Общая ошибка в api_text_command: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Ошибка обработки команды: {e}"}), 500

@app.route("/api/devices/<int:device_id>", methods=["DELETE"])
def devices_delete(device_id: int):
    try:
        success = db.delete_device(device_id)
        if not success:
            return jsonify({"error": "not found"}), 404
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": f"db error: {e}"}), 500

@app.route("/api/device_action", methods=["POST"])
def device_action():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        device_type = payload.get("device_type")
        room = payload.get("room")
        action = payload.get("action")
        
        if not device_type or not room or not action:
            return jsonify({"error": "device_type, room, and action are required"}), 400
        
        # Формируем команду
        command = ""
        if device_type == "light":
            command = f"{'включи' if action == 'on' else 'выключи'} свет в {room}"
        elif device_type == "thermometer":
            value = payload.get("value", 25)
            command = f"установи температуру {value} в {room}"
        elif device_type == "curtain":
            command = f"{'открой' if action == 'open' else 'закрой'} шторы в {room}"
        elif device_type == "vacuum":
            command = f"{'запусти' if action == 'start' else 'останови'} пылесос в {room}"
        
        if command:
            parsed = parse_command(command)
            try:
                room_param = parsed.get("params", {}).get("room")
                if room_param:
                    can = _canonicalize_room(room_param)
                    parsed.setdefault("params", {})["room"] = can
            except Exception:
                pass
            response_text = _format_response(parsed)
            _apply_command(parsed)
            return jsonify({
                "command": command,
                "response": response_text,
                "success": True
            })
        else:
            return jsonify({"error": "Invalid device type or action"}), 400
            
    except Exception as e:
        return jsonify({"error": f"Internal error: {e}"}), 500

@app.route("/api/camera/snapshot", methods=["GET"])
def camera_snapshot():
    url = request.args.get("u", type=str)
    if not url:
        return jsonify({"error": "u required"}), 400
    # Если это http(s) и не rtsp — попробуем просто скачать
    try:
        if url.startswith("http://") or url.startswith("https://"):
            # Некоторые IPCam имеют endpoint snapshot.jpg; попытаемся отдать как есть
            r = requests.get(url, timeout=8)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                resp = make_response(r.content)
                resp.headers["Content-Type"] = r.headers.get("content-type", "image/jpeg")
                return resp
    except Exception:
        pass
    # Fallback: используем ffmpeg для получения одного кадра (rtsp/rtmp/http/mjpeg)
    try:
        ffmpeg_path = os.getenv("FFMPEG_PATH", "ffmpeg")
        cmd = f"{shlex.quote(ffmpeg_path)} -loglevel error -rtsp_transport tcp -i {shlex.quote(url)} -frames:v 1 -f image2 -"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(timeout=10)
        if proc.returncode != 0 or not out:
            return jsonify({"error": f"ffmpeg failed: {err.decode('utf-8', 'ignore')[:200]}"}), 502
        resp = make_response(out)
        resp.headers["Content-Type"] = "image/jpeg"
        return resp
    except subprocess.TimeoutExpired:
        return jsonify({"error": "timeout grabbing frame"}), 504
    except Exception as e:
        return jsonify({"error": f"camera error: {e}"}), 500

if __name__ == "__main__":
    # Для доступа из локальной сети — host="0.0.0.0"
    app.run(debug=False, host="0.0.0.0", port=5000)
