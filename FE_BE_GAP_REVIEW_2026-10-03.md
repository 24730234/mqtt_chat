# Rà soát tính năng FE và BE

**Cập nhật:** 03/10/2026

**Code đã đối chiếu:** `origin/main` tại `78f0fe7`, FE tại `16bbbf5`

**Phạm vi:** `frontend/src/live/`, Django routes/views/services/models và hai MQTT worker.

## Kết luận

Luồng chat cốt lõi đã hoạt động end-to-end không dùng Docker: chọn/tạo user, hồ sơ và
avatar, bạn bè cơ bản, tạo chat cá nhân/nhóm, lịch sử phân trang, tìm kiếm trên server,
reply, gửi/nhận realtime, chống trùng, retry và presence. Đã qua 21 test BE, 18 test FE,
production build và 9 nhóm smoke test với MySQL/Mosquitto cùng hai worker thật.

Phần mềm vẫn là prototype vì chưa có xác thực và nhiều contract backend cần cho trải
nghiệm chat hoàn chỉnh. Không nên chỉ bổ sung giao diện giả cho các mục chưa có contract.

## Những phần đã hoàn thành

- Tìm kiếm tin nhắn đã gọi endpoint server, debounce 300 ms và hủy request cũ.
- Tạo/tìm/cập nhật user; upload/xóa avatar.
- Tạo hoặc dùng lại chat cá nhân; tạo nhóm.
- Lịch sử 50 tin/trang, tải trang cũ theo `before_seq`.
- MQTT send, ACK nghiệp vụ, broadcast, reply, retry giữ nguyên client UUID và chống trùng.
- Presence online/offline, reconnect và resubscribe cơ bản.
- Xem/xóa bạn, gửi lời mời và phản hồi lời mời bằng UUID.

## Phần còn thiếu

| Ưu tiên | Hạng mục | FE hiện tại | Backend/contract cần có |
| --- | --- | --- | --- |
| P0 | Đăng nhập và xác thực | Người dùng có thể chọn bất kỳ username/UUID. | Auth HTTP, token/session và xác thực MQTT/ACL gắn client với đúng user. |
| P0 | Danh sách hội thoại từ server | Catalog chỉ lưu trong trình duyệt; đổi máy hoặc xóa storage sẽ mất. | GET danh sách hội thoại theo user và GET chi tiết hội thoại/thành viên. |
| P0 | Đồng bộ offline đầy đủ | Reconnect chỉ tải 50 tin mới nhất; pending/draft mất khi reload. | Sync theo cursor/sequence, quy tắc resume và có thể cần outbox bền vững. |
| P1 | Đã nhận / đã đọc | Chỉ hiển thị “Đã lưu trên máy chủ”. | Service/API/MQTT handler cho `MessageReceipt`; model hiện có nhưng chưa được sử dụng. |
| P1 | Chỉ báo đang nhập | Chưa gửi hoặc hiển thị typing. | Topic, payload, TTL và quyền publish/subscribe cho typing. |
| P1 | Hộp thư lời mời | Người nhận phải nhập `invitation_id` thủ công. | API liệt kê lời mời đến/đi và trạng thái pending. |
| P1 | Quản lý nhóm | Chỉ tạo và xem thành viên có trong response/history. | API đổi tên, thêm/xóa thành viên, rời nhóm, quyền quản trị và xóa nhóm nếu cần. |
| P1 | Unread bền vững | Đếm trong phiên và đặt về 0 khi mở; reload có thể lệch. | Read cursor/unread state lưu trên server, đồng bộ nhiều thiết bị. |
| P2 | Presence nhiều tab/thiết bị | Một tab đóng có thể publish offline dù tab khác còn mở. | Presence theo session/device hoặc bộ đếm kết nối có timeout. |
| P2 | Tìm kiếm nâng cao | Hiện tối đa 50 kết quả mới nhất và chưa tải tiếp/nhảy về ngữ cảnh. | Contract/context quanh kết quả hoặc dùng `before_seq` để phân trang kết quả. |
| P2 | Tin nhắn đa phương tiện | Composer chỉ gửi text. | Contract upload/storage, metadata và giới hạn file trước khi làm UI. |
| P2 | Sửa/xóa tin nhắn | Chưa có thao tác. | API/topic, quyền, audit và event cập nhật/xóa realtime. |
| P2 | Thông báo nền | Chưa có browser/push notification. | Quyết định phạm vi notification, quyền người dùng và service push nếu cần. |

## Việc FE có thể làm ngay

1. Thêm phân trang kết quả tìm kiếm bằng `before_seq` và trạng thái tải thêm.
2. Lưu draft/outbox tạm vào IndexedDB để giảm mất dữ liệu khi reload; quy tắc reconcile
   cuối cùng vẫn cần contract sync từ BE.
3. Hoàn thiện loading skeleton, keyboard focus, thông báo lỗi/toast và responsive QA.
4. Bổ sung E2E browser test cho chọn user, mở hội thoại, gửi/retry và tìm kiếm.

## Việc cần chốt với BE trước

1. Auth HTTP + MQTT ACL.
2. API danh sách/chi tiết hội thoại và inbox lời mời.
3. Contract sync offline, delivered/read và typing.
4. API quản lý nhóm, unread cursor và presence nhiều phiên.
5. Có đưa attachment, sửa/xóa tin và notification vào phạm vi đồ án hay không.

## Tiêu chí để gọi là bản hoàn thiện tối thiểu

- Người dùng đăng nhập và không thể giả mạo user khác.
- Đăng nhập trên trình duyệt mới vẫn thấy đủ hội thoại và unread đúng.
- Tin gửi khi mạng chập chờn không mất hoặc nhân đôi; reconnect lấy đủ phần bị bỏ lỡ.
- Có inbox lời mời, trạng thái delivered/read và typing hoạt động qua hai client thật.
- Nhóm có luồng quản lý thành viên/quyền rõ ràng.
- Các luồng chính có test tự động và được kiểm tra với broker/database thật.
