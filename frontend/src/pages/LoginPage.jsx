import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { errorMessage } from '../api';
import { useAuth } from '../AuthContext';
import Alert from '../components/Alert';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [values, setValues] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const registered = !!location.state?.registered;

  const onChange = (e) => {
    setError('');
    setValues({ ...values, [e.target.name]: e.target.value });
  };

  async function onSubmit(e) {
    e.preventDefault();
    setError('');
    if (!values.email || !values.password) {
      setError('Введите email и пароль');
      return;
    }
    setBusy(true);
    try {
      await login(values.email, values.password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="row justify-content-center">
      <div className="col-md-6 col-lg-5">
        <div className="card shadow-sm mt-5">
          <div className="card-body p-4">
            <h1 className="h4 mb-3 text-center">Вход</h1>
            {registered && (
              <Alert kind="success">Регистрация успешна. Войдите в аккаунт.</Alert>
            )}
            <Alert>{error}</Alert>
            <form onSubmit={onSubmit} noValidate>
              <div className="mb-3">
                <label className="form-label" htmlFor="email">Email</label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  className="form-control"
                  value={values.email}
                  onChange={onChange}
                  autoComplete="username"
                />
              </div>
              <div className="mb-3">
                <label className="form-label" htmlFor="password">Пароль</label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  className="form-control"
                  value={values.password}
                  onChange={onChange}
                  autoComplete="current-password"
                />
              </div>
              <button className="btn btn-primary w-100" disabled={busy}>
                {busy ? 'Вход...' : 'Войти'}
              </button>
            </form>
            <p className="text-center mt-3 mb-0">
              Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
