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
  const [searchInput, setSearchInput] = useState(search);

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
    // название категории — из общего списка
    api
      .get('/categories')
      .then((resp) => {
        const cat = resp.data.find((c) => String(c.id) === String(id));
        setCategory(cat || null);
      })
      .catch(() => {});
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

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

      <form onSubmit={applySearch} className="row g-2 mb-3">
        <div className="col-auto flex-grow-1">
          <input
            className="form-control"
            placeholder="Поиск по названию темы..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <div className="col-auto">
          <button className="btn btn-outline-secondary">Найти</button>
        </div>
      </form>

      <Alert>{error}</Alert>

      {loading ? (
        <Spinner />
      ) : topics.length === 0 ? (
        <div className="empty-state">
          {search ? 'Ничего не найдено по запросу' : 'В этой категории нет тем'}
        </div>
      ) : (
        <div className="list-group border-0">
          {topics.map((t) => (
            <Link
              key={t.id}
              to={`/topics/${t.id}`}
              className="list-group-item list-group-item-action bg-white"
            >
              <div className="d-flex justify-content-between align-items-start gap-3">
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
