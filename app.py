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
from backend.speech_recognizer import recognize_from_file, RecognitionError, get_status
import random
from flask import make_response, send_from_directory
import subprocess
import shlex
import requests
# Optional Home Assistant bridge (best-effort)
try:
    from backend.home_assistant_bridge import notify_home_assistant_async
    HA_BRIDGE_AVAILABLE = True
except Exception:
    # Provide a noop so code can call notify_home_assistant_async without guard
    def notify_home_assistant_async(parsed):
        return None
    HA_BRIDGE_AVAILABLE = False
try:
    # public helper to call HA services
    from backend.home_assistant_bridge import call_service as ha_call_service
except Exception:
    def ha_call_service(domain, service, data):
        return {"success": False, "error": "home_assistant_bridge not available"}

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
            # Schedule next update every 1 second
            VACUUM_TIMERS[vacuum_key] = threading.Timer(1, _update_vacuum_progress, args=[vacuum_key])
            VACUUM_TIMERS[vacuum_key].start()
        else:
            # Reset if 100% reached
            VACUUM_PROGRESS[vacuum_key] = 0
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
_CACHED_DEVICES = []  # Кэш устройств
_CACHED_DEVICES_TIMESTAMP = 0  # Время последнего обновления кэша
CACHE_TTL = 5  # Время жизни кэша в секундах

# Кэш устройств по комнате и типу для быстрого доступа
_DEVICE_CACHE = {}  # {(room, type): device}

def _get_devices_snapshot() -> dict:
    import time
    global _CACHED_DEVICES, _CACHED_DEVICES_TIMESTAMP
    current_time = time.time()
    
    with _STATE_LOCK:
        snapshot = json.loads(json.dumps(DEVICE_STATE))
        # Добавляем прогресс пылесоса
        snapshot["vacuum_progress"] = json.loads(json.dumps(VACUUM_PROGRESS))
        
        # Используем кэш устройств, если он не устарел
        if current_time - _CACHED_DEVICES_TIMESTAMP > CACHE_TTL:
            try:
                _CACHED_DEVICES = db.list_devices()
                _CACHED_DEVICES_TIMESTAMP = current_time
            except Exception:
                pass
        
        snapshot["devices"] = _CACHED_DEVICES
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

def _broadcast_state_async():
    """Асинхронная версия broadcast_state для использования в критических путях"""
    import threading
    def _do_broadcast():
        _broadcast_state()
    threading.Thread(target=_do_broadcast, daemon=True).start()

def _invalidate_device_cache():
    """Принудительно обновляет кэш устройств"""
    global _CACHED_DEVICES_TIMESTAMP, _DEVICE_CACHE, _CACHED_DEVICES
    _CACHED_DEVICES_TIMESTAMP = 0
    _DEVICE_CACHE = {}
    _CACHED_DEVICES = []

def _get_device_from_cache(room: str, type_: str):
    """Быстрое получение устройства из кэша"""
    cache_key = (room, type_)
    if cache_key in _DEVICE_CACHE:
        return _DEVICE_CACHE[cache_key]
    
    # Если нет в кэше, получаем из БД и кэшируем
    dev = db.get_device_by_room_and_type(room, type_)
    if dev:
        _DEVICE_CACHE[cache_key] = dev
    return dev

def _update_device_cache(room: str, type_: str, device):
    """Обновляет кэш устройства"""
    cache_key = (room, type_)
    _DEVICE_CACHE[cache_key] = device

def _apply_command(parsed: dict):
    import time
    start_time = time.time()
    
    try:
        action = parsed.get("action")
        params = parsed.get("params", {})
        room = params.get("room")
        
        db_start = time.time()
        if action == "turn_on_light":
            if not room:
                # Если комната не указана, выдаем ошибку
                raise ValueError("Необходимо указать комнату для команды")
            
            # ensure device exists in DB
            dev = _get_device_from_cache(room, "light")
            if not dev:
                dev = db.create_device(name=f"light:{room}", room=room, type_="light", is_on=True)
                _update_device_cache(room, "light", dev)
            else:
                db.update_device_state(dev["id"], True)
                _update_device_cache(room, "light", {**dev, "is_on": True})
            with _STATE_LOCK:
                DEVICE_STATE.setdefault("lights", {})[room] = True
        elif action == "turn_off_light":
            if not room:
                # Если комната не указана, выдаем ошибку
                raise ValueError("Необходимо указать комнату для команды")
            
            dev = _get_device_from_cache(room, "light")
            if not dev:
                dev = db.create_device(name=f"light:{room}", room=room, type_="light", is_on=False)
                _update_device_cache(room, "light", dev)
            else:
                db.update_device_state(dev["id"], False)
                _update_device_cache(room, "light", {**dev, "is_on": False})
            with _STATE_LOCK:
                DEVICE_STATE.setdefault("lights", {})[room] = False
        elif action == "decrease_temperature":
            if not room:
                raise ValueError("Необходимо указать комнату для команды")
            
            with _STATE_LOCK:
                t = DEVICE_STATE["thermometers"].setdefault(room, {"temperature": 22.0, "humidity": 50.0})
                t["temperature"] = max(10, t["temperature"] - 1)
        elif action == "decrease_humidity":
            if not room:
                raise ValueError("Необходимо указать комнату для команды")
            
            with _STATE_LOCK:
                t = DEVICE_STATE["thermometers"].setdefault(room, {"temperature": 22.0, "humidity": 50.0})
                t["humidity"] = max(20, t["humidity"] - 1)
        elif action == "set_temperature":
            if not room:
                raise ValueError("Необходимо указать комнату для команды")
            
            if "value" not in params:
                raise ValueError("Необходимо указать значение температуры")
            
            with _STATE_LOCK:
                t = DEVICE_STATE["thermometers"].setdefault(room, {"temperature": 22.0, "humidity": 50.0})
                t["temperature"] = max(10, min(40, float(params["value"])))
        elif action == "set_humidity":
            if not room:
                raise ValueError("Необходимо указать комнату для команды")
            
            if "value" not in params:
                raise ValueError("Необходимо указать значение влажности")
            
            with _STATE_LOCK:
                t = DEVICE_STATE["thermometers"].setdefault(room, {"temperature": 22.0, "humidity": 50.0})
                t["humidity"] = max(20, min(90, float(params["value"])))
        elif action == "open_curtain":
            if not room:
                raise ValueError("Необходимо указать комнату для команды")
            
            print(f"DEBUG: Открываем шторы в комнате {room}")
            dev_start = time.time()
            dev = _get_device_from_cache(room, "curtain")
            dev_time = time.time() - dev_start
            print(f"DEBUG: Получение устройства заняло {dev_time*1000:.2f}ms")
            
            if not dev:
                print(f"DEBUG: Создаем новое устройство шторы для {room}")
                dev = db.create_device(name=f"curtain:{room}", room=room, type_="curtain", is_on=True)
                _update_device_cache(room, "curtain", dev)
            else:
                print(f"DEBUG: Обновляем существующее устройство шторы {dev['id']}")
                db.update_device_state(dev["id"], True)
                _update_device_cache(room, "curtain", {**dev, "is_on": True})
            with _STATE_LOCK:
                DEVICE_STATE.setdefault("curtains", {})[room] = "open"
            print(f"DEBUG: Шторы в {room} открыты")
        elif action == "close_curtain":
            if not room:
                raise ValueError("Необходимо указать комнату для команды")
            
            dev = _get_device_from_cache(room, "curtain")
            if not dev:
                dev = db.create_device(name=f"curtain:{room}", room=room, type_="curtain", is_on=False)
                _update_device_cache(room, "curtain", dev)
            else:
                db.update_device_state(dev["id"], False)
                _update_device_cache(room, "curtain", {**dev, "is_on": False})
            with _STATE_LOCK:
                DEVICE_STATE.setdefault("curtains", {})[room] = "closed"
        elif action == "start_vacuum":
            if not room:
                raise ValueError("Необходимо указать комнату для команды")
            
            # Пылесос логически не привязан к комнате, но если указана — учитываем
            dev = db.get_device_by_room_and_type(room, "vacuum")
            if not dev:
                db.create_device(name=f"vacuum:{room}", room=room, type_="vacuum", is_on=True)
            else:
                db.update_device_state(dev["id"], True)
            with _STATE_LOCK:
                DEVICE_STATE.setdefault("vacuums", {})[room or "global"] = "running"
                VACUUM_PROGRESS.setdefault(room or "global", 0)  # Reset progress on start
            # Start progress updates
            vacuum_key = room or "global"
            if vacuum_key in VACUUM_TIMERS:
                VACUUM_TIMERS[vacuum_key].cancel()
            VACUUM_TIMERS[vacuum_key] = threading.Timer(1, _update_vacuum_progress, args=[vacuum_key])
            VACUUM_TIMERS[vacuum_key].start()
        elif action == "stop_vacuum":
            if not room:
                raise ValueError("Необходимо указать комнату для команды")
            
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
        
        db_time = time.time() - db_start
        # Notify Home Assistant (best-effort, non-blocking)
        try:
            notify_home_assistant_async(parsed)
        except Exception as _e:
            print(f"home_assistant_bridge: notify failed: {_e}")
        total_time = time.time() - start_time
        print(f"_apply_command timing: db_time={db_time*1000:.2f}ms, total_time={total_time*1000:.2f}ms")
        
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
        return f"Свет{_in_room(room)} включен" if room else "Ошибка: необходимо указать комнату"
    if action == "turn_off_light":
        return f"Свет{_in_room(room)} выключен" if room else "Ошибка: необходимо указать комнату"
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
        return f"Температура{_in_room(room)} снижена" if room else "Ошибка: необходимо указать комнату"
    if action == "decrease_humidity":
        return f"Влажность{_in_room(room)} снижена" if room else "Ошибка: необходимо указать комнату"
    if action == "set_temperature":
        value = params.get("value")
        return f"Температура{_in_room(room)} установлена на {value}°C" if room and value is not None else "Ошибка: необходимо указать комнату и значение"
    if action == "set_humidity":
        value = params.get("value")
        return f"Влажность{_in_room(room)} установлена на {value}💧" if room and value is not None else "Ошибка: необходимо указать комнату и значение"
    if action == "open_curtain":
        return f"Шторы{_in_room(room)} открыты" if room else "Ошибка: необходимо указать комнату"
    if action == "close_curtain":
        return f"Шторы{_in_room(room)} закрыты" if room else "Ошибка: необходимо указать комнату"
    if action == "start_vacuum":
        return f"Пылесос запущен{_in_room(room)}" if room else "Ошибка: необходимо указать комнату"
    if action == "stop_vacuum":
        return f"Пылесос остановлен{_in_room(room)}" if room else "Ошибка: необходимо указать комнату"
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

@app.route("/api/speech/status", methods=["GET"])
def speech_status():
    """Получение статуса системы распознавания речи"""
    try:
        status = get_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": f"Ошибка получения статуса: {e}"}), 500

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
        # Обновляем кэш устройств
        _invalidate_device_cache()
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
        # Обновляем кэш устройств
        _invalidate_device_cache()
        return jsonify(dev)
    except Exception as e:
        return jsonify({"error": f"db error: {e}"}), 500

@app.route("/api/devices/stream", methods=["GET"])
def devices_stream():
    def event_stream(q: queue.Queue):
        try:
            # сразу отправим текущее состояние
            first = json.dumps(_get_devices_snapshot())
            yield f"data: {first}\n\n"
            
            # Отправляем heartbeat каждые 30 секунд
            import time
            last_heartbeat = time.time()
            
            while True:
                try:
                    # Таймаут для получения данных
                    data = q.get(timeout=30)
                    yield f"data: {data}\n\n"
                    last_heartbeat = time.time()
                except queue.Empty:
                    # Отправляем heartbeat если нет данных
                    current_time = time.time()
                    if current_time - last_heartbeat > 30:
                        yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                        last_heartbeat = current_time
                        
        except GeneratorExit:
            pass
        except Exception as e:
            print(f"SSE error: {e}")
            yield f"data: {json.dumps({'error': 'Connection error'})}\n\n"

    q: queue.Queue = queue.Queue(maxsize=10)
    _SUBSCRIBERS.append(q)
    
    response = Response(event_stream(q), mimetype="text/event-stream")
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    return response

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
        
        # Обновляем кэш устройств и отправляем состояние синхронно для быстрого обновления
        _invalidate_device_cache()
        _broadcast_state()

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
    import time
    start_time = time.time()
    
    try:
        payload = request.get_json(force=True, silent=True) or {}
        text = payload.get("text", "").strip()
        if not text:
            return jsonify({"error": "Текст команды пуст"}), 400
        
        parse_start = time.time()
        parsed = parse_command(text)
        parse_time = time.time() - parse_start
        
        try:
            room = parsed.get("params", {}).get("room")
            if room:
                can = _canonicalize_room(room)
                parsed.setdefault("params", {})["room"] = can
        except Exception as e:
            pass
        
        response_text = _format_response(parsed)
        
        apply_start = time.time()
        try:
            _apply_command(parsed)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"Ошибка применения команды: {e}"}), 500
        apply_time = time.time() - apply_start
        
        # Обновляем кэш устройств и отправляем состояние синхронно для быстрого обновления
        _invalidate_device_cache()
        _broadcast_state()
        
        total_time = time.time() - start_time
        
        return jsonify({
            "text": text,
            "parsed": parsed,
            "response": response_text,
            "timing": {
                "parse_time": round(parse_time * 1000, 2),
                "apply_time": round(apply_time * 1000, 2),
                "total_time": round(total_time * 1000, 2)
            }
        })
    except Exception as e:
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
            
            # Обновляем кэш устройств и отправляем состояние синхронно для быстрого обновления
            _invalidate_device_cache()
            _broadcast_state()
            
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


            @app.route("/api/ha/service_call", methods=["POST"])
            def api_ha_service_call():
                """Call Home Assistant service via REST API using HA_URL and HA_TOKEN from env.

                Expected JSON body: {"domain": "light", "service": "turn_on", "data": {"entity_id": "light.kitchen"}}
                """
                try:
                    payload = request.get_json(force=True, silent=True) or {}
                    domain = payload.get("domain")
                    service = payload.get("service")
                    data = payload.get("data", {})
                    if not domain or not service:
                        return jsonify({"error": "domain and service are required"}), 400

                    res = ha_call_service(domain, service, data)
                    return jsonify(res)
                except Exception as e:
                    return jsonify({"error": f"Internal error: {e}"}), 500
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
    # Запуск с HTTPS на порту 5443
    import ssl
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('cert.pem', 'key.pem')
    app.run(debug=False, host="0.0.0.0", port=5443, ssl_context=context)
