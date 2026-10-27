import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, errorMessage, extractErrors } from '../api';
import Alert from '../components/Alert';

export default function TopicCreatePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const presetCategory = searchParams.get('category');

  const [categories, setCategories] = useState([]);
  const [values, setValues] = useState({ category: presetCategory || '', title: '' });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get('/categories', { params: { all: 1 } })
      .then((resp) => {
        setCategories(Array.isArray(resp.data) ? resp.data : resp.data.results);
      })
      .catch((err) => setFormError(errorMessage(err)));
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setFormError('');
    const errs = {};
    if (!values.category) errs.category = 'Выберите категорию';
    const title = values.title.trim();
    if (!title || title.length > 120) errs.title = 'Введите название темы (до 120 символов)';
    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }
    setBusy(true);
    try {
      const resp = await api.post('/topics', { category: Number(values.category), title });
      navigate(`/topics/${resp.data.id}`, { replace: true });
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

  return (
    <div className="row justify-content-center">
      <div className="col-md-8 col-lg-6">
        <h1 className="h3 mb-4">Новая тема</h1>
        <Alert>{formError}</Alert>
        <form onSubmit={onSubmit} noValidate className="card shadow-sm">
          <div className="card-body">
            <div className="mb-3">
              <label className="form-label">Категория</label>
              <select
                className={`form-select ${errors.category ? 'is-invalid' : ''}`}
                name="category"
                value={values.category}
                onChange={(e) => setValues({ ...values, category: e.target.value })}
              >
                <option value="">— выберите —</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              {errors.category && <div className="invalid-feedback d-block">{errors.category}</div>}
            </div>
            <div className="mb-3">
              <label className="form-label">Название темы</label>
              <input
                className={`form-control ${errors.title ? 'is-invalid' : ''}`}
                name="title"
                value={values.title}
                maxLength={120}
                onChange={(e) => setValues({ ...values, title: e.target.value })}
              />
              {errors.title && <div className="invalid-feedback d-block">{errors.title}</div>}
            </div>
          </div>
          <div className="card-footer d-flex gap-2">
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? 'Создание...' : 'Создать тему'}
            </button>
            <button type="button" className="btn btn-light" onClick={() => navigate(-1)}>
              Отмена
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
