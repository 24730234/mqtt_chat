import { messageCommand, validUuid } from './state.js';
export function createTransport({ connect, url, userId, username, password, onState, onEvent, onReady, onPresence, ackTimeout = 15000 }) {
  if (!/^wss?:\/\//.test(url)) throw new Error('Trình duyệt cần địa chỉ MQTT ws:// hoặc wss://.');
  if (!validUuid(userId)) throw new Error('User ID không hợp lệ.');
  const statusTopic = `chat/users/${userId}/status`;
  let stopped = false;
  let ready = false;
  let subscriptionVersion = 0;
  let notifyReady = false;
  const watched = new Map();
  const presenceWatched = new Set();
  const pending = new Map();
  const client = connect(url, {
    clientId: `mach-${crypto.randomUUID()}`, clean: true, reconnectPeriod: 2000, connectTimeout: 10000,
    resubscribe: false, queueQoSZero: false,
    ...(username ? { username, password } : {}),
    will: { topic: statusTopic, payload: 'offline', qos: 1, retain: true },
  });
  function update(state, error = '') { if (!stopped) onState(state, error); }
  function presenceUserIds() {
    return new Set([...presenceWatched, ...[...watched.values()].flat()]);
  }
  function topics() {
    return [...new Set([`chat/client/${userId}/event/message_accepted`, `chat/client/${userId}/event/error`,
      ...[...watched.keys()].map(id => `chat/conversations/${id}/event/message_created`),
      ...[...watched.keys()].map(id => `chat/conversations/${id}/event/message_read`),
      ...[...presenceUserIds()].map(id => `chat/users/${id}/status`)])];
  }
  function updateSubscriptions(previousTopics) {
    const currentTopics = topics();
    const currentSet = new Set(currentTopics);
    const removed = previousTopics.filter(topic => !currentSet.has(topic));
    if (client.connected && removed.length) {
      client.unsubscribe(removed, error => { if (error) update('error', error.message); });
    }
    if (client.connected && previousTopics.join('\n') !== currentTopics.join('\n')) {
      synchronize();
    }
  }
  function synchronize() {
    const version = ++subscriptionVersion;
    const current = () => !stopped && client.connected && version === subscriptionVersion;
    ready = false;
    update('connecting');
    client.subscribe(topics(), { qos: 1 }, (error, grants) => {
      if (!current()) return;
      if (error || grants?.some(grant => grant.qos >= 128)) { ready = false; update('error', error?.message || 'Broker từ chối quyền subscribe. Kiểm tra ACL.'); return; }
      client.publish(statusTopic, 'online', { qos: 1, retain: true }, error => {
        if (!current()) return;
        if (error) { update('error', error.message); return; }
        ready = true; update('connected');
        if (notifyReady) { notifyReady = false; onReady?.(); }
      });
    });
  }
  client.on('connect', () => { notifyReady = true; synchronize(); });
  function disconnected(state, error) { ++subscriptionVersion; ready = false; update(state, error); }
  client.on('reconnect', () => disconnected('reconnecting'));
  client.on('offline', () => disconnected('offline'));
  client.on('close', () => disconnected('offline'));
  client.on('error', error => disconnected('error', error.message));
  client.on('message', (topic, bytes) => {
    if (stopped) return;
    const text = bytes.toString();
    const presence = /^chat\/users\/([^/]+)\/status$/.exec(topic);
    if (presence && presenceUserIds().has(presence[1]) && ['online', 'offline'].includes(text)) { onPresence?.(presence[1], text); return; }
    let event;
    try { event = JSON.parse(text); } catch { return; }
    if (!event || typeof event !== 'object') return;
    const isAccepted = topic === `chat/client/${userId}/event/message_accepted` && event.type === 'MESSAGE_ACCEPTED';
    const isError = topic === `chat/client/${userId}/event/error` && event.type === 'ERROR';
    const isCreated = watched.has(event.conversation_id) && topic === `chat/conversations/${event.conversation_id}/event/message_created` && event.type === 'MESSAGE_CREATED';
    const isRead = watched.has(event.conversation_id) && topic === `chat/conversations/${event.conversation_id}/event/message_read` && event.type === 'MESSAGE_READ';
    if (!(isAccepted || isError || isCreated || isRead)) return;
    if ((isAccepted || isCreated) && (!validUuid(event.message_id) || !validUuid(event.conversation_id) || !validUuid(event.client_message_id) || !Number.isSafeInteger(event.seq) || event.seq < 1 || !Number.isFinite(Date.parse(event.created_at)))) return;
    if (isCreated && (!validUuid(event.sender_id) || typeof event.content !== 'string')) return;
    if (isRead && (!validUuid(event.reader_id) || !Array.isArray(event.message_ids) || !event.message_ids.length || event.message_ids.some(id => !validUuid(id)))) return;
    const own = isAccepted || isError || isCreated && event.sender_id === userId;
    if (own && event.client_message_id) {
      const entry = pending.get(event.client_message_id);
      if (entry && (isError || entry.conversationId === event.conversation_id)) {
        clearTimeout(entry.timer); pending.delete(event.client_message_id);
      }
    }
    onEvent(event);
  });
  update('connecting');
  return {
    isReady() { return ready && client.connected; },
    isWatching(conversationId) { return watched.has(conversationId); },
    watch(conversationId, memberIds = []) {
      if (!validUuid(conversationId)) throw new Error('Conversation ID không hợp lệ.');
      const previous = topics();
      watched.set(conversationId, memberIds.filter(validUuid));
      if (client.connected && previous.join('\n') === topics().join('\n') && !ready) synchronize();
      else updateSubscriptions(previous);
    },
    unwatch(conversationId) {
      const previous = topics();
      watched.delete(conversationId);
      updateSubscriptions(previous);
    },
    watchPresence(userIds = []) {
      const previous = topics();
      presenceWatched.clear();
      userIds.filter(validUuid).forEach(id => presenceWatched.add(id));
      updateSubscriptions(previous);
    },
    send(message) {
      if (!ready || !client.connected) throw new Error('MQTT chưa sẵn sàng. Hãy đợi kết nối rồi gửi lại.');
      const command = messageCommand(message);
      clearTimeout(pending.get(command.client_message_id)?.timer);
      const failed = error => {
        if (stopped || !pending.has(command.client_message_id)) return;
        clearTimeout(pending.get(command.client_message_id)?.timer); pending.delete(command.client_message_id);
        onEvent({ type: 'ERROR', client_message_id: command.client_message_id, error });
      };
      pending.set(command.client_message_id, { conversationId: command.conversation_id, timer: setTimeout(() => failed('Chưa nhận xác nhận từ BE. Có thể tin đã được lưu; gửi lại dùng cùng mã để tránh trùng.'), ackTimeout) });
      // MQTT PUBACK is not database confirmation; wait for MESSAGE_ACCEPTED / own MESSAGE_CREATED.
      client.publish(`chat/client/${userId}/command/send`, JSON.stringify(command), { qos: 1, retain: false }, error => { if (error) failed(error.message); });
    },
    markRead(conversationId, messageIds) {
      if (!ready || !client.connected) throw new Error('MQTT chưa sẵn sàng để đồng bộ trạng thái đã đọc.');
      if (!watched.has(conversationId) || !validUuid(conversationId)) throw new Error('Hội thoại chưa được đăng ký nhận tin nhắn.');
      const ids = [...new Set(messageIds)].filter(validUuid).slice(0, 100);
      if (!ids.length) return;
      client.publish(`chat/client/${userId}/command/read`, JSON.stringify({
        conversation_id: conversationId,
        message_ids: ids,
      }), { qos: 1, retain: false }, error => {
        if (error) update('error', error.message);
      });
    },
    close() {
      stopped = true; ready = false;
      pending.forEach(entry => clearTimeout(entry.timer)); pending.clear();
      if (!client.connected) { client.end(true); return; }
      const fallback = setTimeout(() => client.end(true), 1000);
      client.publish(statusTopic, 'offline', { qos: 1, retain: true }, () => { clearTimeout(fallback); client.end(false); });
    },
  };
}
