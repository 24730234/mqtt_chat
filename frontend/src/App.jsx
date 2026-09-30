import React, { useEffect, useRef, useState } from 'react';
import { MessageCircle, Users, Bookmark, Settings, Plus, Search, ArrowUpRight, ArrowLeft, Send, Smile, X, Info, CheckCheck, ChevronDown, Pin, Leaf, Radio, Bell, BellOff, Check, Sparkles } from 'lucide-react';
import { chatService, currentUser, people } from './chatService';

const allPeople = [currentUser, ...people];
const person = (id) => allPeople.find(p => p.user_id === id) || currentUser;
const time = (value) => new Date(value).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
function Avatar({ item, large = false, small = false, online = false }) {
  return <span className={`avatar ${item.color || 'green'} ${large ? 'large' : ''} ${small ? 'small' : ''}`}>{item.conversation_type === 'GROUP' && item.initials === 'M' ? <Radio size={large ? 32 : 23} /> : item.initials}{online && <i className="online-dot" />}</span>;
}
function IconButton({ label, children, className = '', ...props }) { return <button type="button" className={`icon-button ${className}`} aria-label={label} title={label} {...props}>{children}</button>; }

export default function App({ onConnect }) {
  const [data, setData] = useState(() => chatService.load());
  const [activeId, setActiveId] = useState('team');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [nav, setNav] = useState('chats');
  const [drafts, setDrafts] = useState({});
  const [details, setDetails] = useState(() => window.innerWidth >= 1220);
  const [mobileChat, setMobileChat] = useState(false);
  const [modal, setModal] = useState(null);
  const [newType, setNewType] = useState('PRIVATE');
  const [selected, setSelected] = useState([]);
  const [groupName, setGroupName] = useState('');
  const [emoji, setEmoji] = useState(false);
  const [inSearch, setInSearch] = useState(false);
  const [messageQuery, setMessageQuery] = useState('');
  const [typingId, setTypingId] = useState(null);
  const [autoReply, setAutoReply] = useState(true);
  const [muted, setMuted] = useState([]);
  const [notice, setNotice] = useState('');
  const bottom = useRef(null);
  const input = useRef(null);
  const timer = useRef(null);
  const dialog = useRef(null);
  const c = data.conversations.find(c => c.conversation_id === activeId) || data.conversations[0];
  const draft = drafts[c.conversation_id] || '';
  const messages = data.messages.filter(m => m.conversation_id === c.conversation_id).sort((a, b) => a.seq - b.seq);
  const shownMessages = messages.filter(m => m.content.toLocaleLowerCase('vi').includes(messageQuery.toLocaleLowerCase('vi')));
  const unread = data.conversations.reduce((n, c) => n + c.unread, 0);
  useEffect(() => { if (!chatService.save(data)) setNotice('Trình duyệt chưa lưu được dữ liệu. Hãy giữ tab này mở.'); }, [data]);
  useEffect(() => { const list = bottom.current?.parentElement; list?.scrollTo({ top: list.scrollHeight, behavior: 'smooth' }); }, [messages.length, activeId, typingId]);
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => { if (modal) dialog.current?.showModal(); else dialog.current?.close(); }, [modal]);
  useEffect(() => { if (notice) { const t = setTimeout(() => setNotice(''), 4000); return () => clearTimeout(t); } }, [notice]);
  const setDraft = (value) => setDrafts(prev => ({ ...prev, [c.conversation_id]: value }));
  function openConversation(id) {
    setActiveId(id); setMobileChat(true); setMessageQuery(''); setInSearch(false); setEmoji(false);
    setData(prev => ({ ...prev, conversations: prev.conversations.map(c => c.conversation_id === id ? { ...c, unread: 0 } : c) }));
  }
  function send(event) {
    event.preventDefault(); if (!draft.trim()) return;
    const id = c.conversation_id;
    const outgoing = chatService.makeMessage(id, 'quang', draft.trim(), Math.max(0, ...messages.map(m => m.seq)) + 1);
    setData(prev => ({ ...prev, messages: [...prev.messages, outgoing] })); setDraft(''); setEmoji(false);
    if (autoReply && !typingId) {
      setTypingId(id);
      const responder = c.members.find(id => id !== 'quang');
      timer.current = setTimeout(() => {
        setData(prev => ({ ...prev, messages: [...prev.messages.map(m => m.message_id === outgoing.message_id ? { ...m, status: 'READ' } : m), chatService.makeMessage(id, responder, 'Mình nhận được rồi nhé! 🙌 Đây là phản hồi tự động để bạn thử giao diện.', Math.max(0, ...prev.messages.filter(m => m.conversation_id === id).map(m => m.seq)) + 1)] }));
        setTypingId(null);
      }, 1700);
    }
    input.current?.focus();
  }
  function createConversation(event) {
    event.preventDefault(); if (!selected.length || (newType === 'GROUP' && !groupName.trim())) return;
    if (newType === 'PRIVATE') {
      const exists = data.conversations.find(c => c.conversation_type === 'PRIVATE' && c.members.includes(selected[0]));
      if (exists) { openConversation(exists.conversation_id); setModal(null); return; }
    }
    const p = person(selected[0]); const id = crypto.randomUUID();
    const conversation = { conversation_id: id, name: newType === 'GROUP' ? groupName.trim() : p.username, conversation_type: newType, initials: newType === 'GROUP' ? groupName.trim().slice(0, 2).toUpperCase() : p.initials, color: newType === 'GROUP' ? 'green' : p.color, members: ['quang', ...selected], unread: 0 };
    setData(prev => ({ ...prev, conversations: [conversation, ...prev.conversations] })); setActiveId(id); setMobileChat(true); setModal(null); setQuery(''); setFilter('all'); setNav('chats'); setMessageQuery('');
  }
  function togglePin() { setData(prev => ({ ...prev, conversations: prev.conversations.map(item => item.conversation_id === c.conversation_id ? { ...item, pinned: !item.pinned } : item) })); }
  const filtered = data.conversations.filter(c => c.name.toLocaleLowerCase('vi').includes(query.toLocaleLowerCase('vi')) && (filter !== 'unread' || c.unread > 0) && (filter !== 'groups' || c.conversation_type === 'GROUP') && (nav !== 'saved' || c.pinned) && (nav !== 'groups' || c.conversation_type === 'GROUP'));
  const lastMessage = (id) => data.messages.filter(m => m.conversation_id === id).at(-1);
  const onlineCount = c.members.filter(id => person(id).online || id === 'quang').length;
  return <div className={`app ${mobileChat ? 'mobile-chat' : ''} ${details ? '' : 'no-details'}`}>
    <nav className="rail" aria-label="Điều hướng chính">
      <a className="brand-mark" href="#" aria-label="Mạch — Trang chủ" onClick={e => { e.preventDefault(); setNav('chats'); setMobileChat(false); }}><Radio size={28} /></a>
      <div className="rail-links">
        <IconButton label="Tin nhắn" className={nav === 'chats' ? 'active' : ''} onClick={() => { setNav('chats'); setFilter('all'); setMobileChat(false); }}><MessageCircle size={23} /><span className="rail-label">Tin nhắn</span>{unread > 0 && <i className="rail-dot" />}</IconButton>
        <IconButton label="Nhóm" className={nav === 'groups' ? 'active' : ''} onClick={() => { setNav('groups'); setFilter('all'); setMobileChat(false); }}><Users size={23} /><span className="rail-label">Nhóm</span></IconButton>
        <IconButton label="Đã ghim" className={nav === 'saved' ? 'active' : ''} onClick={() => { setNav('saved'); setFilter('all'); setMobileChat(false); }}><Bookmark size={22} /><span className="rail-label">Đã ghim</span></IconButton>
      </div>
      <div className="rail-bottom"><IconButton label="Cài đặt bản thử" onClick={() => setModal('settings')}><Settings size={22} /></IconButton><button className="profile-button" aria-label="Hồ sơ của bạn" onClick={() => setModal('profile')}><Avatar item={currentUser} online /></button></div>
    </nav>
    <aside className="sidebar">
      <div className="workspace"><div><span className="wordmark">mạch<span>•</span></span><span className="workspace-caption">Không gian kết nối</span></div><button className="demo-tag" onClick={onConnect}>KẾT NỐI BE ↗</button></div>
      <div className="sidebar-title"><h1>{nav === 'saved' ? 'Đã ghim' : nav === 'groups' ? 'Nhóm của bạn' : 'Tin nhắn'}<span>{data.conversations.length}</span></h1><IconButton label="Cuộc trò chuyện mới" className="new-chat" onClick={() => { setSelected([]); setGroupName(''); setNewType(nav === 'groups' ? 'GROUP' : 'PRIVATE'); setModal('new'); }}><Plus size={20} /></IconButton></div>
      <label className="search-box"><Search size={17} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Tìm cuộc trò chuyện..." aria-label="Tìm cuộc trò chuyện"/><span>⌕</span></label>
      <div className="filters" aria-label="Lọc hội thoại">{[['all', 'Tất cả'], ['unread', 'Chưa đọc'], ['groups', 'Nhóm']].map(([id, label]) => <button key={id} className={filter === id ? 'selected' : ''} onClick={() => setFilter(id)}>{label}{id === 'unread' && unread > 0 && <span>{unread}</span>}</button>)}</div>
      <div className="list-label">CUỘC TRÒ CHUYỆN <span>{filtered.length}</span></div>
      <div className="conversation-list">{filtered.map(item => { const last = lastMessage(item.conversation_id); return <button key={item.conversation_id} className={`conversation ${c.conversation_id === item.conversation_id ? 'selected' : ''}`} onClick={() => openConversation(item.conversation_id)}>
        <Avatar item={item} online={item.conversation_type === 'PRIVATE' && person(item.members.find(id => id !== 'quang')).online} />
        <span className="conversation-copy"><span className="conversation-top"><strong>{item.name}</strong><time>{last ? time(last.created_at) : 'Mới'}</time></span><span className="conversation-preview"><span>{last ? `${last.sender_id === 'quang' ? 'Bạn: ' : ''}${last.content}` : 'Bắt đầu một câu chuyện...'}</span>{item.unread > 0 ? <b className="unread-count">{item.unread}</b> : item.pinned && <Pin size={12} />}</span></span>
      </button>; })}{!filtered.length && <div className="empty-list"><Search size={26}/><p>Chưa có cuộc trò chuyện phù hợp.</p><button onClick={() => { setQuery(''); setFilter('all'); setNav('chats'); }}>Xem tất cả</button></div>}</div>
      <div className="sidebar-footer"><span className="leaf-icon"><Leaf size={19}/></span><div><strong>Mỗi tin nhắn, một kết nối.</strong><p>Một chút gần nhau hơn mỗi ngày.</p></div></div>
      <div className="local-status"><i/>Không gian demo <span>v0.1</span></div>
    </aside>
    <main className="chat-panel">
      <header className="chat-header"><IconButton label="Quay lại danh sách" className="back-button" onClick={() => setMobileChat(false)}><ArrowLeft size={21}/></IconButton><Avatar item={c}/><div className="chat-heading"><h2>{c.name}<span className="type-tag">{c.conversation_type === 'GROUP' ? 'Nhóm' : 'Cá nhân'}</span></h2><p><i/>{c.conversation_type === 'GROUP' ? `${c.members.length} thành viên · ${onlineCount} đang hoạt động` : person(c.members.find(id => id !== 'quang')).online ? 'Đang hoạt động' : 'Hiện không hoạt động'}<span className="sample-label"> · mô phỏng</span></p></div><div className="header-actions"><IconButton label="Tìm trong cuộc trò chuyện" className={inSearch ? 'is-on' : ''} onClick={() => { setInSearch(!inSearch); setMessageQuery(''); }}><Search size={20}/></IconButton><span className="divider"/><IconButton label="Thông tin cuộc trò chuyện" className={details ? 'is-on' : ''} onClick={() => setDetails(!details)}><Info size={20}/></IconButton></div></header>
      {inSearch && <div className="message-search"><Search size={17}/><input autoFocus placeholder="Tìm nội dung tin nhắn..." aria-label="Tìm nội dung tin nhắn" value={messageQuery} onChange={e => setMessageQuery(e.target.value)}/><span>{shownMessages.length} tin nhắn</span></div>}
      <div className="demo-banner"><Sparkles size={15}/><span>Chào mừng đến với Mạch. Cứ tự nhiên bắt đầu câu chuyện nhé!</span><span className="demo-banner-badge">Dữ liệu mẫu</span></div>
      <section className="messages" aria-label="Nội dung trò chuyện" aria-live="polite">
        <div className="conversation-intro"><span className="intro-line"/><span><Leaf size={13}/> Những câu chuyện bắt đầu từ đây</span><span className="intro-line"/></div>
        {shownMessages.map((m, index) => { const p = person(m.sender_id); const mine = m.sender_id === 'quang'; const prev = shownMessages[index - 1]; const newDay = !prev || new Date(prev.created_at).toDateString() !== new Date(m.created_at).toDateString(); return <React.Fragment key={m.message_id}>{newDay && <div className="day-label">{new Date(m.created_at).toDateString() === new Date().toDateString() ? 'Hôm nay' : new Date(m.created_at).toLocaleDateString('vi-VN')}<span/></div>}<article className={`message-row ${mine ? 'mine' : ''}`}>
          {!mine && <Avatar item={p} small/>}<div className="message-body">{!mine && <div className="sender-name">{p.username}<span>{time(m.created_at)}</span></div>}<div className="bubble">{m.content}</div>{mine && <div className="message-meta">{time(m.created_at)}<CheckCheck size={14}/>{m.status === 'READ' ? 'Đã đọc' : 'Đã gửi'}<span className="sr-only"> (mô phỏng)</span></div>}</div>
        </article></React.Fragment>; })}
        {!shownMessages.length && <div className="empty-chat"><MessageCircle size={38}/><h3>{messageQuery ? 'Không tìm thấy tin nhắn' : 'Một câu chuyện mới'}</h3><p>{messageQuery ? 'Thử tìm bằng một từ khác nhé.' : `Gửi lời chào đến ${c.name} nhé!`}</p></div>}
        {typingId === c.conversation_id && <div className="typing"><span><i/><i/><i/></span>Đang soạn phản hồi mẫu…</div>}<div ref={bottom}/>
      </section>
      <div className="composer-area"><form className="composer" onSubmit={send}><textarea ref={input} rows={2} maxLength={4000} aria-label="Nội dung tin nhắn" placeholder={`Nhắn tin tới ${c.name}...`} value={draft} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(e); } }}/><div className="composer-toolbar"><div className="emoji-wrapper"><IconButton label="Chọn biểu tượng cảm xúc" className={emoji ? 'is-on' : ''} onClick={() => setEmoji(!emoji)}><Smile size={21}/></IconButton>{emoji && <div className="emoji-picker">{['😊', '🙌', '💚', '✨', '👍', '🌿', '🎉', '👋'].map(e => <button type="button" key={e} onClick={() => { setDraft(draft + e); setEmoji(false); input.current?.focus(); }}>{e}</button>)}</div>}<span className="composer-hint">Một lời chào cũng đủ để bắt đầu.</span></div><button className="send-button" disabled={!draft.trim()} type="submit">Gửi tin nhắn<Send size={16}/></button></div></form><div className="composer-bottom"><span><span className="key">↵</span> để gửi · <span className="key">Shift + ↵</span> để xuống dòng</span><span><i/> Chế độ demo · lưu trên trình duyệt</span></div></div>
    </main>
    {details && <aside className="details-panel"><div className="details-title">Thông tin trò chuyện<IconButton label="Đóng thông tin" onClick={() => setDetails(false)}><X size={18}/></IconButton></div><div className="group-profile"><Avatar item={c} large/><h3>{c.name}</h3><p>{c.conversation_type === 'GROUP' ? 'Cùng nhau làm nên điều hay.' : person(c.members.find(id => id !== 'quang')).role}</p><span className="profile-tag">{c.conversation_type === 'GROUP' ? <Users size={12}/> : <MessageCircle size={12}/>} {c.conversation_type === 'GROUP' ? 'Nhóm trò chuyện' : 'Trò chuyện cá nhân'}</span></div><div className="detail-shortcuts"><button className={muted.includes(c.conversation_id) ? 'chosen' : ''} onClick={() => { setMuted(prev => prev.includes(c.conversation_id) ? prev.filter(id => id !== c.conversation_id) : [...prev, c.conversation_id]); setNotice('Đã cập nhật tùy chọn thông báo cho bản thử.'); }}><span>{muted.includes(c.conversation_id) ? <BellOff size={18}/> : <Bell size={18}/>}</span>{muted.includes(c.conversation_id) ? 'Đã tắt' : 'Thông báo'}</button><button className={c.pinned ? 'chosen' : ''} onClick={togglePin}><span><Pin size={18}/></span>{c.pinned ? 'Đã ghim' : 'Ghim chat'}</button></div><div className="details-section"><h4>GIỚI THIỆU</h4><p>{c.description || (c.conversation_type === 'GROUP' ? 'Không gian của những ý tưởng và câu chuyện mới. Hãy gửi lời chào đến mọi người!' : 'Giữ kết nối và chia sẻ những điều nhỏ bé mỗi ngày.')}</p></div><div className="members-section"><h4>Thành viên <span>{c.members.length}</span><ChevronDown size={15}/></h4>{c.members.map(id => { const p = person(id); return <div className="member" key={id}><Avatar item={p} small online={p.online || id === 'quang'}/><div><strong>{p.username}{id === 'quang' && <span> (bạn)</span>}</strong><p>{p.role}</p></div>{id === 'quang' && <span className="you-badge">Bạn</span>}</div>; })}</div><div className="connection-card"><span className="connection-symbol"><Radio size={19}/></span><strong>Chuyện trò không khoảng cách</strong><p>Chia sẻ một ý tưởng.<br/>Kết nối một người bạn.</p><span className="card-dots">● · ● · ●</span></div><div className="details-bottom">MADE FOR CONNECTION <Leaf size={12}/></div></aside>}
    <dialog ref={dialog} onCancel={() => setModal(null)} onClick={e => { if (e.target === dialog.current) setModal(null); }}><div className="modal-heading"><h2>{modal === 'new' ? 'Bắt đầu cuộc trò chuyện' : modal === 'settings' ? 'Cài đặt bản thử' : 'Hồ sơ của bạn'}</h2><IconButton label="Đóng hộp thoại" onClick={() => setModal(null)}><X size={20}/></IconButton></div>
      {modal === 'new' && <form onSubmit={createConversation}><p className="modal-subtitle">Một kết nối mới bắt đầu bằng một lời chào.</p><div className="modal-tabs"><button type="button" className={newType === 'PRIVATE' ? 'selected' : ''} onClick={() => { setNewType('PRIVATE'); setSelected([]); }}>Cá nhân</button><button type="button" className={newType === 'GROUP' ? 'selected' : ''} onClick={() => { setNewType('GROUP'); setSelected([]); }}>Tạo nhóm</button></div>{newType === 'GROUP' && <label className="form-label">Tên nhóm<input required maxLength={80} value={groupName} onChange={e => setGroupName(e.target.value)} placeholder="Ví dụ: Những người bạn"/></label>}<label className="form-label">{newType === 'GROUP' ? 'Chọn thành viên' : 'Bạn muốn trò chuyện với ai?'}</label><div className="people-picker">{people.map(p => <button key={p.user_id} type="button" className={selected.includes(p.user_id) ? 'selected' : ''} onClick={() => setSelected(prev => newType === 'PRIVATE' ? [p.user_id] : prev.includes(p.user_id) ? prev.filter(id => id !== p.user_id) : [...prev, p.user_id])}><Avatar item={p} small/><span>{p.username}</span><span className="checkbox">{selected.includes(p.user_id) && <Check size={14}/>}</span></button>)}</div><button className="primary-button" disabled={!selected.length || (newType === 'GROUP' && !groupName.trim())}>{newType === 'GROUP' ? 'Tạo nhóm trò chuyện' : 'Bắt đầu trò chuyện'}<ArrowUpRight size={17}/></button></form>}
      {modal === 'settings' && <div className="settings-content"><button className="primary-button" onClick={onConnect}>Chuyển sang backend thật</button><p>Đây là bản xem trước giao diện. Tin nhắn và nhóm được lưu trên trình duyệt hiện tại, chưa kết nối backend.</p><label className="switch-row"><span><strong>Phản hồi tự động</strong><small>Mô phỏng người nhận trả lời khi bạn gửi tin.</small></span><input type="checkbox" checked={autoReply} onChange={e => setAutoReply(e.target.checked)}/></label><div className="settings-note"><Info size={18}/>Trạng thái hoạt động và đã đọc đều là dữ liệu mô phỏng.</div></div>}
      {modal === 'profile' && <div className="profile-modal"><Avatar item={currentUser} large/><h3>{currentUser.username}</h3><p>{currentUser.role}</p><span className="demo-tag">TÀI KHOẢN MẪU</span><p className="profile-note">Bạn đang trải nghiệm với tài khoản mẫu. Chức năng đăng nhập sẽ được nối khi backend sẵn sàng.</p></div>}
    </dialog>{notice && <div className="toast" role="status"><Check size={17}/>{notice}</div>}
  </div>;
}
