document.addEventListener('DOMContentLoaded', function() {
    const commandInput = document.getElementById('command-input');
    const sendButton = document.getElementById('send-command');
    const responseP = document.getElementById('response');
    const deviceStatusP = document.getElementById('device-status');
    const statusGrid = document.getElementById('status-grid');

    // Load initial status
    loadStatus();

    // Обработчик для отправки текстовых команд
    sendButton.addEventListener('click', async () => {
        const command = commandInput.value.trim();
        if (!command) {
            responseP.textContent = 'Введите команду';
            return;
        }

        try {
            responseP.textContent = 'Отправляю команду...';
            
            // Добавляем таймаут для запроса
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 секунд таймаут
            
            const response = await fetch('/api/text_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: command }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);

            if (response.ok) {
                const result = await response.json();
                responseP.textContent = result.response || 'Команда выполнена';
                commandInput.value = ''; // Очищаем поле ввода
                
                // Обновляем интерфейс
                setTimeout(() => {
                    loadStatus();
                }, 100);
            } else {
                const error = await response.text();
                responseP.textContent = `Ошибка: ${error}`;
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                responseP.textContent = 'Таймаут: команда выполняется слишком долго';
            } else {
                responseP.textContent = `Ошибка: ${error.message}`;
            }
        }
    });

    // Обработчик для Enter в поле ввода
    commandInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendButton.click();
        }
    });

    // Функция для быстрых команд
    window.sendQuickCommand = async function(command) {
        commandInput.value = command;
        sendButton.click();
    };

    function speak(text) {
        try {
            if (!text) return;
            const u = new SpeechSynthesisUtterance(text);
            u.lang = 'ru-RU';
            speechSynthesis.speak(u);
        } catch(e) {}
    }

    function capitalize(s){ if(!s) return s; return s.charAt(0).toUpperCase()+s.slice(1); }

    function renderStatus(devices, thermometers, vacuumProgress = {}) {
        if (!statusGrid) return;
        const rooms = {};
        devices.forEach(dev => {
            const room = dev.room;
            if (room && room !== 'без комнаты') { // Исключаем устройства без комнаты
                if (!rooms[room]) rooms[room] = {};
                rooms[room][dev.type] = dev;
            }
        });
        
        // Добавляем все комнаты, даже если в них нет устройств
        const allRooms = ['зал', 'кухня', 'комната', 'ванная'];
        allRooms.forEach(room => {
            if (!rooms[room]) {
                rooms[room] = {};
            }
        });
        
        statusGrid.innerHTML = Object.keys(rooms).map(room => {
            // Получаем актуальный статус из DEVICE_STATE
            const lightOn = window.DEVICE_STATE?.lights?.[room] || false;
            const thermometer = window.DEVICE_STATE?.thermometers?.[room];
            const t = thermometer?.temperature || 22;
            const h = thermometer?.humidity || 50;
            const curtainState = window.DEVICE_STATE?.curtains?.[room] || 'closed';
            const vacuumState = window.DEVICE_STATE?.vacuums?.[room] || 'stopped';
            
            // Для ванной комнаты не показываем шторы и пылесос
            const isBathroom = room === 'ванная';
            
            return `
                <div class="status-card">
                    <div class="title">${capitalize(room)}</div>
                    <div class="line"><span>Свет</span><span>${lightOn ? 'включен' : 'выключен'}</span></div>
                    <div class="line"><span>Температура</span><span>${t}°C</span></div>
                    <div class="line"><span>Влажность</span><span>${h}💧</span></div>
                    ${!isBathroom ? `<div class="line"><span>Шторы</span><span>${curtainState === 'open' ? 'открыты' : 'закрыты'}</span></div>` : ''}
                    ${!isBathroom ? `<div class="line"><span>Пылесос</span><span>${vacuumState === 'running' ? 'работает' : 'остановлен'}</span></div>` : ''}
                </div>
            `;
        }).join('');
    }

    function loadStatus() {
        fetch('/api/devices')
        .then(response => response.json())
        .then(data => {
            window.lastDevices = data.devices || [];
            // Используем актуальные данные из DEVICE_STATE или значения по умолчанию
            let thermometers = window.DEVICE_STATE?.thermometers || {};
            let vacuumProgress = window.DEVICE_STATE?.vacuum_progress || {};
            renderStatus(data.devices, thermometers, vacuumProgress);
        })
        .catch(error => {
            console.error('Ошибка загрузки:', error);
            if (statusGrid) statusGrid.innerHTML = '<div class="status-card">Ошибка загрузки</div>';
        });
    }

    // SSE с дебаунсингом
    if (typeof EventSource !== 'undefined') {
        const sse = new EventSource('/api/devices/stream');
        let updateTimeout = null;
        
        sse.onmessage = (e) => {
            try {
                const state = JSON.parse(e.data);
                window.DEVICE_STATE = state; // Сохраняем состояние
                window.lastThermometers = state.thermometers || {};
                window.lastVacuumProgress = state.vacuum_progress || {};
                
                // Дебаунсинг обновлений интерфейса
                if (updateTimeout) clearTimeout(updateTimeout);
                updateTimeout = setTimeout(() => {
                    renderStatus(state.devices || [], state.thermometers || {}, state.vacuum_progress || {});
                }, 100);
            } catch (err) {
                console.error('Ошибка парсинга SSE:', err);
            }
        };
        
        sse.onerror = (err) => {
            console.error('Ошибка SSE соединения:', err);
        };
    }

    // Табы
    (function initTabs(){
        const buttons = Array.from(document.querySelectorAll('.tab-btn'));
        const panes = Array.from(document.querySelectorAll('.tab-pane'));
        function activate(id){
            panes.forEach(p => p.style.display = (p.id === id ? '' : 'none'));
            buttons.forEach(b => {
                if (b.dataset.tab === id) b.classList.add('active'); else b.classList.remove('active');
            });
        }
        buttons.forEach(b => b.addEventListener('click', () => activate(b.dataset.tab)));
        // Стартовая вкладка — Главная
        activate('tab-home');
    })();

    // --- Голосовое управление: тап для старта/стопа (мобильные) и клик (десктоп) ---
    let mediaRecorder, chunks = [], blob = null, isRecording = false;
    const voiceRecordBtn = document.getElementById('voice-record');
    const voiceOut = document.getElementById('voice-out');

    async function startVoiceRecording() {
        if (isRecording) return;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            voiceOut.textContent = 'Ваш браузер не поддерживает запись аудио. Обновите браузер или используйте другой.';
            return;
        }
        
        // Проверяем HTTPS
        if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
            voiceOut.textContent = 'Запись микрофона доступна только по HTTPS. Откройте сайт по защищенному адресу.';
            return;
        }
        
        let stream;
        try {
            // Запрашиваем доступ к микрофону
            stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
        } catch (err) {
            console.error('Ошибка доступа к микрофону:', err);
            
            let errorMessage = 'Не удалось получить доступ к микрофону. ';
            
            if (err.name === 'NotAllowedError') {
                errorMessage += 'Разрешение на использование микрофона отклонено. ';
                errorMessage += 'Нажмите на иконку замка в адресной строке и разрешите доступ к микрофону.';
            } else if (err.name === 'NotFoundError') {
                errorMessage += 'Микрофон не найден. Проверьте подключение микрофона.';
            } else if (err.name === 'NotReadableError') {
                errorMessage += 'Микрофон занят другим приложением. Закройте другие приложения, использующие микрофон.';
            } else if (err.name === 'SecurityError') {
                errorMessage += 'Ошибка безопасности. Убедитесь, что сайт открыт по HTTPS.';
            } else {
                errorMessage += `Ошибка: ${err.name || 'Неизвестная ошибка'}. `;
                errorMessage += 'Попробуйте обновить страницу или перезапустить браузер.';
            }
            
            voiceOut.textContent = errorMessage;
            return;
        }
        mediaRecorder = new MediaRecorder(stream);
        chunks = [];
        mediaRecorder.ondataavailable = e => chunks.push(e.data);
        mediaRecorder.onstop = async () => {
            blob = new Blob(chunks, { type: (chunks[0] && chunks[0].type) || blob?.type || 'audio/webm' });
            // Определяем расширение по MIME
            const mime = blob.type || '';
            let ext = 'webm';
            if (mime.includes('ogg')) ext = 'ogg';
            else if (mime.includes('wav')) ext = 'wav';
            else if (mime.includes('mp4')) ext = 'm4a';
            else if (mime.includes('aac')) ext = 'aac';
            else if (mime.includes('mp3')) ext = 'mp3';

            const fileBlob = new File([blob], `recording.${ext}`, { type: mime || `audio/${ext}` });
            const form = new FormData();
            form.append('audio', fileBlob);
            const res = await fetch('/api/speech_to_action', {
                method: 'POST',
                body: form
            });
            let json;
            try { json = await res.json(); } catch(e) { json = { error: 'Не удалось распарсить ответ сервера' }; }
            
            // Отображаем понятный ответ пользователю
            if (json.error) {
                voiceOut.textContent = `Ошибка: ${json.error}`;
            } else {
                voiceOut.textContent = json.response || 'Команда выполнена';
                // Обновляем интерфейс после выполнения команды
                setTimeout(() => {
                    loadStatus();
                }, 100);
            }
            
            voiceRecordBtn.textContent = '🎤';
            voiceRecordBtn.classList.remove('recording');
            isRecording = false;
        };
        mediaRecorder.start();
        voiceRecordBtn.textContent = '⏹️';
        voiceRecordBtn.classList.add('recording');
        isRecording = true;
    }
    function stopVoiceRecording() {
        if (isRecording && mediaRecorder) {
            mediaRecorder.stop();
        }
    }
    if (voiceRecordBtn && voiceOut) {
        // Принцип "зажать и держать"
        voiceRecordBtn.addEventListener('mousedown', () => {
            if (!isRecording) startVoiceRecording();
        });
        
        voiceRecordBtn.addEventListener('mouseup', () => {
            if (isRecording) stopVoiceRecording();
        });
        
        voiceRecordBtn.addEventListener('mouseleave', () => {
            if (isRecording) stopVoiceRecording();
        });
        
        // Для мобильных устройств
        voiceRecordBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            if (!isRecording) startVoiceRecording();
        }, { passive: false });
        
        voiceRecordBtn.addEventListener('touchend', (e) => {
            e.preventDefault();
            if (isRecording) stopVoiceRecording();
        }, { passive: false });
        
        voiceRecordBtn.addEventListener('touchcancel', (e) => {
            e.preventDefault();
            if (isRecording) stopVoiceRecording();
        }, { passive: false });
    }

    function updateVacuumProgressDisplay(vacuumProgress) {
        const progressFill = document.querySelector('.progress-fill');
        if (progressFill && vacuumProgress) {
            const rooms = Object.keys(vacuumProgress);
            if (rooms.length > 0) {
                const firstRoom = rooms[0];
                const progress = vacuumProgress[firstRoom] || 0;
                progressFill.style.width = `${progress}%`;
            }
        }
    }



    // Простые функции для добавления/удаления устройств
    window.addDevice = async function(type, room) {
        let name = `${type}:${room}`;
        if (type === 'light') name = `Свет в ${room}`;
        if (type === 'thermometer') name = `Термометр в ${room}`;
        await fetch('/api/devices', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, type, room, is_on: false })
        });
        loadStatus();
    };

    window.deleteDeviceByType = async function(type, room) {
        const dev = (window.lastDevices || []).find(d => d.type === type && d.room === room);
        if (!dev) return;
        await fetch(`/api/devices/${dev.id}`, { method: 'DELETE' });
        loadStatus();
    };

});
