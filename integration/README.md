# Kiểm tra FE với hai MQTT worker thật

Môi trường local chạy mã Django hiện có với MySQL 8.4 và Eclipse Mosquitto 2.
Hai service riêng chạy đúng `python manage.py run_mqtt_worker` và
`python manage.py run_mqtt_presence`; không sử dụng fixture.

## Khởi động

Cần Docker Desktop đang chạy, Python 3 để tạo cấu hình, Node 22+ để chạy FE.
Từ thư mục gốc repository:

```sh
python3 integration/setup.py
docker compose -f integration/compose.yaml up -d --build
cd frontend
npm ci
npm run dev
```

Mở `http://127.0.0.1:5173/?mode=live`. Trong **Cấu hình kết nối**, dùng:

- API base: `/api` (Vite proxy tới Django `127.0.0.1:8000`).
- MQTT WebSocket URL: `ws://127.0.0.1:9001`.
- MQTT username/password: để trống trong môi trường local này.
- Không chọn **Dùng server test**, vì nút đó trỏ tới fixture `18000/19001`.

Database mới chưa có user. Tạo user trên giao diện hoặc chạy kiểm thử bên dưới để có
`quang_live` và `thien_live`. Đây là chọn user của backend hiện tại, chưa có auth.

## Kiểm thử lặp lại

Từ thư mục gốc, sau khi `frontend` đã được `npm ci`:

```sh
node integration/smoke.mjs
```

Script dùng chính HTTP/MQTT adapter FE, tạo nhóm mới và 55 tin cho mỗi lần chạy;
UUID nhóm và kết quả được ghi vào `integration/.last-run.json` (không commit).
Dùng **Mở bằng mã UUID** trên FE để xem nhóm này từ cả hai user.
Script cập nhật hồ sơ/avatar của `quang_live`; chỉ dùng các tài khoản test này.
Không chạy script đồng thời với phiên browser cùng user khi kiểm tra presence.

Ngày 01/10/2026 đã qua 8 nhóm kiểm tra với stack thật:

1. Tạo/tìm user, tạo nhóm qua Django.
2. Hai MQTT client kết nối; presence worker lưu `online` vào MySQL.
3. Message worker trả ACK và broadcast tới user thứ hai.
4. Retry cùng UUID trả cùng message/seq, `duplicate=true`.
5. History đọc MySQL: 50 + 5 tin, reply và không nhân đôi.
6. User ngoài nhóm bị từ chối history HTTP 403.
7. PATCH hồ sơ, upload ảnh thật, GET file media và xóa avatar.
8. Presence worker lưu `offline` khi client đóng kết nối bình thường.

Đã kiểm tra thêm trên trình duyệt: tìm `quang_live`, mở nhóm, gửi tin và nhận
“Đã lưu trên máy chủ”. 18 unit/contract tests FE và production build vẫn qua.
Last Will khi client chết đột ngột, broker ACL, reconnect trong sự cố kéo dài và
môi trường triển khai của nhóm vẫn cần kiểm tra riêng.

## Xem trạng thái / dừng

```sh
docker compose -f integration/compose.yaml ps
docker compose -f integration/compose.yaml logs -f message-worker presence-worker
docker compose -f integration/compose.yaml stop
```

`stop` giữ nguyên dữ liệu. Database, media và MQTT persistence dùng Docker volumes.
Không chạy `down -v` nếu còn cần dữ liệu. Giữ `integration/.env` để sử dụng lại volume DB.

Cấu hình `integration.settings` tách riêng, không sửa `config/settings.py` của BE.
Broker local cho phép anonymous và chỉ publish cổng ra host `127.0.0.1`; đây không phải
cấu hình production hoặc kiểm chứng ACL. Mật khẩu MySQL sinh riêng trong `.env` bị Git bỏ qua.
