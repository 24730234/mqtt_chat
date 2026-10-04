export class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.status = status; }
}
export function createApi(base = '/api', fetcher = fetch) {
  const root = base.replace(/\/$/, '');
  async function request(path, { method = 'GET', body, signal } = {}) {
    const form = body instanceof FormData;
    let response;
    try {
      response = await fetcher(`${root}${path}`, {
        method, signal: signal || AbortSignal.timeout(15000),
        ...(body === undefined ? {} : { body: form ? body : JSON.stringify(body) }),
        headers: { Accept: 'application/json', ...(!form && body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
      });
    } catch (error) {
      if (error.name === 'AbortError') throw error;
      throw new ApiError('Không kết nối được API. Kiểm tra Django và cấu hình proxy.');
    }
    let payload;
    try { payload = await response.json(); } catch { throw new ApiError(`API trả về dữ liệu không phải JSON (HTTP ${response.status}). Kiểm tra backend đã chạy và đúng API base; tài khoản fixture cần chọn Dùng server test.`, response.status); }
    if (!response.ok) throw new ApiError(payload?.error || `API báo lỗi ${response.status}`, response.status);
    return payload;
  }
  return {
    searchUsers: (username, signal) => request(`/users/search/?${new URLSearchParams({ username })}`, { signal }),
    createUser: (profile) => request('/users/', { method: 'POST', body: profile }),
    updateUser: (id, profile) => request(`/users/${encodeURIComponent(id)}/`, { method: 'PATCH', body: profile }),
    uploadAvatar(id, file) {
      validateAvatar(file);
      const body = new FormData(); body.append('avatar', file);
      return request(`/users/${encodeURIComponent(id)}/avatar/`, { method: 'POST', body });
    },
    removeAvatar: (id) => request(`/users/${encodeURIComponent(id)}/avatar/`, { method: 'DELETE' }),
    createConversation: (body) => request('/conversations/', { method: 'POST', body }),
    history(id, userId, beforeSeq, signal) {
      const params = new URLSearchParams({ user_id: userId, limit: '50' });
      if (beforeSeq != null) params.set('before_seq', String(beforeSeq));
      return request(`/conversations/${encodeURIComponent(id)}/messages/?${params}`, { signal });
    },
    searchMessages(id, userId, query, beforeSeq, signal) {
      const params = new URLSearchParams({ user_id: userId, q: query, limit: '50' });
      if (beforeSeq != null) params.set('before_seq', String(beforeSeq));
      return request(`/conversations/${encodeURIComponent(id)}/messages/search/?${params}`, { signal });
    },
    friends: (id) => request(`/users/${encodeURIComponent(id)}/friends/`),
    removeFriend: (id, peer) => request(`/users/${encodeURIComponent(id)}/friends/${encodeURIComponent(peer)}/`, { method: 'DELETE' }),
    invite: (sender_id, user_id) => request('/invitations/', { method: 'POST', body: { sender_id, user_id } }),
    respond: (id, user_id, status) => request(`/invitations/${encodeURIComponent(id)}/respond/`, { method: 'POST', body: { user_id, status } }),
  };
}
export function validateAvatar(file) {
  if (!file) throw new ApiError('Hãy chọn một ảnh.');
  if (file.size > 5 * 1024 * 1024) throw new ApiError('Ảnh đại diện phải nhỏ hơn hoặc bằng 5 MB.');
  if (!['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp', 'image/x-ms-bmp'].includes(file.type)) throw new ApiError('Chỉ hỗ trợ JPEG, PNG, GIF, BMP hoặc WebP.');
}
export function avatarUrl(value, apiBase = '/api') {
  if (!value) return null;
  try {
    const origin = /^https?:\/\//.test(apiBase) ? new URL(apiBase).origin : location.origin;
    const url = new URL(value, origin);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}
