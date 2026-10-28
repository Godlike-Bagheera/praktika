import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import './styles.css';
import { AuthProvider, useAuth } from './AuthContext';
import Header from './components/Header';
import RegisterPage from './pages/RegisterPage';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import CategoryPage from './pages/CategoryPage';
import TopicCreatePage from './pages/TopicCreatePage';
import TopicEditPage from './pages/TopicEditPage';
import TopicPage from './pages/TopicPage';
import PostEditPage from './pages/PostEditPage';
import StatsPage from './pages/StatsPage';

function Booting() {
  return (
    <div className="d-flex justify-content-center align-items-center vh-100">
      <div className="spinner-border text-primary" role="status">
        <span className="visually-hidden">Загрузка...</span>
      </div>
    </div>
  );
}

function PrivateRoute() {
  const { user, booting } = useAuth();
  if (booting) return <Booting />;
  if (!user) return <Navigate to="/login" replace />;
  return (
    <>
      <Header />
      <div className="container py-4">
        <Outlet />
      </div>
    </>
  );
}

function PublicOnlyRoute({ children }) {
  const { user, booting } = useAuth();
  if (booting) return <Booting />;
  if (user) return <Navigate to="/" replace />;
  return children;
}

function AdminRoute() {
  const { isAdmin, booting } = useAuth();
  if (booting) return <Booting />;
  if (!isAdmin) return <Navigate to="/" replace />;
  return <Outlet />;
}

function AppRoutes() {
  // Токены теперь в httpOnly-куках — JS их не читает; статус сессии
  // определяет AuthProvider через запрос /auth/me (состояние booting).
  return (
    <Routes>
      <Route
        path="/register"
        element={
          <PublicOnlyRoute>
            <RegisterPage />
          </PublicOnlyRoute>
        }
      />
      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        }
      />
      <Route element={<PrivateRoute />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/stats" element={<AdminRoute />}>
          <Route index element={<StatsPage />} />
        </Route>
        <Route path="/categories/:id" element={<CategoryPage />} />
        <Route path="/topics/new" element={<TopicCreatePage />} />
        <Route path="/topics/:id" element={<TopicPage />} />
        <Route path="/topics/:id/edit" element={<TopicEditPage />} />
        <Route path="/posts/:id/edit" element={<PostEditPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
