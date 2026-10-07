import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import mqtt from 'mqtt';
import { Radio, ArrowLeft, Plus, Search, Send, Users, MessageCircle, X, RefreshCw, Reply, Check, LogOut, Upload, Trash2, UserPlus, UserMinus, Mail, Info, ChevronLeft, ChevronRight } from 'lucide-react';
import { createApi, avatarUrl } from './api.js';
import { createTransport } from './transport.js';
import { initials, validUuid, normalizeHistory, mergeMessages, reconcileAccepted } from './state.js';
import './live.css';
import './read-receipts.css';

const env = import.meta.env;
const initialConfig = { apiBase: env.VITE_API_BASE || '/api', mqttUrl: env.VITE_MQTT_URL || 'ws://127.0.0.1:9001', mqttUsername: '', mqttPassword: '' };
const configKey = 'mach-live-connection-v1';
const noIds = [];
function restoreConfig() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(configKey) || '{}');
    return { ...initialConfig, ...(typeof saved.apiBase === 'string' ? { apiBase: saved.apiBase } : {}), ...(typeof saved.mqttUrl === 'string' ? { mqttUrl: saved.mqttUrl } : {}) };
  } catch { return initialConfig; }
}
const localPreview = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
const clock = value => new Date(value).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
const sortConversations = conversations => [...conversations].sort((a, b) => {
  const aLastMessage = a.last_message ? Date.parse(a.last_message.created_at) : null;
  const bLastMessage = b.last_message ? Date.parse(b.last_message.created_at) : null;
  if (aLastMessage !== null && bLastMessage !== null) return bLastMessage - aLastMessage;
  if (aLastMessage !== null) return -1;
  if (bLastMessage !== null) return 1;
  return Date.parse(b.created_at) - Date.parse(a.created_at);
});
function normalizeConversationLastMessages(conversations) {
  return conversations.flatMap(conversation => conversation.last_message ? [{
    ...conversation.last_message,
    conversation_id: conversation.conversation_id,
    sender_id: conversation.last_message.sender.user_id,
    reply_to: null,
    reply_to_message_id: null,
    status: 'SENT',
  }] : []);
}
function Avatar({ user = {}, large = false, apiBase }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [user.avatar_url]);
  const src = avatarUrl(user.avatar_url, apiBase);
  return <span className={`avatar green ${large ? 'large' : ''}`}>{src && !failed ? <img src={src} alt={`Ảnh của ${user.username || 'người dùng'}`} onError={() => setFailed(true)}/> : initials(user.username || user.name || '?')}{user.status === 'online' && <i className="online-dot"/>}</span>;
}
function ErrorBox({ error }) { return error ? <div className="live-error" role="alert"><Info size={17}/>{error}</div> : null; }
function Modal({ title, close, children }) {
  const ref = useRef(null);
  useEffect(() => { ref.current.showModal(); }, []);
  return <dialog ref={ref} onCancel={close} onClick={event => { if (event.target === ref.current) close(); }}><div className="modal-heading"><h2>{title}</h2><button className="icon-button" onClick={close} aria-label="Đóng"><X size={20}/></button></div>{children}</dialog>;
}
function UserSearch({ api, apiBase, exclude, excludeIds = noIds, onSelect, selected = [], actionLabel }) {
  const [query, setQuery] = useState('');
  const [users, setUsers] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    setUsers([]); setError('');
    if (!query.trim()) { setLoading(false); return; }
    const controller = new AbortController(); setLoading(true);
    const timeout = setTimeout(() => { controller.abort(); setLoading(false); setError('Tìm kiếm quá thời gian. Hãy thử lại.'); }, 15000);
    const timer = setTimeout(async () => {
      try { const result = await api.searchUsers(query, controller.signal); if (!controller.signal.aborted) setUsers(result.users.filter(u => u.user_id !== exclude && !excludeIds.includes(u.user_id))); }
      catch (error) { if (!controller.signal.aborted) setError(error.message); }
      finally { clearTimeout(timeout); if (!controller.signal.aborted) setLoading(false); }
    }, 250);
    return () => { controller.abort(); clearTimeout(timer); clearTimeout(timeout); };
  }, [query, api, exclude, excludeIds]);
  return <div className="user-search"><label className="form-label">Tìm theo username<input value={query} maxLength={100} onChange={event => setQuery(event.target.value)} placeholder="Nhập tên người dùng..."/></label><ErrorBox error={error}/>{loading && <p className="muted" role="status">Đang tìm người dùng…</p>}<div className="people-picker">{users.map(user => <button type="button" key={user.user_id} onClick={() => onSelect(user)} className={selected.includes(user.user_id) ? 'selected' : ''}><Avatar user={user} apiBase={apiBase}/><span>{user.username}<small>{user.short_bio || 'Thành viên'}</small></span>{actionLabel ? <span className="people-action">{actionLabel}</span> : selected.includes(user.user_id) && <Check size={16}/>}</button>)}</div>{query && !loading && !users.length && !error && <p className="muted">Không tìm thấy người dùng.</p>}</div>;
}
export default function LiveApp({ onDemo }) {
  const [config, setConfig] = useState(restoreConfig);
  useEffect(() => {
    try { sessionStorage.setItem(configKey, JSON.stringify({ apiBase: config.apiBase, mqttUrl: config.mqttUrl })); } catch { /* Connection stays usable when storage is unavailable. */ }
  }, [config.apiBase, config.mqttUrl]);
  const [session, setSession] = useState(null);
  const [username, setUsername] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const api = useMemo(() => createApi(config.apiBase), [config.apiBase]);
  async function create(event) {
    event.preventDefault(); setBusy(true); setError('');
    try { const user = await api.createUser({ username: username.trim() }); setSession(user); }
    catch (error) { setError(error.message); } finally { setBusy(false); }
  }
  if (session) return <Workspace key={`${config.apiBase}:${session.user_id}`} initialUser={session} config={config} api={api} onExit={() => setSession(null)} onDemo={onDemo}/>;
  return <main className="live-setup"><div className="setup-brand"><span className="brand-mark"><Radio size={28}/></span><span className="wordmark">mạch<span>•</span></span><button className="text-button" onClick={onDemo}><ArrowLeft size={15}/> Xem bản demo</button></div><div className="setup-grid"><section className="setup-intro"><span className="eyebrow">KHÔNG GIAN KẾT NỐI</span><h1>Chuyện trò thật.<br/>Kết nối ngay.</h1><p>Chọn người dùng của nhóm và bắt đầu trò chuyện trên backend MQTT Chat.</p><div className="setup-note"><Info size={19}/><p>Phiên tích hợp dành cho nhóm phát triển. Backend hiện dùng UUID để xác định người dùng, chưa có đăng nhập hoặc xác thực tài khoản.</p></div><details><summary>Cấu hình kết nối</summary><label className="form-label">API base<input value={config.apiBase} onChange={e => setConfig({ ...config, apiBase: e.target.value })}/></label><label className="form-label">MQTT WebSocket URL<input value={config.mqttUrl} onChange={e => setConfig({ ...config, mqttUrl: e.target.value })}/></label><label className="form-label">MQTT username<input autoComplete="off" value={config.mqttUsername} onChange={e => setConfig({ ...config, mqttUsername: e.target.value })}/></label><label className="form-label">MQTT password<input type="password" autoComplete="off" value={config.mqttPassword} onChange={e => setConfig({ ...config, mqttPassword: e.target.value })}/></label><p className="muted">Địa chỉ API/MQTT được nhớ trong tab này khi tải lại. Username/password broker chỉ giữ trong bộ nhớ. Broker cần listener WebSocket và ACL phù hợp.</p></details></section><section className="setup-card"><h2>Chọn người dùng</h2>{localPreview && <div className="fixture-choice"><button type="button" className="text-button" onClick={() => { setConfig({ ...initialConfig, apiBase: "http://127.0.0.1:18000/api", mqttUrl: "ws://127.0.0.1:19001" }); setError(""); }}>Dùng server test</button><small>quang_fixture / thien_fixture · Cần bật server test local</small></div>}<p className="muted">Tìm username đã được tạo trên backend.</p><UserSearch api={api} apiBase={config.apiBase} onSelect={setSession}/><div className="setup-or">HOẶC TẠO NGƯỜI DÙNG</div><form onSubmit={create}><label className="form-label">Username mới<input required maxLength={100} value={username} onChange={e => setUsername(e.target.value)} placeholder="Ví dụ: quang_fe"/></label><ErrorBox error={error}/><button className="primary-button" disabled={busy || !username.trim()}>{busy ? 'Đang tạo…' : 'Tạo người dùng và tiếp tục'}<UserPlus size={17}/></button></form></section></div></main>;
}
function Workspace({ initialUser, api, config, onExit, onDemo }) {
  const [user, setUser] = useState(initialUser);
  const [module, setModule] = useState('chats');
  const [incomingInvitationCount, setIncomingInvitationCount] = useState(0);
  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [active, setActive] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [filter, setFilter] = useState('all');
  const [connection, setConnection] = useState('connecting');
  const [transportInitialized, setTransportInitialized] = useState(false);
  const [connectionError, setConnectionError] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState({});
  const [older, setOlder] = useState({});
  const [historyErrors, setHistoryErrors] = useState({});
  const [historyStatus, setHistoryStatus] = useState({});
  const [hiddenConversation, setHiddenConversation] = useState(null);
  const [verified, setVerified] = useState({});
  const [modal, setModal] = useState(null);
  const [details, setDetails] = useState(false);
  const [presence, setPresence] = useState({});
  const transport = useRef(null);
  const alive = useRef(false);
  const catalogRef = useRef(conversations);
  const activeRef = useRef(active);
  const list = useRef(null);
  const shouldScroll = useRef(false);
  const inflight = useRef(new Set());
  const seenEvents = useRef(new Set());
  const pendingReads = useRef(new Map());
  const queuedReads = useRef(new Set());
  catalogRef.current = conversations; activeRef.current = active;
  const current = conversations.find(c => c.conversation_id === active);
  const draft = drafts[active] || { text: '', reply: null };
  const displayed = messages.filter(m => m.conversation_id === active);
  const visibleMessages = search.trim() ? searchResults : displayed;
  const merge = incoming => setMessages(prev => mergeMessages(prev, incoming));
  const watchPresence = useCallback(userIds => {
    transport.current?.watchPresence(userIds);
  }, []);
  function flushReadQueue() {
    if (!transport.current?.isReady()) return;
    for (const [conversationId, ids] of pendingReads.current) {
      if (!transport.current.isWatching(conversationId)) continue;
      transport.current.markRead(conversationId, [...ids]);
    }
  }
  function queueVisibleReads(conversationId, messageIds) {
    let pending = pendingReads.current.get(conversationId);
    if (!pending) {
      pending = new Set();
      pendingReads.current.set(conversationId, pending);
    }
    for (const id of messageIds) {
      const key = `${conversationId}:${id}`;
      if (!queuedReads.current.has(key)) {
        queuedReads.current.add(key);
        pending.add(id);
      }
    }
    flushReadQueue();
  }
  useEffect(() => {
    setSearchResults([]); setSearchError('');
    const term = search.trim();
    if (!active || !term) { setSearchLoading(false); return; }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const result = await api.searchMessages(active, user.user_id, term, null, controller.signal);
        if (!controller.signal.aborted) setSearchResults(normalizeHistory(result));
      } catch (error) {
        if (!controller.signal.aborted) setSearchError(error.message);
      } finally {
        if (!controller.signal.aborted) setSearchLoading(false);
      }
    }, 300);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [search, active, api, user.user_id]);
  function watch(c) { transport.current?.watch(c.conversation_id, c.members.map(member => member.user_id)); }
  async function loadHistory(c, before) {
    const id = c.conversation_id;
    if (inflight.current.has(id)) return;
    inflight.current.add(id); setLoading(prev => ({ ...prev, [id]: true })); setHistoryErrors(prev => ({ ...prev, [id]: '' }));
    const previousHeight = list.current?.scrollHeight || 0;
    const previousTop = list.current?.scrollTop || 0;
    try {
      const result = await api.history(id, user.user_id, before);
      if (!alive.current) return;
      const history = normalizeHistory(result); merge(history);
      setVerified(prev => ({ ...prev, [id]: true }));
      setHistoryStatus(prev => ({ ...prev, [id]: 200 }));
      if (before || !messages.some(m => m.conversation_id === id)) setOlder(prev => ({ ...prev, [id]: result.messages.length === 50 }));
      watch(c);
      if (before && activeRef.current === id) requestAnimationFrame(() => { if (list.current) list.current.scrollTop = previousTop + list.current.scrollHeight - previousHeight; });
      else if (activeRef.current === id) shouldScroll.current = true;
    } catch (error) {
      if (alive.current) {
        const reason = error.status === 404 ? 'Hội thoại không còn trên server này. Nếu server test vừa khởi động lại, dữ liệu test cũ đã được đặt lại.' : error.status === 403 ? 'Bạn không có quyền đọc hội thoại này. Liên hệ người tạo nhóm để kiểm tra thành viên.' : error.message;
        setHistoryErrors(prev => ({ ...prev, [id]: reason }));
        setHistoryStatus(prev => ({ ...prev, [id]: error.status }));
        if ([403, 404].includes(error.status)) {
          setVerified(prev => ({ ...prev, [id]: false }));
          transport.current?.unwatch(id);
          setMessages(prev => prev.filter(message => message.conversation_id !== id));
        }
      }
    } finally { inflight.current.delete(id); if (alive.current) setLoading(prev => ({ ...prev, [id]: false })); }
  }
  useEffect(() => {
    alive.current = true;
    try {
      transport.current = createTransport({ connect: mqtt.connect, url: config.mqttUrl, userId: user.user_id, username: config.mqttUsername, password: config.mqttPassword,
        onState: (state, detail) => {
          setConnection(state);
          setConnectionError(detail);
          if (state === 'connected') flushReadQueue();
        },
        onPresence: (id, status) => setPresence(prev => ({ ...prev, [id]: status })),
        onReady: () => { flushReadQueue(); refreshConversationCatalog(); },
        onEvent: event => {
          if (event.type === 'MESSAGE_ACCEPTED') setMessages(prev => reconcileAccepted(prev, event, user.user_id));
          else if (event.type === 'MESSAGE_CREATED') {
            const own = event.sender_id === user.user_id;
            const conversation = catalogRef.current.find(c => c.conversation_id === event.conversation_id);
            const messageSender = conversation?.members.find(member => member.user_id === event.sender_id);
            const lastMessage = {
              ...event,
              sender: messageSender || { user_id: event.sender_id, username: event.sender_id.slice(0, 8) },
              read_by: [],
            };
            setConversations(items => sortConversations(items.map(c => c.conversation_id === event.conversation_id ? {
              ...c,
              last_message: lastMessage,
              unread: !own && !seenEvents.current.has(event.message_id)
                ? (c.unread || 0) + 1
                : c.unread,
            } : c)));
            seenEvents.current.add(event.message_id);
            setMessages(prev => mergeMessages(prev, [{ ...event, status: 'SENT' }]));
            if (event.conversation_id === activeRef.current && list.current && list.current.scrollHeight - list.current.scrollTop - list.current.clientHeight < 160) shouldScroll.current = true;
          } else if (event.type === 'MESSAGE_READ') {
            const member = catalogRef.current.find(c => c.conversation_id === event.conversation_id)?.members.find(item => item.user_id === event.reader_id);
            const pending = pendingReads.current.get(event.conversation_id);
            event.message_ids.forEach(id => {
              queuedReads.current.delete(`${event.conversation_id}:${id}`);
              pending?.delete(id);
            });
            if (pending && !pending.size) pendingReads.current.delete(event.conversation_id);
            if (member) {
              const readIds = new Set(event.message_ids);
              setMessages(prev => prev.map(message => message.conversation_id === event.conversation_id && readIds.has(message.message_id)
                ? { ...message, read_by: [...(message.read_by || []).filter(reader => reader.user_id !== member.user_id), member] }
                : message));
              setConversations(prev => sortConversations(prev.map(conversation => {
                if (conversation.conversation_id !== event.conversation_id) return conversation;
                const lastWasRead = readIds.has(conversation.last_message?.message_id);
                return {
                  ...conversation,
                  unread: event.reader_id === user.user_id
                    ? Math.max(0, (conversation.unread || 0) - readIds.size)
                    : conversation.unread,
                  last_message: lastWasRead
                    ? { ...conversation.last_message, read_by: [...(conversation.last_message.read_by || []).filter(reader => reader.user_id !== member.user_id), member] }
                    : conversation.last_message,
                };
              })));
            }
          } else if (event.type === 'ERROR') {
            if (!event.client_message_id) setError(event.error);
            setMessages(prev => prev.map(m => m.client_message_id === event.client_message_id && m.sender_id === user.user_id && m.status !== 'SENT' ? { ...m, status: 'FAILED', error: event.error } : m));
          }
        },
      });
      setTransportInitialized(true);
    } catch (error) { setConnection('error'); setConnectionError(error.message); }
    return () => { alive.current = false; transport.current?.close(); transport.current = null; setTransportInitialized(false); };
  }, []);
  useEffect(() => {
    let cancelled = false;
    async function loadConversations() {
      try {
        const result = await api.listConversations(user.user_id);
        if (cancelled || !alive.current) return;
        const conversations = sortConversations(result.conversations);
        const normalized = conversations.map(conversation => ({
          ...conversation,
          unread: conversation.unread_count ?? conversation.unread ?? 0,
        }));
        setConversations(normalized);
        merge(normalizeConversationLastMessages(normalized));
        normalized.forEach(conversation => loadHistory(conversation));
      } catch (error) {
        if (!cancelled && alive.current) setError(error.message);
      }
    }
    loadConversations();
    return () => { cancelled = true; };
  }, [api, user.user_id]);
  useEffect(() => { if (shouldScroll.current && list.current) { list.current.scrollTop = list.current.scrollHeight; shouldScroll.current = false; } }, [messages, active]);
  useEffect(() => {
    const root = list.current;
    if (!root || !active || !verified[active] || typeof IntersectionObserver === 'undefined') return undefined;
    const messagesById = new Map(visibleMessages.map(message => [message.message_id, message]));
    const observer = new IntersectionObserver(entries => {
      const visibleIds = entries
        .filter(entry => entry.isIntersecting && entry.intersectionRect.height >= Math.min(
          entry.boundingClientRect.height,
          entry.rootBounds?.height || root.clientHeight,
        ) * 0.5)
        .map(entry => entry.target.dataset.messageId)
        .filter(id => {
          const message = messagesById.get(id);
          return message && message.sender_id !== user.user_id &&
            !(message.read_by || []).some(reader => reader.user_id === user.user_id);
        });
      if (visibleIds.length) queueVisibleReads(active, visibleIds);
    }, { root, threshold: 0.01 });
    root.querySelectorAll('.message-row[data-message-id]').forEach(node => observer.observe(node));
    return () => observer.disconnect();
  }, [active, messages, searchResults, search, verified, user.user_id]);
  function select(c) {
    setActive(c.conversation_id); setSearch(''); setDetails(false); shouldScroll.current = true;
    loadHistory(c);
  }
  function hideConversation(c) {
    transport.current?.unwatch(c.conversation_id);
    pendingReads.current.get(c.conversation_id)?.forEach(id => {
      queuedReads.current.delete(`${c.conversation_id}:${id}`);
    });
    pendingReads.current.delete(c.conversation_id);
    setHiddenConversation(c);
    setConversations(prev => prev.filter(item => item.conversation_id !== c.conversation_id));
    if (active === c.conversation_id) setActive(null);
  }
  function undoHide() {
    if (!hiddenConversation) return;
    setConversations(prev => [...prev.filter(c => c.conversation_id !== hiddenConversation.conversation_id), hiddenConversation]);
    select(hiddenConversation); setHiddenConversation(null);
  }
  function addConversation(c) {
    setModule('chats');
    setConversations(prev => sortConversations([c, ...prev.filter(item => item.conversation_id !== c.conversation_id)]));
    select(c); setModal(null);
    api.listConversations(user.user_id)
      .then(result => {
        const refreshed = result.conversations.map(conversation => ({
          ...conversation,
          unread: conversation.unread_count ?? catalogRef.current.find(item => item.conversation_id === conversation.conversation_id)?.unread ?? 0,
        }));
        setConversations(sortConversations(refreshed));
        merge(normalizeConversationLastMessages(refreshed));
      })
      .catch(error => setError(error.message));
  }
  function refreshConversationCatalog() {
    api.listConversations(user.user_id)
      .then(result => {
        const refreshed = sortConversations(result.conversations.map(conversation => ({
          ...conversation,
          unread: conversation.unread_count ?? catalogRef.current.find(item => item.conversation_id === conversation.conversation_id)?.unread ?? 0,
        })));
        setConversations(refreshed);
        merge(normalizeConversationLastMessages(refreshed));
        refreshed.forEach(conversation => loadHistory(conversation));
      })
      .catch(error => setError(error.message));
  }
  function editDraft(part) { setDrafts(prev => ({ ...prev, [active]: { ...(prev[active] || { text: '', reply: null }), ...part } })); }
  function publish(message) {
    merge([{ ...message, status: 'PENDING', error: undefined }]);
    try { transport.current.send(message); }
    catch (error) { merge([{ ...message, status: 'FAILED', error: error.message }]); }
  }
  function send(event) {
    event.preventDefault();
    if (!draft.text.trim() || connection !== 'connected' || !verified[active]) return;
    const id = crypto.randomUUID();
    const message = { message_id: null, client_message_id: id, conversation_id: active, sender_id: user.user_id, content: draft.text.trim(), created_at: new Date().toISOString(), seq: null, reply_to_message_id: draft.reply?.message_id || null, reply_to: draft.reply ? { message_id: draft.reply.message_id, content: draft.reply.content } : null };
    shouldScroll.current = true; publish(message); editDraft({ text: '', reply: null });
  }
  const members = current?.members || [];
  function sender(id) { const item = id === user.user_id ? user : members.find(p => p.user_id === id) || messages.find(m => m.sender_id === id && m.sender)?.sender || { user_id: id, username: id?.slice(0, 8) || 'Thành viên' }; return { ...item, status: presence[id] || item.status }; }
  const name = c => c.name || (c.type === 'PRIVATE' ? c.members.find(m => m.user_id !== user.user_id)?.username : null) || `Hội thoại ${c.conversation_id.slice(0, 8)}`;
  const statusName = { connecting: 'Đang kết nối MQTT', connected: 'MQTT đã kết nối', reconnecting: 'Đang kết nối lại', offline: 'Mất kết nối MQTT', error: 'Lỗi kết nối MQTT' }[connection];
  const navigateModule = next => { setModule(next); setActive(null); setError(''); };
  const conversationOpened = conversation => { setModule('chats'); addConversation(conversation); };
  useEffect(() => {
    api.invitations(user.user_id)
      .then(result => setIncomingInvitationCount(result.incoming.length + result.room_incoming.length))
      .catch(error => setError(error.message));
  }, [api, user.user_id]);
  return <div className={`live-workspace ${active || module !== 'chats' ? 'has-active' : ''}`}>
    <nav className="rail"><span className="brand-mark"><Radio size={26}/></span><div className="rail-links"><button className={`icon-button ${module === 'chats' ? 'active' : ''}`} aria-label="Danh sách hội thoại" onClick={() => navigateModule('chats')}><MessageCircle size={23}/><span className="rail-label">Tin nhắn</span></button><button className={`icon-button ${module === 'friends' ? 'active' : ''}`} aria-label="Bạn bè" onClick={() => navigateModule('friends')}><Users size={23}/><span className="rail-label">Bạn bè</span></button><button className={`icon-button ${module === 'invitations' ? 'active' : ''}`} aria-label="Lời mời" onClick={() => navigateModule('invitations')}><Mail size={22}/>{incomingInvitationCount > 0 && <b className="rail-badge">{incomingInvitationCount}</b>}<span className="rail-label">Lời mời</span></button></div><div className="rail-bottom"><button className="icon-button" aria-label="Đổi người dùng" onClick={onExit}><LogOut size={21}/></button><button className="profile-button" aria-label="Hồ sơ của bạn" onClick={() => setModal('profile')}><Avatar user={user} apiBase={config.apiBase}/></button></div></nav>
    <aside className="sidebar"><div className="workspace"><div><span className="wordmark">mạch<span>•</span></span><span className="workspace-caption">{user.username}</span></div><button className="demo-tag" onClick={onDemo}>VỀ DEMO</button></div><div className="sidebar-title"><h1>Tin nhắn<span>{conversations.length}</span></h1><button className="icon-button new-chat" aria-label="Cuộc trò chuyện mới" onClick={() => setModal('new')}><Plus size={20}/></button></div><label className="search-box"><Search size={17}/><input placeholder="Tìm hội thoại..." aria-label="Tìm hội thoại" value={query} onChange={e => setQuery(e.target.value)}/></label><div className="filters">{[['all','Tất cả'],['unread','Chưa đọc'],['groups','Nhóm']].map(([id,label]) => <button key={id} className={filter === id ? 'selected' : ''} onClick={() => setFilter(id)}>{label}</button>)}</div><div className="catalog-note">Danh sách đồng bộ từ máy chủ.<button onClick={() => setModal('open')}>Mở bằng mã UUID</button></div><div className="conversation-list">{conversations.filter(c => name(c).toLowerCase().includes(query.toLowerCase()) && (filter !== 'groups' || c.type === 'GROUP') && (filter !== 'unread' || c.unread)).map(c => { const last = messages.filter(m => m.conversation_id === c.conversation_id).at(-1) || c.last_message; return <button className={`conversation ${c.conversation_id === active ? 'selected' : ''} ${c.unread ? 'unread' : ''}`} key={c.conversation_id} onClick={() => select(c)}><Avatar user={{ name: name(c), ...(c.type === 'PRIVATE' ? c.members.find(m => m.user_id !== user.user_id) : {}) }} apiBase={config.apiBase}/><span className="conversation-copy"><span className="conversation-top"><strong>{name(c)}</strong>{last && <time>{clock(last.created_at)}</time>}</span><span className="conversation-preview"><span>{historyStatus[c.conversation_id] === 404 ? 'Không còn trên server' : historyStatus[c.conversation_id] === 403 ? 'Không có quyền truy cập' : last?.content || (loading[c.conversation_id] ? 'Đang tải…' : 'Mở cuộc trò chuyện')}</span>{!!c.unread && <b className="unread-count">{c.unread}</b>}</span></span></button>; })}{!conversations.length && <div className="empty-list"><MessageCircle size={28}/><p>Chưa có hội thoại.<br/>Bắt đầu với một người bạn.</p><button onClick={() => setModal('new')}>Trò chuyện mới</button></div>}</div><div className={`local-status ${connection !== 'connected' ? 'disconnected' : ''}`}><i/>{statusName}</div></aside>
    <main className="chat-panel"><div className="live-connection"><Radio size={15}/><span>{statusName}</span><span>{config.apiBase === "http://127.0.0.1:18000/api" ? "Server test · Dữ liệu mẫu" : "Kết nối backend"}</span></div><ErrorBox error={connectionError}/>{error && <div className="dismiss-error"><ErrorBox error={error}/><button className="icon-button" aria-label="Đóng thông báo" onClick={() => setError('')}><X size={17}/></button></div>}
      {module === 'friends' ? <FriendsPage api={api} config={config} user={user} presence={presence} presenceReady={transportInitialized} watchPresence={watchPresence} onBack={() => navigateModule('chats')} onConversation={conversationOpened} onInvitationSent={() => api.invitations(user.user_id).then(result => setIncomingInvitationCount(result.incoming.length + result.room_incoming.length)).catch(error => setError(error.message))} onInvitations={() => navigateModule('invitations')}/> : module === 'invitations' ? <InvitationsPage api={api} config={config} user={user} onBack={() => navigateModule('chats')} onChanged={result => setIncomingInvitationCount(result.incoming.length + result.room_incoming.length)} onRoomAccepted={refreshConversationCatalog}/> : current ? <><header className="chat-header"><button className="icon-button live-back" aria-label="Quay lại danh sách" onClick={() => setActive(null)}><ArrowLeft size={20}/></button><Avatar user={{ name: name(current) }}/><div className="chat-heading"><h2>{name(current)}</h2><p>{current.type === 'UNKNOWN' ? 'Đã mở bằng mã hội thoại' : `${members.length} thành viên`} · Lịch sử từ backend</p></div><button className="icon-button" aria-label="Thông tin hội thoại" onClick={() => setDetails(!details)}><Info size={20}/></button><button className="icon-button" aria-label="Làm mới lịch sử" disabled={loading[active]} onClick={() => loadHistory(current)}><RefreshCw size={18}/></button></header>
      {details && <div className="live-details"><strong>Mã hội thoại</strong><code>{active}</code><button className="text-button" onClick={async () => { try { await navigator.clipboard.writeText(active); setError('Đã sao chép mã hội thoại.'); } catch { setError('Bạn có thể chọn và sao chép mã hiển thị phía trên.'); } }}>Sao chép mã</button><div className="live-members">{members.map(member => { const p = sender(member.user_id); return <div key={member.user_id}><Avatar user={p} apiBase={config.apiBase}/><span>{p.username}<small>{p.status === 'online' ? 'Online' : 'Offline'}</small></span></div>; })}</div>{current.type === 'UNKNOWN' && <p>Danh sách trên chỉ gồm bạn và người gửi trong trang lịch sử đã tải. BE chưa có API thông tin hội thoại.</p>}</div>}
      <label className="message-search"><Search size={16}/><input value={search} onChange={e => setSearch(e.target.value)} aria-label="Tìm tin nhắn trên máy chủ" placeholder="Tìm toàn bộ tin nhắn trên máy chủ..."/><span>{searchLoading ? 'Đang tìm…' : search.trim() ? `${searchResults.length} kết quả` : ''}</span></label><ErrorBox error={searchError || historyErrors[active]}/>{[403, 404].includes(historyStatus[active]) && <div className="history-recovery"><button className="text-button" onClick={() => loadHistory(current)} disabled={loading[active]}><RefreshCw size={14}/>Thử lại</button><button className="text-button" onClick={() => hideConversation(current)}>Ẩn khỏi danh sách trên máy này</button><small>Chỉ ẩn lối tắt cục bộ, không xóa dữ liệu trên server.</small></div>}
      <section className="messages" ref={list} aria-label="Nội dung trò chuyện"><div className="history-controls">{!search.trim() && older[active] && <button disabled={loading[active]} onClick={() => loadHistory(current, Math.min(...displayed.filter(m => m.seq != null).map(m => m.seq)))}>Tải tin nhắn cũ hơn</button>}{loading[active] && !search.trim() && <span role="status">Đang tải lịch sử…</span>}{search.trim() && !searchLoading && <span role="status">Kết quả tìm kiếm từ backend · tối đa 50 tin mới nhất</span>}</div>{visibleMessages.map(m => { const own = m.sender_id === user.user_id; const p = sender(m.sender_id); const reply = m.reply_to || messages.find(item => item.message_id === m.reply_to_message_id); return <article key={m.message_id || m.client_message_id} data-message-id={m.message_id || undefined} className={`message-row ${own ? 'mine' : ''}`}>
        {!own && <Avatar user={p} apiBase={config.apiBase}/>}<div className="message-body"><div className="sender-name">{own ? 'Bạn' : p.username}<span>{new Date(m.created_at).toLocaleDateString('vi-VN')} · {clock(m.created_at)}</span></div><div className="bubble">{m.reply_to_message_id && <blockquote>{reply?.content || 'Trả lời một tin nhắn trước đó'}</blockquote>}{m.content}</div><div className="live-message-actions">{m.message_id && <button title="Trả lời tin nhắn" aria-label={`Trả lời: ${m.content.slice(0, 40)}`} onClick={() => editDraft({ reply: m })}><Reply size={13}/>Trả lời</button>}{own && <span>{m.status === 'PENDING' ? 'Đang chờ BE…' : m.status === 'FAILED' ? 'Chưa xác nhận' : m.read_by?.length ? `Đã xem${m.read_by.length > 1 ? ` · ${m.read_by.length}` : ''}` : 'Chưa xem'}</span>}{own && m.status === 'FAILED' && <button disabled={connection !== 'connected' || !verified[active]} onClick={() => publish(m)}><RefreshCw size={12}/>Gửi lại</button>}</div>{m.error && <p className="message-error">{m.error}</p>}</div></article>; })}{!visibleMessages.length && !searchLoading && !searchError && (search.trim() ? <div className="empty-chat"><Search size={36}/><h3>Không tìm thấy tin nhắn</h3><p>Thử một từ khóa khác trong hội thoại này.</p></div> : !loading[active] && !historyErrors[active] && <div className="empty-chat"><MessageCircle size={36}/><h3>Bắt đầu câu chuyện</h3><p>Tin nhắn sẽ được lưu bởi backend của nhóm.</p></div>)}</section>
      <div className="composer-area">{draft.reply && <div className="reply-preview"><Reply size={16}/><span>Đang trả lời: {draft.reply.content}</span><button className="icon-button" aria-label="Hủy trả lời" onClick={() => editDraft({ reply: null })}><X size={16}/></button></div>}<form className="composer" onSubmit={send}><textarea rows={2} maxLength={4000} aria-label="Nội dung tin nhắn" placeholder={`Nhắn tin tới ${name(current)}...`} value={draft.text} onChange={e => editDraft({ text: e.target.value })} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(e); } }}/><div className="composer-toolbar"><span className="muted">Enter để gửi · Shift + Enter xuống dòng</span><button className="send-button" disabled={!draft.text.trim() || connection !== 'connected' || !verified[active]}>Gửi tin nhắn<Send size={16}/></button></div></form><div className="composer-bottom">{connection !== 'connected' ? 'Đang ngoại tuyến. Bản nháp được giữ trong phiên này.' : 'Đã đồng bộ tin nhắn đã gửi và trạng thái đã xem.'}</div></div></> : <div className="live-welcome"><span className="brand-mark"><Radio size={32}/></span><h1>Chào {user.username}.</h1><p>Một cuộc trò chuyện mới đang chờ bạn.</p><button className="primary-button" onClick={() => setModal('new')}><Plus size={18}/>Bắt đầu trò chuyện</button><p className="muted">Chọn hội thoại bên trái hoặc mở bằng mã nhóm được chia sẻ.</p></div>}
    </main>
    {hiddenConversation && <div className="undo-notice" role="status"><span>Đã ẩn hội thoại trên máy này.</span><button onClick={undoHide}>Hoàn tác</button><button className="icon-button" aria-label="Đóng thông báo ẩn hội thoại" onClick={() => setHiddenConversation(null)}><X size={14}/></button></div>}
    {modal === 'new' && <NewConversation api={api} config={config} user={user} close={() => setModal(null)} onCreated={addConversation}/>}
    {modal === 'open' && <OpenConversation api={api} user={user} close={() => setModal(null)} onOpened={(c, history) => { merge(history); addConversation(c); }}/>}
    {modal === 'profile' && <Profile api={api} config={config} user={user} close={() => setModal(null)} onUpdate={updated => { setUser(updated); setConversations(prev => prev.map(c => ({ ...c, members: c.members.map(member => member.user_id === updated.user_id ? updated : member) }))); }}/>}
  </div>;
}
function NewConversation({ api, config, user, close, onCreated }) {
  const [type, setType] = useState('PRIVATE'); const [name, setName] = useState(''); const [selected, setSelected] = useState([]); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event) { event.preventDefault(); setBusy(true); setError(''); try { onCreated(await api.createConversation({ user_id: user.user_id, type, ...(type === 'PRIVATE' ? { username: selected[0].username } : { name: name.trim(), usernames: selected.map(p => p.username) }) })); } catch (error) { setError(error.message); } finally { setBusy(false); } }
  return <Modal title="Cuộc trò chuyện mới" close={close}><form onSubmit={submit}><div className="modal-tabs">{[['PRIVATE','Cá nhân'],['GROUP','Tạo nhóm']].map(([value,label]) => <button key={value} type="button" className={type === value ? 'selected' : ''} onClick={() => { setType(value); setSelected([]); }}>{label}</button>)}</div>{type === 'GROUP' && <label className="form-label">Tên nhóm<input required maxLength={255} value={name} onChange={e => setName(e.target.value)} placeholder="Tên nhóm của bạn"/></label>}<UserSearch api={api} apiBase={config.apiBase} exclude={user.user_id} selected={selected.map(p => p.user_id)} onSelect={p => setSelected(prev => type === 'PRIVATE' ? [p] : prev.some(item => item.user_id === p.user_id) ? prev.filter(item => item.user_id !== p.user_id) : [...prev, p])}/><div className="selected-users">{selected.map(p => <button type="button" key={p.user_id} onClick={() => setSelected(prev => prev.filter(item => item.user_id !== p.user_id))}>{p.username}<X size={12}/></button>)}</div><ErrorBox error={error}/><button className="primary-button" disabled={busy || !selected.length || type === 'GROUP' && !name.trim()}>{busy ? 'Đang tạo…' : 'Bắt đầu trò chuyện'}</button></form></Modal>;
}
function OpenConversation({ api, user, close, onOpened }) {
  const [id, setId] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event) { event.preventDefault(); setBusy(true); setError(''); try { const result = await api.history(id.trim(), user.user_id); const catalog = await api.listConversations(user.user_id); const conversation = catalog.conversations.find(item => item.conversation_id === id.trim()); if (!conversation) throw new Error('Không tìm thấy hội thoại trong danh sách thành viên của bạn.'); onOpened(conversation, normalizeHistory(result)); } catch (error) { setError(error.message); } finally { setBusy(false); } }
  return <Modal title="Mở hội thoại bằng mã" close={close}><p className="muted">Nhập UUID do thành viên nhóm chia sẻ. Backend chỉ cho tải lịch sử nếu bạn đã là thành viên. Thao tác này không thêm bạn vào nhóm.</p><form onSubmit={submit}><label className="form-label">Conversation UUID<input required value={id} onChange={e => setId(e.target.value)} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"/></label><ErrorBox error={error}/><button className="primary-button" disabled={busy || !validUuid(id.trim())}>{busy ? 'Đang kiểm tra…' : 'Mở hội thoại'}</button></form></Modal>;
}
function Profile({ api, config, user, close, onUpdate }) {
  const [form, setForm] = useState({ username: user.username, short_bio: user.short_bio || '', bio: user.bio || '', sex: user.sex || '' }); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [saved, setSaved] = useState(false);
  async function perform(action) { setBusy(true); setError(''); setSaved(false); try { onUpdate(await action()); setSaved(true); } catch (error) { setError(error.message); } finally { setBusy(false); } }
  return <Modal title="Hồ sơ của bạn" close={close}><div className="profile-editor"><Avatar user={user} large apiBase={config.apiBase}/><div className="avatar-actions"><label className={`upload-button ${busy ? 'disabled' : ''}`}><Upload size={15}/>Đổi ảnh<input type="file" aria-label="Tải ảnh đại diện" accept="image/jpeg,image/png,image/gif,image/bmp,image/webp" disabled={busy} onChange={e => { const file = e.target.files[0]; if (file) perform(() => api.uploadAvatar(user.user_id, file)); e.target.value = ''; }}/></label><button className="text-button" disabled={busy || !user.avatar_url} onClick={() => perform(() => api.removeAvatar(user.user_id))}><Trash2 size={14}/>Xóa ảnh</button></div><small>JPEG, PNG, GIF, BMP, WebP · Tối đa 5 MB</small></div><form onSubmit={e => { e.preventDefault(); perform(() => api.updateUser(user.user_id, { ...form, username: form.username.trim() })); }}><label className="form-label">Username<input required maxLength={100} value={form.username} onChange={e => setForm({ ...form, username: e.target.value })}/></label><label className="form-label">Giới thiệu ngắn ({form.short_bio.length}/160)<input maxLength={160} value={form.short_bio} onChange={e => setForm({ ...form, short_bio: e.target.value })}/></label><label className="form-label">Giới thiệu<textarea rows={3} value={form.bio} onChange={e => setForm({ ...form, bio: e.target.value })}/></label><label className="form-label">Giới tính<select value={form.sex} onChange={e => setForm({ ...form, sex: e.target.value })}><option value="">Không cung cấp</option><option value="female">Nữ</option><option value="male">Nam</option></select></label><ErrorBox error={error}/>{saved && <p className="saved-notice" role="status">Đã lưu trên backend.</p>}<button className="primary-button" disabled={busy || !form.username.trim()}>{busy ? 'Đang lưu…' : 'Lưu hồ sơ'}</button></form></Modal>;
}
function FriendsPage({ api, config, user, presence, presenceReady, watchPresence, onBack, onConversation, onInvitationSent, onInvitations }) {
  const [friends, setFriends] = useState([]);
  const [query, setQuery] = useState('');
  const [onlineOnly, setOnlineOnly] = useState(false);
  const [total, setTotal] = useState(0);
  const [onlineTotal, setOnlineTotal] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [asideCollapsed, setAsideCollapsed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [cursor, setCursor] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const pageState = useRef({ key: '', cursor: null, generation: 0, loading: false });
  const sentinel = useRef(null);
  const loadPage = useCallback(async (reset = false) => {
    const key = `${query.trim()}\u0000${onlineOnly}`;
    if (reset) {
      pageState.current = {
        key,
        cursor: null,
        generation: pageState.current.generation + 1,
        loading: false,
      };
      setFriends([]);
      setCursor(null);
      setTotal(0);
      setOnlineTotal(0);
      setSelectedId(null);
      setError('');
    }
    const request = pageState.current;
    if (request.key !== key || request.loading || (!reset && !request.cursor)) return;
    const generation = request.generation;
    const after = reset ? null : request.cursor;
    request.loading = true;
    setLoading(true);
    try {
      const result = await api.friends(user.user_id, {
        query: query.trim(),
        onlineOnly,
        cursor: after,
        limit: 25,
      });
      if (pageState.current.generation !== generation) return;
      pageState.current.cursor = result.next_cursor;
      setCursor(result.next_cursor);
      setTotal(result.total);
      setOnlineTotal(result.online_total);
      setFriends(current => reset ? result.friends : [
        ...current,
        ...result.friends.filter(friend => !current.some(item => item.user_id === friend.user_id)),
      ]);
      setSelectedId(current => reset ? result.friends[0]?.user_id || null : current);
    } catch (error) {
      if (pageState.current.generation === generation) setError(error.message);
    } finally {
      if (pageState.current.generation === generation) {
        request.loading = false;
        setLoading(false);
      }
    }
  }, [api, user.user_id, query, onlineOnly]);
  useEffect(() => { loadPage(true); }, [loadPage]);
  useEffect(() => {
    const node = sentinel.current;
    if (!node) return undefined;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) loadPage();
    }, { rootMargin: '180px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [loadPage]);
  const friendIds = useMemo(() => friends.map(friend => friend.user_id), [friends]);
  const selected = friends.find(friend => friend.user_id === selectedId) || null;
  const liveOnlineTotal = Math.max(0, onlineTotal + friends.reduce((delta, friend) => {
    const currentStatus = presence[friend.user_id];
    if (!currentStatus || currentStatus === friend.status) return delta;
    return delta + (currentStatus === 'online' ? 1 : -1);
  }, 0));
  const visibleFriends = onlineOnly
    ? friends.filter(friend => (presence[friend.user_id] || friend.status) === 'online')
    : friends;
  useEffect(() => {
    if (presenceReady) watchPresence(friendIds);
  }, [friendIds, presenceReady, watchPresence]);
  useEffect(() => () => {
    watchPresence([]);
  }, [watchPresence]);
  async function startConversation(friend) {
    setBusyId(friend.user_id);
    setError('');
    try {
      onConversation(await api.createConversation({
        user_id: user.user_id,
        type: 'PRIVATE',
        username: friend.username,
      }));
    } catch (error) {
      setError(error.message);
    } finally {
      setBusyId(null);
    }
  }
  async function removeFriend(friend) {
    if (!window.confirm(`Xóa ${friend.username} khỏi danh sách bạn bè?`)) return;
    setBusyId(friend.user_id);
    setError('');
    setNotice('');
    try {
      await api.removeFriend(user.user_id, friend.user_id);
      setNotice(`Đã xóa ${friend.username} khỏi danh sách bạn bè.`);
      await loadPage(true);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusyId(null);
    }
  }
  async function sendInvitation(person) {
    setBusyId(person.user_id);
    setError('');
    setNotice('');
    try {
      await api.invite(user.user_id, person.user_id);
      setNotice(`Đã gửi lời mời tới ${person.username}.`);
      onInvitationSent();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusyId(null);
    }
  }
  return <section className="network-page">
    <header className="network-heading"><button className="icon-button network-back" aria-label="Quay lại hội thoại" onClick={onBack}><ArrowLeft size={19}/></button><span className="network-icon"><Users size={22}/></span><div><h1>Bạn bè</h1><p>Tìm kiếm và quản lý kết nối của bạn</p></div></header>
    <ErrorBox error={error}/>{notice && <p className="saved-notice" role="status">{notice}</p>}
    <div className={`network-layout ${asideCollapsed ? 'network-layout-aside-collapsed' : ''}`}>
      <div className="network-main">
        <label className="network-search"><Search size={18}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Tìm bạn theo username hoặc giới thiệu..." aria-label="Tìm bạn bè"/></label>
        <div className="network-tabs"><button className={!onlineOnly ? 'selected' : ''} onClick={() => setOnlineOnly(false)}><Users size={16}/>Tất cả bạn bè<span>{total}</span></button><button className={onlineOnly ? 'selected' : ''} onClick={() => setOnlineOnly(true)}><i className="status-dot online"/>Đang online<span>{liveOnlineTotal}</span></button></div>
        <div className="friend-cards">{visibleFriends.map(friend => {
          const online = (presence[friend.user_id] || friend.status) === 'online';
          return <article key={friend.user_id} className={`friend-card ${selectedId === friend.user_id ? 'chosen' : ''}`} role="button" tabIndex={0} aria-pressed={selectedId === friend.user_id} onClick={() => setSelectedId(friend.user_id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedId(friend.user_id); } }}>
            <Avatar user={{...friend, status: presence[friend.user_id] || friend.status}} apiBase={config.apiBase}/><div className="friend-identity"><strong>{friend.username}</strong><small>@{friend.username}</small></div><span className={`friend-status ${online ? 'online' : ''}`}><i className="status-dot"/>{online ? 'Đang online' : 'Ngoại tuyến'}</span><p>{friend.short_bio || friend.bio || 'Thành viên Mạch'}</p><div className="friend-actions"><button className="friend-message" disabled={busyId === friend.user_id} onClick={event => { event.stopPropagation(); startConversation(friend); }}><MessageCircle size={15}/>{busyId === friend.user_id ? 'Đang mở…' : 'Nhắn tin'}</button><button disabled={busyId === friend.user_id} onClick={event => { event.stopPropagation(); removeFriend(friend); }}><UserMinus size={15}/>Xóa bạn</button></div>
          </article>;
        })}</div>
        <div ref={sentinel} className="friend-page-sentinel" aria-live="polite">{loading ? 'Đang tải bạn bè…' : cursor ? 'Cuộn để xem thêm bạn bè' : friends.length ? 'Đã hiển thị tất cả bạn bè' : !error ? 'Chưa có bạn bè phù hợp.' : ''}</div>
        <section className="discover-panel"><div><h2>Tìm thêm bạn</h2><p>Tìm người dùng và gửi lời mời kết bạn.</p></div><UserSearch api={api} apiBase={config.apiBase} exclude={user.user_id} excludeIds={friendIds} actionLabel={busyId ? 'Đang gửi…' : 'Thêm bạn'} onSelect={sendInvitation}/></section>
      </div>
      <aside className={`network-aside ${asideCollapsed ? 'collapsed' : ''}`}>
        <div className="network-aside-heading">
          {!asideCollapsed && <strong>Thông tin bạn bè</strong>}
          <button
            className="network-aside-toggle"
            type="button"
            aria-label={asideCollapsed ? 'Mở rộng thanh thông tin' : 'Thu gọn thanh thông tin'}
            aria-expanded={!asideCollapsed}
            title={asideCollapsed ? 'Mở rộng' : 'Thu gọn'}
            onClick={() => setAsideCollapsed(collapsed => !collapsed)}
          >
            {asideCollapsed ? <ChevronLeft size={17}/> : <ChevronRight size={17}/>}
          </button>
        </div>
        {!asideCollapsed && <>
        <section className="network-aside-card"><h2>Tổng quan bạn bè</h2><div><Users size={17}/>Tổng số bạn bè<strong>{total}</strong></div><div><i className="status-dot online"/>Đang online<strong>{liveOnlineTotal}</strong></div></section>
        <section className="network-aside-card selected-friend"><h2>Bạn bè đã chọn</h2>{selected ? <><Avatar user={{...selected, status: presence[selected.user_id] || selected.status}} large apiBase={config.apiBase}/><strong>{selected.username}</strong><small>@{selected.username}</small><p>{selected.short_bio || selected.bio || 'Thành viên Mạch'}</p><button className="network-primary" onClick={() => startConversation(selected)}><MessageCircle size={16}/>Nhắn tin</button></> : <p className="muted">Chọn một người bạn để xem hồ sơ tóm tắt.</p>}</section>
        <section className="network-aside-card quick-actions"><h2>Thao tác nhanh</h2><button onClick={() => document.querySelector('.discover-panel input')?.focus()}><UserPlus size={20}/><span><strong>Tìm người dùng</strong><small>Tìm và gửi lời mời kết bạn</small></span></button><button onClick={onInvitations}><Mail size={20}/><span><strong>Quản lý lời mời</strong><small>Xem lời mời đến và đã gửi</small></span></button></section>
        </>}
      </aside>
    </div>
  </section>;
}

function InvitationsPage({ api, config, user, onBack, onChanged, onRoomAccepted }) {
  const [tab, setTab] = useState('friends');
  const [asideCollapsed, setAsideCollapsed] = useState(false);
  const [query, setQuery] = useState('');
  const [incoming, setIncoming] = useState([]);
  const [sent, setSent] = useState([]);
  const [roomIncoming, setRoomIncoming] = useState([]);
  const [roomSent, setRoomSent] = useState([]);
  const [groups, setGroups] = useState([]);
  const [selectedGroupId, setSelectedGroupId] = useState('');
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const selectedGroup = groups.find(group => group.conversation_id === selectedGroupId);
  async function refresh() {
    const [result, catalog] = await Promise.all([
      api.invitations(user.user_id),
      api.listConversations(user.user_id),
    ]);
    setIncoming(result.incoming);
    setSent(result.sent);
    setRoomIncoming(result.room_incoming);
    setRoomSent(result.room_sent);
    const groupConversations = catalog.conversations.filter(conversation => conversation.type === 'GROUP');
    setGroups(groupConversations);
    setSelectedGroupId(current => groupConversations.some(group => group.conversation_id === current)
      ? current
      : groupConversations[0]?.conversation_id || '');
    onChanged(result);
    return result;
  }
  useEffect(() => {
    refresh().catch(error => setError(error.message)).finally(() => setLoading(false));
  }, [api, user.user_id]);
  async function respond(invitation, status, room = false) {
    setBusyId(invitation.invitation_id);
    setError('');
    setNotice('');
    try {
      if (room) {
        await api.respondRoom(invitation.invitation_id, user.user_id, status);
      } else {
        await api.respond(invitation.invitation_id, user.user_id, status);
      }
      const result = await refresh();
      setNotice(status === 'ACCEPT'
        ? room ? 'Đã tham gia nhóm từ lời mời.' : 'Đã chấp nhận lời mời kết bạn.'
        : 'Đã từ chối lời mời.');
      onChanged(result);
      if (room && status === 'ACCEPT') onRoomAccepted();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusyId(null);
    }
  }
  async function sendRoomInvitation(person) {
    if (!selectedGroup) return;
    setBusyId(person.user_id);
    setError('');
    setNotice('');
    try {
      await api.inviteRoom(user.user_id, person.user_id, selectedGroup.conversation_id);
      const result = await refresh();
      setNotice(`Đã mời ${person.username} vào ${selectedGroup.name || 'nhóm'}.`);
      onChanged(result);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusyId(null);
    }
  }
  const matches = invitation => {
    const person = invitation.sender || invitation.recipient;
    return `${person.username} ${person.short_bio || ''} ${invitation.conversation?.name || ''}`
      .toLowerCase().includes(query.trim().toLowerCase());
  };
  function invitationCard(invitation, room, outgoing) {
    const person = outgoing ? invitation.recipient : invitation.sender;
    return <article className="invitation-card" key={invitation.invitation_id}>
      <Avatar user={person} apiBase={config.apiBase}/>
      <div className="friend-identity"><strong>{person.username}</strong><small>@{person.username}</small><p>{room ? invitation.conversation.name || 'Nhóm trò chuyện' : person.short_bio || person.bio || 'Thành viên Mạch'}</p></div>
      <time>{new Date(invitation.send_time).toLocaleDateString('vi-VN')}</time>
      {!outgoing
        ? <div className="invitation-actions"><button className="network-primary" disabled={busyId === invitation.invitation_id} onClick={() => respond(invitation, 'ACCEPT', room)}>{busyId === invitation.invitation_id ? 'Đang xử lý…' : 'Chấp nhận'}</button><button disabled={busyId === invitation.invitation_id} onClick={() => respond(invitation, 'REJECT', room)}>Từ chối</button></div>
        : <span className="invitation-pending"><i className="status-dot"/>Đang chờ</span>}
    </article>;
  }
  const activeIncoming = (tab === 'friends' ? incoming : roomIncoming).filter(matches);
  const activeSent = (tab === 'friends' ? sent : roomSent).filter(matches);
  const incomingCount = incoming.length + roomIncoming.length;
  const sentCount = sent.length + roomSent.length;
  return <section className="network-page invitations-page">
    <header className="network-heading"><button className="icon-button network-back" aria-label="Quay lại hội thoại" onClick={onBack}><ArrowLeft size={19}/></button><span className="network-icon"><Mail size={22}/></span><div><h1>Lời mời</h1><p>Quản lý lời mời kết bạn và lời mời vào nhóm</p></div></header>
    <ErrorBox error={error}/>{notice && <p className="saved-notice" role="status">{notice}</p>}
    <div className={`network-layout invitation-layout ${asideCollapsed ? 'network-layout-aside-collapsed' : ''}`}>
      <div className="network-main">
        <div className="network-tabs invitation-tabs"><button className={tab === 'friends' ? 'selected' : ''} onClick={() => setTab('friends')}><Users size={16}/>Lời mời kết bạn<span>{incoming.length}</span></button><button className={tab === 'rooms' ? 'selected' : ''} onClick={() => setTab('rooms')}><Users size={16}/>Lời mời nhóm<span>{roomIncoming.length}</span></button></div>
        <label className="network-search"><Search size={18}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Tìm theo username hoặc nhóm..." aria-label="Tìm lời mời"/></label>
        {tab === 'rooms' && <section className="room-invite-compose"><h2>Mời thành viên vào nhóm</h2>{groups.length ? <><label className="form-label">Chọn nhóm<select value={selectedGroupId} onChange={event => setSelectedGroupId(event.target.value)}>{groups.map(group => <option value={group.conversation_id} key={group.conversation_id}>{group.name || `Nhóm ${group.conversation_id.slice(0, 8)}`}</option>)}</select></label>{selectedGroup && <UserSearch api={api} apiBase={config.apiBase} exclude={user.user_id} excludeIds={selectedGroup.members.map(member => member.user_id)} actionLabel={busyId ? 'Đang gửi…' : 'Mời vào nhóm'} onSelect={sendRoomInvitation}/>}</> : <p className="muted">Bạn chưa có nhóm để gửi lời mời. Tạo nhóm trong mục Tin nhắn trước.</p>}</section>}
        <h2 className="invitation-list-title">Lời mời đã nhận ({activeIncoming.length})</h2>
        {loading ? <p className="network-empty">Đang tải lời mời…</p> : activeIncoming.length ? <div className="invitation-list">{activeIncoming.map(invitation => invitationCard(invitation, tab === 'rooms', false))}</div> : <div className="network-empty"><Mail size={25}/><strong>{query ? 'Không tìm thấy lời mời' : 'Bạn chưa có lời mời mới'}</strong><p>{tab === 'friends' ? 'Lời mời kết bạn mới sẽ xuất hiện ở đây.' : 'Lời mời vào nhóm mới sẽ xuất hiện ở đây.'}</p></div>}
        <h2 className="invitation-list-title">Lời mời đã gửi ({activeSent.length})</h2>
        {activeSent.length ? <div className="invitation-list">{activeSent.map(invitation => invitationCard(invitation, tab === 'rooms', true))}</div> : <p className="network-empty">{query ? 'Không tìm thấy lời mời' : 'Chưa có lời mời nào được gửi.'}</p>}
      </div>
      <aside className={`network-aside ${asideCollapsed ? 'collapsed' : ''}`}>
        <div className="network-aside-heading">
          {!asideCollapsed && <strong>Thông tin lời mời</strong>}
          <button
            className="network-aside-toggle"
            type="button"
            aria-label={asideCollapsed ? 'Mở rộng thanh thông tin' : 'Thu gọn thanh thông tin'}
            aria-expanded={!asideCollapsed}
            title={asideCollapsed ? 'Mở rộng' : 'Thu gọn'}
            onClick={() => setAsideCollapsed(collapsed => !collapsed)}
          >
            {asideCollapsed ? <ChevronLeft size={17}/> : <ChevronRight size={17}/>}
          </button>
        </div>
        {!asideCollapsed && <>
          <section className="network-aside-card"><h2>Tổng quan lời mời</h2><div><Users size={17}/>Lời mời đến<strong>{incomingCount}</strong></div><div><Send size={17}/>Lời mời đã gửi<strong>{sentCount}</strong></div><div><Users size={17}/>Lời mời kết bạn<strong>{incoming.length}</strong></div><div><Users size={17}/>Lời mời nhóm<strong>{roomIncoming.length}</strong></div></section>
          <section className="network-aside-card invitation-tip"><h2>Mẹo</h2><p>Chấp nhận lời mời để kết nối với bạn bè hoặc tham gia vào cuộc trò chuyện nhóm.</p></section>
        </>}
      </aside>
    </div>
  </section>;
}
