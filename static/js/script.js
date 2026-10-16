/**
 * SmartHome OS - Unified Control Center SPA Controller
 */

// Global Application State
window.DEVICE_STATE = {
    lights: { "зал": false, "кухня": false, "комната": false, "ванная": false },
    thermometers: {
        "зал": { temperature: 23.0, humidity: 45 },
        "кухня": { temperature: 24.0, humidity: 52 },
        "комната": { temperature: 21.5, humidity: 48 },
        "ванная": { temperature: 25.5, humidity: 68 }
    },
    curtains: { "зал": "closed", "кухня": "closed", "комната": "closed" },
    vacuums: { "зал": "stopped", "кухня": "stopped", "комната": "stopped" },
    vacuum_progress: { "зал": 0, "кухня": 0, "комната": 0 }
};

let ttsEnabled = true;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let speechRecognition = null;

// ===================================================================
// Initialization
// ===================================================================

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initTTS();
    loadStatus();
    initSSE();
    setupCommandInput();
    setupVoiceRecognition();
});

// ===================================================================
// Theme & TTS Settings
// ===================================================================

function initTheme() {
    const savedTheme = localStorage.getItem('smarthome_theme') || 'dark';
    setTheme(savedTheme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    setTheme(current === 'dark' ? 'light' : 'dark');
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('smarthome_theme', theme);
    const icon = document.getElementById('themeIcon');
    if (icon) {
        icon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
}

function initTTS() {
    const saved = localStorage.getItem('smarthome_tts');
    ttsEnabled = saved !== 'false';
    updateTTSIcon();
}

function toggleTTS() {
    ttsEnabled = !ttsEnabled;
    localStorage.setItem('smarthome_tts', ttsEnabled);
    updateTTSIcon();
    showToast(ttsEnabled ? 'Озвучка ответов включена' : 'Озвучка ответов отключена', 'info');
}

function updateTTSIcon() {
    const icon = document.getElementById('ttsIcon');
    const btn = document.getElementById('ttsToggleBtn');
    if (icon && btn) {
        icon.textContent = ttsEnabled ? '🔊' : '🔇';
        btn.classList.toggle('active', ttsEnabled);
    }
}

function speak(text) {
    if (!ttsEnabled || !window.speechSynthesis || !text) return;
    try {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'ru-RU';
        utterance.rate = 1.05;
        window.speechSynthesis.speak(utterance);
    } catch (e) {
        console.warn('Speech synthesis error:', e);
    }
}

// ===================================================================
// Toast Notifications
// ===================================================================

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icons = { success: '✅', error: '❌', info: '⚡' };

    toast.innerHTML = `
        <span style="font-size: 1.15rem;">${icons[type] || 'ℹ️'}</span>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(30px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ===================================================================
// Device State Management & Rendering
// ===================================================================

async function loadStatus() {
    try {
        const res = await fetch('/api/devices', { cache: 'no-cache' });
        if (!res.ok) throw new Error('Failed to fetch devices');
        const data = await res.json();

        // Update local state from devices API
        if (data && Array.isArray(data)) {
            data.forEach(dev => {
                if (dev.room && dev.type === 'light') {
                    window.DEVICE_STATE.lights[dev.room] = !!dev.is_on;
                }
            });
        }

        renderDashboard();
    } catch (err) {
        console.warn('Could not load device status:', err);
        renderDashboard();
    }
}

function renderDashboard() {
    renderRoomsGrid();
    updateStatsRibbon();
}

function renderRoomsGrid() {
    const container = document.getElementById('roomsGrid');
    if (!container) return;

    const roomsConfig = [
        { id: 'зал', name: '🛋️ Зал', hasCurtains: true, hasVacuum: true },
        { id: 'кухня', name: '🍳 Кухня', hasCurtains: true, hasVacuum: true },
        { id: 'комната', name: '🛏️ Спальня', hasCurtains: true, hasVacuum: true },
        { id: 'ванная', name: '🚿 Ванная', hasCurtains: false, hasVacuum: false }
    ];

    container.innerHTML = roomsConfig.map(room => {
        const lightOn = !!window.DEVICE_STATE.lights[room.id];
        const thermo = window.DEVICE_STATE.thermometers[room.id] || { temperature: 22.0, humidity: 50 };
        const curtainState = window.DEVICE_STATE.curtains[room.id] || 'closed';
        const isCurtainOpen = curtainState === 'open';
        const vacuumState = window.DEVICE_STATE.vacuums[room.id] || 'stopped';
        const isVacuumRunning = vacuumState === 'running';
        const vacuumProgress = window.DEVICE_STATE.vacuum_progress[room.id] || 0;

        return `
            <div class="room-card" id="room-${room.id}">
                <div class="room-header">
                    <div class="room-name">${room.name}</div>
                    <div class="temp-gauge">
                        <span>${thermo.temperature.toFixed(1)}°C</span>
                        <span class="humidity-badge">💧 ${thermo.humidity}%</span>
                    </div>
                </div>

                <!-- Light Switch -->
                <div class="device-item">
                    <div class="device-info">
                        <span class="device-icon" style="color: ${lightOn ? '#f59e0b' : 'var(--text-muted)'};">💡</span>
                        <div>
                            <div class="device-name">Освещение</div>
                            <div style="font-size: 0.76rem; color: var(--text-muted);">${lightOn ? 'Включено' : 'Выключено'}</div>
                        </div>
                    </div>
                    <label class="switch">
                        <input type="checkbox" ${lightOn ? 'checked' : ''} onchange="toggleLight('${room.id}', this.checked)" />
                        <span class="slider"></span>
                    </label>
                </div>

                <!-- Curtains Control -->
                ${room.hasCurtains ? `
                    <div class="device-item">
                        <div class="device-info">
                            <span class="device-icon" style="color: ${isCurtainOpen ? '#10b981' : 'var(--text-muted)'};">🪟</span>
                            <div>
                                <div class="device-name">Шторы</div>
                                <div style="font-size: 0.76rem; color: var(--text-muted);">${isCurtainOpen ? 'Открыты' : 'Закрыты'}</div>
                            </div>
                        </div>
                        <button type="button" class="btn btn-secondary" style="font-size: 0.78rem; padding: 5px 12px;" onclick="toggleCurtains('${room.id}')">
                            ${isCurtainOpen ? 'Закрыть' : 'Открыть'}
                        </button>
                    </div>
                ` : ''}

                <!-- Vacuum Robot -->
                ${room.hasVacuum ? `
                    <div class="device-item" style="flex-direction: column; align-items: stretch; gap: 8px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div class="device-info">
                                <span class="device-icon" style="color: ${isVacuumRunning ? '#6366f1' : 'var(--text-muted)'};">🧹</span>
                                <div>
                                    <div class="device-name">Пылесос</div>
                                    <div style="font-size: 0.76rem; color: var(--text-muted);">${isVacuumRunning ? `Уборка: ${vacuumProgress}%` : 'На базе'}</div>
                                </div>
                            </div>
                            <button type="button" class="btn ${isVacuumRunning ? 'btn-secondary' : 'btn-primary'}" style="font-size: 0.78rem; padding: 5px 12px;" onclick="toggleVacuum('${room.id}')">
                                ${isVacuumRunning ? 'Стоп' : 'Уборка'}
                            </button>
                        </div>
                        ${isVacuumRunning ? `
                            <div class="progress-container">
                                <div class="progress-fill" style="width: ${vacuumProgress}%;"></div>
                            </div>
                        ` : ''}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

function updateStatsRibbon() {
    const lights = Object.values(window.DEVICE_STATE.lights);
    const activeLights = lights.filter(Boolean).length;
    document.getElementById('statLights').textContent = `${activeLights} / ${lights.length}`;

    const temps = Object.values(window.DEVICE_STATE.thermometers).map(t => t.temperature);
    const avgTemp = (temps.reduce((a, b) => a + b, 0) / temps.length).toFixed(1);
    document.getElementById('statTemp').textContent = `${avgTemp}°C`;

    const openCurtains = Object.values(window.DEVICE_STATE.curtains).filter(s => s === 'open').length;
    document.getElementById('statCurtains').textContent = openCurtains > 0 ? `${openCurtains} откр.` : 'Закрыты';

    const runningVacuums = Object.values(window.DEVICE_STATE.vacuums).filter(s => s === 'running').length;
    document.getElementById('statVacuum').textContent = runningVacuums > 0 ? 'Идет уборка' : 'На базе';
}

// ===================================================================
// Interactive Control Actions
// ===================================================================

async function toggleLight(room, turnOn) {
    const cmd = turnOn ? `включи свет в ${room}` : `выключи свет в ${room}`;
    await sendCommandText(cmd);
}

async function toggleCurtains(room) {
    const current = window.DEVICE_STATE.curtains[room] || 'closed';
    const cmd = current === 'open' ? `закрой шторы в ${room}` : `открой шторы в ${room}`;
    await sendCommandText(cmd);
}

async function toggleVacuum(room) {
    const current = window.DEVICE_STATE.vacuums[room] || 'stopped';
    const cmd = current === 'running' ? `останови пылесос в ${room}` : `запусти пылесос в ${room}`;
    await sendCommandText(cmd);
}

function quickCommand(text) {
    const input = document.getElementById('commandInput');
    if (input) input.value = text;
    sendCommand();
}

// ===================================================================
// Text Command Execution
// ===================================================================

function setupCommandInput() {
    const input = document.getElementById('commandInput');
    if (input) {
        input.addEventListener('keyup', (e) => {
            if (e.key === 'Enter') sendCommand();
        });
    }
}

async function sendCommand() {
    const input = document.getElementById('commandInput');
    if (!input) return;
    const text = input.value.trim();
    if (!text) {
        showToast('Пожалуйста, введите команду', 'info');
        return;
    }

    input.value = '';
    await sendCommandText(text);
}

async function sendCommandText(text) {
    const respBox = document.getElementById('commandResponse');
    if (respBox) {
        respBox.innerHTML = `<span>⏳ Выполняю: <strong>${text}</strong>...</span>`;
    }

    const startTime = performance.now();

    try {
        // Try /api/command first (MVC backend), fallback to /api/text_command
        let res = await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });

        if (!res.ok && res.status === 404) {
            res = await fetch('/api/text_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });
        }

        const data = await res.json();
        const duration = Math.round(performance.now() - startTime);

        if (res.ok) {
            const answer = data.result || data.message || 'Команда выполнена успешно';
            if (respBox) {
                respBox.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                        <span>${answer}</span>
                        <span class="brand-badge" style="background: var(--success-light); color: var(--success);">⚡ ${duration}ms</span>
                    </div>
                `;
            }
            speak(answer);
            showToast(answer, 'success');
            loadStatus();
        } else {
            const err = data.error || 'Ошибка выполнения команды';
            if (respBox) respBox.innerHTML = `<span style="color: var(--danger);">${err}</span>`;
            showToast(err, 'error');
        }
    } catch (err) {
        const duration = Math.round(performance.now() - startTime);
        if (respBox) respBox.innerHTML = `<span style="color: var(--danger);">Ошибка соединения с сервером</span>`;
        showToast('Сервер недоступен', 'error');
    }
}

// ===================================================================
// Voice Control Studio (Whisper + Web Speech API)
// ===================================================================

function setupVoiceRecognition() {
    const micBtn = document.getElementById('micBtn');
    if (!micBtn) return;

    // Check for Browser Native Web Speech API
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        speechRecognition = new SpeechRecognition();
        speechRecognition.lang = 'ru-RU';
        speechRecognition.continuous = false;
        speechRecognition.interimResults = true;

        speechRecognition.onstart = () => {
            isRecording = true;
            micBtn.classList.add('recording');
            document.getElementById('micHint').textContent = 'Слушаю вас... Говорите команду';
        };

        speechRecognition.onresult = (event) => {
            let transcript = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                transcript += event.results[i][0].transcript;
            }
            document.getElementById('voiceTranscript').innerHTML = `
                <span>🗣️ <strong>${transcript}</strong></span>
            `;
            if (event.results[0].isFinal) {
                sendCommandText(transcript);
            }
        };

        speechRecognition.onerror = (event) => {
            console.warn('Web Speech error:', event.error);
            stopVoiceRecording();
        };

        speechRecognition.onend = () => {
            stopVoiceRecording();
        };

        micBtn.addEventListener('click', () => {
            if (isRecording) {
                speechRecognition.stop();
            } else {
                try {
                    speechRecognition.start();
                } catch (e) {
                    fallbackToMediaRecorder();
                }
            }
        });
    } else {
        // Fallback to MediaRecorder audio upload to /api/speech
        setupMediaRecorder(micBtn);
    }
}

function stopVoiceRecording() {
    isRecording = false;
    const micBtn = document.getElementById('micBtn');
    if (micBtn) micBtn.classList.remove('recording');
    document.getElementById('micHint').textContent = 'Нажмите на микрофон для записи команды';
}

function setupMediaRecorder(micBtn) {
    micBtn.addEventListener('mousedown', startAudioRecording);
    micBtn.addEventListener('mouseup', stopAudioRecording);
    micBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startAudioRecording(); });
    micBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopAudioRecording(); });
}

async function startAudioRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
        mediaRecorder.onstop = uploadRecordedAudio;

        mediaRecorder.start();
        isRecording = true;
        document.getElementById('micBtn').classList.add('recording');
        document.getElementById('micHint').textContent = 'Запись идет... Отпустите для отправки';
    } catch (err) {
        showToast('Микрофон недоступен: ' + err.message, 'error');
    }
}

function stopAudioRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        stopVoiceRecording();
    }
}

async function uploadRecordedAudio() {
    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
    const formData = new FormData();
    formData.append('audio', audioBlob, 'command.wav');

    document.getElementById('voiceTranscript').innerHTML = '<span>⏳ Распознавание речи через Whisper...</span>';

    try {
        const res = await fetch('/api/speech', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.text) {
            document.getElementById('voiceTranscript').innerHTML = `<span>🗣️ <strong>${data.text}</strong></span>`;
            sendCommandText(data.text);
        } else {
            showToast('Не удалось распознать речь', 'error');
        }
    } catch (err) {
        showToast('Ошибка при загрузке аудио на сервер', 'error');
    }
}

// ===================================================================
// Server-Sent Events (SSE) Live Feed
// ===================================================================

function initSSE() {
    try {
        const evtSource = new EventSource('/api/events');
        const sseText = document.getElementById('sseText');
        const sseDot = document.getElementById('sseDot');

        evtSource.onopen = () => {
            if (sseText) sseText.textContent = 'Онлайн (SSE)';
            if (sseDot) sseDot.style.background = 'var(--success)';
        };

        evtSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.lights) Object.assign(window.DEVICE_STATE.lights, data.lights);
                if (data.thermometers) Object.assign(window.DEVICE_STATE.thermometers, data.thermometers);
                if (data.curtains) Object.assign(window.DEVICE_STATE.curtains, data.curtains);
                if (data.vacuums) Object.assign(window.DEVICE_STATE.vacuums, data.vacuums);
                if (data.vacuum_progress) Object.assign(window.DEVICE_STATE.vacuum_progress, data.vacuum_progress);
                renderDashboard();
            } catch (err) {}
        };

        evtSource.onerror = () => {
            if (sseText) sseText.textContent = 'Автономно';
            if (sseDot) sseDot.style.background = 'var(--warning)';
        };
    } catch (e) {
        // SSE not supported, fall back to polling
        setInterval(loadStatus, 4000);
    }
}

// ===================================================================
// Modals
// ===================================================================

function openHAModal() {
    document.getElementById('haModal')?.classList.remove('hidden');
}

function closeHAModal() {
    document.getElementById('haModal')?.classList.add('hidden');
}
