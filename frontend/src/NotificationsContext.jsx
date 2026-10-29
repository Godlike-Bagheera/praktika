import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { api } from './api';

const NotificationsContext = createContext(null);

export const NOTIF_POLL_MS = 15000; // период опроса новых упоминаний
export const TOAST_TTL_MS = 5000;   // тост живёт 5 секунд, затем плавно исчезает
const TOAST_FADE_MS = 400;          // длительность плавного исчезновения (совпадает с CSS)

// Простейшая очередь «всплывающих» уведомлений: справа снизу, плавное
// появление, авто-скрытие через 5 секунд с плавным исчезновением.
function Toast({ toast, onDismiss }) {
  const timerRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    timerRef.current = setTimeout(() => onDismiss(toast.id), TOAST_TTL_MS);
    return () => clearTimeout(timerRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={`notif-toast ${toast.leaving ? 'is-leaving' : ''}`}>
      <button
        type="button"
        className="notif-toast-close"
        aria-label="Закрыть"
        onClick={() => onDismiss(toast.id)}
      >
        ×
      </button>
      <div className="notif-toast-title">
        <span className="notif-toast-from">@{toast.me}</span> — вас упомянул{' '}
        <strong>{toast.from_user?.username}</strong>
      </div>
      <div className="notif-toast-text">{toast.text}</div>
      <a
        className="notif-toast-link"
        href={`/topics/${toast.topic_id}`}
        onClick={(e) => {
          e.preventDefault();
          onDismiss(toast.id, false);
          navigate(`/topics/${toast.topic_id}`);
        }}
      >
        {toast.category_name} → {toast.topic_title}
      </a>
    </div>
  );
}

export function NotificationsProvider({ children }) {
  const { user } = useAuth();
  const [unread, setUnread] = useState(0);
  const [toasts, setToasts] = useState([]);
  const seenIdsRef = useRef(new Set());
  const initializedRef = useRef(false);

  const dismissToast = useCallback((id, markRead = true) => {
    setToasts((list) =>
      list.map((t) => (t.id === id ? { ...t, leaving: true } : t)),
    );
    if (markRead) {
      api.post('/notifications/read', { ids: [id] }).catch(() => {});
      setUnread((n) => Math.max(0, n - 1));
    }
    setTimeout(() => {
      setToasts((list) => list.filter((t) => t.id !== id));
    }, TOAST_FADE_MS);
  }, []);

  const poll = useCallback(async () => {
    try {
      const [{ data: countData }, { data: recent }] = await Promise.all([
        api.get('/notifications/count'),
        api.get('/notifications', { params: { unread: 1, limit: 5 } }),
      ]);
      setUnread(countData.count ?? 0);

      const items = recent.results ?? recent ?? [];
      // При первом опросе ничего не всплываем — показываем только совсем
      // свежие уведомления, иначе после перезагрузки вывалится пачка старых.
      if (!initializedRef.current) {
        items.forEach((it) => seenIdsRef.current.add(it.id));
        initializedRef.current = true;
        return;
      }
      const fresh = items.filter((it) => !seenIdsRef.current.has(it.id));
      fresh.forEach((it) => seenIdsRef.current.add(it.id));
      if (fresh.length) {
        setToasts((list) => [...fresh.map((it) => ({ ...it, me: user.username })), ...list].slice(0, 4));
      }
    } catch {
      /* сеть/токен — следующий цикл разберётся */
    }
  }, [user]);

  useEffect(() => {
    if (!user) {
      setUnread(0);
      setToasts([]);
      initializedRef.current = false;
      seenIdsRef.current = new Set();
      return undefined;
    }
    initializedRef.current = false;
    poll();
    const timer = setInterval(poll, NOTIF_POLL_MS);
    return () => clearInterval(timer);
  }, [user, poll]);

  return (
    <NotificationsContext.Provider value={{ unread, refreshCount: poll }}>
      {children}
      <div className="notif-toast-container" aria-live="polite">
        {toasts.map((t) => (
          <Toast key={t.id} toast={t} onDismiss={dismissToast} />
        ))}
      </div>
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  return useContext(NotificationsContext);
}
