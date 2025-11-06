# 🏠 Smart Home Web Service

Веб-сервис для управления умным домом с поддержкой голосовых команд и модульной архитектурой MVC.

## ✨ Особенности

- 🎤 **Голосовое управление** - распознавание команд на русском языке с помощью Whisper
- 💡 **Управление освещением** - включение/выключение света в разных комнатах
- 🌡️ **Контроль климата** - управление температурой и влажностью
- 🪟 **Управление шторами** - открытие/закрытие штор
- 🧹 **Управление пылесосом** - запуск/остановка пылесоса
- 📱 **Адаптивный интерфейс** - работает на всех устройствах
- 🔒 **HTTPS поддержка** - безопасное соединение
- ⚡ **Real-time обновления** - Server-Sent Events для мгновенных обновлений

## 🏗️ Архитектура

Проект построен по принципу **MVC (Model-View-Controller)**:

```
├── app/
│   ├── models/          # Модели данных
│   │   ├── database.py  # Работа с БД
│   │   ├── device.py    # Модель устройств
│   │   └── command.py   # Модель команд
│   ├── views/           # Представления
│   │   └── templates/   # HTML шаблоны
│   ├── controllers/     # Контроллеры
│   │   ├── app_controller.py      # Главный контроллер
│   │   └── device_controller.py   # Контроллер устройств
│   ├── services/        # Сервисы
│   │   ├── speech_service.py           # Распознавание речи
│   │   └── command_parser_service.py   # Парсинг команд
│   └── utils/           # Утилиты
│       └── file_utils.py
├── config/              # Конфигурация
│   └── settings.py
├── static/              # Статические файлы
│   ├── css/
│   ├── js/
│   └── templates/
└── main.py             # Главный файл приложения
```

## 🚀 Установка и запуск

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Генерация SSL сертификатов (для HTTPS)

```bash
python -c "
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime

# Генерируем приватный ключ
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

# Создаем сертификат
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'RU'),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Moscow'),
    x509.NameAttribute(NameOID.LOCALITY_NAME, 'Moscow'),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Smart Home'),
    x509.NameAttribute(NameOID.COMMON_NAME, 'localhost'),
])

cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    private_key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.datetime.utcnow()
).not_valid_after(
    datetime.datetime.utcnow() + datetime.timedelta(days=365)
).add_extension(
    x509.SubjectAlternativeName([
        x509.DNSName('localhost'),
        x509.IPAddress(ipaddress.IPv4Address('127.0.0.1')),
    ]),
    critical=False,
).sign(private_key, hashes.SHA256())

# Сохраняем файлы
with open('cert.pem', 'wb') as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

with open('key.pem', 'wb') as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))

print('SSL сертификаты созданы: cert.pem, key.pem')
"
```

### 3. Запуск приложения

```bash
python main.py
```

Приложение будет доступно по адресу: `https://localhost:5443`

## 🎤 Голосовые команды

### Освещение
- "включи свет в зале"
- "выключи свет в кухне"

### Температура
- "повысь температуру в зале"
- "снизи температуру в кухне"
- "установи температуру 25 в зале"

### Влажность
- "повысь влажность в зале"
- "снизи влажность в кухне"
- "установи влажность 60 в зале"

### Шторы
- "открой шторы в зале"
- "закрой шторы в кухне"

### Пылесос
- "запусти пылесос в зале"
- "останови пылесос в кухне"

## 🔧 API Endpoints

- `GET /` - Главная страница
- `GET /api/devices` - Список устройств
- `POST /api/command` - Текстовая команда
- `POST /api/speech` - Голосовая команда
- `GET /api/speech/status` - Статус распознавания речи
- `POST /api/device/<id>/<action>` - Действие с устройством
- `GET /api/events` - SSE события

## 🛠️ Разработка

### Структура модулей

- **Models** - работа с данными и бизнес-логика
- **Views** - HTML шаблоны и представления
- **Controllers** - обработка запросов и координация
- **Services** - внешние сервисы (распознавание речи, парсинг)
- **Utils** - вспомогательные функции

### Добавление новых устройств

1. Добавьте тип устройства в `DeviceType` enum
2. Создайте методы в `DeviceController`
3. Добавьте команды в `CommandParserService`
4. Обновите frontend для отображения

## 📝 Лицензия

MIT License

## 👨‍💻 Автор

Создано при поддержке **ИИ-COPILOT** 🤖
