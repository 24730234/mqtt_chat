# Mạch — MQTT Chat Frontend

React + Vite + MQTT.js. Giao diện tiếng Việt, chế độ demo độc lập và chế độ kết nối API/MQTT theo BE commit `78f0fe7`.

## Chạy

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

- Demo: `http://127.0.0.1:5173/`.
- Live: `http://127.0.0.1:5173/?mode=live`, hoặc nút **KẾT NỐI BE** trong demo.
- Live chưa có auth: chọn user tồn tại bằng tìm username hoặc tạo user. Không nhập tài khoản giả từ demo vào BE.
- Chạy Django HTTP server, MQTT message worker, presence subscriber và broker theo README gốc.

## Cấu hình

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `BACKEND_URL` | `http://127.0.0.1:8000` | Chỉ phía Vite dev server; proxy `/api`, `/media` |
| `VITE_API_BASE` | `/api` | Prefix API được bundle vào FE |
| `VITE_MQTT_URL` | `ws://127.0.0.1:9001` | URL ví dụ; BE phải bật listener WebSocket tương ứng |

Có thể thay API base, URL MQTT và credentials trên màn **Cấu hình kết nối** trước khi chọn user.
Địa chỉ API/MQTT được nhớ trong sessionStorage của tab qua lần reload; credentials không được lưu.
Trên localhost, nút **Dùng server test** điền sẵn API `18000` và MQTT WebSocket `19001` cho fixture.
MQTT password chỉ ở bộ nhớ, không đưa vào env `VITE_*` hoặc localStorage.
Nếu dùng API URL khác origin, BE cần CORS. Nếu serve bản build, reverse proxy `/api`, `/media`
hoặc cấu hình API base; `npm run preview` không phải cấu hình deployment sản xuất.
Trang HTTPS cần `wss://` để tránh mixed content.

## Cấu trúc

- `src/Root.jsx`: đổi demo/live, lazy-load MQTT.
- `src/App.jsx`, `src/chatService.js`: demo cũ, dữ liệu riêng.
- `src/live/LiveApp.jsx`: chọn user, workspace chat, profile/avatar, bạn bè, tạo/mở hội thoại.
- `src/live/api.js`: HTTP API adapter, validation avatar, lỗi mạng/HTTP.
- `src/live/transport.js`: MQTT topics, ACK nghiệp vụ, timeout, retry, presence, reconnect.
- `src/live/state.js`: chuẩn hóa history, merge/ordering/dedup, catalog tách theo API/user.
- `tests/*.test.js`: các ca logic và contract có hồi quy cần kiểm tra.

## Các quyết định theo contract hiện tại

- `seq` do BE cấp. FE chỉ gửi `conversation_id`, `client_message_id`, `content`, `reply_to_message_id`.
- MQTT PUBACK không chứng minh BE đã lưu. UI chờ `MESSAGE_ACCEPTED` hoặc broadcast của chính tin đó.
- Retry dùng nguyên UUID/nội dung/reply target. Tin timeout có thể đã lưu; retry phải idempotent.
- Receipt READ/DELIVERED không có API/topic chính thức nên không giả lập trong live.
- Catalog chỉ chứa hội thoại đã mở/tạo trên trình duyệt. BE chưa có GET danh sách/chi tiết.
- Mở bằng UUID kiểm tra membership bằng history. Không tự join. Khi không có metadata,
  chỉ biết các tác giả từ trang history, không suy diễn thành toàn bộ thành viên.
- Reconnect resubscribe và fetch trang 50 tin mới nhất; người dùng bấm tải cũ hơn nếu cần.
  Chưa có outbox offline hoặc đảm bảo đồng bộ mọi khoảng trống; BE còn thiếu sync contract.
- Drafts/pending messages chỉ trong bộ nhớ phiên; reload/đổi tài khoản sẽ mất.
- Presence theo một topic/user có hạn chế nhiều tab đồng thời; cần chốt xử lý ở BE.

## Kiểm tra

```sh
npm test
npm run build
```

Đã qua 18 unit/contract tests và build. Đã kiểm tra trình duyệt với fixture: profile PATCH,
tạo nhóm, mở history có 55 tin, tải 50 + 5, reply, ACK, refresh không trùng và hai phiên user realtime.
Avatar có test validation/multipart; vẫn cần kiểm tra upload/delete storage thật với Django.
Ngày 03/10 đã chạy 9 nhóm kiểm thử với MySQL + Mosquitto + Django local và cả hai worker thật,
bao gồm endpoint tìm kiếm tin nhắn mới; không dùng Docker.
Xem [hướng dẫn tích hợp thật](../integration/README.md). Môi trường triển khai/ACL của nhóm vẫn cần kiểm tra riêng.

### Fixture cô lập để kiểm tra FE

```sh
node tests/fixture.mjs
```

Mở live mode, cấu hình **API base** `http://127.0.0.1:18000/api`, **MQTT WebSocket URL**
`ws://127.0.0.1:19001`. Hai user: `quang_fixture`, `thien_fixture`. Hội thoại có 55 tin mẫu:
`33333333-3333-4333-8333-333333333333`. Gửi nội dung `[timeout]` để kiểm tra không có ACK.
Dữ liệu fixture ở bộ nhớ, reset khi dừng process. Không dùng fixture cho production hoặc xem
kết quả của nó là nghiệm thu backend. Fixture chỉ bao phủ endpoint cần cho kiểm tra ở trên,
không giả lập đầy đủ avatar storage, friend removal, retained presence hay ACL.

Báo cáo tiến độ bàn giao: [README gốc](../README.md#frontend--tiến-độ-ngày-29092026).

## Sửa lỗi cấu hình và hội thoại cũ (30/09/2026)

Nếu báo API không phải JSON khi tìm `quang_fixture`, nhấn **Dùng server test**.
Mặc định `/api` proxy về Django `8000`; fixture chạy `18000` và MQTT WebSocket `19001`.
Địa chỉ được nhớ khi reload cùng tab; broker credentials vẫn chỉ nằm trong bộ nhớ.

Server fixture reset dữ liệu khi khởi động lại, nên UUID nhóm tạo trước đó có thể không còn.
FE hiện lý do 403/404, unsubscribe hội thoại, chặn gửi và cho **Ẩn khỏi danh sách trên máy này**
kèm **Hoàn tác**. Không có yêu cầu DELETE hội thoại được gửi tới backend.

Rà soát bàn giao 30/09: khôi phục MQTT sau khi bỏ topic bị từ chối, bỏ qua callback
subscribe cũ sau disconnect và giữ timeout nếu ACK thuộc hội thoại khác. API lỗi có
JSON `null` vẫn giữ HTTP status. Các trường hợp này đã có regression tests.

## Chạy với backend thật không dùng Docker (03/10/2026)

Khởi động stack theo [integration/README.md](../integration/README.md), dùng API base
`/api` và MQTT `ws://127.0.0.1:9001`. Sau chạy `node integration/smoke.mjs` từ thư mục gốc,
có thể chọn `quang_live` hoặc `thien_live`. Django, Mosquitto và hai worker được chạy
thành các process local riêng. Không bấm **Dùng server test** khi muốn kiểm tra stack này.
