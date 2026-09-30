// Demo adapter. Replace this adapter when the HTTP/MQTT contract is agreed with BE.
export const currentUser = { user_id: 'quang', username: 'Quang Nguyễn', initials: 'QN', color: 'green', role: 'Frontend developer' };
export const people = [
  { user_id: 'thien', username: 'Thiên Nguyễn', initials: 'TN', color: 'peach', online: true, role: 'Backend developer' },
  { user_id: 'linh', username: 'Linh Trần', initials: 'LT', color: 'violet', online: true, role: 'UI/UX designer' },
  { user_id: 'minh', username: 'Minh Anh', initials: 'MA', color: 'blue', online: false, role: 'Thành viên' },
  { user_id: 'huy', username: 'Hoàng Huy', initials: 'HH', color: 'yellow', online: false, role: 'Thành viên' },
];
const date = new Date(); date.setHours(9, 0, 0, 0);
const at = (minute) => new Date(date.getTime() + minute * 60000).toISOString();
const msg = (id, sender_id, content, minute, conversation_id = 'team') => ({ message_id: id, client_message_id: id, conversation_id, sender_id, content, seq: minute, created_at: at(minute), status: 'READ' });
const seed = {
  conversations: [
    { conversation_id: 'team', name: 'Đồ án MQTT Chat', conversation_type: 'GROUP', initials: 'M', color: 'green', members: ['quang', 'thien', 'linh', 'minh'], unread: 0, pinned: true, description: 'Một nơi để chia sẻ ý tưởng, cùng xây dựng và kết nối. Đồ án ứng dụng chat thời gian thực của chúng mình.', created_at: at(-14400) },
    { conversation_id: 'thien', name: 'Thiên Nguyễn', conversation_type: 'PRIVATE', initials: 'TN', color: 'peach', members: ['quang', 'thien'], unread: 2, pinned: true },
    { conversation_id: 'linh', name: 'Linh Trần', conversation_type: 'PRIVATE', initials: 'LT', color: 'violet', members: ['quang', 'linh'], unread: 1 },
    { conversation_id: 'ideas', name: 'Góc ý tưởng', conversation_type: 'GROUP', initials: '✦', color: 'yellow', members: ['quang', 'linh', 'huy'], unread: 0 },
    { conversation_id: 'minh', name: 'Minh Anh', conversation_type: 'PRIVATE', initials: 'MA', color: 'blue', members: ['quang', 'minh'], unread: 0 },
    { conversation_id: 'huy', name: 'Hoàng Huy', conversation_type: 'PRIVATE', initials: 'HH', color: 'yellow', members: ['quang', 'huy'], unread: 0 },
  ],
  messages: [
    msg('m1', 'thien', 'Chào buổi sáng cả nhà! ☀️\nMình cập nhật một chút tiến độ đồ án nhé.', 12),
    msg('m2', 'thien', 'Cuối tuần mình xong phần BE rồi. Tuần sau cả nhóm call để tích hợp nha anh.', 13),
    msg('m3', 'quang', 'Ok Thiên nhé! Anh đang lên giao diện chat.\nMình giữ mọi thứ đơn giản, dễ dùng trước nha 🙌', 15),
    msg('m4', 'linh', 'Mình thích hướng này! Tông xanh nhìn nhẹ nhàng, hợp với một không gian trò chuyện 🌿', 18),
    msg('m5', 'thien', 'Tuyệt vời! Có gì cần thống nhất về API thì cứ nhắn mình nhé.', 20),
    msg('m6', 'quang', 'Nhất trí. Cùng làm một chiếc app thật xịn nào ✨', 22),
    msg('t1', 'thien', 'Anh ơi, mình chốt format tin nhắn nha.', 24, 'thien'),
    msg('l1', 'linh', 'Mình vừa có vài ý tưởng cho giao diện nè 🌱', 19, 'linh'),
    msg('i1', 'linh', 'Một góc nhỏ cho những ý tưởng lớn ✨', -70, 'ideas'),
    msg('a1', 'minh', 'Ok anh, để em test thêm nhé!', -130, 'minh'),
    msg('h1', 'huy', 'Hẹn cả nhóm vào buổi call tuần sau 👋', -1400, 'huy'),
  ],
};
const key = 'mach-chat-demo-v1';
export const chatService = {
  load() {
    try { const data = JSON.parse(localStorage.getItem(key)); if (data && Array.isArray(data.conversations) && data.conversations.length && Array.isArray(data.messages)) return data; } catch { /* First visit or unavailable storage. */ }
    return structuredClone(seed);
  },
  save(data) { try { localStorage.setItem(key, JSON.stringify(data)); return true; } catch { return false; } },
  makeMessage(conversation_id, sender_id, content, seq) {
    const id = crypto.randomUUID();
    return { message_id: id, client_message_id: id, conversation_id, sender_id, content, seq, created_at: new Date().toISOString(), status: 'SENT' };
  },
};
