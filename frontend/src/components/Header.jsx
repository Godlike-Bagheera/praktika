import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { useNotifications } from '../NotificationsContext';
import { api } from '../api';
import ThemeToggle from './ThemeToggle';
import ReportNotificationsDropdown from './ReportNotificationsDropdown';

export default function Header() {
  const { user, isAdmin, logout } = useAuth();
  const notifications = useNotifications();
  const unreadCount = notifications?.unread ?? 0;
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const [pendingReports, setPendingReports] = useState(0);
  const [reportNotifCount, setReportNotifCount] = useState(0);

  // Счётчик жалоб «на рассмотрении» для админа: при монтировании + каждые 30 сек.
  useEffect(() => {
    if (!isAdmin) {
      setPendingReports(0);
      return undefined;
    }
    let cancelled = false;
    const loadCount = () => {
      api
        .get('/reports/pending-count/')
        .then((resp) => {
          if (!cancelled) setPendingReports(resp.data.count ?? 0);
        })
        .catch(() => {});
    };
    loadCount();
    const timer = setInterval(loadCount, 30000);
    // Внеочередное обновление после действий на странице /reports
    const onRefresh = () => loadCount();
    window.addEventListener('forum-reports-refresh', onRefresh);
    return () => {
      cancelled = true;
      clearInterval(timer);
      window.removeEventListener('forum-reports-refresh', onRefresh);
    };
  }, [isAdmin]);

  // Счётчик непрочитанных уведомлений о жалобах (отдельная система ReportNotification):
  // загрузка при монтировании + опрос каждые 30 сек, интервал очищается при unmount.
  useEffect(() => {
    if (!isAdmin) {
      setReportNotifCount(0);
      return undefined;
    }
    let cancelled = false;
    const loadNotifCount = async () => {
      try {
        const response = await api.get('/admin-report-notifications/unread-count/');
        if (!cancelled) setReportNotifCount(response.data.count || 0);
      } catch (err) {
        console.error('Failed to load report notification count', err);
      }
    };
    loadNotifCount();
    const interval = setInterval(loadNotifCount, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [isAdmin]);

  // Закрытие меню по клику вне него и по Escape
  useEffect(() => {
    if (!menuOpen) return undefined;
    const onClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  const doLogout = () => {
    setMenuOpen(false);
    logout().then(() => navigate('/login'));
  };

  return (
    <header className="navbar navbar-expand-lg forum-header" data-bs-theme="dark">
      <div className="container">
        <Link className="navbar-brand fw-bold d-flex align-items-center" to="/">
          <span className="brand-logo">F</span>
          Форум
        </Link>
        <div className="ms-auto d-flex align-items-center gap-2">
          <ThemeToggle />
          {user && (
            <div className="profile-menu" ref={menuRef}>
              <button
                type="button"
                className={`user-chip text-light profile-menu-toggle ${menuOpen ? 'is-open' : ''}`}
                onClick={() => setMenuOpen((v) => !v)}
                aria-haspopup="true"
                aria-expanded={menuOpen}
              >
                <span className="avatar-circle">{user.username.charAt(0).toUpperCase()}</span>
                {user.username}
                {isAdmin && <span className="badge badge-admin">Администратор</span>}
                <span className="profile-caret">▾</span>
              </button>

              {menuOpen && (
                <div className="profile-menu-dropdown">
                  <Link
                    className="profile-menu-item"
                    to="/notifications"
                    onClick={() => setMenuOpen(false)}
                  >
                    Уведомления
                    {unreadCount > 0 && (
                      <span className="notif-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
                    )}
                  </Link>
                  {isAdmin && (
                    <div className="report-notif-row d-flex align-items-center justify-content-between px-3 py-2 border-bottom">
                      <span style={{ fontSize: '13px', color: 'var(--bs-body-color)' }}>
                        Уведомления о жалобах
                      </span>
                      <ReportNotificationsDropdown
                        count={reportNotifCount}
                        onMarkRead={() => setReportNotifCount(0)}
                      />
                    </div>
                  )}
                  {isAdmin && (
                    <Link
                      className="profile-menu-item"
                      to="/reports"
                      onClick={() => setMenuOpen(false)}
                    >
                      Жалобы
                      {pendingReports > 0 && (
                        <span className="notif-badge">
                          {pendingReports > 99 ? '99+' : pendingReports}
                        </span>
                      )}
                    </Link>
                  )}
                  {isAdmin && (
                    <Link
                      className="profile-menu-item"
                      to="/stats"
                      onClick={() => setMenuOpen(false)}
                    >
                      Статистика
                    </Link>
                  )}
                  <button type="button" className="profile-menu-item is-danger" onClick={doLogout}>
                    Выйти
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
