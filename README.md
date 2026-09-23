# MQTT Chat System

A Django-based realtime chat project built around MQTT messaging and MySQL persistence. The system is designed to support private chat, group chat, message delivery tracking, typing indicators, and presence updates with a broker-based architecture.

## Project Overview

This project follows a modern messaging architecture where:

- MQTT is used for realtime transport and event delivery.
- Django handles business logic and API flow.
- MySQL stores the source of truth for users, conversations, messages, and delivery receipts.

Core design principle:

- MQTT handles realtime communication.
- MySQL handles durable storage.
- Django handles validation, orchestration, and business rules.

## Features

- Private chat
- Group chat
- Realtime message delivery
- Message persistence in MySQL
- Message ordering
- Duplicate protection
- Offline synchronization
- Sent / Delivered / Read status
- Typing indicator
- Online / Offline presence
- MQTT Last Will support
- Django admin for testing and maintenance

## Technology Stack

- Python 3
- Django 6.1.1
- MySQL 8.4
- mysqlclient
- Paho MQTT
- Mosquitto broker
- JSON message format

## Project Structure

```text
mqtt_chat/
├── manage.py
├── requirements.txt
├── .venv/
├── db.sqlite3
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── chat/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tests.py
│   ├── views.py
│   └── migrations/
└── README.md
```

## Local Development Setup

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

The project dependencies include:

```text
asgiref==3.12.1
Django==6.1.1
mysqlclient==2.3.0
paho-mqtt==2.1.0
sqlparse==0.6.0
tzdata==2026.4
```

### 3. Configure MySQL

This project is configured for MySQL on port `3307` instead of the default MariaDB/XAMPP port `3306`.

Create the database:

```sql
CREATE DATABASE mqtt_chat
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

```

Then verify the Django database settings in `config/settings.py`:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "mqtt_chat",
        "USER": "root",
        "PASSWORD": "123456",
        "HOST": "127.0.0.1",
        "PORT": "3307",
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}
```

For production or team projects, avoid hardcoding secrets directly in source code. Prefer environment variables or a `.env` file.

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Run the Django development server

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## MQTT Broker Setup

A Mosquitto broker should be running for the realtime message layer.

Example broker connection:

- Host: `127.0.0.1`
- Port: `1883`

The system design expects a broker topic model similar to:

```text
chat/client/{user_id}/command/send
chat/client/{user_id}/command/sync
chat/client/{user_id}/command/delivered
```

## Recommended Next Steps

The project is currently in the scaffolding / planning stage. The next implementation milestones normally include:

1. Define user and conversation models in `chat/models.py`
2. Add repository and service layers for chat logic
3. Implement MQTT worker commands
4. Add message persistence and sync logic
5. Build client communication for sending and receiving realtime messages
6. Add tests for message ordering, deduplication, and receipts

## Notes

- The current database configuration uses MySQL on port `3307` because `3306` is occupied by the local MariaDB/XAMPP installation.
- This project is intended for learning and prototype development, with a clear separation between MQTT transport and persistent database storage.
- The app is designed to grow from a CLI/client-first architecture into a richer web or desktop chat experience.

## License

This project is for academic / development use unless a specific project license is added later.
