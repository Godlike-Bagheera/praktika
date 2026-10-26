import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, errorMessage, extractErrors } from '../api';
import { useAuth } from '../AuthContext';
import Alert from '../components/Alert';
import Spinner from '../components/Spinner';

export default function PostEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [post, setPost] = useState(null);
  const [text, setText] = useState('');
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get(`/posts/${id}`)
      .then((resp) => {
        const p = resp.data;
        if (user && p.owner.id !== user.id) {
          setFormError('Редактировать сообщение может только его автор.');
        }
        setPost(p);
        setText(p.text);
      })
      .catch((err) => setFormError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [id, user]);

  async function onSubmit(e) {
    e.preventDefault();
    setFormError('');
    const trimmed = text.trim();
    const errs = {};
    if (!trimmed || trimmed.length > 2000) {
      errs.text = 'Введите сообщение (до 2000 символов)';
    }
    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }
    setBusy(true);
    try {
      await api.put(`/posts/${id}`, { text: trimmed });
      navigate(`/topics/${post.topic}`, { replace: true });
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
      <div className="col-md-8 col-lg-7">
        <h1 className="h3 mb-4">Редактирование сообщения</h1>
        <Alert>{formError}</Alert>
        {post && !formError && (
          <form onSubmit={onSubmit} noValidate className="card shadow-sm">
            <div className="card-body">
              <div className="mb-2 text-muted-small">
                Тема: <Link to={`/topics/${post.topic}`}>{post.topic_title}</Link> · Автор: {post.owner.username}
              </div>
              <textarea
                className={`form-control ${errors.text ? 'is-invalid' : ''}`}
                rows={6}
                maxLength={2000}
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
              {errors.text && <div className="invalid-feedback d-block">{errors.text}</div>}
            </div>
            <div className="card-footer d-flex gap-2">
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? 'Сохранение...' : 'Сохранить'}
              </button>
              <button type="button" className="btn btn-light" onClick={() => navigate(`/topics/${post.topic}`)}>
                Отмена
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
