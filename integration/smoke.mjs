// Real Django + MySQL + Mosquitto integration; no fixture or mocked transport.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import mqtt from '../frontend/node_modules/mqtt/build/index.js';
import { createApi } from '../frontend/src/live/api.js';
import { createTransport } from '../frontend/src/live/transport.js';
const apiBase = process.env.API_BASE || 'http://127.0.0.1:8000/api';
const mqttUrl = process.env.MQTT_URL || 'ws://127.0.0.1:9001';
const api = createApi(apiBase);
const checks = [];
function pass(name) { checks.push(name); console.log(`PASS ${name}`); }
async function until(check, label, timeout = 15000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { const value = await check(); if (value) return value; await new Promise(r => setTimeout(r, 100)); }
  throw new Error(`Timed out: ${label}`);
}
async function user(username) {
  const result = await api.searchUsers(username);
  return result.users.find(u => u.username === username) || await api.createUser({ username });
}
const [alice, bob, outsider] = await Promise.all(['quang_live', 'thien_live', 'outsider_live'].map(user));
const c = await api.createConversation({ user_id: alice.user_id, type: 'GROUP', name: `Kiểm tra tích hợp ${new Date().toISOString()}`, usernames: [bob.username] });
pass('Create/search users and group through Django');
const clients = [];
function connect(user) {
  const state = { value: '', events: [], presence: [] };
  const client = createTransport({ connect: mqtt.connect, url: mqttUrl, userId: user.user_id,
    onState: value => { state.value = value; }, onEvent: e => state.events.push(e),
    onPresence: (id, value) => state.presence.push({ id, value }) });
  clients.push(client); return { client, state };
}
const a = connect(alice), b = connect(bob);
let bClosed = false;
try {
  await until(() => a.state.value === 'connected' && b.state.value === 'connected', 'MQTT connection');
  a.client.watch(c.conversation_id, [alice.user_id, bob.user_id]);
  b.client.watch(c.conversation_id, [alice.user_id, bob.user_id]);
  await until(() => a.state.value === 'connected' && b.state.value === 'connected', 'SUBACK');
  await until(async () => (await api.searchUsers(alice.username)).users.find(u => u.user_id === alice.user_id)?.status === 'online', 'presence persisted to MySQL');
  pass('Both MQTT clients connected; presence worker persisted online');
  async function send(actor, content, extra = {}) {
    const command = { conversation_id: c.conversation_id, client_message_id: crypto.randomUUID(), content, ...extra };
    const start = actor.state.events.length; actor.client.send(command);
    const ack = await until(() => actor.state.events.slice(start).find(e => e.type === 'MESSAGE_ACCEPTED' && e.client_message_id === command.client_message_id), 'business ACK');
    return { command, ack };
  }
  const first = await send(a, 'Kiểm tra thật: FE → Mosquitto → message worker → MySQL.');
  await until(() => b.state.events.some(e => e.type === 'MESSAGE_CREATED' && e.message_id === first.ack.message_id), 'peer broadcast');
  pass('Message worker ACK and broadcast to second user');
  const retry = await send(a, first.command.content, first.command);
  assert.equal(retry.ack.message_id, first.ack.message_id); assert.equal(retry.ack.seq, first.ack.seq); assert.equal(retry.ack.duplicate, true);
  pass('Retry with same UUID is idempotent');
  const reply = await send(b, 'Đã nhận được tin từ backend thật.', { reply_to_message_id: first.ack.message_id });
  for (let i = 3; i <= 55; i++) await send(a, `Tin kiểm tra phân trang ${i}`);
  const latest = await api.history(c.conversation_id, alice.user_id);
  assert.equal(latest.messages.length, 50);
  const oldestSeq = Math.min(...latest.messages.map(m => m.seq));
  const older = await api.history(c.conversation_id, alice.user_id, oldestSeq);
  assert.equal(older.messages.length, 5);
  const all = [...older.messages, ...latest.messages];
  assert.equal(new Set(all.map(m => m.message_id)).size, 55);
  assert.equal(all.find(m => m.message_id === reply.ack.message_id).reply_to.message_id, first.ack.message_id);
  pass('MySQL-backed HTTP history: 50 + 5 messages, ordered seq, reply and no duplicate');
  const found = await api.searchMessages(c.conversation_id, alice.user_id, 'phân trang 5');
  assert.ok(found.messages.length > 0);
  assert.ok(found.messages.every(m => m.content.toLocaleLowerCase('vi').includes('phân trang 5')));
  pass('Server-side message search returns matching conversation messages');
  await assert.rejects(api.history(c.conversation_id, outsider.user_id), e => e.status === 403);
  pass('History denies non-members with HTTP 403');
  const profile = await api.updateUser(alice.user_id, { short_bio: 'Đã kiểm tra với Django + MySQL + Mosquitto thật' });
  assert.equal(profile.short_bio, 'Đã kiểm tra với Django + MySQL + Mosquitto thật');
  const png = new File([Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=', 'base64')], 'integration.png', { type: 'image/png' });
  const avatar = await api.uploadAvatar(alice.user_id, png);
  assert.ok(avatar.avatar_url);
  const response = await fetch(new URL(avatar.avatar_url, apiBase)); assert.equal(response.status, 200);
  assert.equal((await api.removeAvatar(alice.user_id)).avatar_url, null);
  pass('Profile PATCH and actual avatar upload, media GET and delete');
  b.client.close(); bClosed = true;
  await until(async () => (await api.searchUsers(bob.username)).users.find(u => u.user_id === bob.user_id)?.status === 'offline', 'offline persisted');
  pass('Presence worker persisted offline after client disconnect');
  const result = { timestamp: new Date().toISOString(), apiBase, mqttUrl, conversation_id: c.conversation_id, users: [alice, bob].map(u => ({ username: u.username, user_id: u.user_id })), checks };
  await writeFile(new URL('./.last-run.json', import.meta.url), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} finally { a.client.close(); if (!bClosed) b.client.close(); }
