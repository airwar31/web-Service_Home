#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Home Web Service - Main Application
Главный файл приложения с MVC архитектурой
"""

import os
import sys
import json
import ssl
import threading
import queue as queue_module
import time
from typing import Dict, Any

from flask import Flask, request, jsonify, render_template, Response, stream_with_context

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.controllers.app_controller import AppController
from app.services.speech_service import SpeechService
from app.utils.file_utils import allowed_file, temp_filepath
from config.settings import Settings


# Создаем Flask приложение
app = Flask(__name__, 
            template_folder='static/templates',
            static_folder='static',
            static_url_path='/static')

# Инициализируем контроллер (кэш инициализации выключен для ускорения)
app_controller = AppController()
speech_service = SpeechService()

# Инициализируем базу данных
app_controller.device_controller.db.init_db()

# Предзагружаем устройства в кэш для быстрой отдачи
print("Preloading devices...")
devices = app_controller.device_controller.db.list_devices()
app_controller.cached_devices = devices
print(f"Preloaded {len(devices)} devices")


@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')


@app.route('/api/devices')
def api_devices():
    """API для получения списка устройств"""
    try:
        print("DEBUG: /api/devices called")
        snapshot = app_controller.get_devices_snapshot()
        print(f"DEBUG: snapshot keys: {snapshot.keys()}")
        print(f"DEBUG: devices count: {len(snapshot.get('devices', []))}")
        return jsonify(snapshot)
    except Exception as e:
        print(f"DEBUG: Error in /api/devices: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/command', methods=['POST'])
def api_text_command():
    """API для обработки текстовых команд"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Текст команды не указан"}), 400
        
        text = data['text'].strip()
        if not text:
            return jsonify({"error": "Пустая команда"}), 400
        
        result = app_controller.process_text_command(text)
        return jsonify({"result": result})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/speech', methods=['POST'])
def api_speech_to_action():
    """API для обработки голосовых команд"""
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "Аудиофайл не найден"}), 400
        
        file = request.files['audio']
        if file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": "Неподдерживаемый формат файла"}), 400
        
        # Сохраняем временный файл
        temp_path = temp_filepath(f".{file.filename.rsplit('.', 1)[1].lower()}")
        file.save(temp_path)
        
        try:
            result = app_controller.process_speech_command(temp_path)
            return jsonify({"result": result})
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/speech/status')
def api_speech_status():
    """API для получения статуса распознавания речи"""
    try:
        status = app_controller.get_speech_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/device/<int:device_id>/<action>', methods=['POST'])
def device_action(device_id: int, action: str):
    """API для выполнения действий с устройствами"""
    try:
        payload = request.get_json() or {}
        result = app_controller.device_action(device_id, action, payload)
        return jsonify({"result": result})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/events')
def api_events():
    """SSE endpoint для получения событий в реальном времени"""
    def event_stream():
        # Создаем очередь для этого клиента
        subscriber_q = app_controller.add_subscriber()
        
        try:
            while True:
                try:
                    # Ждем данные с таймаутом
                    data = subscriber_q.get(timeout=30)
                    yield f"data: {data}\n\n"
                except queue_module.Empty:
                    # Отправляем ping для поддержания соединения
                    try:
                        yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    except:
                        break
                except Exception:
                    break
                    
        except GeneratorExit:
            pass
        finally:
            # Клиент отключился
            try:
                app_controller.remove_subscriber(subscriber_q)
            except:
                pass
    
    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control'
        }
    )


def start_background_tasks():
    """Запуск фоновых задач"""
    # Фоновая задача для обновления термометров отключена
    # Термометры теперь обновляются только при командах пользователя
    # Это предотвращает случайные изменения значений через секунду после команды
    pass


if __name__ == '__main__':
    # Запускаем фоновые задачи
    start_background_tasks()
    
    # Получаем SSL контекст
    ssl_context = Settings.get_ssl_context()
    
    # Запускаем сервер с SSL
    if ssl_context:
        print(f"Starting server on https://{Settings.HOST}:{Settings.PORT}")
        app.run(
            host=Settings.HOST,
            port=Settings.PORT,
            ssl_context=ssl_context,
            debug=Settings.DEBUG,
            threaded=True
        )
    else:
        print(f"Starting server on http://{Settings.HOST}:5000")
        app.run(
            host=Settings.HOST,
            port=5000,
            debug=Settings.DEBUG,
            threaded=True
        )
