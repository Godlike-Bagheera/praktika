import axios from 'axios';

const TOKEN_KEY = 'forum_access';
const REFRESH_KEY = 'forum_refresh';
const USER_KEY = 'forum_user';

export const tokenStore = {
  get access() {
    return localStorage.getItem(TOKEN_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set({ access, refresh, user }) {
    if (access) localStorage.setItem(TOKEN_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  },
  getUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY));
    } catch {
      return null;
    }
  },
};

export const api = axios.create({ baseURL: '/api' });

api.interceptors.request.use((config) => {
  const token = tokenStore.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let onUnauthorized = null;
export function setOnUnauthorized(fn) {
  onUnauthorized = fn;
}

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error.response && error.response.status === 401 && onUnauthorized) {
      onUnauthorized();
    }
    return Promise.reject(error);
  }
);

/** Извлекает сообщения об ошибках валидации в виде {поле: сообщение}. */
export function extractErrors(error) {
  const data = error?.response?.data;
  if (data && typeof data === 'object') {
    if (data.errors && typeof data.errors === 'object') return data.errors;
    if (typeof data.detail === 'string') return { detail: data.detail };
    // стандартный DRF-формат {field: [msgs]}
    const out = {};
    Object.keys(data).forEach((k) => {
      const v = data[k];
      out[k] = Array.isArray(v) ? String(v[0]) : String(v);
    });
    return out;
  }
  return { detail: 'Произошла ошибка. Попробуйте ещё раз.' };
}

export function errorMessage(error) {
  const errs = extractErrors(error);
  return errs.detail || Object.values(errs)[0] || 'Произошла ошибка';
}

/** Скачивание Excel с авторизацией; возвращает Blob. */
export async function downloadExport(params) {
  const resp = await api.get('/posts/export', {
    params,
    responseType: 'blob',
  });
  return resp.data;
}
