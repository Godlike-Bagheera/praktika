import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import Spinner from '../components/Spinner';
import Pagination from '../components/Pagination';
import { useNotifications } from '../NotificationsContext';

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return '';
  }
}

export default function NotificationsPage() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const notifications = useNotifications();

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { data: resp } = await api.get('/notifications', { params: { page } });
      setData(resp);
    } catch (e) {
      setError(e?.response?.data?.detail ?? 'Не удалось загрузить уведомления');
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  const markAllRead = async () => {
    await api.post('/notifications/read', {}).catch(() => {});
    notifications?.refreshCount?.();
    load();
  };

  const items = data?.results ?? [];
  const hasUnread = items.some((it) => !it.read_at);

  return (
    <div className="notifications-page">
      <div className="d-flex align-items-center justify-content-between mb-4">
        <h1 className="page-title mb-0">Уведомления</h1>
        {(notifications?.unread > 0 || hasUnread) && (
          <button type="button" className="btn btn-forum btn-sm" onClick={markAllRead}>
            Прочитать все
          </button>
        )}
      </div>

      {loading && <Spinner />}
      {error && <div className="alert alert-danger">{error}</div>}
      {!loading && !error && items.length === 0 && (
        <div className="notif-empty">Пока нет уведомлений. Вас упомянут здесь, когда кто-то напишет @ваше_имя в сообщении.</div>
      )}

      {!loading && items.length > 0 && (
        <div className="notif-list">
          {items.map((it) => (
            <Link
              key={it.id}
              to={`/topics/${it.topic_id}?post=${it.post_id}`}
              className={`notif-item ${it.read_at ? '' : 'is-unread'}`}
              onClick={() => {
                if (!it.read_at) {
                  api.post('/notifications/read', { ids: [it.id] }).catch(() => {});
                  notifications?.refreshCount?.();
                }
              }}
            >
              <div className="notif-item-head">
                <strong>{it.from_user?.username}</strong>
                <span className="notif-item-where">
                  упомянул вас в теме{' '}
                  <b>{it.topic_title}</b>
                  {' · категория '}
                  <b>{it.category_name}</b>
                </span>
                <span className="notif-item-date">{formatDate(it.created_at)}</span>
              </div>
              <div className="notif-item-text">{it.text}</div>
            </Link>
          ))}
        </div>
      )}

      {data && (
        <Pagination count={data.count} limit={data.limit ?? 20} page={data.page} onChange={setPage} />
      )}
    </div>
  );
}
