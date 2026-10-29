import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, errorMessage } from '../api';

const REASONS = [
  { value: 'spam', label: 'Спам' },
  { value: 'offtopic', label: 'Не по теме' },
  { value: 'insult', label: 'Оскорбление' },
  { value: 'other', label: 'Другое' },
];

// Кнопка «Пожаловаться» с выпадающим списком причин (без Bootstrap-модалки:
// она оставляла .modal-backdrop на весь экран). Список закрывается по клику
// вне кнопки и по Escape. Не рендерится для собственных постов пользователя.
export default function ReportButton({ postId, isOwnPost }) {
  const [open, setOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false); // жалоба уже отправлена — дизейблим кнопку
  const [notice, setNotice] = useState(''); // сообщение об успехе/ошибке
  const wrapRef = useRef(null);
  const navigate = useNavigate();

  // Закрытие по клику вне виджета и по Escape
  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (isOwnPost) return null;

  const submitReason = async (reason) => {
    if (sending) return;
    setSending(true);
    setNotice('');
    try {
      await api.post(`/posts/${postId}/report/`, { post: postId, reason });
      setOpen(false);
      setDone(true);
      setNotice('Жалоба отправлена');
      window.dispatchEvent(new Event('forum-reports-refresh'));
    } catch (err) {
      const msg = errorMessage(err) || '';
      if (/уже жаловались/i.test(msg)) {
        setNotice('Вы уже отправляли жалобу на это сообщение');
        setDone(true); // повторная жалоба невозможна — кнопку больше не активим
      } else if (err?.response?.status === 401) {
        setOpen(false);
        navigate('/login');
      } else {
        setNotice(msg || 'Не удалось отправить жалобу, попробуйте позже');
      }
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="report-widget position-relative d-inline-flex flex-column align-items-start" ref={wrapRef}>
      <button
        type="button"
        className={`btn btn-sm px-2 btn-report ${done ? 'disabled' : 'btn-outline-danger'}`}
        onClick={() => {
          setNotice('');
          setOpen((v) => !v);
        }}
        disabled={done}
        aria-haspopup="true"
        aria-expanded={open}
        title={done ? 'Жалоба уже отправлена' : 'Пожаловаться на сообщение'}
      >
        🚩 {done ? 'Жалоба отправлена' : 'Пожаловаться'}
      </button>

      {open && (
        <div className="report-menu card shadow-sm">
          <div className="card-body p-2">
            <div className="report-menu-title">Пожаловаться на сообщение</div>
            {REASONS.map((r) => (
              <button
                key={r.value}
                type="button"
                className="btn btn-sm btn-outline-primary w-100 text-start mb-1"
                disabled={sending}
                onClick={() => submitReason(r.value)}
              >
                {r.label}
              </button>
            ))}
            <button
              type="button"
              className="btn btn-sm btn-secondary w-100"
              onClick={() => setOpen(false)}
            >
              Отмена
            </button>
          </div>
        </div>
      )}

      {notice && !open && (
        <span className="report-notice text-body-secondary">{notice}</span>
      )}
    </div>
  );
}
