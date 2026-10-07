export const validUuid = (value) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value || '');
export const initials = (name = '?') => name.trim().split(/\s+/).slice(-2).map(word => word[0]).join('').toUpperCase();
export function normalizeHistory(payload) {
  return payload.messages.map(message => ({ ...message, conversation_id: payload.conversation_id, sender_id: message.sender.user_id, reply_to_message_id: message.reply_to?.message_id || null, status: 'SENT' }));
}
function sameMessage(a, b) {
  return a.conversation_id === b.conversation_id && (a.message_id && b.message_id && a.message_id === b.message_id || a.client_message_id && b.client_message_id && a.sender_id === b.sender_id && a.client_message_id === b.client_message_id);
}
export function mergeMessages(current, incoming) {
  let result = [...current];
  for (const message of incoming) {
    const matches = result.filter(item => sameMessage(item, message));
    let combined = Object.assign({}, ...matches, message);
    // A delayed timeout / optimistic state must never downgrade a server-confirmed message.
    if (matches.some(item => item.status === 'SENT') && ['PENDING', 'FAILED'].includes(message.status)) combined = Object.assign({}, ...matches);
    if (combined.status === 'SENT') delete combined.error;
    result = result.filter(item => !sameMessage(item, message));
    result.push(combined);
  }
  return result.sort((a, b) => (a.seq ?? Number.MAX_SAFE_INTEGER) - (b.seq ?? Number.MAX_SAFE_INTEGER) || a.created_at.localeCompare(b.created_at));
}
export function reconcileAccepted(messages, accepted, userId) {
  const pending = messages.find(message => message.sender_id === userId && message.client_message_id === accepted.client_message_id && message.conversation_id === accepted.conversation_id);
  if (!pending) return messages;
  return mergeMessages(messages, [{ ...pending, ...accepted, sender_id: userId, status: 'SENT' }]);
}
export function messageCommand(message) {
  return { conversation_id: message.conversation_id, client_message_id: message.client_message_id, content: message.content, reply_to_message_id: message.reply_to_message_id || null };
}
