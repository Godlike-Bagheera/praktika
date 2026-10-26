import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, setOnUnauthorized, tokenStore } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [user, setUser] = useState(tokenStore.getUser());
  const [booting, setBooting] = useState(true);

  const logoutLocal = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  useEffect(() => {
    setOnUnauthorized(() => {
      logoutLocal();
      navigate('/login', { replace: true });
    });
  }, [logoutLocal, navigate]);

  // Проверяем валидность сессии при загрузке (токен — в httpOnly-куке,
  // просто запрашиваем /auth/me; браузер сам приложит куку)
  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const resp = await api.get('/auth/me');
        if (!cancelled) {
          setUser(resp.data);
          tokenStore.set({ user: resp.data });
        }
      } catch {
        if (!cancelled) logoutLocal();
      } finally {
        if (!cancelled) setBooting(false);
      }
    }
    check();
    return () => {
      cancelled = true;
    };
  }, [logoutLocal]);

  const login = useCallback(async (email, password) => {
    const resp = await api.post('/auth/login', { email, password });
    const u = resp.data.user;
    tokenStore.set({ user: u });
    setUser(u);
    return u;
  }, []);

  const register = useCallback(async (payload) => {
    await api.post('/auth/register', payload);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      /* токен уже недействителен — просто чистим клиента */
    }
    logoutLocal();
    navigate('/login', { replace: true });
  }, [logoutLocal, navigate]);

  const isAdmin = !!user && user.role === 'admin';

  return (
    <AuthContext.Provider value={{ user, isAdmin, booting, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
