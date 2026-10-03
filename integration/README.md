# Chạy và kiểm tra FE với hai MQTT worker, không dùng Docker

Môi trường local chạy trực tiếp Django, MySQL 8.4, Eclipse Mosquitto 2 và hai
management command `run_mqtt_worker`, `run_mqtt_presence`. Fixture không được dùng
trong kiểm thử tích hợp này.

## Cài lần đầu trên macOS

Cần Homebrew, Python 3 và Node 22+:

```sh
brew install mysql@8.4 mosquitto
python3 -m venv .venv
MYSQLCLIENT_CFLAGS="-I/opt/homebrew/opt/mysql@8.4/include/mysql" \
MYSQLCLIENT_LDFLAGS="-L/opt/homebrew/opt/mysql@8.4/lib -lmysqlclient" \
  .venv/bin/pip install -r requirements.txt
cd frontend
npm ci
```

Nếu máy Intel dùng Homebrew tại `/usr/local`, thay `/opt/homebrew` trong hai biến
trên bằng `/usr/local`.

## Khởi động

Mỗi khối lệnh dưới đây chạy trong một terminal riêng, từ thư mục gốc repository.

MySQL chạy ở cổng 3307:

```sh
/opt/homebrew/opt/mysql@8.4/bin/mysqld_safe \
  --datadir=/opt/homebrew/var/mysql \
  --port=3307 --bind-address=127.0.0.1 \
  --socket=/tmp/mysql-mqtt-chat.sock
```

Ở lần đầu, tạo database và migration:

```sh
/opt/homebrew/opt/mysql@8.4/bin/mysql \
  --socket=/tmp/mysql-mqtt-chat.sock -u root \
  -e 'CREATE DATABASE IF NOT EXISTS mqtt_chat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'
DB_PASSWORD='' .venv/bin/python manage.py migrate
```

Khởi động broker, Django, hai worker và FE:

```sh
/opt/homebrew/opt/mosquitto/sbin/mosquitto -c integration/mosquitto-local.conf -v
DB_PASSWORD='' .venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
DB_PASSWORD='' .venv/bin/python manage.py run_mqtt_worker
DB_PASSWORD='' .venv/bin/python manage.py run_mqtt_presence
cd frontend && npm run dev
```

Mở `http://127.0.0.1:5173/?mode=live`. Trong **Cấu hình kết nối**, dùng API base
`/api`, MQTT WebSocket URL `ws://127.0.0.1:9001`, để trống MQTT username/password.
Không chọn **Dùng server test** vì nút đó trỏ tới fixture.

Database mới chưa có user. Tạo user trên giao diện hoặc chạy smoke test để có
`quang_live`, `thien_live` và `outsider_live`. Đây là bước chọn user; backend hiện
chưa có cơ chế đăng nhập.

## Kiểm thử tích hợp

```sh
node integration/smoke.mjs
```

Script dùng chính HTTP/MQTT adapter FE, tạo nhóm mới và 55 tin, kiểm tra tìm kiếm
server, phân trang, reply, phân quyền, avatar, ACK/broadcast, chống trùng và presence.
UUID nhóm cùng kết quả được ghi vào `integration/.last-run.json` và không commit.

Hai worker là bắt buộc khi kiểm tra live:

- `run_mqtt_worker` nhận lệnh gửi tin, lưu MySQL rồi phát ACK/broadcast.
- `run_mqtt_presence` lưu trạng thái online/offline từ broker vào MySQL.

Broker chỉ lắng nghe loopback và cho phép anonymous để phát triển local. Cấu hình này
không thay cho ACL/xác thực ở môi trường triển khai.
