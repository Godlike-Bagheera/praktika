import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, errorMessage } from '../api';
import Alert from '../components/Alert';
import Pagination from '../components/Pagination';
import Spinner from '../components/Spinner';

export default function CategoryPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') || '';
  const page = parseInt(searchParams.get('page') || '1', 10);

  const [category, setCategory] = useState(null);
  const [topics, setTopics] = useState([]);
  const [count, setCount] = useState(0);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  // input — контролируемое поле поиска; searchParams обновляются с debounce
  const [inputValue, setInputValue] = useState(search);

  // синхронизируем поле, если ?search= изменился извне (ссылка/назад)
  useEffect(() => {
    setInputValue((prev) => ((prev.trim() === search) ? prev : search));
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const resp = await api.get('/topics', {
        params: { category: id, search: search || undefined, page, limit: 20 },
      });
      setTopics(resp.data.results);
      setCount(resp.data.count);
      setLimit(resp.data.limit);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [id, search, page]);

  useEffect(() => {
    // название категории — из общего списка (без page/limit сервер
    // отвечает плоским массивом всех категорий — обратная совместимость)
    api
      .get('/categories')
      .then((resp) => {
        const list = Array.isArray(resp.data) ? resp.data : resp.data.results;
        const cat = list.find((c) => String(c.id) === String(id));
        setCategory(cat || null);
      })
      .catch(() => {});
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // Поиск в реальном времени: debounce 400 мс — запрос к API без нажатия «Найти»
  useEffect(() => {
    const t = setTimeout(() => {
      const current = searchParams.get('search') || '';
      const wanted = inputValue.trim();
      if (wanted !== current) {
        const params = {};
        if (wanted) params.search = wanted;
        setSearchParams(params, { replace: true });
      }
    }, 400);
    return () => clearTimeout(t);
  }, [inputValue]); // eslint-disable-line react-hooks/exhaustive-deps

  function changePage(p) {
    const params = {};
    if (search) params.search = search;
    params.page = String(p);
    setSearchParams(params);
    window.scrollTo({ top: 0 });
  }

  return (
    <div>
      <nav aria-label="breadcrumb">
        <ol className="breadcrumb">
          <li className="breadcrumb-item"><Link to="/">Категории</Link></li>
          <li className="breadcrumb-item active">{category ? category.name : `Категория #${id}`}</li>
        </ol>
      </nav>

      <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <h1 className="h3 mb-0">{category ? category.name : 'Темы категории'}</h1>
        <button className="btn btn-primary" onClick={() => navigate(`/topics/new?category=${id}`)}>
          Создать тему
        </button>
      </div>

      <input
        type="search"
        className="form-control mb-3 search-input"
        placeholder="Поиск по названию темы..."
        aria-label="Поиск тем"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
      />

      <Alert>{error}</Alert>

      {loading ? (
        <Spinner />
      ) : topics.length === 0 ? (
        <div className="empty-state">
          {search ? `Ничего не найдено по запросу «${search}»` : 'В этой категории нет тем'}
        </div>
      ) : (
        <div className="list-group border-0">
          {topics.map((t) => (
            <Link
              key={t.id}
              to={`/topics/${t.id}`}
              className="list-group-item list-group-item-action bg-white"
            >
              <div className="d-flex justify-content-between align-items-center gap-3">
                <span className="cat-icon" style={{ width: 38, height: 38, fontSize: '1rem' }}>
                  {t.title.charAt(0).toUpperCase()}
                </span>
                <div className="flex-grow-1">
                  <div className="fw-semibold">{t.title}</div>
                  <div className="text-muted-small">
                    Автор: {t.owner.username} · {new Date(t.created_at).toLocaleString('ru-RU')}
                  </div>
                </div>
                <span className="count-badge">{t.posts_count} сообщ.</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      <Pagination count={count} limit={limit} page={page} onChange={changePage} />
    </div>
  );
}
