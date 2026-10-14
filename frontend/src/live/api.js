export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function createApi(base = '/api', fetcher = fetch) {
  const root = base.replace(/\/$/, '');
  let csrfToken = null;
  let onUnauthorized = () => {};

  async function loadCsrfToken() {
    let response;
    try {
      response = await fetcher(`${root}/auth/csrf/`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new ApiError('Không kết nối được API. Kiểm tra Django và cấu hình proxy.');
    }
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new ApiError(`API trả về dữ liệu không phải JSON (HTTP ${response.status}).`, response.status);
    }
    if (!response.ok || typeof payload.csrfToken !== 'string') {
      throw new ApiError(payload?.error || 'Không lấy được mã CSRF.', response.status);
    }
    csrfToken = payload.csrfToken;
    return csrfToken;
  }

  async function request(path, { method = 'GET', body, signal, headers = {}, allowUnauthorized = false } = {}) {
    const form = body instanceof FormData;
    const upperMethod = method.toUpperCase();
    const requestHeaders = { Accept: 'application/json', ...headers };
    if (body !== undefined && !form) requestHeaders['Content-Type'] = 'application/json';
    if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(upperMethod)) {
      if (!csrfToken) await loadCsrfToken();
      requestHeaders['X-CSRFToken'] = csrfToken;
    }

    let response;
    try {
      response = await fetcher(`${root}${path}`, {
        method: upperMethod,
        credentials: 'same-origin',
        signal: signal || AbortSignal.timeout(15000),
        ...(body === undefined ? {} : { body: form ? body : JSON.stringify(body) }),
        headers: requestHeaders,
      });
    } catch (error) {
      if (error.name === 'AbortError' || error.name === 'TimeoutError') throw error;
      throw new ApiError('Không kết nối được API. Kiểm tra Django và cấu hình proxy.');
    }

    if (response.status === 204) return null;
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new ApiError(
        `API trả về dữ liệu không phải JSON (HTTP ${response.status}). Kiểm tra backend và cấu hình proxy.`,
        response.status,
      );
    }
    if (response.status === 401 && !allowUnauthorized) onUnauthorized();
    if (!response.ok) throw new ApiError(payload?.error || `API báo lỗi ${response.status}`, response.status);
    if (path === '/auth/login/') csrfToken = payload.csrfToken || csrfToken;
    if (path === '/auth/logout/') csrfToken = null;
    return payload;
  }

  const userPath = id => `/users/${encodeURIComponent(id)}`;
  const conversationPath = id => `/conversations/${encodeURIComponent(id)}`;
  return {
    setUnauthorizedHandler(handler) {
      onUnauthorized = typeof handler === 'function' ? handler : () => {};
    },
    csrf: loadCsrfToken,
    register: (credentials) => request('/auth/register/', { method: 'POST', body: credentials, allowUnauthorized: true }),
    login: (credentials) => request('/auth/login/', { method: 'POST', body: credentials, allowUnauthorized: true }),
    me: () => request('/auth/me/', { allowUnauthorized: true }),
    logout: () => request('/auth/logout/', { method: 'POST', allowUnauthorized: true }),
    searchUsers: (username, signal) => request(`/users/search/?${new URLSearchParams({ username })}`, { signal }),
    createUser: () => Promise.reject(new ApiError('Hãy đăng ký bằng tài khoản và mật khẩu.', 410)),
    updateUser: (id, profile) => request(`${userPath(id)}/`, { method: 'PATCH', body: profile }),
    uploadAvatar(id, file) {
      validateAvatar(file);
      const body = new FormData();
      body.append('avatar', file);
      return request(`${userPath(id)}/avatar/`, { method: 'POST', body });
    },
    removeAvatar: id => request(`${userPath(id)}/avatar/`, { method: 'DELETE' }),
    createConversation: body => {
      const { user_id, ...payload } = body;
      return request('/conversations/', { method: 'POST', body: payload });
    },
    listConversations: id => request(`${userPath(id)}/conversations/`),
    history(id, _userId, beforeSeq, signal) {
      const params = new URLSearchParams({ limit: '50' });
      if (beforeSeq != null) params.set('before_seq', String(beforeSeq));
      return request(`${conversationPath(id)}/messages/?${params}`, { signal });
    },
    searchMessages(id, _userId, query, beforeSeq, signal) {
      const params = new URLSearchParams({ q: query, limit: '50' });
      if (beforeSeq != null) params.set('before_seq', String(beforeSeq));
      return request(`${conversationPath(id)}/messages/search/?${params}`, { signal });
    },
    groupDetails: id => request(`${conversationPath(id)}/`),
    updateGroup(id, version, fields) {
      return request(`${conversationPath(id)}/`, {
        method: 'PATCH',
        body: fields,
        headers: { 'If-Match': `"${version}"` },
      });
    },
    removeGroupMember(id, userId, version) {
      return request(`${conversationPath(id)}/members/${encodeURIComponent(userId)}/`, {
        method: 'DELETE',
        headers: { 'If-Match': `"${version}"` },
      });
    },
    leaveGroup(id, version) {
      return request(`${conversationPath(id)}/leave/`, {
        method: 'POST',
        headers: { 'If-Match': `"${version}"` },
      });
    },
    setGroupMemberRole(id, userId, version, role) {
      return request(`${conversationPath(id)}/members/${encodeURIComponent(userId)}/role/`, {
        method: 'PATCH',
        body: { role },
        headers: { 'If-Match': `"${version}"` },
      });
    },
    transferGroupOwnership(id, version, newOwnerId) {
      return request(`${conversationPath(id)}/transfer-ownership/`, {
        method: 'POST',
        body: { new_owner_id: newOwnerId },
        headers: { 'If-Match': `"${version}"` },
      });
    },
    archiveGroup(id, version) {
      return request(`${conversationPath(id)}/archive/`, {
        method: 'POST',
        headers: { 'If-Match': `"${version}"` },
      });
    },
    friends(id, { query = '', onlineOnly = false, cursor = null, limit = 25, signal } = {}) {
      const params = new URLSearchParams({ limit: String(limit) });
      if (query) params.set('q', query);
      if (onlineOnly) params.set('online', 'true');
      if (cursor) params.set('cursor', cursor);
      return request(`${userPath(id)}/friends/?${params}`, { signal });
    },
    invitations: (id, signal) => request(`${userPath(id)}/invitations/`, { signal }),
    removeFriend: (id, peer) => request(`${userPath(id)}/friends/${encodeURIComponent(peer)}/`, { method: 'DELETE' }),
    invite: (_senderId, userId) => request('/invitations/', { method: 'POST', body: { user_id: userId } }),
    respond: (id, _userId, status) => request(`/invitations/${encodeURIComponent(id)}/respond/`, {
      method: 'POST',
      body: { status },
    }),
    inviteRoom(_senderId, userId, conversationId, version) {
      return request('/room-invitations/', {
        method: 'POST',
        body: { user_id: userId, conversation_id: conversationId },
        headers: { 'If-Match': `"${version}"` },
      });
    },
    respondRoom(id, _userId, status, version) {
      return request(`/room-invitations/${encodeURIComponent(id)}/respond/`, {
        method: 'POST',
        body: { status },
        headers: { 'If-Match': `"${version}"` },
      });
    },
    cancelRoomInvitation(id, version) {
      return request(`/room-invitations/${encodeURIComponent(id)}/`, {
        method: 'DELETE',
        headers: { 'If-Match': `"${version}"` },
      });
    },
  };
}

export function validateAvatar(file) {
  if (!file) throw new ApiError('Hãy chọn một ảnh.');
  if (file.size > 5 * 1024 * 1024) throw new ApiError('Ảnh đại diện phải nhỏ hơn hoặc bằng 5 MB.');
  if (!['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp', 'image/x-ms-bmp'].includes(file.type)) {
    throw new ApiError('Chỉ hỗ trợ JPEG, PNG, GIF, BMP hoặc WebP.');
  }
}

export function avatarUrl(value, apiBase = '/api') {
  if (!value) return null;
  try {
    const origin = /^https?:\/\//.test(apiBase) ? new URL(apiBase).origin : location.origin;
    const url = new URL(value, origin);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
