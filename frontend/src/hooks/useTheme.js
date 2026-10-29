import { useCallback, useEffect, useState } from 'react';

const THEME_KEY = 'theme';

// Читаем выбранную пользователем тему из localStorage; если её нет —
// определяем системную тему через prefers-color-scheme.
export function getInitialTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    /* localStorage может быть недоступен (приватный режим) */
  }
  if (typeof window !== 'undefined' && window.matchMedia
      && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
}

// Нативный механизм Bootstrap 5.3: атрибут data-bs-theme на <html>.
export function applyTheme(theme) {
  document.documentElement.setAttribute('data-bs-theme', theme);
}

export default function useTheme() {
  const [theme, setTheme] = useState(getInitialTheme);

  // Применяем тему к <html> при каждом изменении (в main.jsx applyTheme
  // вызывается до ReactDOM.render, чтобы не было мигания белой темы).
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        /* игнорируем недоступность localStorage */
      }
      return next;
    });
  }, []);

  return { theme, toggleTheme };
}
