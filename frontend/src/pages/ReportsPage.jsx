import { useCallback, useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api, errorMessage } from '../api';
import { useAuth } from '../AuthContext';
import Alert from '../components/Alert';
import Spinner from '../components/Spinner';

const REASON_LABELS = {
  spam: 'Спам',
  offtopic: 'Не по теме',
  insult: 'Оскорбление',
  other: 'Другое',
};

const STATUS_LABELS = {
  pending: 'На рассмотрении',
  resolved: 'Решено',
  dismissed: 'Отклонено',
};

const STATUS_BADGES = {
  pending: 'text-bg-warning',
  resolved: 'text-bg-success',
  dismissed: 'text-bg-secondary',
};

const FILTERS = [
  { value: '', label: 'Все' },
  { value: 'pending', label: 'На рассмотрении' },
  { value: 'resolved', label: 'Решено' },
  { value: 'dismissed', label: 'Отклонено' },
];

// Вспомогательная ссылка «название темы» по id поста: тянем topic id из
// GET /api/posts/<id>/ (в сериализаторе жалобы есть только post и post_title).
function PostTopicLink({ postId, fallbackTitle }) {
  const [topicId, setTopicId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/posts/${postId}`)
      .then((resp) => {
        if (!cancelled) setTopicId(resp.data.topic);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [postId]);

  if (!topicId) {
    return <span className="text-body-secondary">{fallbackTitle}</span>;
  }
  return (
    <Link to={`/topics/${topicId}?post=${postId}`} title="Открыть сообщение">
      {fallbackTitle}
    </Link>
  );
}

// Панель модерации жалоб (только админ).
export default function ReportsPage() {
  const { user, isAdmin } = useAuth();
  const [reports, setReports] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = statusFilter ? { status: statusFilter } : {};
      const resp = await api.get('/reports/', { params });
      setReports(resp.data);
      // Синхронизируем счётчик в хедере сразу после загрузки списка
      window.dispatchEvent(new Event('forum-reports-refresh'));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    if (isAdmin) loadReports();
  }, [isAdmin, loadReports]);

  if (!user) return <Navigate to="/login" replace />;
  if (!isAdmin) return <Navigate to="/" replace />;

  const doAction = async (reportId, action) => {
    setBusyId(reportId);
    setError('');
    try {
      await api.post(`/reports/${reportId}/action/`, { action });
      await loadReports(); // обновляем список без перезагрузки страницы
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="container py-4" style={{ maxWidth: 960 }}>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h1 className="h4 mb-0">Жалобы на сообщения</h1>
        <button
          type="button"
          className="btn btn-sm btn-outline-secondary"
          onClick={loadReports}
          disabled={loading}
        >
          Обновить
        </button>
      </div>

      {/* Фильтр по статусу */}
      <div className="btn-group mb-3" role="group" aria-label="Фильтр по статусу">
        {FILTERS.map((f) => (
          <button
            key={f.value || 'all'}
            type="button"
            className={`btn btn-sm ${statusFilter === f.value ? 'btn-primary' : 'btn-outline-primary'}`}
            onClick={() => setStatusFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <Alert color="danger">{error}</Alert>}

      {loading ? (
        <Spinner />
      ) : reports.length === 0 ? (
        <div className="empty-state">Жалоб нет</div>
      ) : (
        <div className="card shadow-sm">
          {/* Горизонтальный скролл на мобильных */}
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Автор жалобы</th>
                  <th>Пост</th>
                  <th>Причина</th>
                  <th>Статус</th>
                  <th>Дата</th>
                  <th className="text-end">Действия</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id}>
                    <td className="text-body-secondary">#{r.id}</td>
                    <td>{r.reporter_username}</td>
                    <td>
                      {/* r.post — id поста; ссылка на тему поста (см. GET /api/posts/<id>/) */}
                      <PostTopicLink postId={r.post} fallbackTitle={r.post_title} />
                      <div className="text-muted-small">автор поста: {r.post_author}</div>
                    </td>
                    <td>{REASON_LABELS[r.reason] || r.reason_display || r.reason}</td>
                    <td>
                      <span className={`badge ${STATUS_BADGES[r.status] || 'text-bg-secondary'}`}>
                        {STATUS_LABELS[r.status] || r.status_display || r.status}
                      </span>
                    </td>
                    <td className="text-muted-small text-nowrap">
                      {new Date(r.created_at).toLocaleString('ru-RU')}
                    </td>
                    <td className="text-end text-nowrap">
                      {r.status === 'pending' ? (
                        <>
                          <button
                            type="button"
                            className="btn btn-sm btn-danger me-1"
                            disabled={busyId === r.id}
                            onClick={() => doAction(r.id, 'resolve')}
                          >
                            Скрыть пост
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-secondary"
                            disabled={busyId === r.id}
                            onClick={() => doAction(r.id, 'dismiss')}
                          >
                            Отклонить
                          </button>
                        </>
                      ) : (
                        <span className="text-muted-small">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
