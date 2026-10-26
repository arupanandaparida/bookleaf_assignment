const TOKEN_KEY = 'bookleaf_token';
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.error?.message || `Request failed (${status})`);
    this.status = status;
    this.code = body?.error?.code;
    this.details = body?.error?.details;
  }
}

async function request(method, path, body) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && getToken()) { setToken(null); window.location.assign('/login'); }
    throw new ApiError(res.status, data);
  }
  return data;
}

const qs = (o = {}) => {
  const p = new URLSearchParams(Object.entries(o).filter(([, v]) => v !== '' && v != null));
  return p.toString() ? `?${p}` : '';
};

export const api = {
  login: (email, password) => request('POST', '/auth/login', { email, password }),
  me: () => request('GET', '/auth/me'),
  meta: () => request('GET', '/meta'),
  books: () => request('GET', '/books'),
  tickets: (filters) => request('GET', `/tickets${qs(filters)}`),
  ticket: (id) => request('GET', `/tickets/${id}`),
  createTicket: (data) => request('POST', '/tickets', data),
  updateTicket: (id, patch) => request('PATCH', `/tickets/${id}`, patch),
  reply: (id, body, status) => request('POST', `/tickets/${id}/messages`, { body, status }),
  addNote: (id, body) => request('POST', `/tickets/${id}/notes`, { body }),
  draft: (id, regenerate = false) => request('POST', `/tickets/${id}/draft?regenerate=${regenerate}`),
  reclassify: (id) => request('POST', `/tickets/${id}/reclassify`),
  stats: () => request('GET', '/admin/stats'),
  admins: () => request('GET', '/admin/admins'),
};
