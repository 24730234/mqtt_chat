import test from 'node:test';
import assert from 'node:assert/strict';
import { createApi, validateAvatar } from '../src/live/api.js';

function withCsrf(handler) {
  return async (url, options) => {
    if (url === '/api/auth/csrf/') {
      return new Response('{"csrfToken":"csrf-token"}');
    }
    return handler(url, options);
  };
}

test('authenticated requests omit actor IDs and preserve history pagination', async () => {
  const calls = [];
  const api = createApi('/api/', withCsrf(async (url, options) => {
    calls.push([url, options]);
    return new Response('{}');
  }));
  await api.createConversation({ user_id: 'me', type: 'PRIVATE', username: 'Thiên' });
  assert.equal(calls[0][0], '/api/conversations/');
  assert.deepEqual(JSON.parse(calls[0][1].body), { type: 'PRIVATE', username: 'Thiên' });
  assert.equal(calls[0][1].headers['X-CSRFToken'], 'csrf-token');
  assert.equal(calls[0][1].credentials, 'same-origin');

  await api.history('group', 'me', 51);
  assert.equal(calls[1][0], '/api/conversations/group/messages/?limit=50&before_seq=51');
  await api.searchUsers('a&b');
  assert.equal(calls[2][0], '/api/users/search/?username=a%26b');
  await api.searchMessages('group', 'me', 'ready & done', 30);
  assert.equal(calls[3][0], '/api/conversations/group/messages/search/?q=ready+%26+done&limit=50&before_seq=30');
});

test('account APIs register, login, restore and handle bodyless logout', async () => {
  const calls = [];
  const api = createApi('/api', withCsrf(async (url, options) => {
    calls.push([url, options]);
    if (url === '/api/auth/logout/') return new Response(null, { status: 204 });
    return new Response('{"user":{"user_id":"u"}}');
  }));
  await api.register({ username: 'u', password: 'secret', password_confirm: 'secret' });
  assert.equal(calls[0][0], '/api/auth/register/');
  await api.login({ username: 'u', password: 'secret', remember_me: true });
  assert.deepEqual(JSON.parse(calls[1][1].body), { username: 'u', password: 'secret', remember_me: true });
  await api.me();
  assert.equal(calls[2][0], '/api/auth/me/');
  assert.equal(await api.logout(), null);
  assert.equal(calls[3][0], '/api/auth/logout/');
});

test('list and friend endpoints keep authenticated profile-scoped URLs', async () => {
  let requestUrl;
  const api = createApi('/api', async url => {
    requestUrl = url;
    return new Response('{"conversations":[]}');
  });
  assert.deepEqual(await api.listConversations('user/id'), { conversations: [] });
  assert.equal(requestUrl, '/api/users/user%2Fid/conversations/');
  await api.friends('me', { query: 'maker', onlineOnly: true, cursor: 'next-id', limit: 20 });
  assert.equal(requestUrl, '/api/users/me/friends/?limit=20&q=maker&online=true&cursor=next-id');
});

test('room invitation mutations use group versions and do not accept actor IDs', async () => {
  const calls = [];
  const api = createApi('/api', withCsrf(async (url, options) => {
    calls.push([url, options]);
    return new Response('{}', { status: url === '/api/room-invitations/' ? 201 : 200 });
  }));
  await api.inviteRoom('sender', 'recipient', 'group', 4);
  assert.equal(calls[0][0], '/api/room-invitations/');
  assert.deepEqual(JSON.parse(calls[0][1].body), { user_id: 'recipient', conversation_id: 'group' });
  assert.equal(calls[0][1].headers['If-Match'], '"4"');
  await api.respondRoom('invite', 'recipient', 'ACCEPT', 5);
  assert.equal(calls[1][0], '/api/room-invitations/invite/respond/');
  assert.deepEqual(JSON.parse(calls[1][1].body), { status: 'ACCEPT' });
  assert.equal(calls[1][1].headers['If-Match'], '"5"');
});

test('avatar validates size/type and uploads multipart without JSON content type', async () => {
  let request;
  const api = createApi('/api', withCsrf(async (url, options) => {
    request = { url, ...options };
    return new Response('{}');
  }));
  assert.throws(() => validateAvatar({ size: 5 * 1024 * 1024 + 1, type: 'image/png' }), /5 MB/);
  assert.throws(() => validateAvatar({ size: 10, type: 'image/svg+xml' }), /JPEG/);
  const file = new File(['png'], 'avatar.png', { type: 'image/png' });
  await api.uploadAvatar('user', file);
  assert.ok(request.body instanceof FormData);
  assert.equal(request.body.get('avatar').name, 'avatar.png');
  assert.equal(request.headers['Content-Type'], undefined);
});

test('401 invokes the session-expired handler and 204 does not parse JSON', async () => {
  const api = createApi('/api', async () => new Response('{"error":"expired"}', { status: 401 }));
  let expired = 0;
  api.setUnauthorizedHandler(() => { expired += 1; });
  await assert.rejects(api.friends('user'), error => error.status === 401);
  assert.equal(expired, 1);
  const noContent = createApi('/api', withCsrf(async () => new Response(null, { status: 204 })));
  assert.equal(await noContent.logout(), null);
});

test('API errors retain status and malformed proxy responses remain visible', async () => {
  const denied = createApi('/api', async () => new Response('{"error":"not a member"}', { status: 403 }));
  await assert.rejects(denied.history('id', 'user'), error => error.status === 403 && error.message === 'not a member');
  const html = createApi('/api', async () => new Response('<html>Proxy error</html>', { status: 502 }));
  await assert.rejects(html.friends('user'), /không phải JSON/);
  const nullError = createApi('/api', async () => new Response('null', { status: 404 }));
  await assert.rejects(nullError.history('id', 'user'), error => error.status === 404 && error.message === 'API báo lỗi 404');
});
