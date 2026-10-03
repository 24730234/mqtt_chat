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
chat/client/{user_id}/command/sync
chat/client/{user_id}/command/delivered
```

Chạy message worker trong terminal riêng, tách khỏi web server Django:

```bash
python manage.py run_mqtt_worker
```

Worker subscribe vào `chat/client/+/command/send`. Publish một object JSON tới
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

## Frontend — tiến độ ngày 29/09/2026

FE được triển khai trong `frontend/` bằng **React + Vite + MQTT.js**, đối chiếu README,
`chat/views.py`, `config/urls.py` và `chat/mqtt_messages.py` tại BE commit `7dc68e8`.

**Trạng thái:** đã có giao diện và adapter cho API/MQTT hiện có; đã build và kiểm thử
FE riêng. **Ngày 03/10 đã kiểm tra với Django + MySQL + Mosquitto local và cả hai worker thật**;
môi trường triển khai/ACL của nhóm vẫn cần nghiệm thu riêng.
Không coi chức năng trong danh sách Features phía trên là đã hoàn thành toàn bộ.

### Đã làm được

| Hạng mục | Tiến độ FE | Ghi chú tích hợp |
| --- | --- | --- |
| Giao diện chat | Hoàn thành bản đầu | Tiếng Việt, responsive, tìm hội thoại/tin nhắn trên server, draft riêng từng hội thoại |
| Demo riêng | Hoàn thành | Dữ liệu mẫu và phản hồi mẫu chỉ chạy trong chế độ demo |
| Chọn/tạo người dùng | Đã nối API | Search username / POST user; đây **không phải đăng nhập** |
| Hồ sơ | Đã nối API | PATCH username, short_bio (160 ký tự), bio, sex |
| Avatar | Đã nối API | POST multipart `avatar`, DELETE avatar, hiển thị `avatar_url`, giới hạn 5 MB và định dạng ảnh |
| Chat cá nhân/nhóm | Đã nối API | Dùng đúng `user_id`, `type`, `username` / `usernames`; hiển thị member từ response |
| Danh sách hội thoại | Tạm thời lưu cục bộ | Phân tách theo API base + user UUID; BE chưa có GET danh sách hội thoại |
| Mở nhóm đã có | Đã làm phương án tạm | Nhập conversation UUID; kiểm tra quyền qua API history, không tự thêm thành viên |
| Lịch sử | Đã nối API | 50 tin/lần, nút tải trước `before_seq`, xử lý 403/404/lỗi mạng |
| Tìm tin nhắn | Đã nối API | Debounce 300 ms, gọi endpoint search mới, tối đa 50 kết quả mới nhất và hủy request cũ |
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
- Đã qua **9 nhóm kiểm tra tích hợp thật**: user/nhóm, presence online/offline lưu DB, ACK và broadcast, retry chống trùng, history 50 + 5 tin/reply, tìm kiếm server, quyền history 403, hồ sơ và upload/GET/xóa avatar.
- Đã gửi tin trực tiếp từ FE qua broker thật và nhận xác nhận lưu MySQL; **18/18 unit tests FE + build** vẫn qua.
- FE: `http://127.0.0.1:5173/?mode=live`, API base `/api`, MQTT `ws://127.0.0.1:9001`. User sau chạy smoke: `quang_live`, `thien_live`.
- Cấu hình và hướng dẫn khởi động cả stack: [integration/README.md](integration/README.md). Không cần fixture cho luồng này.
- Broker local chỉ mở cổng trên loopback, dùng anonymous cho phát triển. Chưa kiểm chứng ACL production, Last Will khi client chết đột ngột hoặc full offline sync.

### Cập nhật theo backend ngày 03/10/2026

- Đã đồng bộ commit BE `78f0fe7` và nối endpoint tìm kiếm tin nhắn
  `GET /api/conversations/{conversation_id}/messages/search/` vào giao diện live.
- Ô tìm kiếm dùng dữ liệu toàn bộ hội thoại từ server thay vì chỉ lọc các tin đang hiển thị;
  request được debounce và request cũ bị hủy khi người dùng tiếp tục gõ.
- Cấu hình database đọc được từ `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
  để chạy local thuận tiện mà không sửa mã nguồn.
- Stack kiểm tra local chạy trực tiếp bằng Homebrew/Python/Node, không dùng Docker. Xem
  [integration/README.md](integration/README.md).
- Kiểm tra lại: **21/21 tests BE, 18/18 tests FE, production build và 9/9 nhóm smoke test đều qua**.

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

## Các bước đề xuất tiếp theo

Các hạng mục nhắn tin còn lại:

1. Bổ sung API xác nhận đã nhận/đã đọc và đồng bộ khi ngoại tuyến.
2. Kiểm thử HTTP/MQTT client của frontend với backend đang chạy của nhóm (xem tiến độ frontend ở trên).

## Ghi chú

- Cấu hình cơ sở dữ liệu hiện dùng MySQL ở cổng `3307` vì cổng `3306` đang được MariaDB/XAMPP cục bộ sử dụng.
- Dự án phục vụ mục đích học tập và phát triển prototype, với sự phân tách rõ ràng giữa truyền tải MQTT và lưu trữ dữ liệu bền vững.
- Ứng dụng được thiết kế để phát triển từ kiến trúc ưu tiên CLI/client thành trải nghiệm web hoặc desktop đầy đủ hơn.

## Giấy phép

Dự án phục vụ mục đích học tập và phát triển, trừ khi có giấy phép riêng được bổ sung sau này.
