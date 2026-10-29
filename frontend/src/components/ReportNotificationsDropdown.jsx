import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

export default function ReportNotificationsDropdown({ count, onMarkRead }) {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef(null);

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

  const loadNotifications = async () => {
    setLoading(true);
    try {
      const response = await api.get('/admin-report-notifications/');
      setNotifications(response.data);
    } catch (err) {
      console.error('Failed to load report notifications', err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpen = () => {
    setIsOpen(true);
    loadNotifications();
    // Отмечаем все непрочитанные уведомления прочитанными и сбрасываем счётчик
    api.post('/admin-report-notifications/read/', {})
      .then(() => { if (onMarkRead) onMarkRead(); })
      .catch(() => {});
  };

  const formatTime = (dateStr) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return 'только что';
    if (diff < 3600) return Math.floor(diff / 60) + ' мин. назад';
    if (diff < 86400) return Math.floor(diff / 3600) + ' ч. назад';
    return date.toLocaleDateString('ru-RU');
  };

  return (
    <div className="position-relative d-inline-block" ref={dropdownRef}>
      <button
        className="btn btn-sm btn-link text-decoration-none position-relative"
        onClick={handleOpen}
        title="Уведомления о жалобах"
        style={{ color: 'inherit', padding: '4px 8px' }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 16 16">
          <path d="M8 16a2 2 0 0 0 2-2H6a2 2 0 0 0 2 2zm.995-14.901a1 1 0 1 0-1.99 0A5.002 5.002 0 0 0 3 6c0 1.098-.5 6-2 7h14c-1.5-1-2-5.902-2-7 0-2.42-1.72-4.44-4.005-4.901z"/>
        </svg>
        {count > 0 && (
          <span className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger" style={{ fontSize: '10px', minWidth: '16px', height: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {count}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            zIndex: 1050,
            minWidth: '320px',
            maxWidth: '400px',
            backgroundColor: 'var(--bs-body-bg, #fff)',
            border: '1px solid var(--bs-border-color, #dee2e6)',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
            maxHeight: '400px',
            overflowY: 'auto',
          }}
        >
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--bs-border-color)', fontWeight: 600, fontSize: '14px' }}>
            Уведомления о жалобах
          </div>

          {loading && (
            <div style={{ padding: '20px', textAlign: 'center', color: '#6c757d' }}>Загрузка...</div>
          )}

          {!loading && notifications.length === 0 && (
            <div style={{ padding: '20px', textAlign: 'center', color: '#6c757d', fontSize: '13px' }}>
              Нет новых уведомлений
            </div>
          )}

          {notifications.map((n) => (
            <Link
              key={n.id}
              to={'/topics/' + n.topic_id}
              className="text-decoration-none"
              onClick={() => setIsOpen(false)}
              style={{
                display: 'block',
                padding: '12px 16px',
                borderBottom: '1px solid var(--bs-border-color, #dee2e6)',
                color: 'inherit',
              }}
            >
              <div style={{ fontSize: '13px', marginBottom: '4px' }}>
                <strong>{n.reporter_username}</strong> пожаловался на сообщение от <strong>{n.post_author}</strong>
              </div>
              <div style={{ fontSize: '12px', color: '#6c757d', marginBottom: '4px' }}>
                Причина: {n.reason_display}
              </div>
              <div style={{ fontSize: '12px', color: '#0d6efd', marginBottom: '4px' }}>
                Тема: {n.topic_title}
              </div>
              <div style={{ fontSize: '11px', color: '#adb5bd' }}>
                {formatTime(n.created_at)}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
