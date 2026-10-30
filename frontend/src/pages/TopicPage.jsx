import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, downloadExport, errorMessage, extractErrors } from '../api';
import { containsProfanity, PROFANITY_MESSAGE } from '../profanity';
import { useAuth } from '../AuthContext';
import Alert from '../components/Alert';
import Pagination from '../components/Pagination';
import PostEditModal from '../components/PostEditModal';
import ReportButton from '../components/ReportButton';
import Spinner from '../components/Spinner';

// Сколько постов тянем одной страницей при «перелёте» к посту по ссылке
// из уведомления (?post=<id>). Бэкенд ограничивает limit значением max_page_size.
const POST_LOCATE_LIMIT = 100;

export default function TopicPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, isAdmin } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') || '';
  const page = parseInt(searchParams.get('page') || '1', 10);
  // ссылка вида /topics/:id?post=<id> из уведомлений — на какой странице
  // находится нужный пост, заранее неизвестно (см. locatePost)
  const targetPostParam = searchParams.get('post');
  const targetPostId = Number.parseInt(targetPostParam, 10) || null;

  const [topic, setTopic] = useState(null);
  const [posts, setPosts] = useState([]);
  const [count, setCount] = useState(0);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  // подсвеченный пост, к которому мы «перелетели» по ссылке из уведомления
  const [highlightedPostId, setHighlightedPostId] = useState(null);
  // input — контролируемое поле поиска; searchParams обновляются с debounce
  const [inputValue, setInputValue] = useState(search);

  // синхронизируем поле, если ?search= изменился извне (ссылка/назад)
  useEffect(() => {
    setInputValue((prev) => ((prev.trim() === search) ? prev : search));
  }, [search]);

  const [newText, setNewText] = useState('');
  const [postError, setPostError] = useState('');
  const [sending, setSending] = useState(false);
  const [exporting, setExporting] = useState(false);
  // сообщение, открытое для редактирования в модалке (без перехода на другую страницу)
  const [editingPost, setEditingPost] = useState(null);

  const loadTopic = useCallback(() => {
    api
      .get(`/topics/${id}`)
      .then((resp) => setTopic(resp.data))
      .catch((err) => setError(errorMessage(err)));
  }, [id]);

  // «Перелёт» к посту по ссылке из уведомления (/topics/:id?post=<id>).
  // Порядок постов — новые сверху, поэтому страница, на которой лежит пост,
  // заранее неизвестна. Сортировка детерминированная (-created_at, -id), так
  // что позицию можно вычислить одним лёгким запросом count более новых
  // сообщений и открыть нужную страницу обычной пагинацией (limit=20).
  // Фолбэк для старых бэкендов без параметра `after`: тянем одну крупную
  // страницу (limit<=100 — максимум сервера) и находим пост в ней.
  const locatePost = useCallback(
    async (postId) => {
      setLoading(true);
      try {
        // Фолбэк на случай, когда нужную страницу вычислить не удалось
        // (старый бэкенд без `after` / пост глубже первой крупной страницы):
        // подтягиваем крупную страницу и показываем пост прямо из неё.
        const fallbackFetch = async () => {
          const resp = await api.get(`/topics/${id}/posts`, {
            params: { page: 1, limit: POST_LOCATE_LIMIT },
          });
          setPosts(resp.data.results);
          setCount(resp.data.count);
          setLimit(resp.data.limit);
          return (resp.data.results ?? []).some((p) => p.id === postId);
        };
        let targetPage = null;
        let newerCount = null;
        try {
          const resp = await api.get(`/topics/${id}/posts`, {
            params: { after: postId, limit: 1 },
          });
          newerCount = Number.parseInt(resp.data?.count, 10);
          if (!Number.isNaN(newerCount)) {
            targetPage = Math.floor(newerCount / 20) + 1;
          }
        } catch {
          /* старый бэкенд не знает про after — используем фолбэк ниже */
        }
        if (targetPage !== null) {
          const params = { page: String(targetPage) };
          if (search) params.search = search;
          setSearchParams(params, { replace: true });
          window.scrollTo({ top: 0 });
          return true;
        }
        return await fallbackFetch();
      } catch (err) {
        setError(errorMessage(err));
        return false;
      } finally {
        setLoading(false);
      }
    },
    [id, search, setSearchParams],
  );

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

  // Обработка ?post= при заходе в тему: находим страницу поста и переходим на
  // неё (параметр убирается из URL, чтобы повторные render-циклы не зациклили
  // запросы). Если пост пришёл во время просмотра этой же темы (переход по
  // тосту без remount-а компонента) — внеочередной locate через ref.
  useEffect(() => {
    if (!targetPostId) return undefined;
    let cancelled = false;
    (async () => {
      const found = await locatePost(targetPostId);
      if (cancelled) return;
      if (found) {
        setHighlightedPostId(targetPostId);
        // убираем только ?post=, сохраняя ?page= и ?search=
        setSearchParams(
          (prev) => {
            const params = new URLSearchParams(prev);
            params.delete('post');
            return params;
          },
          { replace: true },
        );
      } else {
        const params = {};
        if (search) params.search = search;
        setSearchParams(params, { replace: true });
        setError('Сообщение из уведомления не найдено — возможно, оно было удалено');
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetPostId, id]);

  // подсветка целевого поста: автоскролл к нему и снятие подсветки через 3 с
  useEffect(() => {
    if (!highlightedPostId) return undefined;
    const el = document.getElementById(`post-${highlightedPostId}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const t = setTimeout(() => setHighlightedPostId(null), 3000);
    return () => clearTimeout(t);
  }, [highlightedPostId, posts]);

  // Поиск в реальном времени: debounce 400 мс — запрос к API без нажатия «Найти»
  useEffect(() => {
    const t = setTimeout(() => {
      const current = searchParams.get('search') || '';
      const wanted = inputValue.trim();
      if (wanted !== current) {
        // сохраняем остальные параметры (?page=, ?post=), иначе debounce-запись
        // затирает URL и сбивает навигацию/пагинацию
        setSearchParams(
          (prev) => {
            const params = new URLSearchParams(prev);
            if (wanted) params.set('search', wanted);
            else params.delete('search');
            // при изменении поиска сбрасываем страницу на 1
            params.delete('page');
            return params;
          },
          { replace: true },
        );
      }
    }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputValue]);

  const profanityWarning = containsProfanity(newText);

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
      // Новые сообщения сверху: после отправки показываем первую страницу,
      // где только что написанное сообщение будет в самом верху.
      // Раньше здесь был лишний loadPosts() + changePage(1) — двойная загрузка.
      // Теперь: если мы уже на первой странице (без поиска) — обновляем её один
      // раз; иначе просто меняем страницу в URL, а подгрузку сделает эффект
      // [loadPosts] ровно одним запросом.
      if (page === 1 && !search) {
        loadPosts();
      } else {
        changePage(1);
      }
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
                <div className="d-flex justify-content-between align-items-center flex-wrap gap-2">
                  <div>
                    <h1 className="h4 mb-1">{topic.title}</h1>
                    <div className="text-muted-small">
                      Автор: {topic.owner.username} · Создана: {new Date(topic.created_at).toLocaleString('ru-RU')}
                    </div>
                  </div>
                  <div className="topic-actions d-flex gap-2 align-items-center">
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
            <div className="d-flex gap-2 align-items-center w-100 justify-content-end">
              <div className="flex-grow-1" style={{ maxWidth: 640 }}>
                <input
                  type="search"
                  className="form-control form-control-sm search-input"
                  placeholder="Поиск по сообщениям темы..."
                  aria-label="Поиск по сообщениям"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                />
              </div>
              {isAdmin && (
                <button className="btn btn-sm btn-success flex-shrink-0" onClick={exportExcel} disabled={exporting}>
                  {exporting ? 'Экспорт...' : 'Скачать Excel'}
                </button>
              )}
            </div>
          </div>

          {loading ? (
            <Spinner />
          ) : posts.length === 0 ? (
            <div className="empty-state">
              {search ? `Ничего не найдено по запросу «${search}»` : 'В теме нет сообщений. Напишите первое!'}
            </div>
          ) : (
            <div className="mb-3">
              {posts.map((p) => (
                <div
                  key={p.id}
                  id={`post-${p.id}`}
                  className={`card post-card shadow-sm mb-2${
                    p.id === highlightedPostId ? ' post-highlight' : ''
                  }`}
                >
                  <div className="card-body py-2 d-flex gap-3 align-items-center">
                    <span className="post-avatar">{p.owner.username.charAt(0).toUpperCase()}</span>
                    <div className="flex-grow-1 min-w-0">
                      <div
                        className="post-text"
                        style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                      >
                        {p.text}
                      </div>
                      <div className="text-muted-small mt-1 d-flex align-items-center gap-2 flex-wrap">
                        <span className="fw-semibold text-body">{p.owner.username}</span>
                        <span>·</span>
                        <span>{new Date(p.created_at).toLocaleString('ru-RU')}</span>
                        {p.updated_at !== p.created_at && (
                          <span className="edited-badge">изменено</span>
                        )}
                        {/* Пометка для админа: пост скрыт модератором (обычные юзеры его не видят) */}
                        {isAdmin && p.is_hidden && (
                          <span className="badge text-bg-danger">Скрыто модератором</span>
                        )}
                      </div>
                    </div>
                    <div className="post-actions d-flex gap-1 flex-shrink-0 align-items-center">
                      {(p.owner.id === user?.id || isAdmin) && (
                        <>
                          {p.owner.id === user?.id && (
                            <button
                              type="button"
                              className="btn btn-sm btn-action-edit"
                              onClick={() => setEditingPost(p)}
                              title="Изменить сообщение"
                            >
                              Изменить
                            </button>
                          )}
                          <button
                            type="button"
                            className="btn btn-sm btn-action-delete"
                            onClick={() => deletePost(p)}
                            title="Удалить сообщение"
                          >
                            Удалить
                          </button>
                        </>
                      )}
                      {/* Жалоба — доступна всем авторизованным, кроме автора поста */}
                      <ReportButton postId={p.id} isOwnPost={p.owner.id === user?.id} />
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
                className={`form-control ${postError || profanityWarning ? 'is-invalid' : ''}`}
                rows={3}
                maxLength={2000}
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
                placeholder="Введите текст сообщения (до 2000 символов)"
              />
              {profanityWarning && !postError && (
                <div className="invalid-feedback d-block">{PROFANITY_MESSAGE}</div>
              )}
              {postError && <div className="invalid-feedback d-block">{postError}</div>}
              <div className="mt-2">
                <button type="submit" className="btn btn-primary" disabled={sending || profanityWarning}>
                  {sending ? 'Отправка...' : 'Отправить'}
                </button>
              </div>
            </div>
          </form>
        </>
      )}

      {editingPost && (
        <PostEditModal
          post={editingPost}
          onClose={() => setEditingPost(null)}
          onSaved={(newText) => {
            // обновляем сообщение в списке на месте, без перезагрузки страницы
            setPosts((prev) =>
              prev.map((x) =>
                x.id === editingPost.id
                  ? { ...x, text: newText, updated_at: new Date().toISOString() }
                  : x
              )
            );
            setEditingPost(null);
          }}
        />
      )}
    </div>
  );
}
