import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function Header() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="navbar navbar-expand-lg forum-header" data-bs-theme="dark">
      <div className="container">
        <Link className="navbar-brand fw-bold d-flex align-items-center" to="/">
          <span className="brand-logo">F</span>
          Форум
        </Link>
        <div className="ms-auto d-flex align-items-center gap-2">
          {user && (
            <>
              <span className="user-chip text-light">
                <span className="avatar-circle">{user.username.charAt(0).toUpperCase()}</span>
                {user.username}
                {isAdmin && <span className="badge badge-admin">Администратор</span>}
              </span>
              <button
                className="btn btn-outline-light btn-sm"
                onClick={() => logout().then(() => navigate('/login'))}
              >
                Выйти
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
