# Rà soát tính năng FE và BE

**Ngày rà soát:** 03/10/2026  
**Phạm vi:** Đối chiếu giao diện live trong `frontend/src/live/` với API routes, Django views/services và MQTT worker hiện có.

## Kết luận

FE đã tích hợp được các luồng cơ bản của prototype chat: chọn/tạo người dùng, cập nhật hồ sơ và avatar, tạo hội thoại cá nhân/nhóm, bạn bè/lời mời, tải lịch sử, reply, gửi tin nhắn qua MQTT và presence.

Một số chức năng FE còn thiếu hoặc mới chỉ có hành vi cục bộ. Đặc biệt, API tìm kiếm tin nhắn đã có ở BE nhưng FE chưa sử dụng. Các mục liên quan xác thực, đồng bộ offline, receipts/typing và quản lý hội thoại cần có contract/service phía BE trước khi hoàn thiện.

## Các hạng mục còn thiếu hoặc chưa hoàn chỉnh

| Ưu tiên | Hạng mục | Hiện trạng FE | Hiện trạng BE / phần cần bổ sung |
| --- | --- | --- | --- |
| Cao | Tìm tin nhắn trong toàn bộ hội thoại | Ô tìm kiếm hiện chỉ lọc các tin đã tải vào trình duyệt. Adapter FE chưa có hàm gọi search messages. | Đã có `GET /api/conversations/{conversation_id}/messages/search/`, gồm kiểm tra thành viên và phân trang. Cần nối adapter và UI FE vào endpoint. |
| Cao | Đăng nhập và xác thực danh tính | Live mode cho phép chọn hoặc tạo user; chưa có đăng nhập. | API/MQTT hiện nhận `user_id` từ client, chưa xác thực danh tính hoặc ràng buộc quyền client với user đó. Cần thiết kế auth và cơ chế xác thực MQTT trước khi dùng production. |
| Cao | Đồng bộ offline đầy đủ | Khi reconnect, FE tải lại tối đa 50 tin mới nhất. Không có outbox bền vững; draft và tin chờ xác nhận nằm trong bộ nhớ phiên, có thể mất khi reload. | Chưa có contract đồng bộ tin bị bỏ lỡ theo sequence/cursor. Cần API hoặc MQTT sync command cùng quy tắc phân trang/resume. |
| Trung bình | Danh sách và chi tiết hội thoại | Danh sách hội thoại được lưu cục bộ theo API base và user. Mở hội thoại chưa biết cần nhập UUID; metadata nhóm có thể không đầy đủ. | Chưa có API GET danh sách hội thoại hoặc chi tiết hội thoại/thành viên. |
| Trung bình | Hộp thư lời mời kết bạn | FE gửi lời mời và phản hồi bằng invitation UUID được chia sẻ thủ công. | Có API gửi và phản hồi lời mời, nhưng chưa có API liệt kê lời mời đến/đi hoặc trạng thái pending cho người dùng. |
| Trung bình | Đã nhận / đã đọc | Live UI chỉ xác nhận tin đã được lưu trên server; chưa hiển thị receipt DELIVERED/READ thật. | Model `MessageReceipt` có trạng thái `DELIVERED` và `READ`, nhưng chưa thấy service/API/MQTT handler để tạo, cập nhật và phân phối receipt. |
| Trung bình | Chỉ báo đang nhập | FE chưa gửi/nhận trạng thái typing. | Chưa có topic hoặc contract typing ở BE. |
| Trung bình | Quản lý nhóm sau khi tạo | FE hỗ trợ tạo nhóm và xem thông tin thành viên hiện có. Chưa có thao tác quản lý nhóm. | Chưa có API sửa tên nhóm, thêm/xóa thành viên, rời nhóm hoặc xóa nhóm. |
| Thấp | Unread count bền vững | Unread được tăng từ event nhận trong phiên và đặt về 0 khi mở hội thoại. | Chưa có unread/read state lưu ở BE; số đếm FE có thể mất hoặc lệch sau reload/đăng nhập trên thiết bị khác. |
| Thấp | Presence nhiều tab/thiết bị | FE publish presence theo một topic trên mỗi user, dùng retained online và Last Will offline. | Cách biểu diễn hiện tại có thể đánh dấu user offline khi một trong nhiều tab/thiết bị ngắt kết nối. Cần thống nhất presence theo session hoặc cơ chế đếm kết nối. |

## Đã có tích hợp ở FE

- Tìm user theo username, tạo user và cập nhật hồ sơ.
- Upload/xóa avatar.
- Tạo hội thoại cá nhân hoặc nhóm.
- Xem/xóa bạn; gửi và phản hồi lời mời theo invitation UUID.
- Tải lịch sử có phân trang theo `before_seq`.
- Gửi tin nhắn realtime, reply, nhận ACK/broadcast, chống trùng và retry với cùng client message ID.
- Theo dõi presence và tự reconnect/resubscribe MQTT ở mức cơ bản.

## Thứ tự đề xuất

1. Nối FE vào API tìm kiếm tin nhắn BE đã có và hỗ trợ điều hướng đến kết quả trong lịch sử.
2. Chốt thiết kế xác thực user cho HTTP và MQTT trước khi triển khai ra môi trường chia sẻ/production.
3. Bổ sung API danh sách/chi tiết hội thoại và inbox lời mời để bỏ thao tác nhập UUID thủ công.
4. Chốt contract đồng bộ offline, receipt và typing; sau đó triển khai service/endpoint/topic BE và tích hợp FE.
5. Bổ sung API quản lý thành viên/metadata nhóm và xử lý presence nhiều phiên nếu nằm trong phạm vi sản phẩm.

## Ghi chú phạm vi

Đây là rà soát tĩnh dựa trên mã nguồn hiện có tại thời điểm **03/10/2026**; không phải nghiệm thu end-to-end với Django, database và Mosquitto đang chạy. Các mục được đánh dấu thiếu có nghĩa là chưa thấy luồng triển khai đầy đủ qua các lớp cần thiết, không chỉ dựa trên tên model hoặc tài liệu mô tả.
