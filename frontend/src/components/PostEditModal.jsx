import { useEffect, useRef, useState } from 'react';
import { api, errorMessage, extractErrors } from '../api';
import { containsProfanity, PROFANITY_MESSAGE } from '../profanity';
import Alert from './Alert';

/**
 * Модальное окно редактирования сообщения прямо на странице темы.
 * Раньше «Изменить» вёл на отдельную страницу /posts/:id/edit — при клике
 * происходил переход и страница «дёргалась». Теперь редактирование
 * происходит поверх текущего экрана без навигации.
 */
export default function PostEditModal({ post, onClose, onSaved }) {
  const [text, setText] = useState(post.text);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const areaRef = useRef(null);

  useEffect(() => {
    // фокус и выделение текста сразу после открытия
    const el = areaRef.current;
    if (el) {
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    }
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const profanityWarning = containsProfanity(text);

  async function onSubmit(e) {
    e.preventDefault();
    setFormError('');
    const trimmed = text.trim();
    if (!trimmed || trimmed.length > 2000) {
      setErrors({ text: 'Введите сообщение (до 2000 символов)' });
      return;
    }
    setBusy(true);
    try {
      await api.put(`/posts/${post.id}`, { text: trimmed });
      onSaved(trimmed);
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
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-panel card shadow">
        <div className="card-header d-flex justify-content-between align-items-center">
          <span className="fw-semibold">Редактирование сообщения</span>
          <button
            type="button"
            className="btn-close"
            aria-label="Закрыть"
            onClick={onClose}
          />
        </div>
        <form onSubmit={onSubmit} noValidate>
          <div className="card-body">
            <Alert>{formError}</Alert>
            <textarea
              ref={areaRef}
              className={`form-control ${errors.text || profanityWarning ? 'is-invalid' : ''}`}
              rows={5}
              maxLength={2000}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            {errors.text && (
              <div className="invalid-feedback d-block">{errors.text}</div>
            )}
            {profanityWarning && !errors.text && (
              <div className="invalid-feedback d-block">{PROFANITY_MESSAGE}</div>
            )}
            <div className="text-muted-small mt-2">
              {text.length} / 2000 · Esc — отмена
            </div>
          </div>
          <div className="card-footer d-flex gap-2">
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? 'Сохранение...' : 'Сохранить'}
            </button>
            <button type="button" className="btn btn-light" onClick={onClose}>
              Отмена
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
