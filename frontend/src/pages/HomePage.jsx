import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, errorMessage, extractErrors } from '../api';
import { useAuth } from '../AuthContext';
import Alert from '../components/Alert';
import Pagination from '../components/Pagination';
import Spinner from '../components/Spinner';

const PAGE_LIMIT = 12; // категорий на странице (сетка 3 колонки x 4 ряда)

export default function HomePage() {
  const { isAdmin } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(1, parseInt(searchParams.get('page') || '1', 10) || 1);
  const search = searchParams.get('search') || '';

  const [categories, setCategories] = useState([]);
  const [count, setCount] = useState(0);
  const [limit, setLimit] = useState(PAGE_LIMIT);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Модалка создания/редактирования категории (только админ)
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null); // null = создание
  const [name, setName] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const resp = await api.get('/categories', {
        params: { page, limit: PAGE_LIMIT, search: search || undefined },
      });
      const data = resp.data;
      // Сервер может ответить как пагинированным объектом, так и плоским
      // списком (обратная совместимость) — нормализуем оба формата
      if (Array.isArray(data)) {
        setCategories(data);
        setCount(data.length);
      } else {
        setCategories(data.results || []);
        setCount(data.count || 0);
        setLimit(data.limit || PAGE_LIMIT);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setEditing(null);
    setName('');
    setFieldErrors({});
    setModalOpen(true);
  }

  function openEdit(cat) {
    setEditing(cat);
    setName(cat.name);
    setFieldErrors({});
    setModalOpen(true);
  }

  async function save(e) {
    e.preventDefault();
    const errs = {};
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 100) {
      errs.name = 'Введите название категории (до 100 символов)';
    }
    if (Object.keys(errs).length) {
      setFieldErrors(errs);
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/categories/${editing.id}`, { name: trimmed });
      } else {
        await api.post('/categories', { name: trimmed });
      }
      setModalOpen(false);
      load();
    } catch (err) {
      setFieldErrors(extractErrors(err));
    } finally {
      setSaving(false);
    }
  }

  async function remove(cat) {
    if (!window.confirm(`Удалить категорию «${cat.name}»? Все темы и сообщения в ней будут удалены.`)) {
      return;
    }
    try {
      await api.delete(`/categories/${cat.id}`);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  // Поиск категорий в реальном времени: debounce 400 мс — запрос к API
  // без нажатия кнопки; сбрасывает страницу на 1
  const [query, setQuery] = useState(search);

  useEffect(() => {
    const t = setTimeout(() => {
      const current = searchParams.get('search') || '';
      const wanted = query.trim();
      if (wanted !== current) {
        const params = {};
        if (wanted) params.search = wanted;
        setSearchParams(params, { replace: true });
      }
    }, 400);
    return () => clearTimeout(t);
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps

  function changePage(p) {
    const params = {};
    if (search) params.search = search;
    params.page = String(p);
    setSearchParams(params);
    window.scrollTo({ top: 0 });
  }

  const pages = Math.max(1, Math.ceil((count || 0) / (limit || PAGE_LIMIT)));

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h1 className="h3 mb-0 page-title">Категории</h1>
        {isAdmin && (
          <button className="btn btn-primary" onClick={openCreate}>
            Создать категорию
          </button>
        )}
      </div>

      <input
        className="form-control mb-4 search-input"
        placeholder="Поиск по названию категории..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Поиск категорий"
      />

      <Alert>{error}</Alert>

      {loading ? (
        <Spinner />
      ) : categories.length === 0 ? (
        <div className="empty-state">
          {search ? `Ничего не найдено по запросу «${search}»` : 'Пока нет категорий'}
        </div>
      ) : (
        <>
          <div className="row g-3">
            {categories.map((cat) => (
            <div key={cat.id} className="col-md-6 col-lg-4">
              <div className="card h-100 card-hover shadow-sm position-relative">
                <div className="card-body d-flex flex-column">
                  <div className="d-flex align-items-center gap-3">
                    <span className="cat-icon">{cat.name.charAt(0).toUpperCase()}</span>
                    <Link
                      to={`/categories/${cat.id}`}
                      className="text-decoration-none fw-semibold fs-5 text-dark category-link"
                    >
                      {cat.name}
                    </Link>
                  </div>
                  <div className="text-muted-small mt-2">Создана: {new Date(cat.created_at).toLocaleDateString('ru-RU')}</div>
                  {typeof cat.topics_count === 'number' && (
                    <div className="text-muted-small">{cat.topics_count} тем</div>
                  )}
                  <div className="mt-auto pt-3">
                    {isAdmin ? (
                      <div className="d-flex gap-2">
                        <button
                          className="btn btn-sm btn-outline-secondary"
                          onClick={() => openEdit(cat)}
                        >
                          Редактировать
                        </button>
                        <button
                          className="btn btn-sm btn-outline-danger"
                          onClick={() => remove(cat)}
                        >
                          Удалить
                        </button>
                      </div>
                    ) : (
                      <Link
                        to={`/categories/${cat.id}`}
                        className="btn btn-sm btn-outline-primary w-100"
                      >
                        Открыть
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
          </div>

          <Pagination count={count} limit={limit} page={Math.min(page, pages)} onChange={changePage} />
        </>
      )}

      {modalOpen && (
        <div
          className="modal fade show d-block"
          style={{ backgroundColor: 'rgba(0,0,0,.5)' }}
          role="dialog"
        >
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content">
              <form onSubmit={save}>
                <div className="modal-header">
                  <h5 className="modal-title">
                    {editing ? 'Редактировать категорию' : 'Новая категория'}
                  </h5>
                  <button type="button" className="btn-close" onClick={() => setModalOpen(false)} />
                </div>
                <div className="modal-body">
                  <div className="mb-3">
                    <label className="form-label">Название</label>
                    <input
                      className={`form-control ${fieldErrors.name ? 'is-invalid' : ''}`}
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      maxLength={100}
                      autoFocus
                    />
                    {fieldErrors.name && (
                      <div className="invalid-feedback d-block">{fieldErrors.name}</div>
                    )}
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-light" onClick={() => setModalOpen(false)}>
                    Отмена
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={saving}>
                    {saving ? 'Сохранение...' : 'Сохранить'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
