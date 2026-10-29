import { useState, useRef, useEffect } from 'react';
import { api } from '../api';

const REASONS = [
  { value: 'spam', label: 'Спам' },
  { value: 'offtopic', label: 'Не по теме' },
  { value: 'insult', label: 'Оскорбление' },
  { value: 'other', label: 'Другое' },
];

export default function ReportButton({ postId, isOwnPost }) {
  const [isOpen, setIsOpen] = useState(false);
  const [status, setStatus] = useState('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [hasReported, setHasReported] = useState(false);
  const dropdownRef = useRef(null);

  // Проверка при загрузке: если пользователь уже жаловался на этот пост —
  // кнопку не показываем (кнопка исчезает полностью, без "Отправлено").
  useEffect(() => {
    if (isOwnPost) return undefined;
    let cancelled = false;
    const checkExistingReport = async () => {
      try {
        const response = await api.get('/posts/' + postId + '/my-reports/');
        if (!cancelled && response.data && response.data.has_reported) {
          setHasReported(true);
        }
      } catch (err) {
        // Если ошибка - просто игнорируем, кнопка останется
      }
    };
    checkExistingReport();
    return () => { cancelled = true; };
  }, [postId, isOwnPost]);

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  if (isOwnPost) return null;
  if (hasReported || status === 'success') return null;  // Скрываем кнопку полностью

  const handleReport = async (reason) => {
    setStatus('loading');
    try {
      await api.post('/posts/' + postId + '/report/', { post: postId, reason: reason });
      setStatus('success');
      setHasReported(true);  // Запоминаем что уже пожаловались
      setIsOpen(false);
    } catch (err) {
      const msg = (err.response && err.response.data && err.response.data.errors && err.response.data.errors.detail) || (err.response && err.response.data && err.response.data.detail) || 'Ошибка';
      setErrorMsg(msg);
      setStatus('error');
      setIsOpen(false);
      setTimeout(function() { setStatus('idle'); setErrorMsg(''); }, 3000);
    }
  };

  return (
    <div style={{ position: 'relative', display: 'inline-block' }} ref={dropdownRef}>
      <button
        className="btn btn-sm btn-action-report"
        onClick={() => setIsOpen(!isOpen)}
        disabled={status === 'loading'}
        title="Пожаловаться на сообщение"
      >
        Пожаловаться
      </button>

      {isOpen && (
        <div
          className="report-dropdown"
        >
          <div className="report-dropdown-header">Пожаловаться на сообщение</div>
          {REASONS.map((r) => (
            <button
              key={r.value}
              className="report-dropdown-item"
              onClick={() => handleReport(r.value)}
              disabled={status === 'loading'}
            >
              {r.label}
            </button>
          ))}
          <div className="report-dropdown-divider"></div>
          <button
            className="report-dropdown-item report-dropdown-cancel"
            onClick={() => setIsOpen(false)}
          >
            Отмена
          </button>
        </div>
      )}

      {status === 'error' && errorMsg && (
        <div style={{ position: 'absolute', left: 0, top: '100%', marginTop: '4px', zIndex: 1051, whiteSpace: 'nowrap', fontSize: '12px', color: '#dc3545', backgroundColor: 'var(--bs-body-bg)', padding: '4px 8px', borderRadius: '4px', boxShadow: '0 2px 4px rgba(0,0,0,0.2)' }}>
          {errorMsg}
        </div>
      )}
    </div>
  );
}
