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
- User avatar uploads
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
│   ├── repositories/
│   │   ├── user_repository.py
│   │   ├── invitation_repository.py
│   │   ├── friendship_repository.py
│   │   ├── conversation_repository.py
│   │   └── message_repository.py
│   ├── services/
│   │   ├── chat_service.py
│   │   ├── user_service.py
│   │   ├── conversation_service.py
│   │   ├── message_service.py
│   │   └── errors.py
│   ├── mqtt_messages.py
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

## User Avatars

Upload an avatar using `POST /api/users/{user_id}/avatar/` with a multipart
form field named `avatar`. JPEG, PNG, GIF, BMP, and WebP files up to 5 MB are
accepted. Use `DELETE` on the same endpoint to remove the avatar. User API
responses include `avatar_url`, which is `null` when no avatar is set. In
development, uploaded files are served from `/media/`; configure media storage
and serving separately for production.

## User Profiles and Conversations

Create users with `username` and optional `status` (`online` or `offline`),
`short_bio` (up to 160 characters), `bio`, and `sex` (`female` or `male`).
New users default to `offline`; `PATCH /api/users/{user_id}/` accepts any
subset of these fields.

Create or reuse a private conversation with
`POST /api/conversations/` and JSON `{"user_id":"...","type":"PRIVATE","username":"peer"}`.
Create a group with `{"user_id":"...","type":"GROUP","name":"Team","usernames":["peer1","peer2"]}`;
the creator is added as a member automatically. Usernames must exist, and a
private conversation is reused only when its exact two members match.

Load messages with
`GET /api/conversations/{conversation_id}/messages/?user_id={user_id}`.
Only conversation members can read history. `limit` defaults to 50 and is
capped at 100; `before_seq` returns messages preceding that sequence number.

## MQTT Broker Setup

A Mosquitto broker should be running for the realtime message layer.

Example broker connection:

- Host: `127.0.0.1`
- Port: `1883`

Start the Django presence subscriber with:

```bash
python manage.py run_mqtt_presence
```

It reads `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, and `MQTT_PASSWORD` from
the environment (host and port default to `127.0.0.1:1883`) and subscribes to
`chat/users/+/status`. MQTT clients publish the literal payload `online` or
`offline` to `chat/users/{user_id}/status` at QoS 1. Set a retained `offline`
Last Will on that topic before connecting, and publish retained `online` after
connecting, so unexpected disconnects also update the database.

The system design expects a broker topic model similar to:

```text
chat/client/{user_id}/command/send
chat/client/{user_id}/command/sync
chat/client/{user_id}/command/delivered
```

Run the message worker in a separate terminal from Django's web server:

```bash
python manage.py run_mqtt_worker
```

It subscribes to `chat/client/+/command/send`. Publish a JSON object to
`chat/client/{user_id}/command/send`, where `{user_id}` is the sender UUID:

```json
{
  "conversation_id": "conversation-uuid",
  "client_message_id": "client-generated-uuid",
  "content": "Hello",
  "reply_to_message_id": null
}
```

Do not include `seq`: the worker allocates it while locking the conversation
row inside a database transaction. This serializes sends in one conversation
without blocking sends to other conversations. The database also enforces
unique `(conversation, seq)` and `(sender, client_message_id)` constraints.
Retries with the same client ID and unchanged message content return the
original sequence as a duplicate acknowledgment; reusing that ID for different
message data returns an error.

The sender receives `MESSAGE_ACCEPTED` on
`chat/client/{user_id}/event/message_accepted`, or `ERROR` on
`chat/client/{user_id}/event/error`. New messages are broadcast after database
commit on `chat/conversations/{conversation_id}/event/message_created`.
Configure Mosquitto authentication and ACLs so a client can publish commands
only under its own user ID and subscribe only to authorized event topics.

## Recommended Next Steps

Remaining messaging milestones include:

1. Add delivery/read receipt and offline synchronization APIs.
2. Build client communication for sending and receiving realtime messages.

## Notes

- The current database configuration uses MySQL on port `3307` because `3306` is occupied by the local MariaDB/XAMPP installation.
- This project is intended for learning and prototype development, with a clear separation between MQTT transport and persistent database storage.
- The app is designed to grow from a CLI/client-first architecture into a richer web or desktop chat experience.

## License

This project is for academic / development use unless a specific project license is added later.
