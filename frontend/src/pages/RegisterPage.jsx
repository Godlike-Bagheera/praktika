import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { extractErrors } from '../api';
import { useAuth } from '../AuthContext';
import Alert from '../components/Alert';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const USERNAME_RE = /^[A-Za-z0-9_]{3,30}$/;

export function validateClient(values) {
  const errors = {};
  if (!values.email || !EMAIL_RE.test(values.email)) {
    errors.email = 'Введите корректный email';
  } else if (values.email.length > 254) {
    errors.email = 'Слишком длинный email';
  }
  if (!USERNAME_RE.test(values.username)) {
    errors.username = 'Только латиница, цифры и _, от 3 до 30 символов';
  }
  const pwOk =
    values.password.length >= 8 &&
    values.password.length <= 64 &&
    /[A-Za-zА-Яа-я]/.test(values.password) &&
    /\d/.test(values.password);
  if (!pwOk) errors.password = 'Пароль: от 8 символов, буквы и цифры';
  if (values.password !== values.password_confirm) {
    errors.password_confirm = 'Пароли не совпадают';
  }
  return errors;
}

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [values, setValues] = useState({
    email: '',
    username: '',
    password: '',
    password_confirm: '',
  });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  const onChange = (e) => {
    setValues({ ...values, [e.target.name]: e.target.value });
  };

  async function onSubmit(e) {
    e.preventDefault();
    setFormError('');
    const clientErrors = validateClient(values);
    if (Object.keys(clientErrors).length > 0) {
      setErrors(clientErrors);
      return;
    }
    setErrors({});
    setBusy(true);
    try {
      await register(values);
      navigate('/login', { state: { registered: true } });
    } catch (err) {
      const errs = extractErrors(err);
      if (errs.detail && Object.keys(errs).length === 1) {
        setFormError(errs.detail);
      } else {
        setErrors(errs);
      }
    } finally {
      setBusy(false);
    }
  }

  const field = (name, label, type = 'text', placeholder = '') => (
    <div className="mb-3">
      <label className="form-label" htmlFor={name}>{label}</label>
      <input
        id={name}
        name={name}
        type={type}
        className={`form-control ${errors[name] ? 'is-invalid' : ''}`}
        value={values[name]}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete="off"
      />
      {errors[name] && <div className="invalid-feedback d-block">{errors[name]}</div>}
    </div>
  );

  return (
    <div className="row justify-content-center">
      <div className="col-md-6 col-lg-5">
        <div className="card shadow-sm mt-5">
          <div className="card-body p-4">
            <h1 className="h4 mb-3 text-center">Регистрация</h1>
            <Alert>{formError}</Alert>
            <form onSubmit={onSubmit} noValidate>
              {field('email', 'Email', 'email', 'name@example.com')}
              {field('username', 'Имя пользователя', 'text', 'user_123')}
              {field('password', 'Пароль', 'password')}
              {field('password_confirm', 'Повторите пароль', 'password')}
              <button className="btn btn-primary w-100" disabled={busy}>
                {busy ? 'Регистрация...' : 'Зарегистрироваться'}
              </button>
            </form>
            <p className="text-center mt-3 mb-0">
              Уже есть аккаунт? <Link to="/login">Войти</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
