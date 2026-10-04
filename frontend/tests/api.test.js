import test from 'node:test';
import assert from 'node:assert/strict';
import { createApi, validateAvatar } from '../src/live/api.js';
test('conversation and history requests follow Django field names and pagination', async () => {
  const calls = []; const api = createApi('/api/', async (url, options) => { calls.push([url, options]); return new Response('{}'); });
  await api.createConversation({ user_id: 'me', type: 'PRIVATE', username: 'Thiên' });
  assert.equal(calls[0][0], '/api/conversations/');
  assert.deepEqual(JSON.parse(calls[0][1].body), { user_id: 'me', type: 'PRIVATE', username: 'Thiên' });
  await api.history('group', 'me', 51);
  assert.equal(calls[1][0], '/api/conversations/group/messages/?user_id=me&limit=50&before_seq=51');
  await api.searchUsers('a&b'); assert.equal(calls[2][0], '/api/users/search/?username=a%26b');
  await api.searchMessages('group', 'me', 'ready & done', 30);
  assert.equal(calls[3][0], '/api/conversations/group/messages/search/?user_id=me&q=ready+%26+done&limit=50&before_seq=30');
});
test('avatar validates size/type and uploads multipart field avatar without JSON content type', async () => {
  let request; const api = createApi('/api', async (url, options) => { request = { url, ...options }; return new Response('{}'); });
  assert.throws(() => validateAvatar({ size: 5*1024*1024+1, type: 'image/png' }), /5 MB/);
  assert.throws(() => validateAvatar({ size: 10, type: 'image/svg+xml' }), /JPEG/);
  const file = new File(['png'], 'avatar.png', { type: 'image/png' }); await api.uploadAvatar('user', file);
  assert.ok(request.body instanceof FormData); assert.equal(request.body.get('avatar').name, 'avatar.png'); assert.equal(request.headers['Content-Type'], undefined);
});
test('API error message, status and malformed proxy HTML are surfaced', async () => {
  const denied = createApi('/api', async () => new Response(JSON.stringify({ error: 'not a member' }), { status: 403 }));
  await assert.rejects(denied.history('id', 'user'), error => error.status === 403 && error.message === 'not a member');
  const html = createApi('/api', async () => new Response('<html>Proxy error</html>', { status: 502 }));
  await assert.rejects(html.friends('user'), /không phải JSON/);
});
test('null JSON error body retains the HTTP status for recovery', async () => {
  const api = createApi('/api', async () => new Response('null', { status: 404 }));
  await assert.rejects(api.history('id', 'user'), error => error.status === 404 && error.message === 'API báo lỗi 404');
});
