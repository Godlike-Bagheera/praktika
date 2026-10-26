import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function Header() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="navbar navbar-expand-lg bg-dark forum-header" data-bs-theme="dark">
      <div className="container">
        <Link className="navbar-brand fw-bold" to="/">
          💬 Форум
        </Link>
        <div className="ms-auto d-flex align-items-center gap-3">
          {user && (
            <>
              <span className="text-light">
                {user.username}{' '}
                {isAdmin && <span className="badge bg-warning text-dark ms-1">Администратор</span>}
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
