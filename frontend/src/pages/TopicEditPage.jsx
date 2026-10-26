import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, errorMessage, extractErrors } from '../api';
import { useAuth } from '../AuthContext';
import Alert from '../components/Alert';
import Spinner from '../components/Spinner';

export default function TopicEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [topic, setTopic] = useState(null);
  const [title, setTitle] = useState('');
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get(`/topics/${id}`)
      .then((resp) => {
        const t = resp.data;
        // Редактировать может только владелец
        if (user && t.owner.id !== user.id) {
          setFormError('Редактировать тему может только её автор.');
        }
        setTopic(t);
        setTitle(t.title);
      })
      .catch((err) => setFormError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [id, user]);

  async function onSubmit(e) {
    e.preventDefault();
    setFormError('');
    const trimmed = title.trim();
    const errs = {};
    if (!trimmed || trimmed.length > 120) {
      errs.title = 'Введите название темы (до 120 символов)';
    }
    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }
    setBusy(true);
    try {
      await api.put(`/topics/${id}`, { category: topic.category, title: trimmed });
      navigate(`/topics/${id}`, { replace: true });
    } catch (err) {
      const serverErrs = extractErrors(err);
      if (serverErrs.detail && Object.keys(serverErrs).length === 1) {
        setFormError(serverErrs.detail);
      } else {
        setErrors(serverErrs);
      }
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner />;

  return (
    <div className="row justify-content-center">
      <div className="col-md-8 col-lg-6">
        <h1 className="h3 mb-4">Редактирование темы</h1>
        <Alert>{formError}</Alert>
        {topic && !formError && (
          <form onSubmit={onSubmit} noValidate className="card shadow-sm">
            <div className="card-body">
              <div className="mb-2 text-muted-small">
                Категория: {topic.category_name} · Автор: {topic.owner.username}
              </div>
              <div className="mb-3">
                <label className="form-label">Название темы</label>
                <input
                  className={`form-control ${errors.title ? 'is-invalid' : ''}`}
                  value={title}
                  maxLength={120}
                  onChange={(e) => setTitle(e.target.value)}
                  disabled={!!formError}
                />
                {errors.title && <div className="invalid-feedback d-block">{errors.title}</div>}
              </div>
            </div>
            <div className="card-footer d-flex gap-2">
              <button type="submit" className="btn btn-primary" disabled={busy || !!formError}>
                {busy ? 'Сохранение...' : 'Сохранить'}
              </button>
              <button type="button" className="btn btn-light" onClick={() => navigate(`/topics/${id}`)}>
                Отмена
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
