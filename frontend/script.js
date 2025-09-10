document.addEventListener('DOMContentLoaded', function() {
    const commandInput = document.getElementById('command-input');
    const sendButton = document.getElementById('send-command');
    const responseP = document.getElementById('response');
    const deviceStatusP = document.getElementById('device-status');

    // Load initial status
    loadStatus();

    sendButton.addEventListener('click', function() {
        const text = commandInput.value.trim();
        if (text) {
            sendCommand(text);
        }
    });

    function sendCommand(text) {
        fetch('http://localhost:5000/command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: text })
        })
        .then(response => response.json())
        .then(data => {
            responseP.textContent = data.response || 'Команда выполнена';
            loadStatus(); // Update status after command
        })
        .catch(error => {
            responseP.textContent = 'Ошибка: ' + error.message;
        });
    }

    function loadStatus() {
        fetch('http://localhost:5000/devices')
        .then(response => response.json())
        .then(data => {
            deviceStatusP.textContent = `Свет: ${data.light}, Отопление: ${data.heating}, Температура: ${data.temperature}°C`;
        })
        .catch(error => {
            deviceStatusP.textContent = 'Ошибка загрузки статуса';
        });
    }
});
