# Hệ thống trò chuyện MQTT

Dự án trò chuyện thời gian thực trên Django, sử dụng MQTT để truyền tin và MySQL để lưu trữ dữ liệu. Hệ thống hỗ trợ trò chuyện cá nhân, trò chuyện nhóm, theo dõi trạng thái gửi tin, chỉ báo đang nhập và trạng thái trực tuyến thông qua kiến trúc broker.

## Tổng quan dự án

Dự án sử dụng kiến trúc nhắn tin hiện đại:

- MQTT đảm nhiệm truyền dữ liệu thời gian thực và phân phối sự kiện.
- Django xử lý nghiệp vụ và luồng API.
- MySQL lưu dữ liệu chính thức về người dùng, cuộc trò chuyện, tin nhắn và xác nhận gửi/nhận.

Nguyên tắc thiết kế:

- MQTT xử lý giao tiếp thời gian thực.
- MySQL xử lý việc lưu trữ bền vững.
- Django xử lý kiểm tra dữ liệu, điều phối và các quy tắc nghiệp vụ.

## Tính năng

- Trò chuyện cá nhân
- Trò chuyện nhóm
- Tải ảnh đại diện người dùng
- Gửi và nhận tin nhắn thời gian thực
- Lưu tin nhắn trong MySQL
- Sắp xếp thứ tự tin nhắn
- Chống tin nhắn trùng lặp
- Đồng bộ khi ngoại tuyến
- Trạng thái Đã gửi / Đã nhận / Đã đọc
- Chỉ báo đang nhập
- Trạng thái Trực tuyến / Ngoại tuyến
- Hỗ trợ MQTT Last Will
- Django Admin để kiểm thử và quản trị

## Công nghệ sử dụng

- Python 3
- Django 6.1.1
- MySQL 8.4
- mysqlclient
- Paho MQTT
- Mosquitto broker
- Định dạng tin nhắn JSON
- React + Vite + MQTT.js (frontend)

## Cấu trúc dự án

```text
mqtt_chat/
├── manage.py
├── requirements.txt
├── frontend/                # Giao diện React, HTTP/MQTT client và kiểm thử FE
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

## Cài đặt môi trường phát triển

### 1. Tạo và kích hoạt môi trường ảo

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. Cài đặt các thư viện phụ thuộc

```bash
pip install -r requirements.txt
```

Dự án sử dụng các thư viện:

```text
asgiref==3.12.1
Django==6.1.1
mysqlclient==2.3.0
paho-mqtt==2.1.0
sqlparse==0.6.0
tzdata==2026.4
```

### 3. Cấu hình MySQL

Dự án được cấu hình sử dụng MySQL ở cổng `3307` thay vì cổng mặc định `3306` của MariaDB/XAMPP.

Tạo cơ sở dữ liệu:

```sql
CREATE DATABASE mqtt_chat
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Kiểm tra lại cấu hình cơ sở dữ liệu Django trong `config/settings.py`:

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

Với môi trường production hoặc dự án làm việc nhóm, không nên ghi cứng thông tin bí mật trong mã nguồn. Hãy ưu tiên biến môi trường hoặc file `.env`.

### 4. Chạy migration

```bash
python manage.py migrate
```

### 5. Khởi động máy chủ phát triển Django

```bash
python manage.py runserver
```

Mở:

```text
http://127.0.0.1:8000/
```

## Ảnh đại diện người dùng

Tải ảnh đại diện bằng `POST /api/users/{user_id}/avatar/` với trường multipart
tên `avatar`. Hệ thống chấp nhận ảnh JPEG, PNG, GIF, BMP và WebP có dung lượng
tối đa 5 MB. Dùng `DELETE` trên cùng endpoint để xóa ảnh. Phản hồi API người
dùng có trường `avatar_url`, nhận giá trị `null` nếu chưa có ảnh. Trong môi
trường phát triển, file tải lên được phục vụ từ `/media/`; môi trường production
cần cấu hình riêng việc lưu trữ và phục vụ media.

## Hồ sơ người dùng và cuộc trò chuyện

Tạo người dùng với `username` và các trường tùy chọn `status` (`online` hoặc
`offline`), `short_bio` (tối đa 160 ký tự), `bio` và `sex` (`female` hoặc
`male`). Người dùng mới mặc định có trạng thái `offline`;
`PATCH /api/users/{user_id}/` chấp nhận một phần hoặc toàn bộ các trường trên.

Tạo mới hoặc sử dụng lại cuộc trò chuyện cá nhân bằng
`POST /api/conversations/` and JSON `{"user_id":"...","type":"PRIVATE","username":"peer"}`.
Tạo nhóm bằng `{"user_id":"...","type":"GROUP","name":"Team","usernames":["peer1","peer2"]}`;
người tạo sẽ tự động được thêm vào nhóm. Username phải tồn tại. Cuộc trò chuyện
cá nhân chỉ được sử dụng lại khi có đúng hai thành viên trùng khớp.

Lấy danh sách bạn bè bằng `GET /api/users/{user_id}/friends/?limit=25`. Dùng
`cursor` trong phản hồi `next_cursor` để tải trang tiếp theo theo keyset; `q` tìm
theo username/giới thiệu ngắn và `online=true` chỉ trả về bạn đang trực tuyến.
`total` và `online_total` là số lượng bạn khớp với từ khóa tìm kiếm.
Lấy lời mời kết bạn đang chờ bằng `GET /api/users/{user_id}/invitations/`;
phản hồi có danh sách `incoming`/`sent` cho lời mời kết bạn và
`room_incoming`/`room_sent` cho lời mời nhóm; mỗi mục có hồ sơ sender/recipient,
trạng thái và thời gian gửi.
Chấp nhận hoặc từ chối lời mời đến bằng
`POST /api/invitations/{invitation_id}/respond/` với `user_id` và `status`
(`ACCEPT` hoặc `REJECT`).
Tạo lời mời vào nhóm bằng `POST /api/room-invitations/` với
`sender_id`, `user_id` (người nhận) và `conversation_id`; sender phải là thành
viên của nhóm và recipient chưa là thành viên. Người nhận chấp nhận/từ chối bằng
`POST /api/room-invitations/{invitation_id}/respond/`; chấp nhận sẽ thêm thành
viên vào nhóm.

Lấy danh sách cuộc trò chuyện của người dùng bằng
`GET /api/users/{user_id}/conversations/`. Phản hồi gồm `conversations`, sắp xếp
theo thời gian tin nhắn mới nhất giảm dần. Mỗi mục có `conversation_id`, `name`,
`type`, `created_at`, danh sách `members` chứa hồ sơ người dùng và `last_message`
(hoặc `null` nếu chưa có tin nhắn). `last_message` gồm `message_id`, `content`,
`seq`, `created_at` và hồ sơ `sender`.

Tải tin nhắn bằng
`GET /api/conversations/{conversation_id}/messages/?user_id={user_id}`.
Chỉ thành viên cuộc trò chuyện mới có thể đọc lịch sử. `limit` mặc định là 50 và
giới hạn tối đa 100; `before_seq` trả về các tin nhắn trước số thứ tự đó.

Tìm tin nhắn theo nội dung trong một cuộc trò chuyện bằng
`GET /api/conversations/{conversation_id}/messages/search/?user_id={user_id}&q={keyword}`.
Tìm kiếm không phân biệt chữ hoa/chữ thường, chỉ áp dụng trong cuộc trò chuyện
được chỉ định và chỉ thành viên mới có quyền truy cập. `q` là bắt buộc;
`limit` mặc định là 50, tối đa 100, và `before_seq` phân trang về các kết quả
có số thứ tự nhỏ hơn giá trị đã cho. Phản hồi gồm `conversation_id`, `query`
và danh sách `messages` theo thứ tự thời gian.

## Cấu hình MQTT Broker

Cần khởi động Mosquitto broker để phục vụ tầng tin nhắn thời gian thực.

Thông tin kết nối broker mẫu:

- Host: `127.0.0.1`
- Port: `1883`

Khởi động tiến trình Django theo dõi trạng thái người dùng:

```bash
python manage.py run_mqtt_presence
```

Tiến trình đọc `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME` và `MQTT_PASSWORD` từ
biến môi trường (mặc định host và port là `127.0.0.1:1883`) rồi subscribe vào
`chat/users/+/status`. MQTT client publish payload `online` hoặc `offline` tới
`chat/users/{user_id}/status` với QoS 1. Hãy đặt Last Will `offline` dạng retained
trên topic trước khi kết nối và publish `online` dạng retained sau khi kết nối để
việc ngắt kết nối bất ngờ cũng được cập nhật vào cơ sở dữ liệu.

Thiết kế hệ thống sử dụng mô hình topic tương tự:

```text
chat/client/{user_id}/command/send
chat/client/{user_id}/command/read
```

Chạy message worker trong terminal riêng, tách khỏi web server Django:

```bash
python manage.py run_mqtt_worker
```

Worker subscribe vào `chat/client/+/command/send` và
`chat/client/+/command/read`. Publish một object JSON tới
`chat/client/{user_id}/command/send`, trong đó `{user_id}` là UUID của người gửi:

```json
{
  "conversation_id": "conversation-uuid",
  "client_message_id": "client-generated-uuid",
  "content": "Hello",
  "reply_to_message_id": null
}
```

Không gửi trường `seq`: worker sẽ tự cấp số thứ tự trong lúc khóa dòng cuộc trò
chuyện bên trong một transaction cơ sở dữ liệu. Cách này tuần tự hóa việc gửi
trong cùng một cuộc trò chuyện nhưng không chặn các cuộc trò chuyện khác. Cơ sở
dữ liệu cũng áp dụng ràng buộc duy nhất cho `(conversation, seq)` và
`(sender, client_message_id)`. Khi retry với cùng client ID và nội dung không
đổi, hệ thống trả về số thứ tự ban đầu dưới dạng xác nhận trùng lặp; nếu dùng
lại ID đó cho dữ liệu tin nhắn khác, hệ thống trả về lỗi.

Người gửi nhận sự kiện `MESSAGE_ACCEPTED` tại
`chat/client/{user_id}/event/message_accepted`, hoặc `ERROR` tại
`chat/client/{user_id}/event/error`. Tin nhắn mới được broadcast sau khi commit
cơ sở dữ liệu tại `chat/conversations/{conversation_id}/event/message_created`.
Cấu hình xác thực và ACL của Mosquitto để client chỉ được publish command dưới
user ID của chính mình và chỉ subscribe các event topic được cấp quyền.

Frontend gửi `command/read` theo batch cho các tin nhắn của thành viên khác thực
sự đi vào vùng nhìn thấy trong cửa sổ chat (tối đa 100 ID mỗi batch):

```json
{
  "conversation_id": "conversation-uuid",
  "message_ids": ["message-uuid"]
}
```

Worker kiểm tra tư cách thành viên, lưu `READ` receipt có tính lặp an toàn, rồi
broadcast `MESSAGE_READ` tại
`chat/conversations/{conversation_id}/event/message_read`. Lịch sử trả thêm
`read_by`; danh sách hội thoại trả `unread_count` để khôi phục trạng thái chưa
đọc sau khi tải lại.

## Tiến độ frontend và ghi chú bàn giao

Lịch sử cập nhật, bảng tính năng, kết quả kiểm thử theo từng mốc và các việc còn cần phối hợp được chuyển sang [HANDOFF.md](HANDOFF.md).

Frontend hiện triển khai bằng React + Vite trong `frontend/`; hướng dẫn cài đặt và chạy ở phần dưới và [frontend/README.md](frontend/README.md).

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

## Ghi chú

- Cấu hình cơ sở dữ liệu hiện dùng MySQL ở cổng `3307` vì cổng `3306` đang được MariaDB/XAMPP cục bộ sử dụng.
- Dự án phục vụ mục đích học tập và phát triển prototype, với sự phân tách rõ ràng giữa truyền tải MQTT và lưu trữ dữ liệu bền vững.
- Ứng dụng được thiết kế để phát triển từ kiến trúc ưu tiên CLI/client thành trải nghiệm web hoặc desktop đầy đủ hơn.

## Giấy phép

Dự án phục vụ mục đích học tập và phát triển, trừ khi có giấy phép riêng được bổ sung sau này.
