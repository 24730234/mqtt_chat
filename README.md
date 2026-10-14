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

- Trò chuyện cá nhân/nhóm, lưu tin trong MySQL, sắp thứ tự theo sequence và chống trùng khi retry.
- Đăng ký/đăng nhập bằng Django session, CSRF, thời hạn phiên và bảo vệ API HTTP.
- Phân quyền nhóm OWNER/ADMIN/MEMBER, lời mời, rời nhóm, loại thành viên, chuyển owner và archive.
  Khi tạo nhóm, các tài khoản được chọn nhận lời mời; họ trở thành thành viên sau khi chấp nhận.
- Hồ sơ/avatar, bạn bè/lời mời, lịch sử/tìm kiếm tin nhắn và READ receipt.
- Truyền tin realtime, presence retained và MQTT Last Will qua broker hiện tại.
- Django Admin để kiểm thử và quản trị.

Typing indicator đã được nối trực tiếp qua MQTT theo hội thoại; delivered, đồng bộ offline đầy đủ
và xác thực/ACL MQTT chưa được triển khai. Broker anonymous chỉ phù hợp môi trường phát triển tin cậy.
Đăng nhập HTTP **không** xác thực kết nối MQTT.

Trong giao diện live, lời mời nhóm đang chờ được tách khỏi danh sách thành viên; thông tin/quản
lý nhóm mở trong panel bên phải có thể cuộn. Chọn hội thoại ở sidebar sẽ chuyển sang màn hình
Tin nhắn và mở hội thoại đó dù đang đứng ở Bạn bè hoặc Lời mời. Header chat cá nhân không hiển
thị số thành viên.

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

### 3. Cấu hình MySQL và Django

Dự án được cấu hình sử dụng MySQL ở cổng `3307` thay vì cổng mặc định `3306` của MariaDB/XAMPP.

Tạo cơ sở dữ liệu:

```sql
CREATE DATABASE mqtt_chat
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Ví dụ đặt biến môi trường trong PowerShell:

```powershell
$env:DB_NAME = "mqtt_chat"
$env:DB_USER = "root"
$env:DB_PASSWORD = "<your-local-password>"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3307"
$env:DJANGO_DEBUG = "true"
```

Có thể bỏ qua các biến DB để dùng mặc định phát triển trong `config/settings.py`.
`DJANGO_SECRET_KEY` có giá trị phát triển cục bộ khi `DJANGO_DEBUG=true`; production bắt buộc
đặt secret riêng và `DJANGO_DEBUG=false`. Khi production, session/CSRF cookie dùng Secure mặc
định và ứng dụng phải được phục vụ qua HTTPS.

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

## Đăng nhập HTTP và quản lý nhóm

Mọi API nghiệp vụ HTTP yêu cầu session đăng nhập, trừ các endpoint auth. Lấy cookie CSRF
trước khi đăng ký/đăng nhập và gửi token trong header `X-CSRFToken` cho request thay đổi dữ
liệu. Các endpoint auth:

- `GET /api/auth/csrf/`
- `POST /api/auth/register/` với `{"username":"...","password":"...","password_confirm":"..."}`
- `POST /api/auth/login/` với `{"username":"...","password":"...","remember_me":false}`
- `GET /api/auth/me/` để phục hồi session hiện tại
- `POST /api/auth/logout/`

Session hết hạn sau 8 giờ, hoặc 7 ngày khi `remember_me` bật. Profile gắn với tài khoản
session; client không thể tự đặt presence `status`. Endpoint tạo profile cũ `POST /api/users/`
bị tắt và trả `410 Gone`. Profile lịch sử chưa liên kết tài khoản không thể đăng nhập cho
đến khi được ánh xạ rõ ràng bởi quản trị viên.

Tạo private chat hoặc group qua `POST /api/conversations/`; actor lấy từ session. Group mới
có creator là OWNER; username được mời chưa tự động trở thành thành viên. Quản lý nhóm gồm
`GET/PATCH /api/conversations/{id}/`, mời/hủy/đáp lời mời nhóm, đổi role, loại thành viên,
rời nhóm, chuyển owner và archive. Mỗi mutation nhóm yêu cầu header `If-Match` với version
hiện tại; stale version trả `412`, thiếu version trả `428`. Chỉ thành viên active mới truy
cập hội thoại; quyền OWNER/ADMIN giới hạn theo thao tác. API bạn bè, lời mời, profile,
avatar, conversation list, message history và search cũng yêu cầu session hợp lệ.

Các nhóm cũ không tự được gán owner. Sau khi rà soát và sao lưu dữ liệu, quản trị viên có thể
chuẩn bị file JSON mapping rõ ràng rồi chạy:

```powershell
.\.venv\Scripts\python.exe manage.py link_chat_accounts C:\secure\account-mapping.json
.\.venv\Scripts\python.exe manage.py assign_group_owners C:\secure\group-owner-mapping.json
```

File account mapping là mảng `{"chat_user_id":"...","auth_username":"..."}`; file owner
mapping là mảng `{"conversation_id":"...","owner_id":"..."}`. Username phải khớp chính xác,
owner phải là thành viên active. Không suy đoán hoặc tự gán owner cho dữ liệu cũ.

Lịch sử tin nhắn: `GET /api/conversations/{id}/messages/?limit=50&before_seq=...`;
tìm kiếm: `GET /api/conversations/{id}/messages/search/?q=...`. Cả hai chỉ cho phép thành
viên active; `limit` mặc định 50, tối đa 100. Conversation list trả members, role, owner,
version, trạng thái archive và unread count.

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
Mỗi thành viên khác trong hội thoại nhận một thông báo `MESSAGE_CREATED` trên inbox
riêng `chat/client/{user_id}/event/message_created`. Thông báo gồm `sender_id`,
`conversation_id`, `message_id`, `seq` và `created_at` (không gồm nội dung tin).
Nếu hội thoại chưa có trong catalog, client tải lại danh sách và history rồi bắt
đầu subscribe topic tin nhắn của hội thoại.

Mosquitto config hiện tại trong `integration/mosquitto-local.conf` cho phép anonymous access
phát triển. HTTP session không được truyền hoặc xác minh bởi MQTT worker/broker; vì vậy MQTT v1
và các topic ở trên **không được bảo vệ bởi đăng nhập HTTP**. Không expose broker này ra mạng
công cộng hoặc coi dữ liệu MQTT là riêng tư. Cần Dynamic Security/ACL, credential theo client
và giao thức MQTT đã xác thực trước khi triển khai bảo vệ end-to-end.

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

Typing indicator do các MQTT client của hội thoại trao đổi trực tiếp qua
`chat/conversations/{conversation_id}/event/typing`; payload `TYPING` không retain,
và client tự ẩn trạng thái sau 3,5 giây nếu không nhận cập nhật. Broker hiện
anonymous, vì vậy giao thức này chỉ phù hợp môi trường phát triển tin cậy cho
đến khi triển khai ACL chỉ cho phép thành viên publish/subscribe.

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
