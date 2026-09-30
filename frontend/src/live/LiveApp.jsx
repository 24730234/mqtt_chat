import React, { useEffect, useMemo, useRef, useState } from 'react';
import mqtt from 'mqtt';
import { Radio, ArrowLeft, Plus, Search, Send, Users, MessageCircle, X, RefreshCw, Reply, Check, LogOut, Upload, Trash2, UserPlus, Info } from 'lucide-react';
import { createApi, avatarUrl } from './api.js';
import { createTransport } from './transport.js';
import { initials, validUuid, normalizeHistory, mergeMessages, reconcileAccepted, readCatalog, saveCatalog } from './state.js';
import './live.css';

const env = import.meta.env;
const initialConfig = { apiBase: env.VITE_API_BASE || '/api', mqttUrl: env.VITE_MQTT_URL || 'ws://127.0.0.1:9001', mqttUsername: '', mqttPassword: '' };
const configKey = 'mach-live-connection-v1';
function restoreConfig() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(configKey) || '{}');
    return { ...initialConfig, ...(typeof saved.apiBase === 'string' ? { apiBase: saved.apiBase } : {}), ...(typeof saved.mqttUrl === 'string' ? { mqttUrl: saved.mqttUrl } : {}) };
  } catch { return initialConfig; }
}
const localPreview = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
const clock = value => new Date(value).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
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
function UserSearch({ api, apiBase, exclude, onSelect, selected = [] }) {
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
      try { const result = await api.searchUsers(query, controller.signal); if (!controller.signal.aborted) setUsers(result.users.filter(u => u.user_id !== exclude)); }
      catch (error) { if (!controller.signal.aborted) setError(error.message); }
      finally { clearTimeout(timeout); if (!controller.signal.aborted) setLoading(false); }
    }, 250);
    return () => { controller.abort(); clearTimeout(timer); clearTimeout(timeout); };
  }, [query, api, exclude]);
  return <div className="user-search"><label className="form-label">Tìm theo username<input value={query} maxLength={100} onChange={event => setQuery(event.target.value)} placeholder="Nhập tên người dùng..."/></label><ErrorBox error={error}/>{loading && <p className="muted" role="status">Đang tìm người dùng…</p>}<div className="people-picker">{users.map(user => <button type="button" key={user.user_id} onClick={() => onSelect(user)} className={selected.includes(user.user_id) ? 'selected' : ''}><Avatar user={user} apiBase={apiBase}/><span>{user.username}<small>{user.short_bio || 'Thành viên'}</small></span>{selected.includes(user.user_id) && <Check size={16}/>}</button>)}</div>{query && !loading && !users.length && !error && <p className="muted">Không tìm thấy người dùng.</p>}</div>;
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
  const [conversations, setConversations] = useState(() => readCatalog(config.apiBase, user.user_id));
  const [messages, setMessages] = useState([]);
  const [active, setActive] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [connection, setConnection] = useState('connecting');
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
  catalogRef.current = conversations; activeRef.current = active;
  const current = conversations.find(c => c.conversation_id === active);
  const draft = drafts[active] || { text: '', reply: null };
  const displayed = messages.filter(m => m.conversation_id === active);
  const merge = incoming => setMessages(prev => mergeMessages(prev, incoming));
  useEffect(() => { if (!saveCatalog(config.apiBase, user.user_id, conversations)) setError('Trình duyệt không lưu được danh sách hội thoại cục bộ.'); }, [conversations, config.apiBase, user.user_id]);
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
        onState: (state, detail) => { setConnection(state); setConnectionError(detail); },
        onPresence: (id, status) => setPresence(prev => ({ ...prev, [id]: status })),
        onReady: () => { catalogRef.current.forEach(c => loadHistory(c)); },
        onEvent: event => {
          if (event.type === 'MESSAGE_ACCEPTED') setMessages(prev => reconcileAccepted(prev, event, user.user_id));
          else if (event.type === 'MESSAGE_CREATED') {
            const own = event.sender_id === user.user_id;
            if (!own && !seenEvents.current.has(event.message_id) && activeRef.current !== event.conversation_id) setConversations(items => items.map(c => c.conversation_id === event.conversation_id ? { ...c, unread: (c.unread || 0) + 1 } : c));
            seenEvents.current.add(event.message_id);
            setMessages(prev => mergeMessages(prev, [{ ...event, status: 'SENT' }]));
            if (event.conversation_id === activeRef.current && list.current && list.current.scrollHeight - list.current.scrollTop - list.current.clientHeight < 160) shouldScroll.current = true;
          } else if (event.type === 'ERROR') {
            if (!event.client_message_id) setError(event.error);
            setMessages(prev => prev.map(m => m.client_message_id === event.client_message_id && m.sender_id === user.user_id && m.status !== 'SENT' ? { ...m, status: 'FAILED', error: event.error } : m));
          }
        },
      });
    } catch (error) { setConnection('error'); setConnectionError(error.message); }
    catalogRef.current.forEach(c => loadHistory(c));
    return () => { alive.current = false; transport.current?.close(); transport.current = null; };
  }, []);
  useEffect(() => { if (shouldScroll.current && list.current) { list.current.scrollTop = list.current.scrollHeight; shouldScroll.current = false; } }, [messages, active]);
  function select(c) {
    setActive(c.conversation_id); setSearch(''); setDetails(false); shouldScroll.current = true;
    setConversations(prev => prev.map(item => item.conversation_id === c.conversation_id ? { ...item, unread: 0 } : item));
    loadHistory(c);
  }
  function hideConversation(c) {
    transport.current?.unwatch(c.conversation_id);
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
    setConversations(prev => [c, ...prev.filter(item => item.conversation_id !== c.conversation_id)]);
    select(c); setModal(null);
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
  return <div className={`live-workspace ${active ? 'has-active' : ''}`}>
    <nav className="rail"><span className="brand-mark"><Radio size={26}/></span><div className="rail-links"><button className="icon-button active" aria-label="Danh sách hội thoại" onClick={() => setActive(null)}><MessageCircle size={23}/><span className="rail-label">Tin nhắn</span></button><button className="icon-button" aria-label="Bạn bè" onClick={() => setModal('friends')}><Users size={23}/><span className="rail-label">Bạn bè</span></button></div><div className="rail-bottom"><button className="icon-button" aria-label="Đổi người dùng" onClick={onExit}><LogOut size={21}/></button><button className="profile-button" aria-label="Hồ sơ của bạn" onClick={() => setModal('profile')}><Avatar user={user} apiBase={config.apiBase}/></button></div></nav>
    <aside className="sidebar"><div className="workspace"><div><span className="wordmark">mạch<span>•</span></span><span className="workspace-caption">{user.username}</span></div><button className="demo-tag" onClick={onDemo}>VỀ DEMO</button></div><div className="sidebar-title"><h1>Tin nhắn<span>{conversations.length}</span></h1><button className="icon-button new-chat" aria-label="Cuộc trò chuyện mới" onClick={() => setModal('new')}><Plus size={20}/></button></div><label className="search-box"><Search size={17}/><input placeholder="Tìm hội thoại đã mở..." aria-label="Tìm hội thoại đã mở" value={query} onChange={e => setQuery(e.target.value)}/></label><div className="filters">{[['all','Tất cả'],['unread','Chưa đọc'],['groups','Nhóm']].map(([id,label]) => <button key={id} className={filter === id ? 'selected' : ''} onClick={() => setFilter(id)}>{label}</button>)}</div><div className="catalog-note">Hội thoại đã mở trên trình duyệt này.<button onClick={() => setModal('open')}>Mở bằng mã UUID</button></div><div className="conversation-list">{conversations.filter(c => name(c).toLowerCase().includes(query.toLowerCase()) && (filter !== 'groups' || c.type === 'GROUP') && (filter !== 'unread' || c.unread)).map(c => { const last = messages.filter(m => m.conversation_id === c.conversation_id).at(-1); return <button className={`conversation ${c.conversation_id === active ? 'selected' : ''}`} key={c.conversation_id} onClick={() => select(c)}><Avatar user={{ name: name(c), ...(c.type === 'PRIVATE' ? c.members.find(m => m.user_id !== user.user_id) : {}) }} apiBase={config.apiBase}/><span className="conversation-copy"><span className="conversation-top"><strong>{name(c)}</strong>{last && <time>{clock(last.created_at)}</time>}</span><span className="conversation-preview"><span>{historyStatus[c.conversation_id] === 404 ? 'Không còn trên server' : historyStatus[c.conversation_id] === 403 ? 'Không có quyền truy cập' : last?.content || (loading[c.conversation_id] ? 'Đang tải…' : 'Mở cuộc trò chuyện')}</span>{!!c.unread && <b className="unread-count">{c.unread}</b>}</span></span></button>; })}{!conversations.length && <div className="empty-list"><MessageCircle size={28}/><p>Chưa có hội thoại.<br/>Bắt đầu với một người bạn.</p><button onClick={() => setModal('new')}>Trò chuyện mới</button></div>}</div><div className={`local-status ${connection !== 'connected' ? 'disconnected' : ''}`}><i/>{statusName}</div></aside>
    <main className="chat-panel"><div className="live-connection"><Radio size={15}/><span>{statusName}</span><span>{config.apiBase === "http://127.0.0.1:18000/api" ? "Server test · Dữ liệu mẫu" : "Kết nối backend"}</span></div><ErrorBox error={connectionError}/>{error && <div className="dismiss-error"><ErrorBox error={error}/><button className="icon-button" aria-label="Đóng thông báo" onClick={() => setError('')}><X size={17}/></button></div>}
      {current ? <><header className="chat-header"><button className="icon-button live-back" aria-label="Quay lại danh sách" onClick={() => setActive(null)}><ArrowLeft size={20}/></button><Avatar user={{ name: name(current) }}/><div className="chat-heading"><h2>{name(current)}</h2><p>{current.type === 'UNKNOWN' ? 'Đã mở bằng mã hội thoại' : `${members.length} thành viên`} · Lịch sử từ backend</p></div><button className="icon-button" aria-label="Thông tin hội thoại" onClick={() => setDetails(!details)}><Info size={20}/></button><button className="icon-button" aria-label="Làm mới lịch sử" disabled={loading[active]} onClick={() => loadHistory(current)}><RefreshCw size={18}/></button></header>
      {details && <div className="live-details"><strong>Mã hội thoại</strong><code>{active}</code><button className="text-button" onClick={async () => { try { await navigator.clipboard.writeText(active); setError('Đã sao chép mã hội thoại.'); } catch { setError('Bạn có thể chọn và sao chép mã hiển thị phía trên.'); } }}>Sao chép mã</button><div className="live-members">{members.map(member => { const p = sender(member.user_id); return <div key={member.user_id}><Avatar user={p} apiBase={config.apiBase}/><span>{p.username}<small>{p.status === 'online' ? 'Online' : 'Offline'}</small></span></div>; })}</div>{current.type === 'UNKNOWN' && <p>Danh sách trên chỉ gồm bạn và người gửi trong trang lịch sử đã tải. BE chưa có API thông tin hội thoại.</p>}</div>}
      <label className="message-search"><Search size={16}/><input value={search} onChange={e => setSearch(e.target.value)} aria-label="Tìm trong tin đã tải" placeholder="Tìm trong các tin đã tải..."/></label><ErrorBox error={historyErrors[active]}/>{[403, 404].includes(historyStatus[active]) && <div className="history-recovery"><button className="text-button" onClick={() => loadHistory(current)} disabled={loading[active]}><RefreshCw size={14}/>Thử lại</button><button className="text-button" onClick={() => hideConversation(current)}>Ẩn khỏi danh sách trên máy này</button><small>Chỉ ẩn lối tắt cục bộ, không xóa dữ liệu trên server.</small></div>}
      <section className="messages" ref={list} aria-label="Nội dung trò chuyện"><div className="history-controls">{older[active] && <button disabled={loading[active]} onClick={() => loadHistory(current, Math.min(...displayed.filter(m => m.seq != null).map(m => m.seq)))}>Tải tin nhắn cũ hơn</button>}{loading[active] && <span role="status">Đang tải lịch sử…</span>}</div>{displayed.filter(m => m.content.toLowerCase().includes(search.toLowerCase())).map(m => { const own = m.sender_id === user.user_id; const p = sender(m.sender_id); const reply = m.reply_to || messages.find(item => item.message_id === m.reply_to_message_id); return <article key={m.message_id || m.client_message_id} className={`message-row ${own ? 'mine' : ''}`}>
        {!own && <Avatar user={p} apiBase={config.apiBase}/>}<div className="message-body"><div className="sender-name">{own ? 'Bạn' : p.username}<span>{new Date(m.created_at).toLocaleDateString('vi-VN')} · {clock(m.created_at)}</span></div><div className="bubble">{m.reply_to_message_id && <blockquote>{reply?.content || 'Trả lời một tin nhắn trước đó'}</blockquote>}{m.content}</div><div className="live-message-actions">{m.message_id && <button title="Trả lời tin nhắn" aria-label={`Trả lời: ${m.content.slice(0, 40)}`} onClick={() => editDraft({ reply: m })}><Reply size={13}/>Trả lời</button>}{own && <span>{m.status === 'PENDING' ? 'Đang chờ BE…' : m.status === 'FAILED' ? 'Chưa xác nhận' : 'Đã lưu trên máy chủ'}</span>}{own && m.status === 'FAILED' && <button disabled={connection !== 'connected' || !verified[active]} onClick={() => publish(m)}><RefreshCw size={12}/>Gửi lại</button>}</div>{m.error && <p className="message-error">{m.error}</p>}</div></article>; })}{!displayed.length && !loading[active] && !historyErrors[active] && <div className="empty-chat"><MessageCircle size={36}/><h3>Bắt đầu câu chuyện</h3><p>Tin nhắn sẽ được lưu bởi backend của nhóm.</p></div>}</section>
      <div className="composer-area">{draft.reply && <div className="reply-preview"><Reply size={16}/><span>Đang trả lời: {draft.reply.content}</span><button className="icon-button" aria-label="Hủy trả lời" onClick={() => editDraft({ reply: null })}><X size={16}/></button></div>}<form className="composer" onSubmit={send}><textarea rows={2} maxLength={4000} aria-label="Nội dung tin nhắn" placeholder={`Nhắn tin tới ${name(current)}...`} value={draft.text} onChange={e => editDraft({ text: e.target.value })} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(e); } }}/><div className="composer-toolbar"><span className="muted">Enter để gửi · Shift + Enter xuống dòng</span><button className="send-button" disabled={!draft.text.trim() || connection !== 'connected' || !verified[active]}>Gửi tin nhắn<Send size={16}/></button></div></form><div className="composer-bottom">{connection !== 'connected' ? 'Đang ngoại tuyến. Bản nháp được giữ trong phiên này.' : 'Chờ MESSAGE_ACCEPTED từ BE để xác nhận đã lưu. Chưa có trạng thái đã đọc.'}</div></div></> : <div className="live-welcome"><span className="brand-mark"><Radio size={32}/></span><h1>Chào {user.username}.</h1><p>Một cuộc trò chuyện mới đang chờ bạn.</p><button className="primary-button" onClick={() => setModal('new')}><Plus size={18}/>Bắt đầu trò chuyện</button><p className="muted">Chọn hội thoại bên trái hoặc mở bằng mã nhóm được chia sẻ.</p></div>}
    </main>
    {hiddenConversation && <div className="undo-notice" role="status"><span>Đã ẩn hội thoại trên máy này.</span><button onClick={undoHide}>Hoàn tác</button><button className="icon-button" aria-label="Đóng thông báo ẩn hội thoại" onClick={() => setHiddenConversation(null)}><X size={14}/></button></div>}
    {modal === 'new' && <NewConversation api={api} config={config} user={user} close={() => setModal(null)} onCreated={addConversation}/>}
    {modal === 'open' && <OpenConversation api={api} user={user} close={() => setModal(null)} onOpened={(c, history) => { merge(history); addConversation(c); }}/>}
    {modal === 'profile' && <Profile api={api} config={config} user={user} close={() => setModal(null)} onUpdate={updated => { setUser(updated); setConversations(prev => prev.map(c => ({ ...c, members: c.members.map(member => member.user_id === updated.user_id ? updated : member) }))); }}/>}
    {modal === 'friends' && <Friends api={api} config={config} user={user} close={() => setModal(null)} onConversation={addConversation}/>}
  </div>;
}
function NewConversation({ api, config, user, close, onCreated }) {
  const [type, setType] = useState('PRIVATE'); const [name, setName] = useState(''); const [selected, setSelected] = useState([]); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event) { event.preventDefault(); setBusy(true); setError(''); try { onCreated(await api.createConversation({ user_id: user.user_id, type, ...(type === 'PRIVATE' ? { username: selected[0].username } : { name: name.trim(), usernames: selected.map(p => p.username) }) })); } catch (error) { setError(error.message); } finally { setBusy(false); } }
  return <Modal title="Cuộc trò chuyện mới" close={close}><form onSubmit={submit}><div className="modal-tabs">{[['PRIVATE','Cá nhân'],['GROUP','Tạo nhóm']].map(([value,label]) => <button key={value} type="button" className={type === value ? 'selected' : ''} onClick={() => { setType(value); setSelected([]); }}>{label}</button>)}</div>{type === 'GROUP' && <label className="form-label">Tên nhóm<input required maxLength={255} value={name} onChange={e => setName(e.target.value)} placeholder="Tên nhóm của bạn"/></label>}<UserSearch api={api} apiBase={config.apiBase} exclude={user.user_id} selected={selected.map(p => p.user_id)} onSelect={p => setSelected(prev => type === 'PRIVATE' ? [p] : prev.some(item => item.user_id === p.user_id) ? prev.filter(item => item.user_id !== p.user_id) : [...prev, p])}/><div className="selected-users">{selected.map(p => <button type="button" key={p.user_id} onClick={() => setSelected(prev => prev.filter(item => item.user_id !== p.user_id))}>{p.username}<X size={12}/></button>)}</div><ErrorBox error={error}/><button className="primary-button" disabled={busy || !selected.length || type === 'GROUP' && !name.trim()}>{busy ? 'Đang tạo…' : 'Bắt đầu trò chuyện'}</button></form></Modal>;
}
function OpenConversation({ api, user, close, onOpened }) {
  const [id, setId] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event) { event.preventDefault(); setBusy(true); setError(''); try { const result = await api.history(id.trim(), user.user_id); const members = [...new Map([user, ...result.messages.map(m => m.sender)].map(p => [p.user_id, p])).values()]; onOpened({ conversation_id: id.trim(), name: `Hội thoại ${id.trim().slice(0,8)}`, type: 'UNKNOWN', members }, normalizeHistory(result)); } catch (error) { setError(error.message); } finally { setBusy(false); } }
  return <Modal title="Mở hội thoại bằng mã" close={close}><p className="muted">Nhập UUID do thành viên nhóm chia sẻ. Backend chỉ cho tải lịch sử nếu bạn đã là thành viên. Thao tác này không thêm bạn vào nhóm.</p><form onSubmit={submit}><label className="form-label">Conversation UUID<input required value={id} onChange={e => setId(e.target.value)} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"/></label><ErrorBox error={error}/><button className="primary-button" disabled={busy || !validUuid(id.trim())}>{busy ? 'Đang kiểm tra…' : 'Mở hội thoại'}</button></form></Modal>;
}
function Profile({ api, config, user, close, onUpdate }) {
  const [form, setForm] = useState({ username: user.username, short_bio: user.short_bio || '', bio: user.bio || '', sex: user.sex || '' }); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [saved, setSaved] = useState(false);
  async function perform(action) { setBusy(true); setError(''); setSaved(false); try { onUpdate(await action()); setSaved(true); } catch (error) { setError(error.message); } finally { setBusy(false); } }
  return <Modal title="Hồ sơ của bạn" close={close}><div className="profile-editor"><Avatar user={user} large apiBase={config.apiBase}/><div className="avatar-actions"><label className={`upload-button ${busy ? 'disabled' : ''}`}><Upload size={15}/>Đổi ảnh<input type="file" aria-label="Tải ảnh đại diện" accept="image/jpeg,image/png,image/gif,image/bmp,image/webp" disabled={busy} onChange={e => { const file = e.target.files[0]; if (file) perform(() => api.uploadAvatar(user.user_id, file)); e.target.value = ''; }}/></label><button className="text-button" disabled={busy || !user.avatar_url} onClick={() => perform(() => api.removeAvatar(user.user_id))}><Trash2 size={14}/>Xóa ảnh</button></div><small>JPEG, PNG, GIF, BMP, WebP · Tối đa 5 MB</small></div><form onSubmit={e => { e.preventDefault(); perform(() => api.updateUser(user.user_id, { ...form, username: form.username.trim() })); }}><label className="form-label">Username<input required maxLength={100} value={form.username} onChange={e => setForm({ ...form, username: e.target.value })}/></label><label className="form-label">Giới thiệu ngắn ({form.short_bio.length}/160)<input maxLength={160} value={form.short_bio} onChange={e => setForm({ ...form, short_bio: e.target.value })}/></label><label className="form-label">Giới thiệu<textarea rows={3} value={form.bio} onChange={e => setForm({ ...form, bio: e.target.value })}/></label><label className="form-label">Giới tính<select value={form.sex} onChange={e => setForm({ ...form, sex: e.target.value })}><option value="">Không cung cấp</option><option value="female">Nữ</option><option value="male">Nam</option></select></label><ErrorBox error={error}/>{saved && <p className="saved-notice" role="status">Đã lưu trên backend.</p>}<button className="primary-button" disabled={busy || !form.username.trim()}>{busy ? 'Đang lưu…' : 'Lưu hồ sơ'}</button></form></Modal>;
}
function Friends({ api, config, user, close, onConversation }) {
  const [friends, setFriends] = useState([]); const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [busy, setBusy] = useState(false); const [inviteId, setInviteId] = useState('');
  async function refresh() { const result = await api.friends(user.user_id); setFriends(result.friends); }
  useEffect(() => { refresh().catch(e => setError(e.message)); }, []);
  async function run(action) { if (busy) return; setBusy(true); setError(''); setNotice(''); try { await action(); } catch (error) { setError(error.message); } finally { setBusy(false); } }
  return <Modal title="Bạn bè & lời mời" close={close}><ErrorBox error={error}/>{notice && <p className="saved-notice" role="status">{notice}</p>}<div className="friends-list">{friends.map(p => <div key={p.user_id}><Avatar user={p} apiBase={config.apiBase}/><strong>{p.username}</strong><button disabled={busy} className="icon-button" aria-label={`Chat với ${p.username}`} onClick={() => run(async () => onConversation(await api.createConversation({ user_id: user.user_id, type: 'PRIVATE', username: p.username })))}><MessageCircle size={17}/></button><button disabled={busy} className="icon-button" aria-label={`Xóa bạn ${p.username}`} onClick={() => run(async () => { await api.removeFriend(user.user_id, p.user_id); await refresh(); setNotice('Đã xóa kết nối bạn bè.'); })}><Trash2 size={16}/></button></div>)}</div>{!friends.length && <p className="muted">Chưa có bạn bè trong danh sách.</p>}<h3 className="form-label">Gửi lời mời kết bạn</h3><UserSearch api={api} apiBase={config.apiBase} exclude={user.user_id} onSelect={p => run(async () => { const result = await api.invite(user.user_id, p.user_id); setNotice(`Đã gửi lời mời tới ${p.username}. Mã lời mời: ${result.invitation_id}`); })}/><details className="invitation-details"><summary>Phản hồi lời mời bằng mã</summary><p className="muted">BE chưa có API hộp thư lời mời. Nhập mã invitation_id do người gửi chia sẻ để chấp nhận hoặc từ chối.</p><label className="form-label">Mã lời mời<input value={inviteId} onChange={e => setInviteId(e.target.value)}/></label><div className="modal-tabs">{[['ACCEPT','Chấp nhận'],['REJECT','Từ chối']].map(([status,label]) => <button key={status} disabled={busy || !validUuid(inviteId.trim())} onClick={() => run(async () => { await api.respond(inviteId.trim(), user.user_id, status); await refresh(); setNotice(status === 'ACCEPT' ? 'Đã chấp nhận lời mời.' : 'Đã từ chối lời mời.'); setInviteId(''); })}>{label}</button>)}</div></details></Modal>;
}
