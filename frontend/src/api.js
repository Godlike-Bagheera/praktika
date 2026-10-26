import axios from 'axios';

const USER_KEY = 'forum_user';

// Токены хранятся в httpOnly-куках (устанавливает сервер), JS их не видит.
// В localStorage остаётся только кэш профиля пользователя для UI.
export const tokenStore = {
  set({ user }) {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() {
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

export const api = axios.create({
  baseURL: '/api',
  withCredentials: true, // слать httpOnly-куки с каждым запросом
});

let onUnauthorized = null;
export function setOnUnauthorized(fn) {
  onUnauthorized = fn;
}

// Флаг «идёт обновление токена», чтобы параллельные 401 не плодили рефреши
let refreshingPromise = null;

async function tryRefresh() {
  if (!refreshingPromise) {
    refreshingPromise = axios
      .post('/api/auth/refresh', {}, { withCredentials: true })
      .finally(() => {
        refreshingPromise = null;
      });
  }
  try {
    await refreshingPromise;
    return true; // новая access-кука установлена сервером
  } catch {
    return false; // refresh тоже истёк/заблокирован
  }
}

api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const req = error.config || {};
    const resp = error.response;
    // 401 на самом логине/рефреше — не перепроверять, иначе цикл
    const isAuthEndpoint =
      req.url && (req.url.includes('/auth/login') || req.url.includes('/auth/refresh'));
    if (resp && resp.status === 401 && !isAuthEndpoint && !req._retried) {
      const ok = await tryRefresh();
      if (ok) {
        req._retried = true; // повтор исходного запроса с новой кукой
        return api.request(req);
      }
      if (onUnauthorized) onUnauthorized();
    } else if (resp && resp.status === 401 && !req._retried) {
      if (onUnauthorized) onUnauthorized();
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
