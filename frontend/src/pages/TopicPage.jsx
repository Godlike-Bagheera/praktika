import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, downloadExport, errorMessage, extractErrors } from '../api';
import { useAuth } from '../AuthContext';
import Alert from '../components/Alert';
import Pagination from '../components/Pagination';
import Spinner from '../components/Spinner';

export default function TopicPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, isAdmin } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') || '';
  const page = parseInt(searchParams.get('page') || '1', 10);

  const [topic, setTopic] = useState(null);
  const [posts, setPosts] = useState([]);
  const [count, setCount] = useState(0);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchInput, setSearchInput] = useState(search);

  const [newText, setNewText] = useState('');
  const [postError, setPostError] = useState('');
  const [sending, setSending] = useState(false);
  const [exporting, setExporting] = useState(false);

  const loadTopic = useCallback(() => {
    api
      .get(`/topics/${id}`)
      .then((resp) => setTopic(resp.data))
      .catch((err) => setError(errorMessage(err)));
  }, [id]);

  const loadPosts = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get(`/topics/${id}/posts`, {
        params: { page, limit: 20, search: search || undefined },
      });
      setPosts(resp.data.results);
      setCount(resp.data.count);
      setLimit(resp.data.limit);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [id, page, search]);

  useEffect(() => {
    loadTopic();
  }, [loadTopic]);

  useEffect(() => {
    loadPosts();
  }, [loadPosts]);

  function applySearch(e) {
    e.preventDefault();
    const params = {};
    if (searchInput.trim()) params.search = searchInput.trim();
    setSearchParams(params);
  }

  function changePage(p) {
    const params = {};
    if (search) params.search = search;
    params.page = String(p);
    setSearchParams(params);
    window.scrollTo({ top: 0 });
  }

  async function addPost(e) {
    e.preventDefault();
    setPostError('');
    const text = newText.trim();
    if (!text || text.length > 2000) {
      setPostError('Введите сообщение (до 2000 символов)');
      return;
    }
    setSending(true);
    try {
      await api.post(`/topics/${id}/posts`, { text });
      setNewText('');
      // переходим на последнюю страницу, чтобы видеть новое сообщение
      const total = count + 1;
      const lastPage = Math.max(1, Math.ceil(total / limit));
      loadPosts();
      if (lastPage !== page) changePage(lastPage);
    } catch (err) {
      const errs = extractErrors(err);
      setPostError(errs.text || errs.detail || 'Не удалось отправить сообщение');
    } finally {
      setSending(false);
    }
  }

  async function deletePost(post) {
    if (!window.confirm('Удалить это сообщение?')) return;
    try {
      await api.delete(`/posts/${post.id}`);
      loadPosts();
      loadTopic();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function deleteTopic() {
    if (!window.confirm(`Удалить тему «${topic.title}» и все её сообщения?`)) return;
    try {
      await api.delete(`/topics/${id}`);
      navigate(topic ? `/categories/${topic.category}` : '/', { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function exportExcel() {
    setExporting(true);
    setError('');
    try {
      const blob = await downloadExport({ topic: id, search: search || undefined });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const today = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `forum_posts_${today}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      // при ошибке тело — JSON в виде blob
      let msg = 'Не удалось выполнить экспорт';
      try {
        const text = await err.response?.data?.text?.();
        const json = text ? JSON.parse(text) : null;
        msg = json?.errors?.detail || msg;
      } catch {
        /* ignore */
      }
      setError(msg);
    } finally {
      setExporting(false);
    }
  }

  const canEditTopic = topic && user && topic.owner.id === user.id;
  const canDeleteTopic = topic && user && (topic.owner.id === user.id || isAdmin);

  return (
    <div>
      <nav aria-label="breadcrumb">
        <ol className="breadcrumb">
          <li className="breadcrumb-item"><Link to="/">Категории</Link></li>
          <li className="breadcrumb-item">
            {topic && <Link to={`/categories/${topic.category}`}>{topic.category_name}</Link>}
          </li>
          <li className="breadcrumb-item active">Тема</li>
        </ol>
      </nav>

      {loading && !topic ? (
        <Spinner />
      ) : (
        <>
          <Alert>{error}</Alert>

          {topic && (
            <div className="card shadow-sm mb-4">
              <div className="card-body">
                <div className="d-flex justify-content-between align-items-start flex-wrap gap-2">
                  <div>
                    <h1 className="h4 mb-1">{topic.title}</h1>
                    <div className="text-muted-small">
                      Автор: {topic.owner.username} · Создана: {new Date(topic.created_at).toLocaleString('ru-RU')}
                    </div>
                  </div>
                  <div className="d-flex gap-2">
                    {canEditTopic && (
                      <button className="btn btn-sm btn-outline-secondary" onClick={() => navigate(`/topics/${id}/edit`)}>
                        Редактировать
                      </button>
                    )}
                    {canDeleteTopic && (
                      <button className="btn btn-sm btn-outline-danger" onClick={deleteTopic}>
                        Удалить тему
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h2 className="h5 mb-0">Сообщения ({count})</h2>
            <div className="d-flex gap-2">
              <form onSubmit={applySearch} className="d-flex gap-2">
                <input
                  className="form-control form-control-sm"
                  placeholder="Поиск по сообщениям..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                />
                <button className="btn btn-sm btn-outline-secondary">Найти</button>
              </form>
              <button className="btn btn-sm btn-success" onClick={exportExcel} disabled={exporting}>
                {exporting ? 'Экспорт...' : '📥 Скачать Excel'}
              </button>
            </div>
          </div>

          {loading ? (
            <Spinner />
          ) : posts.length === 0 ? (
            <div className="alert alert-info">
              {search ? 'Ничего не найдено' : 'В теме нет сообщений. Напишите первое!'}
            </div>
          ) : (
            <div className="mb-3">
              {posts.map((p) => (
                <div key={p.id} className="card post-card shadow-sm mb-2">
                  <div className="card-body py-2">
                    <div className="d-flex justify-content-between align-items-start">
                      <div
                        className="flex-grow-1"
                        style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                      >
                        {p.text}
                      </div>
                      {(p.owner.id === user?.id || isAdmin) && (
                        <div className="d-flex gap-1 ms-3 flex-shrink-0">
                          {p.owner.id === user?.id && (
                            <button
                              className="btn btn-sm btn-outline-secondary py-0 px-2"
                              onClick={() => navigate(`/posts/${p.id}/edit`)}
                            >
                              ✏️
                            </button>
                          )}
                          <button
                            className="btn btn-sm btn-outline-danger py-0 px-2"
                            onClick={() => deletePost(p)}
                          >
                            🗑
                          </button>
                        </div>
                      )}
                    </div>
                    <div className="text-muted-small mt-1">
                      {p.owner.username} · {new Date(p.created_at).toLocaleString('ru-RU')}
                      {p.updated_at !== p.created_at && ' (изменено)'}
                    </div>
                  </div>
                </div>
              ))}
              <Pagination count={count} limit={limit} page={page} onChange={changePage} />
            </div>
          )}

          <form onSubmit={addPost} className="card shadow-sm">
            <div className="card-body">
              <label className="form-label fw-semibold">Новое сообщение</label>
              <textarea
                className={`form-control ${postError ? 'is-invalid' : ''}`}
                rows={3}
                maxLength={2000}
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
                placeholder="Введите текст сообщения (до 2000 символов)"
              />
              {postError && <div className="invalid-feedback d-block">{postError}</div>}
              <div className="mt-2">
                <button type="submit" className="btn btn-primary" disabled={sending}>
                  {sending ? 'Отправка...' : 'Отправить'}
                </button>
              </div>
            </div>
          </form>
        </>
      )}
    </div>
  );
}
