import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { createTransport } from '../src/live/transport.js';
const uid = '11111111-1111-4111-8111-111111111111', cid = '22222222-2222-4222-8222-222222222222', mid = '33333333-3333-4333-8333-333333333333';
class Client extends EventEmitter {
  connected = true; publications = []; subscriptions = []; rejected = false;
  subscribe(topics, options, callback) { this.subscriptions.push(topics); callback(null, topics.map(topic => ({ topic, qos: this.rejected ? 128 : 1 }))); }
  publish(topic, payload, options, callback) { this.publications.push({ topic, payload, options }); callback?.(null); }
  unsubscribe(topics, callback) { this.unsubscribed = topics; callback?.(null); }
  end(force) { this.ended = force; }
}
function setup(extra = {}) {
  const client = new Client(), events = [], states = [], presence = []; let config;
  const transport = createTransport({ connect: (url, options) => { config = options; return client; }, url: 'ws://localhost:9001', userId: uid, onState: (...args) => states.push(args), onEvent: event => events.push(event), onPresence: (...args) => presence.push(args), ...extra });
  return { client, transport, events, states, presence, config };
}
const message = { conversation_id: cid, client_message_id: mid, content: 'Hello', seq: 99 };
const accepted = { type: 'MESSAGE_ACCEPTED', ...message, message_id: mid, seq: 1, created_at: '2026-09-29T09:00:00Z' };
test('retained will/presence, exact topics, QoS1 and payload without seq', () => {
  const t = setup(); t.transport.watch(cid, [uid]); t.client.emit('connect'); t.transport.send(message);
  assert.equal(t.config.will.payload, 'offline'); assert.equal(t.config.will.retain, true);
  assert.ok(t.client.subscriptions.flat().includes(`chat/conversations/${cid}/event/message_created`));
  assert.ok(t.client.publications.some(p => p.topic === `chat/users/${uid}/status` && p.payload === 'online' && p.options.retain));
  const send = t.client.publications.at(-1); assert.equal(send.options.qos, 1); assert.equal(send.options.retain, false); assert.equal(JSON.parse(send.payload).seq, undefined); assert.equal(t.events.length, 0);
  t.client.emit('message', `chat/client/${uid}/event/message_accepted`, Buffer.from(JSON.stringify(accepted)));
  assert.equal(t.events[0].type, 'MESSAGE_ACCEPTED'); t.transport.close(); assert.equal(t.client.publications.at(-1).payload, 'offline');
});
test('timeout means unconfirmed, retries reuse ID; MQTT PUBACK alone is insufficient', async () => {
  const t = setup({ ackTimeout: 10 }); t.client.emit('connect'); t.transport.send(message);
  await new Promise(resolve => setTimeout(resolve, 25)); assert.equal(t.events[0].type, 'ERROR'); assert.equal(t.events[0].client_message_id, mid);
  t.transport.send(message); const sends = t.client.publications.filter(p => p.topic.endsWith('/send')); assert.equal(sends[0].payload, sends[1].payload); t.transport.close();
});
test('reject malformed events, handle peer presence and reconnect resubscriptions', () => {
  const t = setup(); t.transport.watch(cid, [uid]); t.client.emit('connect');
  t.client.emit('message', `chat/client/${uid}/event/message_accepted`, Buffer.from('{bad'));
  t.client.emit('message', 'unrelated/topic', Buffer.from(JSON.stringify(accepted))); assert.equal(t.events.length, 0);
  t.client.emit('message', `chat/users/${uid}/status`, Buffer.from('offline')); assert.deepEqual(t.presence, [[uid, 'offline']]);
  t.client.emit('offline'); assert.throws(() => t.transport.send(message), /chưa sẵn sàng/);
  const n = t.client.subscriptions.length; t.client.emit('connect'); assert.ok(t.client.subscriptions.length > n); t.transport.close();
});
test('subscription denial does not advertise connected; invalid browser protocol rejected', () => {
  const t = setup(); t.client.rejected = true; t.client.emit('connect'); assert.equal(t.states.at(-1)[0], 'error'); assert.throws(() => t.transport.send(message), /chưa sẵn sàng/); t.transport.close();
  assert.throws(() => setup({ url: 'mqtt://localhost:1883' }), /ws/);
});

test('unwatch removes denied conversation topic, retains shared presence, ignores late broadcasts', () => {
  const t = setup();
  const second = '44444444-4444-4444-8444-444444444444';
  t.transport.watch(cid, [uid]); t.transport.watch(second, [uid]); t.client.emit('connect');
  t.transport.unwatch(cid);
  assert.deepEqual(t.client.unsubscribed, [`chat/conversations/${cid}/event/message_created`]);
  t.client.emit('message', `chat/conversations/${cid}/event/message_created`, Buffer.from(JSON.stringify({ ...accepted, type: 'MESSAGE_CREATED', sender_id: uid, content: 'late' })));
  assert.equal(t.events.length, 0);
  t.transport.unwatch(second);
  assert.ok(t.client.unsubscribed.includes(`chat/users/${uid}/status`));
  t.transport.close();
});
test('removing a rejected conversation recovers sending on remaining subscriptions', () => {
  const t = setup(); t.client.emit('connect');
  t.client.rejected = true; t.transport.watch(cid, [uid]);
  assert.throws(() => t.transport.send(message), /chưa sẵn sàng/);
  t.client.rejected = false; t.transport.unwatch(cid);
  assert.equal(t.states.at(-1)[0], 'connected');
  t.transport.send(message); t.transport.close();
});
test('late subscription callbacks cannot restore readiness after disconnect', () => {
  const t = setup(); let complete;
  t.client.subscribe = (topics, options, callback) => { complete = callback; };
  t.client.emit('connect'); t.client.emit('offline'); complete(null, []);
  assert.equal(t.states.at(-1)[0], 'offline');
  assert.throws(() => t.transport.send(message), /chưa sẵn sàng/);
  assert.equal(t.client.publications.length, 0); t.transport.close();
});
test('ACK for a different conversation cannot cancel the pending timeout', async () => {
  const t = setup({ ackTimeout: 10 }); t.client.emit('connect'); t.transport.send(message);
  t.client.emit('message', `chat/client/${uid}/event/message_accepted`, Buffer.from(JSON.stringify({ ...accepted, conversation_id: uid })));
  await new Promise(resolve => setTimeout(resolve, 25));
  assert.ok(t.events.some(event => event.type === 'ERROR' && event.client_message_id === mid));
  t.transport.close();
});
