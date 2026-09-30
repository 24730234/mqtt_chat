// Isolated FE acceptance fixture. This is NOT Django/MySQL/Mosquitto and must never be used in production.
import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { WebSocketServer } from 'ws';
import mqttPacket from 'mqtt-packet';
const alice = '11111111-1111-4111-8111-111111111111', bob = '22222222-2222-4222-8222-222222222222', group = '33333333-3333-4333-8333-333333333333';
const users = new Map([[alice, { user_id: alice, username: 'quang_fixture', status: 'offline', avatar_url: null, short_bio: 'Frontend test account', bio: '', sex: null }], [bob, { user_id: bob, username: 'thien_fixture', status: 'online', avatar_url: null, short_bio: 'Backend test account', bio: '', sex: null }]]);
const conversations = new Map([[group, { conversation_id: group, type: 'GROUP', name: 'Nhóm kiểm thử phân trang', members: [...users.values()] }]]);
const messages = Array.from({ length: 55 }, (_, i) => ({ conversation_id: group, message_id: randomUUID(), client_message_id: randomUUID(), sender_id: bob, content: `Tin lịch sử ${i + 1}`, seq: i + 1, created_at: new Date(Date.now() - (55 - i) * 60000).toISOString(), reply_to_message_id: null }));
const clients = new Set();
const broker = new WebSocketServer({ host: '127.0.0.1', port: 19001 });
function broadcast(topic, event) { for (const client of clients) if (client.topics.has(topic) && client.ws.readyState === 1) client.ws.send(mqttPacket.generate({ cmd: 'publish', qos: 0, topic, payload: typeof event === 'string' ? event : JSON.stringify(event) })); }
broker.on('connection', ws => {
  const client = { ws, topics: new Set() }; clients.add(client); const parser = mqttPacket.parser();
  ws.on('message', bytes => parser.parse(bytes)); ws.on('close', () => clients.delete(client));
  parser.on('error', () => ws.close());
  parser.on('packet', packet => {
    if (packet.cmd === 'connect') ws.send(mqttPacket.generate({ cmd: 'connack', returnCode: 0, sessionPresent: false }));
    if (packet.cmd === 'subscribe') { packet.subscriptions.forEach(s => client.topics.add(s.topic)); ws.send(mqttPacket.generate({ cmd: 'suback', messageId: packet.messageId, granted: packet.subscriptions.map(s => s.qos) })); }
    if (packet.cmd === 'pingreq') ws.send(mqttPacket.generate({ cmd: 'pingresp' }));
    if (packet.cmd === 'disconnect') ws.close();
    if (packet.cmd !== 'publish') return;
    if (packet.qos === 1) ws.send(mqttPacket.generate({ cmd: 'puback', messageId: packet.messageId }));
    if (/^chat\/users\/.+\/status$/.test(packet.topic)) { const user = users.get(packet.topic.split('/')[2]); if (user) user.status = packet.payload.toString(); broadcast(packet.topic, packet.payload.toString()); return; }
    if (!packet.topic.endsWith('/command/send')) return;
    const sender_id = packet.topic.split('/')[2]; let command;
    try { command = JSON.parse(packet.payload.toString()); } catch { return; }
    const c = conversations.get(command.conversation_id);
    if (!c?.members.some(p => p.user_id === sender_id)) { broadcast(`chat/client/${sender_id}/event/error`, { type: 'ERROR', client_message_id: command.client_message_id, error: 'sender is not a member of this conversation' }); return; }
    if (command.content === '[timeout]') return;
    let message = messages.find(m => m.sender_id === sender_id && m.client_message_id === command.client_message_id); const duplicate = !!message;
    if (!message) { message = { ...command, sender_id, message_id: randomUUID(), seq: Math.max(0, ...messages.filter(m => m.conversation_id === command.conversation_id).map(m => m.seq)) + 1, created_at: new Date().toISOString() }; messages.push(message); }
    const ack = { type: 'MESSAGE_ACCEPTED', client_message_id: message.client_message_id, message_id: message.message_id, conversation_id: message.conversation_id, seq: message.seq, created_at: message.created_at, duplicate };
    broadcast(`chat/client/${sender_id}/event/message_accepted`, ack);
    if (!duplicate) broadcast(`chat/conversations/${message.conversation_id}/event/message_created`, { ...ack, type: 'MESSAGE_CREATED', sender_id, content: message.content, reply_to_message_id: message.reply_to_message_id });
  });
});
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1:18000');
  res.setHeader('Access-Control-Allow-Origin', '*'); res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS'); res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.end(); return; }
  const json = (value, status = 200) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(value)); };
  let raw = ''; for await (const chunk of req) raw += chunk;
  let body = {}; try { body = raw ? JSON.parse(raw) : {}; } catch { /* multipart fixture */ }
  const path = url.pathname;
  if (path === '/api/users/search/') return json({ users: [...users.values()].filter(p => p.username.includes(url.searchParams.get('username') || '')) });
  if (path === '/api/users/' && req.method === 'POST') { if ([...users.values()].some(p => p.username === body.username)) return json({ error: 'username already exists' }, 409); const user = { ...body, user_id: randomUUID(), status: 'offline', avatar_url: null }; users.set(user.user_id, user); return json(user, 201); }
  const userPath = /^\/api\/users\/([^/]+)\/$/.exec(path);
  if (userPath && req.method === 'PATCH') { const user = users.get(userPath[1]); if (!user) return json({ error: 'user not found' }, 404); Object.assign(user, body); return json(user); }
  if (/\/friends\/$/.test(path)) return json({ friends: [users.get(bob)] });
  if (path === '/api/invitations/') return json({ invitation_id: randomUUID(), ...body, status: 'PENDING', send_time: new Date().toISOString() }, 201);
  if (/\/respond\/$/.test(path)) return json({ status: body.status, invitation_id: path.split('/')[3] });
  if (path === '/api/conversations/' && req.method === 'POST') {
    const members = [users.get(body.user_id), ...(body.type === 'PRIVATE' ? [body.username] : body.usernames).map(name => [...users.values()].find(p => p.username === name))];
    if (members.some(p => !p)) return json({ error: 'user not found' }, 404);
    let c = body.type === 'PRIVATE' && [...conversations.values()].find(c => c.type === 'PRIVATE' && c.members.every(p => members.some(m => m.user_id === p.user_id)));
    if (!c) { c = { conversation_id: randomUUID(), type: body.type, name: body.name || null, members }; conversations.set(c.conversation_id, c); } return json(c, 201);
  }
  const historyPath = /^\/api\/conversations\/([^/]+)\/messages\/$/.exec(path);
  if (historyPath) {
    const c = conversations.get(historyPath[1]); if (!c) return json({ error: 'conversation not found' }, 404);
    if (!c.members.some(p => p.user_id === url.searchParams.get('user_id'))) return json({ error: 'user is not a member of this conversation' }, 403);
    const before = Number(url.searchParams.get('before_seq')) || Infinity;
    return json({ conversation_id: c.conversation_id, messages: messages.filter(m => m.conversation_id === c.conversation_id && m.seq < before).slice(-50).map(m => ({ message_id: m.message_id, content: m.content, seq: m.seq, created_at: m.created_at, sender: users.get(m.sender_id), reply_to: m.reply_to_message_id ? messages.find(other => other.message_id === m.reply_to_message_id) : null })) });
  }
  json({ error: 'Fixture endpoint not implemented' }, 404);
});
server.listen(18000, '127.0.0.1', () => console.log('FE TEST FIXTURE ONLY: HTTP 18000, MQTT WebSocket 19001. Accounts quang_fixture / thien_fixture. Group UUID:', group));
