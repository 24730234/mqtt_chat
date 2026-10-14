# Frontend implementation handoff

File này ghi lại tiến độ, các mốc bàn giao, kết quả kiểm tra và việc còn cần phối hợp. Hướng dẫn cài đặt/chạy ứng dụng nằm trong [README.md](README.md) và [frontend/README.md](frontend/README.md).

## Trạng thái hiện tại — HTTP auth và quản lý nhóm

Implementation plan peer-to-peer đã được triển khai trong phạm vi HTTP và quản lý nhóm; broker
không được thay đổi theo quyết định của người dùng.

**Đã hoàn thành**

- Đăng ký/đăng nhập Django session, CSRF, phục hồi session, logout và thời hạn tuyệt đối 8 giờ
  (hoặc 7 ngày với `remember_me`). Các API nghiệp vụ HTTP yêu cầu session; actor lấy từ session,
  không tin user ID do client tự chọn. Endpoint tạo profile legacy trả `410 Gone`.
- Quản lý group OWNER/ADMIN/MEMBER, active membership, lời mời/cancel, cập nhật tên/mô tả,
  đổi role, kick/leave, chuyển owner và archive. Mutation dùng `If-Match`/version để phát hiện
  cập nhật cũ.
- Giao diện live có đăng ký/đăng nhập/khôi phục session/logout và panel quản lý nhóm; CSRF được
  gửi cho mutation HTTP. README gốc và README frontend đã được cập nhật theo contract hiện tại.
- Thêm management command để link profile cũ và gán owner từ mapping JSON được người quản trị
  xác nhận. Không tự suy luận danh tính hoặc owner.
- Cấu hình Django production đọc `DJANGO_DEBUG`/`DJANGO_SECRET_KEY`, bắt buộc secret riêng khi
  `DEBUG=false`, và bật Secure cookie mặc định khi production.

**Xác nhận:** 39 Django tests ở mốc kiểm tra trước; 25 frontend tests và Vite production build
ở mốc giao diện mới nhất đều qua. Django system check và `makemigrations --check --dry-run`
cũng qua ở lần kiểm tra trước. Migration chưa được áp dụng lên database thật/production; cần
backup và mapping legacy đã duyệt trước khi chạy `manage.py migrate`.

**Chưa hoàn thành / giới hạn phải giữ rõ**

- Broker vẫn anonymous MQTT v1; đăng nhập HTTP không bảo vệ MQTT topic, publish hoặc subscription.
  Chưa có Dynamic Security, MQTT credential theo connection, thu hồi MQTT khi logout/kick hoặc
  authorization cho command/event. Không xem đây là hệ thống an toàn để expose ra Internet.
- Typing indicator đã chạy trực tiếp qua MQTT topic theo hội thoại, payload không retain và client tự hết hạn sau 3,5 giây. Broker vẫn chưa có ACL nên chỉ dùng trong môi trường development tin cậy; delivery receipt, presence đa browser/session và full offline sync chưa hoàn thành.
- Chưa nghiệm thu migration với MySQL live, broker production, cấu hình HTTPS/reverse proxy hoặc
  vận hành triển khai; chưa có rate limiting login/register bằng shared storage.
- Profile người dùng/group legacy cần mapping explicit; các management command chưa có test riêng.

Đây là trạng thái mới nhất và thay thế các ghi chú “chưa có auth”/“chọn user” trong các mốc FE
trước đây bên dưới. Các mốc cũ được giữ lại làm nhật ký lịch sử, không phải contract hiện hành.

## Cập nhật giao diện live — 15/10/2026

- Tạo nhóm gửi lời mời cho các username đã chọn; người tạo là thành viên ban đầu, người được
  mời chỉ thành thành viên sau khi chấp nhận. Toast xác nhận liệt kê người nhận; panel nhóm có
  danh sách lời mời đang chờ để phân biệt với thành viên hiện tại.
- Panel thông tin/quản lý nhóm được thiết kế lại thành drawer bên phải, cuộn độc lập từ đầu
  xuống cuối để dùng được khi thông tin nhóm dài.
- Chọn hội thoại ở sidebar luôn chuyển về module Tin nhắn và mở hội thoại đó, kể cả khi đang
  ở module Bạn bè hoặc Lời mời.
- Header của hội thoại PRIVATE không hiện số thành viên; avatar người bạn đã chọn được căn
  giữa trong thẻ thông tin.
- Đã nối typing indicator qua MQTT topic riêng của hội thoại: không retain, chỉ chấp nhận event
  từ thành viên đang theo dõi và tự ẩn sau 3,5 giây. Broker anonymous chưa có ACL nên chỉ dùng
  trong môi trường phát triển tin cậy.
- Kiểm tra frontend tại mốc cập nhật: **25/25 tests qua**, `npm run build` thành công. Django
  tests không chạy trong môi trường hiện tại do thiếu Django.

## Tiến độ frontend — ngày 29/09/2026

FE được triển khai trong `frontend/` bằng **React + Vite + MQTT.js**, đối chiếu README,
`chat/views.py`, `config/urls.py` và `chat/mqtt_messages.py` tại BE commit `7dc68e8`.

**Trạng thái tại mốc này:** đã có giao diện và adapter cho API/MQTT hiện có; đã build và kiểm thử FE riêng. Ngày 03/10 đã kiểm tra với Django + MySQL + Mosquitto local và cả hai worker thật; môi trường triển khai/ACL của nhóm vẫn cần nghiệm thu riêng. Không coi chức năng trong danh sách Features của README là đã hoàn thành toàn bộ.

### Tính năng đã làm

| Hạng mục | Tiến độ FE | Ghi chú tích hợp |
| --- | --- | --- |
| Giao diện chat | Hoàn thành bản đầu | Tiếng Việt, responsive, tìm hội thoại/tin nhắn trên server, draft riêng từng hội thoại |
| Demo riêng | Hoàn thành | Dữ liệu mẫu và phản hồi mẫu chỉ chạy trong chế độ demo |
| Chọn/tạo người dùng | Đã nối API | Search username / POST user; đây **không phải đăng nhập** |
| Hồ sơ | Đã nối API | PATCH username, short_bio (160 ký tự), bio, sex |
| Avatar | Đã nối API | POST multipart `avatar`, DELETE avatar, hiển thị `avatar_url`, giới hạn 5 MB và định dạng ảnh |
| Chat cá nhân/nhóm | Đã nối API | Dùng đúng `user_id`, `type`, `username` / `usernames`; hiển thị member từ response |
| Danh sách hội thoại | Đã nối API | Tải từ backend với thành viên và tin nhắn cuối, sắp xếp theo hoạt động |
| Mở nhóm đã có | Đã nối metadata | Nhập conversation UUID; kiểm tra quyền qua API history, không tự thêm thành viên |
| Lịch sử | Đã nối API | 50 tin/lần, nút tải trước `before_seq`, xử lý 403/404/lỗi mạng |
| Tìm tin nhắn | Đã nối API | Debounce 300 ms, gọi endpoint search mới, tối đa 50 kết quả mới nhất và hủy request cũ |
| Gửi và nhận realtime | Đã nối MQTT WebSocket | QoS 1, publish `command/send`, subscribe `message_accepted`/`error`/`message_created` |
| Đã xem / chưa xem | Đã nối MQTT và database | Đánh dấu khi tin nhắn của người khác hiển thị; receipt bền vững, cập nhật người gửi realtime và badge hội thoại chưa đọc |
| Reply | Đã nối hợp đồng BE | Gửi `reply_to_message_id`, hiển thị trích dẫn nếu tin gốc đã tải |
| Xác nhận và chống trùng | Đã làm | Chờ ACK nghiệp vụ từ BE; ghép optimistic/ACK/broadcast/history, sắp theo server `seq` |
| Timeout / retry | Đã làm | Giữ nguyên client UUID và nội dung khi gửi lại; không gửi `seq` lên worker |
| Presence | Đã nối giao thức, cần kiểm tra thêm đa trình duyệt | Retained online, Last Will offline; mỗi browser subscribe status của bạn bè đã tải và thành viên hội thoại đang theo dõi |
| Reconnect | Đã làm mức cơ bản | Tự kết nối lại, subscribe lại, tải 50 tin mới nhất cho hội thoại đã biết |
| Bạn bè/lời mời | Đã nối API | Danh sách bạn có keyset paging, tìm kiếm/lọc online; lời mời bạn bè/nhóm đến và đã gửi, chấp nhận/từ chối; sidebar thông tin thu gọn/mở rộng |
| Đã nhận / typing | Typing đã nối MQTT; delivered chưa có | Typing gửi event không retain trong topic hội thoại, chỉ hiện user thuộc danh sách member đang theo dõi và tự hết hạn sau 3,5 giây. Broker anonymous chưa an toàn để expose |
| Đồng bộ offline đầy đủ | Chưa hoàn thành | Không có offline outbox; sau reconnect cần tải thêm lịch sử nếu thiếu hơn 50 tin |

### Cập nhật sửa lỗi ngày 30/09/2026

- Sửa luồng chọn môi trường test: thêm nút **Dùng server test** trên localhost để điền API `18000` và MQTT WebSocket `19001`. Lỗi không phải JSON trước đó do `/api` proxy tới Django `8000` chưa chạy.
- Nhớ API base / MQTT URL trong sessionStorage sau reload; không lưu broker username/password.
- Hiển thị nhãn **Server test · Dữ liệu mẫu** khi dùng fixture, tránh nhầm với backend của nhóm.
- Khi history trả 403/404: hiện lý do, ngừng subscribe MQTT hội thoại, bỏ tin đã tải khỏi màn hình và chặn gửi/retry.
- Thêm ẩn lối tắt hội thoại cũ trên máy kèm **Hoàn tác**; thao tác này không xóa dữ liệu server.
- Đã kiểm tra trên giao diện: cấu hình qua reload, vào user fixture, ẩn/hoàn tác hội thoại không tồn tại và gửi tin nhận xác nhận từ server test.
- Bộ kiểm thử đạt **18 tests**, gồm unsubscribe khi mất quyền và bỏ qua broadcast đến muộn; production build thành công.

### Rà soát và bàn giao ngày 30/09/2026

- Đối chiếu lại FE với BE mới nhất đã fetch: `7dc68e8`; thay đổi bàn giao gồm `frontend/` và báo cáo.
- Sửa trạng thái MQTT khi bỏ hội thoại bị broker từ chối; subscribe lại các topic còn dùng và chỉ cho gửi sau khi broker xác nhận.
- Bỏ qua callback subscribe cũ sau ngắt kết nối; ACK sai conversation không hủy timeout của tin đang chờ.
- Giữ nguyên HTTP status khi server trả JSON `null` cho lỗi, để giao diện vẫn xử lý được 403/404.
- Kiểm tra lại: **18/18 tests qua**, `npm run build` thành công; tìm `thien_fixture`, mở hội thoại mẫu và gửi tin nhận ACK trên trình duyệt.
- Chưa nghiệm thu với backend thật của nhóm. Các mục còn chờ BE được liệt kê ở checklist tích hợp phía dưới.

### Tích hợp backend thật, cập nhật ngày 03/10/2026

- Đã chạy trực tiếp `run_mqtt_worker` và `run_mqtt_presence` cùng Django, MySQL 8.4 và Mosquitto 2; log xác nhận subscribe đúng topic. Không dùng Docker.
- Đã qua **9 nhóm kiểm tra tích hợp thật**: user/nhóm, presence online/offline lưu DB, ACK và broadcast, retry chống trùng, history 50 + 5 tin/reply, tìm kiếm server, quyền history 403, hồ sơ và upload/GET/xóa avatar.
- Đã gửi tin trực tiếp từ FE qua broker thật và nhận xác nhận lưu MySQL; **18/18 unit tests FE + build** vẫn qua.
- FE: `http://127.0.0.1:5173/?mode=live`, API base `/api`, MQTT `ws://127.0.0.1:9001`. User sau chạy smoke: `quang_live`, `thien_live`.
- Cấu hình và hướng dẫn khởi động cả stack: [integration/README.md](integration/README.md). Không cần fixture cho luồng này.
- Broker local chỉ mở cổng trên loopback, dùng anonymous cho phát triển. Chưa kiểm chứng ACL production, Last Will khi client chết đột ngột hoặc full offline sync.

### Cập nhật theo backend ngày 03/10/2026

- Đã đồng bộ commit BE `78f0fe7` và nối endpoint tìm kiếm tin nhắn `GET /api/conversations/{conversation_id}/messages/search/` vào giao diện live.
- Ô tìm kiếm dùng dữ liệu toàn bộ hội thoại từ server thay vì chỉ lọc các tin đang hiển thị; request debounce và request cũ bị hủy khi người dùng tiếp tục gõ.
- Cấu hình database đọc được từ `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` để chạy local thuận tiện mà không sửa mã nguồn.
- Stack kiểm tra local chạy trực tiếp bằng Homebrew/Python/Node, không dùng Docker. Xem [integration/README.md](integration/README.md).
- Kiểm tra tại thời điểm đó: **21/21 tests BE, 18/18 tests FE, production build và 9/9 nhóm smoke test đều qua**.

### Rà soát toàn bộ và bàn giao FE ngày 04/10/2026

Đã đồng bộ và kiểm tra lại `origin/main` tại commit `78f0fe7`. Nhánh FE bao gồm:

- Giao diện React/Vite responsive có demo riêng và live mode kết nối Django/MQTT thật.
- Chọn/tạo user; chỉnh username, giới thiệu, giới tính và upload/xóa avatar.
- Tìm user, xem/xóa bạn, gửi lời mời và phản hồi lời mời bằng UUID theo contract hiện có.
- Tạo chat cá nhân/nhóm, mở hội thoại bằng UUID và lưu catalog riêng theo API/user trên trình duyệt.
- Tải lịch sử 50 tin/trang, tải tin cũ, reply và xử lý lỗi quyền 403/không tồn tại 404.
- Tìm toàn bộ tin nhắn của hội thoại qua endpoint server, debounce request và hủy request cũ.
- Gửi/nhận realtime qua MQTT WebSocket; optimistic message, ACK nghiệp vụ, broadcast, chống trùng, server sequence, timeout và retry giữ nguyên client message UUID.
- Presence online/offline với retained Last Will; reconnect, resubscribe và tải lại lịch sử.
- Cấu hình local không Docker cho MySQL 8.4, Mosquitto, Django, Vite cùng hai process `run_mqtt_worker` và `run_mqtt_presence`.
- Ghi rõ vai trò của bốn JetBrains Run Configuration do nhóm BE cung cấp: compound config chỉ chạy Django và hai worker; UI vẫn chạy riêng theo `frontend/README.md`.

Kết quả xác nhận tại ngày 04/10:

- **21/21 test backend qua**, Django system check không có lỗi.
- **18/18 test frontend qua** và Vite production build thành công.
- **9/9 nhóm smoke test qua** với MySQL/Mosquitto thật: user/nhóm, presence, ACK/broadcast, retry chống trùng, history 50 + 5/reply, tìm kiếm server, quyền 403, profile/avatar và offline.
- Kiểm tra process xác nhận MySQL `3307`, Mosquitto TCP `1883`, WebSocket `9001`, Django `8000`, Vite `5173` và cả hai MQTT worker đang chạy trực tiếp, không có Docker trong luồng này.
- Giao diện live tải thành công tại `http://127.0.0.1:5173/?mode=live`.

Các phần chưa hoàn thiện tại mốc rà soát này được phân loại FE/BE và mức ưu tiên trong [REVIEW_03-10-26.md](REVIEW_03-10-26.md).

### Cập nhật tính năng ngày 07/10/2026

- **Đã xem / chưa xem được lưu bền vững:** dùng model `MessageReceipt` hiện có, không cần migration. Backend chỉ ghi nhận đã đọc cho tin của thành viên khác trong đúng hội thoại; yêu cầu đọc có thể gửi lặp an toàn.
- **Đọc theo vùng nhìn thấy:** frontend dùng `IntersectionObserver` để gửi batch ID khi tin nhắn đi vào vùng nhìn thấy, không đánh dấu toàn bộ hội thoại chỉ vì người dùng mở chat.
- **Đồng bộ realtime và khi tải lại:** worker MQTT nhận `chat/client/{user_id}/command/read`, broadcast `MESSAGE_READ` trên `chat/conversations/{conversation_id}/event/message_read`; history trả `read_by`, conversation catalog trả `unread_count`. Giao diện cập nhật trạng thái “Chưa xem/Đã xem”, badge và bộ lọc hội thoại chưa đọc.
- **Nhận hội thoại mới realtime:** sau khi có tin nhắn mới, worker gửi một thông báo `MESSAGE_CREATED` tới inbox riêng của từng thành viên khác. Payload gồm `sender_id` và metadata hội thoại/tin nhắn; nếu conversation chưa có trong catalog, FE tải lại danh sách và history để bắt đầu theo dõi message topic.
- **Friends và Invitations:** sidebar thông tin bên phải có thể thu gọn/mở rộng để dành thêm chiều rộng cho nội dung; nút vẫn hiển thị khi thu gọn và dùng được trên màn hình nhỏ.
- **Presence cần nghiệm thu thêm:** mỗi browser là MQTT client riêng; các browser cần cùng broker và client nhận cần subscribe topic `chat/users/{user_id}/status`. Chưa xác nhận được nguyên nhân lệch trạng thái giữa hai browser; nhãn “MQTT đã kết nối” chưa chứng minh đã nhận đúng presence topic.
- **Kiểm tra sau cập nhật:** 31 Django tests, 25 frontend tests, Django system check và Vite production build thành công; không phát sinh migration.

## Kiểm thử FE

Lệnh kiểm thử:

```bash
cd frontend
npm test
npm run build
```

Kết quả được ghi theo từng mốc ở trên. Kiểm thử fixture HTTP + MQTT WebSocket không thay thế xác nhận MySQL transaction, Mosquitto ACL, avatar storage hoặc Django worker chạy end-to-end trên backend của nhóm.

## Việc còn lại / phối hợp nghiệm thu

1. Trước khi bảo vệ MQTT: thống nhất thay broker/config, triển khai Dynamic Security hoặc ACL, credential theo client và kiểm thử quyền publish/subscribe; HTTP authentication hiện không có tác dụng với MQTT v1.
2. Sau khi broker có danh tính/ACL: triển khai MQTT authorization, thu hồi khi kick/logout, presence multi-session và realtime group invalidation; typing hiện tại chưa được bảo vệ bởi ACL.
3. Sao lưu database, áp dụng migration trên môi trường thử nghiệm/live có kiểm soát, rồi dùng mapping JSON đã được chủ dự án duyệt để liên kết profile và gán owner cũ.
4. Chạy nghiệm thu với MySQL/broker thực tế, HTTPS/reverse proxy, avatar storage, retry/Last Will và kiểm tra hai browser; bổ sung shared-store rate limiting cho đăng ký/đăng nhập.

Chi tiết cấu trúc FE, cấu hình và fixture: [frontend/README.md](frontend/README.md).
