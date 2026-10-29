import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

// Всплывающие тосты о новых жалобах для админа: polling unread-count каждые 10 сек.
// prevCount храним в useRef — так интервал не пересоздаётся на каждое обновление
// состояния (в отличие от варианта с prevCount в deps useEffect).
export default function ReportToast({ isAdmin }) {
  const [toasts, setToasts] = useState([]);
  const prevCountRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!isAdmin) return undefined;
    let cancelled = false;

    const checkNewReports = async () => {
      try {
        const response = await api.get('/admin-report-notifications/unread-count/');
        if (cancelled) return;
        const newCount = response.data.count || 0;
        const prev = prevCountRef.current;
        // Первый опрос (prev === null) только запоминаем базовое значение,
        // чтобы не показывать тосты за старые жалобы при загрузке страницы.
        if (prev !== null && newCount > prev) {
          const diff = newCount - prev;
          const newToast = {
            id: Date.now(),
            message:
              diff === 1 ? 'Новая жалоба на сообщение' : `Новых жалоб: ${diff}`,
            time: new Date().toLocaleTimeString('ru-RU', {
              hour: '2-digit',
              minute: '2-digit',
            }),
          };
          setToasts((old) => [...old, newToast]);
          setTimeout(() => {
            setToasts((old) => old.filter((t) => t.id !== newToast.id));
          }, 5000);
        }
        prevCountRef.current = newCount;
      } catch (err) {
        console.error('Failed to check report count', err);
      }
    };

    checkNewReports();
    const interval = setInterval(checkNewReports, 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [isAdmin]);

  if (toasts.length === 0) return null;

  return (
    <div
      className="report-toast-stack"
      role="status"
      aria-live="polite"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="report-toast"
          onClick={() => navigate('/reports')}
        >
          <div className="report-toast-title">{toast.message}</div>
          <div className="report-toast-time">
            {toast.time} • Нажмите чтобы просмотреть
          </div>
        </div>
      ))}
    </div>
  );
}
