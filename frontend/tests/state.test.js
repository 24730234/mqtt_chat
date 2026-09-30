import test from 'node:test';
import assert from 'node:assert/strict';
import { mergeMessages, reconcileAccepted, normalizeHistory, messageCommand, readCatalog, saveCatalog } from '../src/live/state.js';
const id = '11111111-1111-4111-8111-111111111111';
const pending = { conversation_id: id, client_message_id: 'client', sender_id: 'me', content: 'hello', created_at: '2026-09-29T09:00:00Z', seq: null, status: 'PENDING' };
const accepted = { conversation_id: id, client_message_id: 'client', message_id: 'server', seq: 3, created_at: '2026-09-29T09:00:01Z' };
test('ACK and broadcast in either order reconcile optimistic message once', () => {
  const created = { ...pending, ...accepted, status: 'SENT' };
  const a = mergeMessages(reconcileAccepted([pending], accepted, 'me'), [created, created]);
  const b = reconcileAccepted(mergeMessages([pending], [created]), accepted, 'me');
  assert.equal(a.length, 1); assert.equal(b.length, 1); assert.equal(a[0].seq, 3); assert.equal(b[0].status, 'SENT');
});
test('history lacking client ID then ACK collapses both copies', () => {
  const history = normalizeHistory({ conversation_id: id, messages: [{ message_id: 'server', sender: { user_id: 'me' }, content: 'hello', seq: 3, created_at: accepted.created_at, reply_to: null }] });
  const result = reconcileAccepted(mergeMessages([pending], history), accepted, 'me');
  assert.equal(result.length, 1); assert.equal(result[0].client_message_id, 'client');
});
test('server seq orders messages, pending stays last, late failure cannot downgrade sent', () => {
  const result = mergeMessages([{ ...pending, ...accepted, status: 'SENT' }], [{ ...pending, status: 'FAILED', error: 'late timeout' }, { ...pending, client_message_id: 'other', seq: 2 }]);
  assert.equal(result[0].seq, 2); assert.equal(result[1].seq, 3); assert.equal(result[1].status, 'SENT'); assert.equal(result[1].error, undefined);
});
test('retry command excludes seq, identity and preserves original client ID and reply target', () => {
  const original = { ...pending, reply_to_message_id: 'reply', seq: 999 };
  assert.deepEqual(messageCommand(original), { conversation_id: id, client_message_id: 'client', content: 'hello', reply_to_message_id: 'reply' });
  assert.deepEqual(messageCommand({ ...original, status: 'FAILED' }), messageCommand(original));
});
test('catalog is isolated by API and account; malformed storage recovers', () => {
  const data = new Map(); const storage = { getItem: k => data.get(k), setItem: (k,v) => data.set(k,v) };
  saveCatalog('/api', 'alice', [{ conversation_id: id, members: [] }], storage);
  assert.equal(readCatalog('/api', 'alice', storage).length, 1);
  assert.equal(readCatalog('/api', 'bob', storage).length, 0);
  assert.equal(readCatalog('https://other/api', 'alice', storage).length, 0);
  storage.setItem('mach-live-catalog:/api:alice', '{'); assert.deepEqual(readCatalog('/api', 'alice', storage), []);
});
test('ACK for a different conversation cannot resolve pending message', () => {
  assert.equal(reconcileAccepted([pending], { ...accepted, conversation_id: 'different' }, 'me')[0].status, 'PENDING');
});
