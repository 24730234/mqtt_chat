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
- React + Vite + MQTT.js (frontend)

## Project Structure

```text
mqtt_chat/
├── manage.py
├── requirements.txt
├── frontend/                # React UI, HTTP/MQTT client and FE tests
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

## Frontend — tiến độ ngày 29/09/2026

FE được triển khai trong `frontend/` bằng **React + Vite + MQTT.js**, đối chiếu README,
`chat/views.py`, `config/urls.py` và `chat/mqtt_messages.py` tại BE commit `7dc68e8`.

**Trạng thái:** đã có giao diện và adapter cho API/MQTT hiện có; đã build và kiểm thử
FE riêng. **Ngày 01/10 đã kiểm tra với Django + MySQL + Mosquitto local và cả hai worker thật**;
môi trường triển khai/ACL của nhóm vẫn cần nghiệm thu riêng.
Không coi chức năng trong danh sách Features phía trên là đã hoàn thành toàn bộ.

### Đã làm được

| Hạng mục | Tiến độ FE | Ghi chú tích hợp |
| --- | --- | --- |
| Giao diện chat | Hoàn thành bản đầu | Tiếng Việt, responsive, tìm hội thoại/tin đã tải, draft riêng từng hội thoại |
| Demo riêng | Hoàn thành | Dữ liệu mẫu và phản hồi mẫu chỉ chạy trong chế độ demo |
| Chọn/tạo người dùng | Đã nối API | Search username / POST user; đây **không phải đăng nhập** |
| Hồ sơ | Đã nối API | PATCH username, short_bio (160 ký tự), bio, sex |
| Avatar | Đã nối API | POST multipart `avatar`, DELETE avatar, hiển thị `avatar_url`, giới hạn 5 MB và định dạng ảnh |
| Chat cá nhân/nhóm | Đã nối API | Dùng đúng `user_id`, `type`, `username` / `usernames`; hiển thị member từ response |
| Danh sách hội thoại | Tạm thời lưu cục bộ | Phân tách theo API base + user UUID; BE chưa có GET danh sách hội thoại |
| Mở nhóm đã có | Đã làm phương án tạm | Nhập conversation UUID; kiểm tra quyền qua API history, không tự thêm thành viên |
| Lịch sử | Đã nối API | 50 tin/lần, nút tải trước `before_seq`, xử lý 403/404/lỗi mạng |
| Gửi và nhận realtime | Đã nối MQTT WebSocket | QoS 1, publish command/send, subscribe message_accepted/error/message_created |
| Reply | Đã nối hợp đồng BE | Gửi `reply_to_message_id`, hiển thị trích dẫn nếu tin gốc đã tải |
| Xác nhận và chống trùng | Đã làm | Chờ ACK nghiệp vụ từ BE; ghép optimistic/ACK/broadcast/history, sắp theo server `seq` |
| Timeout / retry | Đã làm | Giữ nguyên client UUID và nội dung khi gửi lại; không gửi `seq` lên worker |
| Presence | Đã nối giao thức | Retained online, Last Will offline, subscribe status của thành viên đã biết |
| Reconnect | Đã làm mức cơ bản | Tự kết nối lại, subscribe lại, tải 50 tin mới nhất cho hội thoại đã biết |
| Bạn bè/lời mời | Đã nối các API sẵn có | Xem/xóa bạn, gửi lời mời; nhận lời/từ chối qua invitation UUID vì BE chưa có inbox |
| Đã nhận / đã đọc / typing | Chưa tích hợp thật | Chờ API/topic chính thức; live chỉ ghi “Đã lưu trên máy chủ” sau xác nhận BE |
| Đồng bộ offline đầy đủ | Chưa hoàn thành | Không có offline outbox; sau reconnect cần tải thêm lịch sử nếu thiếu hơn 50 tin |

### Cập nhật sửa lỗi ngày 30/09/2026

- Sửa luồng chọn môi trường test: thêm nút **Dùng server test** trên localhost để điền API `18000` và MQTT WebSocket `19001`. Lỗi không phải JSON trước đó do `/api` proxy tới Django `8000` chưa chạy.
- Nhớ API base / MQTT URL trong sessionStorage của tab sau reload; không lưu broker username/password.
- Hiển thị nhãn **Server test · Dữ liệu mẫu** khi dùng fixture, tránh nhầm với backend của nhóm.
- Khi history trả 403/404: hiện lý do, ngừng subscribe MQTT hội thoại, bỏ tin đã tải khỏi màn hình và chặn gửi/retry.
- Thêm ẩn lối tắt hội thoại cũ trên máy kèm **Hoàn tác**; thao tác này không xóa dữ liệu server.
- Đã kiểm tra trên giao diện: cấu hình qua reload, vào user fixture, ẩn/hoàn tác hội thoại không tồn tại và gửi tin nhận xác nhận từ server test.
- Bộ kiểm thử tăng lên **18 tests**, bao gồm unsubscribe khi mất quyền và bỏ qua broadcast đến muộn; build production đã qua.

### Rà soát và bàn giao ngày 30/09/2026

- Đối chiếu lại FE với BE mới nhất đã fetch: `7dc68e8`; thay đổi bàn giao gồm `frontend/` và báo cáo này.
- Sửa trạng thái MQTT khi bỏ hội thoại bị broker từ chối; subscribe lại các topic còn dùng và chỉ cho gửi sau khi broker xác nhận.
- Bỏ qua callback subscribe cũ sau ngắt kết nối; ACK sai conversation không hủy timeout của tin đang chờ.
- Giữ nguyên HTTP status khi server trả JSON `null` cho lỗi, để giao diện vẫn xử lý được 403/404.
- Kiểm tra lại: **18/18 tests qua**, `npm run build` thành công; tìm `thien_fixture`, mở hội thoại mẫu và gửi tin nhận ACK trên trình duyệt.
- Chưa nghiệm thu với backend thật của nhóm. Các mục còn chờ BE được liệt kê ở checklist integrate bên dưới.

### Tích hợp backend thật ngày 01/10/2026

- Đã chạy `run_mqtt_worker` và `run_mqtt_presence` trong hai container riêng cùng Django, MySQL 8.4 và Mosquitto 2; log xác nhận subscribe đúng topic.
- Đã qua **8 nhóm kiểm tra tích hợp thật**: user/nhóm, presence online/offline lưu DB, ACK và broadcast, retry chống trùng, history 50 + 5 tin/reply, quyền history 403, hồ sơ và upload/GET/xóa avatar.
- Đã gửi tin trực tiếp từ FE qua broker thật và nhận xác nhận lưu MySQL; **18/18 unit tests FE + build** vẫn qua.
- FE: `http://127.0.0.1:5173/?mode=live`, API base `/api`, MQTT `ws://127.0.0.1:9001`. User sau chạy smoke: `quang_live`, `thien_live`.
- Cấu hình và hướng dẫn khởi động cả stack: [integration/README.md](integration/README.md). Không cần fixture cho luồng này.
- Broker local chỉ mở cổng trên loopback, dùng anonymous cho phát triển. Chưa kiểm chứng ACL production, Last Will khi client chết đột ngột hoặc full offline sync.

### Cách chạy FE

Yêu cầu Node.js phù hợp với Vite (khuyến nghị Node 22+).

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

- Mở `http://127.0.0.1:5173/` để xem demo.
- Nhấn **KẾT NỐI BE** hoặc mở `http://127.0.0.1:5173/?mode=live` để dùng adapter thật.
- `BACKEND_URL` mặc định `http://127.0.0.1:8000`; Vite proxy `/api` và `/media` về Django.
- `VITE_API_BASE=/api`; có thể chỉnh API base trên màn hình cấu hình.
- `VITE_MQTT_URL=ws://127.0.0.1:9001` là **giá trị cấu hình mẫu**, không phải listener đã có trong repo.
  Phía BE cần bật listener WebSocket, cấp broker credentials và ACL phù hợp.
  Web dùng `ws://` / `wss://`, không kết nối trực tiếp MQTT TCP `1883`.
- Chạy Django web, `run_mqtt_worker` và `run_mqtt_presence` như hướng dẫn phía trên.
- Credentials MQTT chỉ giữ trong bộ nhớ phiên; không lưu password vào localStorage.
- Chỉ catalog hội thoại được lưu cục bộ; bản nháp và tin đang chờ xác nhận sẽ mất khi tải lại/đổi người dùng.
- Khi triển khai bản build, cấu hình reverse proxy `/api`, `/media` hoặc API base + CORS phù hợp;
  Vite dev proxy không đi kèm file static production. Trang HTTPS cần broker `wss://`.

### Kết quả kiểm thử FE

```bash
cd frontend
npm test
npm run build
```

- **18 kiểm thử tự động đã qua:** HTTP contract/pagination, multipart avatar và validation,
  lỗi API, ACK/broadcast/history đến khác thứ tự, chống trùng, server seq, retry giữ UUID,
  timeout, presence/Last Will, reconnect/resubscribe và broker từ chối subscribe.
- Build production đã qua. MQTT bundle được lazy-load khi chuyển sang live mode.
- Đã kiểm tra trên trình duyệt với **HTTP + MQTT WebSocket fixture cô lập**:
  chọn người dùng, sửa hồ sơ, tạo nhóm, tải lịch sử 50 → 55 tin, reply,
  gửi có ACK, refresh không nhân đôi, hai người dùng gửi/nhận realtime.
- Không có lỗi console trong các luồng kiểm thử trên.
- Fixture là server kiểm thử FE, **không phải** bằng chứng MySQL transaction,
  Mosquitto ACL, avatar storage hoặc Django worker của nhóm đã chạy đúng end-to-end.

### Việc cần phối hợp với BE ở buổi integrate

1. Chốt và cung cấp WebSocket broker URL/credentials/ACL; kiểm tra hai user với Django worker thật.
2. Bổ sung GET danh sách/chi tiết hội thoại và inbox lời mời để bỏ bước nhập UUID thủ công.
3. Bổ sung đăng nhập/xác thực và gắn user identity với quyền API/MQTT. Hiện FE chỉ chọn user của môi trường phát triển.
4. Thống nhất delivery/read receipt, typing và full offline sync; chưa publish các command chỉ mới nêu ý tưởng trong README.
5. Kiểm tra avatar upload/delete và phục vụ `/media` trên môi trường thật; kiểm tra history 403, retry khi ACK mất và Last Will.
6. Chốt semantics presence khi cùng user mở nhiều tab: topic status hiện là một topic/user nên một tab ngắt có thể đánh dấu offline cho cả user.

Chi tiết cấu trúc FE, cấu hình và fixture: [frontend/README.md](frontend/README.md).

## Recommended Next Steps

Remaining messaging milestones include:

1. Add delivery/read receipt and offline synchronization APIs.
2. Validate the implemented frontend HTTP/MQTT client against the team's running backend (see frontend progress above).

## Notes

- The current database configuration uses MySQL on port `3307` because `3306` is occupied by the local MariaDB/XAMPP installation.
- This project is intended for learning and prototype development, with a clear separation between MQTT transport and persistent database storage.
- The app is designed to grow from a CLI/client-first architecture into a richer web or desktop chat experience.

## License

This project is for academic / development use unless a specific project license is added later.
