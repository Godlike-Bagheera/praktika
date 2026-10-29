import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { api } from './api';

const NotificationsContext = createContext(null);

export const NOTIF_POLL_MS = 5000; // период фонового опроса новых упоминаний (5 сек)
export const TOAST_TTL_MS = 5000;   // тост живёт 5 секунд, затем плавно исчезает
const TOAST_FADE_MS = 400;          // длительность плавного исчезновения (совпадает с CSS)

// Простейшая очередь «всплывающих» уведомлений: справа снизу, плавное
// появление, авто-скрытие через 5 секунд с плавным исчезновением.
function Toast({ toast, onDismiss }) {
  const timerRef = useRef(null);
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  useEffect(() => {
    timerRef.current = setTimeout(() => onDismiss(toast.id), TOAST_TTL_MS);
    return () => clearTimeout(timerRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Если в тексте поста есть жалоба от модерационной системы — для админа
  // показываем специальный заголовок.
  const isReportToast = isAdmin && toast.is_report;

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
        {isReportToast ? (
          <>
            Новая жалоба на сообщение в теме{' '}
            <strong>{toast.topic_title}</strong>
          </>
        ) : (
          <>
            <span className="notif-toast-from">@{toast.me}</span> — вас упомянул{' '}
            <strong>{toast.from_user?.username}</strong>
          </>
        )}
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
  // Актуальные данные пользователя для poll — через ref, чтобы колбэк poll не
  // пересоздавался при каждом обновлении объекта user (иначе useEffect ниже
  // сбрасывал инициализацию и пересоздавал интервал на каждый render).
  const userRef = useRef(user);
  userRef.current = user;
  // Счётчик смонтированного провайдера: защита от «гонки» — результаты
  // асинхронного опроса применяются только если провайдер ещё жив и это тот
  // же цикл инициализации.
  const epochRef = useRef(0);

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
    const epoch = epochRef.current;
    try {
      const [{ data: countData }, { data: recent }] = await Promise.all([
        api.get('/notifications/count'),
        api.get('/notifications', { params: { unread: 1, limit: 10 } }),
      ]);
      // провайдер перемонтирован (logout/login) или сменилась сессия —
      // устаревший ответ не должен трогать состояние
      if (epoch !== epochRef.current || !userRef.current) return;
      setUnread(countData.count ?? 0);

      const items = recent.results ?? recent ?? [];
      // Ключ дедупликации — ID уведомления (Set в useRef), а НЕ created_at:
      // сравнение по времени с таймзонами давало бы и дубли, и молчание.
      //   • Первый опрос после монтирования (F5): показываем непрочитанные
      //     из ленты один раз и заносим их в Set — при следующем опросе или
      //     повторной перезагрузке те же ID уже в Set, дублей нет.
      //   • Каждый последующий опрос: тост только для ID, которых нет в Set.
      const addSeen = (it) => seenIdsRef.current.add(it.id);
      const username = userRef.current.username;
      if (!initializedRef.current) {
        const toShow = items.filter((it) => !seenIdsRef.current.has(it.id));
        items.forEach(addSeen);
        initializedRef.current = true;
        if (toShow.length) {
          setToasts((list) => [...toShow.map((it) => ({ ...it, me: username })), ...list].slice(0, 4));
        }
        return;
      }
      const fresh = items.filter((it) => !seenIdsRef.current.has(it.id));
      items.forEach(addSeen);
      if (fresh.length) {
        setToasts((list) => [...fresh.map((it) => ({ ...it, me: username })), ...list].slice(0, 4));
      }
    } catch {
      /* сеть/токен — следующий цикл разберётся */
    }
  }, []); // стабильный колбэк: интервал больше не пересоздаётся

  useEffect(() => {
    if (!user) {
      epochRef.current += 1;
      setUnread(0);
      setToasts([]);
      initializedRef.current = false;
      seenIdsRef.current = new Set();
      return undefined;
    }
    // сброс только при СМЕНЕ пользователя (login/logout), но не при каждом
    // обновлении объекта user: иначе Set чистился бы между поллингами и
    // одни и те же непрочитанные всплывали бы повторно («тосты после F5»)
    epochRef.current += 1;
    initializedRef.current = false;
    seenIdsRef.current = new Set();
    poll();
    const timer = setInterval(poll, NOTIF_POLL_MS);
    // Внеочередной опрос, когда пользователь возвращается во вкладку.
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') poll();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

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
