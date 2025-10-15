document.addEventListener('DOMContentLoaded', function() {
    const commandInput = document.getElementById('command-input');
    const sendButton = document.getElementById('send-command');
    const responseP = document.getElementById('response');
    const deviceStatusP = document.getElementById('device-status');
    const roomsContainer = document.getElementById('rooms-container');
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
            const response = await fetch('/api/text_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: command })
            });

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
            responseP.textContent = `Ошибка: ${error.message}`;
        }
    });

    // Обработчик для Enter в поле ввода
    commandInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendButton.click();
        }
    });

    function speak(text) {
        try {
            if (!text) return;
            const u = new SpeechSynthesisUtterance(text);
            u.lang = 'ru-RU';
            speechSynthesis.speak(u);
        } catch(e) {}
    }

    function capitalize(s){ if(!s) return s; return s.charAt(0).toUpperCase()+s.slice(1); }

    const ROOM_IMG = {
        'зал': 'https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?q=80&w=1200&auto=format&fit=crop',
        'гостиная': 'https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?q=80&w=1200&auto=format&fit=crop',
        'кухня': 'https://images.unsplash.com/photo-1504754524776-8f4f37790ca0?q=80&w=1200&auto=format&fit=crop',
        'комната': 'https://images.unsplash.com/photo-1493666438817-866a91353ca9?q=80&w=1200&auto=format&fit=crop',
        'ванная': 'https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?q=80&w=1200&auto=format&fit=crop',
        'без комнаты': 'https://images.unsplash.com/photo-1493666438817-866a91353ca9?q=80&w=1200&auto=format&fit=crop'
    };

    function imgFor(room){ return ROOM_IMG[room] || ROOM_IMG['без комнаты']; }

    const ROOM_EMOJI = {
        'зал': '🛋️',
        'гостиная': '🛋️',
        'кухня': '🍳',
        'комната': '🛏️',
        'ванная': '🛁',
        'без комнаты': '🏠'
    };
    function emojiFor(room){ return ROOM_EMOJI[room] || '🏠'; }

    function renderRooms(devices, thermometers, vacuumProgress = {}) {
        const rooms = {};
        devices.forEach(dev => {
            const room = dev.room;
            if (room && room !== 'без комнаты') { // Исключаем устройства без комнаты
                if (!rooms[room]) rooms[room] = {};
                rooms[room][dev.type] = dev;
            }
        });
        
        // Добавляем комнаты без устройств
        const allRooms = ['зал', 'кухня', 'комната', 'ванная'];
        allRooms.forEach(room => {
            if (!rooms[room]) {
                rooms[room] = {};
            }
        });
        
        roomsContainer.innerHTML = Object.keys(rooms).map(room => {
            // Получаем актуальный статус из DEVICE_STATE
            console.log(`Rendering room: ${room}, DEVICE_STATE:`, window.DEVICE_STATE);
            
            const lightOn = window.DEVICE_STATE?.lights?.[room] || false;
            const thermometer = window.DEVICE_STATE?.thermometers?.[room];
            const t = thermometer?.temperature || 22;
            const h = thermometer?.humidity || 50;
            const curtainState = window.DEVICE_STATE?.curtains?.[room] || 'closed';
            const vacuumState = window.DEVICE_STATE?.vacuums?.[room] || 'stopped';
            
            console.log(`Room ${room}: light=${lightOn}, temp=${t}, humidity=${h}, curtain=${curtainState}, vacuum=${vacuumState}`);
            return `
                <div class="room-card" data-room="${room}">
                    <h3>${capitalize(room)}</h3>
                    <div class="room-stats">
                        <div>Свет: ${lightOn ? 'включен' : 'выключен'}</div>
                        <div>Температура: ${t}°C</div>
                        <div>Влажность: ${h}💧</div>
                        <div>Шторы: ${curtainState === 'open' ? 'открыты' : 'закрыты'}</div>
                        <div>Пылесос: ${vacuumState === 'running' ? 'работает' : 'остановлен'}</div>
                    </div>
                    <div class="room-controls">
                        <div class="control-group">
                            <button onclick="turnOnLight('${room}')" class="light-btn-on" id="light-on-${room}">Включить свет</button>
                            <button onclick="turnOffLight('${room}')" class="light-btn-off" id="light-off-${room}">Выключить свет</button>
                        </div>
                        <div class="control-group">
                            <button onclick="openCurtain('${room}')" class="curtain-btn-open" id="curtain-open-${room}">Открыть шторы</button>
                            <button onclick="closeCurtain('${room}')" class="curtain-btn-close" id="curtain-close-${room}">Закрыть шторы</button>
                        </div>
                        <div class="control-group">
                            <button onclick="startVacuum('${room}')" class="vacuum-btn-start" id="vacuum-start-${room}">Запустить пылесос</button>
                            <button onclick="stopVacuum('${room}')" class="vacuum-btn-stop" id="vacuum-stop-${room}">Остановить пылесос</button>
                        </div>
                    </div>
                    <div class="room-sliders">
                        <div class="slider-group">
                            <label>Температура: ${t}°C</label>
                            <input type="range" min="10" max="40" step="1" value="${t}" onchange="setTemperature('${room}', this.value)">
                        </div>
                        <div class="slider-group">
                            <label>Влажность: ${h}%</label>
                            <input type="range" min="20" max="90" step="1" value="${h}" onchange="setHumidity('${room}', this.value)">
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

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
            
            return `
                <div class="status-card">
                    <div class="title">${capitalize(room)}</div>
                    <div class="line"><span>Свет</span><span>${lightOn ? 'включен' : 'выключен'}</span></div>
                    <div class="line"><span>Температура</span><span>${t}°C</span></div>
                    <div class="line"><span>Влажность</span><span>${h}💧</span></div>
                    <div class="line"><span>Шторы</span><span>${curtainState === 'open' ? 'открыты' : 'закрыты'}</span></div>
                    <div class="line"><span>Пылесос</span><span>${vacuumState === 'running' ? 'работает' : 'остановлен'}</span></div>
                </div>
            `;
        }).join('');
    }

    function loadStatus() {
        fetch('/api/devices')
        .then(response => response.json())
        .then(data => {
            window.lastDevices = data.devices || [];
            let thermometers = window.lastThermometers || {};
            let vacuumProgress = window.lastVacuumProgress || {};
            renderStatus(data.devices, thermometers, vacuumProgress);
            renderRooms(data.devices, thermometers, vacuumProgress);
        })
        .catch(error => {
            console.error('Ошибка загрузки:', error);
            if (statusGrid) statusGrid.innerHTML = '<div class="status-card">Ошибка загрузки</div>';
        });
    }

    // SSE
    if (typeof EventSource !== 'undefined') {
        const sse = new EventSource('/api/devices/stream');
        sse.onmessage = (e) => {
            try {
                const state = JSON.parse(e.data);
                window.DEVICE_STATE = state; // Сохраняем состояние
                window.lastThermometers = state.thermometers || {};
                window.lastVacuumProgress = state.vacuum_progress || {};
                console.log('Получено состояние через SSE:', state);
                
                // Обновляем интерфейс напрямую с актуальными данными
                renderStatus(state.devices || [], state.thermometers || {}, state.vacuum_progress || {});
                renderRooms(state.devices || [], state.thermometers || {}, state.vacuum_progress || {});
            } catch (err) {
                console.error('Ошибка парсинга SSE:', err);
            }
        };
    }

    // Инициализация камеры (live) с выбором устройств
    (function initCameraPanel(){
        const video = document.getElementById('camera-video');
        const label = document.getElementById('camera-status');
        const select = document.getElementById('camera-select');
        const refreshBtn = document.getElementById('camera-refresh');
        let currentStream = null;

        async function stopCurrent() {
            try {
                if (currentStream) {
                    currentStream.getTracks().forEach(t => t.stop());
                    currentStream = null;
                }
            } catch(_) {}
        }
        async function listCameras() {
            try {
                const all = await navigator.mediaDevices.enumerateDevices();
                const cams = all.filter(d => d.kind === 'videoinput');
                select.innerHTML = cams.map((c, i) => `<option value="${c.deviceId}">${c.label || 'Камера ' + (i+1)}</option>`).join('');
                if (!cams.length) {
                    if (label) label.textContent = 'Камеры не найдены';
                }
            } catch(e) {
                if (label) label.textContent = 'Не удалось получить список камер';
            }
        }
        async function startWithDevice(deviceId) {
            await stopCurrent();
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                if (label) label.textContent = 'Браузер не поддерживает камеру';
                return;
            }
            const base = { audio: false, video: deviceId ? { deviceId: { exact: deviceId } } : { facingMode: 'environment' } };
            try {
                currentStream = await navigator.mediaDevices.getUserMedia(base);
                video.srcObject = currentStream;
                if (label) label.textContent = '';
            } catch (e) {
                // Попробуем мягче
                try {
                    currentStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                    video.srcObject = currentStream;
                    if (label) label.textContent = '';
                } catch (e2) {
                    const name = (e2 && e2.name) || (e && e.name) || 'Ошибка';
                    if (name === 'NotReadableError') {
                        if (label) label.textContent = 'Камера занята другим приложением. Закройте другие приложения, использующие камеру, и попробуйте снова.';
                    } else if (name === 'SecurityError' || name === 'NotAllowedError') {
                        if (label) label.textContent = 'Дайте разрешение на использование камеры в настройках браузера.';
                    } else {
                        if (label) label.textContent = 'Камера недоступна: ' + name;
                    }
                }
            }
        }
        if (refreshBtn) refreshBtn.addEventListener('click', listCameras);
        if (select) select.addEventListener('change', () => startWithDevice(select.value));
        // Первичная инициализация: запросить доступ, затем заполнить список и запустить
        (async function init(){
            try {
                await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            } catch(_) {}
            await listCameras();
            await startWithDevice(select && select.value ? select.value : undefined);
        })();
    })();

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
        if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
            voiceOut.textContent = 'Запись микрофона доступна только по HTTPS. Откройте сайт по защищенному адресу.';
            return;
        }
        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (err) {
            const msg = (err && err.name) ? err.name : 'Неизвестная ошибка доступа к микрофону';
            voiceOut.textContent = 'Не удалось получить доступ к микрофону: ' + msg + '. Проверьте разрешения браузера и откройте сайт по HTTPS.';
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
            
            voiceRecordBtn.textContent = 'Записать голосовую команду';
            isRecording = false;
        };
        mediaRecorder.start();
        voiceRecordBtn.textContent = 'Идет запись... Нажмите снова, чтобы отправить';
        isRecording = true;
    }
    function stopVoiceRecording() {
        if (isRecording && mediaRecorder) {
            mediaRecorder.stop();
        }
    }
    if (voiceRecordBtn && voiceOut) {
        // Единое поведение: первое нажатие — старт, второе — стоп/отправка
        voiceRecordBtn.addEventListener('click', () => {
            if (!isRecording) startVoiceRecording(); else stopVoiceRecording();
        });
        // Дополнительно поддержим touch (если click глючит)
        voiceRecordBtn.addEventListener('touchend', (e) => {
            e.preventDefault();
            if (!isRecording) startVoiceRecording(); else stopVoiceRecording();
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

    // Управление устройствами
    (function initDeviceControls() {
        const deviceTypeSelect = document.getElementById('device-type');
        const deviceRoomSelect = document.getElementById('device-room');
        const deviceActionBtn = document.getElementById('device-action-btn');
        const deviceStatusDisplay = document.getElementById('device-status-display');

        if (!deviceActionBtn) return;

        deviceActionBtn.addEventListener('click', async () => {
            const deviceType = deviceTypeSelect.value;
            const room = deviceRoomSelect.value;
            
            let command = '';
            if (deviceType === 'light') {
                command = `включи свет в ${room}`;
            } else if (deviceType === 'thermometer') {
                command = `установи температуру 25 в ${room}`;
            } else if (deviceType === 'curtain') {
                command = `открой шторы в ${room}`;
            } else if (deviceType === 'vacuum') {
                command = `запусти пылесос в ${room}`;
            }

            if (command) {
                try {
                    const response = await fetch('/api/text_command', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: command })
                    });
                    const result = await response.json();
                    deviceStatusDisplay.innerHTML = `<p>${result.response}</p>`;
                    loadStatus();
                } catch (error) {
                    deviceStatusDisplay.innerHTML = `<p style="color: red;">Ошибка</p>`;
                }
            }
        });
    })();

    // Простые функции управления светом
    window.turnOnLight = async function(room) {
        console.log('ВКЛЮЧАЕМ СВЕТ В:', room);
        
        try {
            const command = `включи свет в ${room}`;
            console.log('Отправляем команду:', command);
            
            // Отправляем команду через текстовый API
            const response = await fetch('/api/text_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: command })
            });
            
            console.log('Ответ сервера:', response.status);
            
            if (response.ok) {
                const result = await response.json();
                console.log('Результат:', result);
                console.log('СВЕТ ВКЛЮЧЕН!');
                // Принудительно обновляем DEVICE_STATE
                if (window.DEVICE_STATE) {
                    if (!window.DEVICE_STATE.lights) window.DEVICE_STATE.lights = {};
                    window.DEVICE_STATE.lights[room] = true;
                }
                // Сразу обновляем интерфейс без задержки
                renderStatus(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
                renderRooms(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
            } else {
                const error = await response.text();
                console.error('Ошибка включения света:', response.status, error);
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    };

    window.turnOffLight = async function(room) {
        console.log('ВЫКЛЮЧАЕМ СВЕТ В:', room);
        
        try {
            const command = `выключи свет в ${room}`;
            console.log('Отправляем команду:', command);
            
            // Отправляем команду через текстовый API
            const response = await fetch('/api/text_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: command })
            });
            
            console.log('Ответ сервера:', response.status);
            
            if (response.ok) {
                const result = await response.json();
                console.log('Результат:', result);
                console.log('СВЕТ ВЫКЛЮЧЕН!');
                // Принудительно обновляем DEVICE_STATE
                if (window.DEVICE_STATE) {
                    if (!window.DEVICE_STATE.lights) window.DEVICE_STATE.lights = {};
                    window.DEVICE_STATE.lights[room] = false;
                }
                // Сразу обновляем интерфейс без задержки
                renderStatus(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
                renderRooms(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
            } else {
                const error = await response.text();
                console.error('Ошибка выключения света:', response.status, error);
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    };

    // Функции для ползунков
    window.setTemperature = async function(room, value) {
        console.log('УСТАНАВЛИВАЕМ ТЕМПЕРАТУРУ В', room, 'НА', value);
        
        try {
            const response = await fetch('/api/text_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: `установи температуру в ${room} ${value}` })
            });
            
            if (response.ok) {
                console.log('ТЕМПЕРАТУРА УСТАНОВЛЕНА!');
                // Принудительно обновляем DEVICE_STATE
                if (window.DEVICE_STATE) {
                    if (!window.DEVICE_STATE.thermometers) window.DEVICE_STATE.thermometers = {};
                    if (!window.DEVICE_STATE.thermometers[room]) window.DEVICE_STATE.thermometers[room] = {temperature: 22, humidity: 50};
                    window.DEVICE_STATE.thermometers[room].temperature = parseFloat(value);
                }
                // Сразу обновляем интерфейс без задержки
                renderStatus(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
                renderRooms(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
            } else {
                console.error('Ошибка установки температуры');
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    };

    window.setHumidity = async function(room, value) {
        console.log('УСТАНАВЛИВАЕМ ВЛАЖНОСТЬ В', room, 'НА', value);
        
        try {
            const response = await fetch('/api/text_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: `установи влажность в ${room} ${value}` })
            });
            
            if (response.ok) {
                console.log('ВЛАЖНОСТЬ УСТАНОВЛЕНА!');
                // Принудительно обновляем DEVICE_STATE
                if (window.DEVICE_STATE) {
                    if (!window.DEVICE_STATE.thermometers) window.DEVICE_STATE.thermometers = {};
                    if (!window.DEVICE_STATE.thermometers[room]) window.DEVICE_STATE.thermometers[room] = {temperature: 22, humidity: 50};
                    window.DEVICE_STATE.thermometers[room].humidity = parseFloat(value);
                }
                // Сразу обновляем интерфейс без задержки
                renderStatus(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
                renderRooms(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
            } else {
                console.error('Ошибка установки влажности');
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    };

    window.startVacuum = async function(room) {
        console.log('ЗАПУСКАЕМ ПЫЛЕСОС В:', room);
        
        try {
            const command = `запусти пылесос в ${room}`;
            console.log('Отправляем команду:', command);
            
            const response = await fetch('/api/text_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: command })
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('Результат:', result);
                console.log('ПЫЛЕСОС ЗАПУЩЕН!');
                // Принудительно обновляем DEVICE_STATE
                if (window.DEVICE_STATE) {
                    if (!window.DEVICE_STATE.vacuums) window.DEVICE_STATE.vacuums = {};
                    window.DEVICE_STATE.vacuums[room] = 'running';
                }
                // Сразу обновляем интерфейс без задержки
                renderStatus(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
                renderRooms(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
            } else {
                const error = await response.text();
                console.error('Ошибка запуска пылесоса:', response.status, error);
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    };

    window.stopVacuum = async function(room) {
        console.log('ОСТАНАВЛИВАЕМ ПЫЛЕСОС В:', room);
        
        try {
            const command = `останови пылесос в ${room}`;
            console.log('Отправляем команду:', command);
            
            const response = await fetch('/api/text_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: command })
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('Результат:', result);
                console.log('ПЫЛЕСОС ОСТАНОВЛЕН!');
                // Принудительно обновляем DEVICE_STATE
                if (window.DEVICE_STATE) {
                    if (!window.DEVICE_STATE.vacuums) window.DEVICE_STATE.vacuums = {};
                    window.DEVICE_STATE.vacuums[room] = 'stopped';
                }
                // Сразу обновляем интерфейс без задержки
                renderStatus(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
                renderRooms(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
            } else {
                const error = await response.text();
                console.error('Ошибка остановки пылесоса:', response.status, error);
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    };

    // Функции управления шторами
    window.openCurtain = async function(room) {
        console.log('ОТКРЫВАЕМ ШТОРЫ В:', room);
        
        try {
            const command = `открой шторы в ${room}`;
            console.log('Отправляем команду:', command);
            
            const response = await fetch('/api/text_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: command })
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('Результат:', result);
                console.log('ШТОРЫ ОТКРЫТЫ!');
                // Принудительно обновляем DEVICE_STATE
                if (window.DEVICE_STATE) {
                    if (!window.DEVICE_STATE.curtains) window.DEVICE_STATE.curtains = {};
                    window.DEVICE_STATE.curtains[room] = 'open';
                }
                // Сразу обновляем интерфейс без задержки
                renderStatus(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
                renderRooms(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
            } else {
                const error = await response.text();
                console.error('Ошибка открытия штор:', response.status, error);
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    };

    window.closeCurtain = async function(room) {
        console.log('ЗАКРЫВАЕМ ШТОРЫ В:', room);
        
        try {
            const command = `закрой шторы в ${room}`;
            console.log('Отправляем команду:', command);
            
            const response = await fetch('/api/text_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: command })
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('Результат:', result);
                console.log('ШТОРЫ ЗАКРЫТЫ!');
                // Принудительно обновляем DEVICE_STATE
                if (window.DEVICE_STATE) {
                    if (!window.DEVICE_STATE.curtains) window.DEVICE_STATE.curtains = {};
                    window.DEVICE_STATE.curtains[room] = 'closed';
                }
                // Сразу обновляем интерфейс без задержки
                renderStatus(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
                renderRooms(window.lastDevices || [], window.lastThermometers || {}, window.lastVacuumProgress || {});
            } else {
                const error = await response.text();
                console.error('Ошибка закрытия штор:', response.status, error);
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    };

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
