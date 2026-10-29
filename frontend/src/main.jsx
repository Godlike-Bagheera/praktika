import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { applyTheme, getInitialTheme } from './hooks/useTheme';

// Применяем тему к <html> ДО рендера компонентов — иначе при тёмной теме
// на долю секунды мигает белая (светлая) тема.
applyTheme(getInitialTheme());

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
