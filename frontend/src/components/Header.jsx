import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { useNotifications } from '../NotificationsContext';

export default function Header() {
  const { user, isAdmin, logout } = useAuth();
  const notifications = useNotifications();
  const unreadCount = notifications?.unread ?? 0;
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

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
