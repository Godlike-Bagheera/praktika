import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, errorMessage } from '../api';

/**
 * Страница статистики форума (доступна только администратору).
 * Открывается из меню профиля: клик по чипу пользователя -> «Статистика».
 * Диаграммы нарисованы чистым CSS (горизонтальные бары + столбики активности),
 * без внешних библиотек — аккуратно и в стиле сайта.
 */

function HBarChart({ items, colorClass, valueLabel }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  if (!items.length) {
    return <p className="text-muted small mb-0">Пока нет данных.</p>;
  }
  return (
    <div className="stats-bars">
      {items.map((item, idx) => (
        <div className="stats-bar-row" key={`${item.label}-${idx}`}>
          <div className="stats-bar-label text-truncate" title={item.label}>
            {item.to ? <Link to={item.to}>{item.label}</Link> : item.label}
          </div>
          <div className="stats-bar-track">
            <div
              className={`stats-bar-fill ${colorClass || ''}`}
              style={{ width: `${Math.round((item.value / max) * 100)}%` }}
            />
          </div>
          <div className="stats-bar-value">
            {item.value} {valueLabel || ''}
          </div>
        </div>
      ))}
    </div>
  );
}

function ActivityChart({ activity }) {
  const max = Math.max(1, ...activity.map((a) => a.count));
  return (
    <div className="stats-activity">
      {activity.map((a) => (
        <div
          className="stats-activity-col"
          key={a.date}
          title={`${a.date}: ${a.count} сообщ.`}
        >
          <div
            className="stats-activity-bar"
            style={{ height: `${Math.max(4, Math.round((a.count / max) * 100))}%` }}
          />
          <span className="stats-activity-day">{a.date.slice(8)}</span>
        </div>
      ))}
    </div>
  );
}

export default function StatsPage() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .get('/stats')
      .then((r) => {
        if (alive) setStats(r.data);
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="d-flex justify-content-center py-5">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Загрузка...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container py-4">
        <div className="alert alert-danger">{error}</div>
        <Link to="/" className="btn-ghost">
          <span className="btn-ghost-arrow">←</span> На главную
        </Link>
      </div>
    );
  }

  const totals = stats.totals || {};

  return (
    <div className="container py-4">
      <div className="d-flex align-items-center justify-content-between mb-4">
        <h1 className="forum-page-title h3 mb-0">Статистика форума</h1>
        <Link to="/" className="btn-ghost">
          <span className="btn-ghost-arrow">←</span> На главную
        </Link>
      </div>

      {/* Карточки-итоги */}
      <div className="row g-3 mb-4">
        {[
          ['Темы', totals.topics],
          ['Сообщения', totals.posts],
          ['Категории', totals.categories],
          ['Пользователи', totals.users],
        ].map(([label, value]) => (
          <div className="col-6 col-md-3" key={label}>
            <div className="stats-tile">
              <div className="stats-tile-value">{value ?? 0}</div>
              <div className="stats-tile-label">{label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="row g-4">
        <div className="col-lg-7">
          <div className="stats-card">
            <h2 className="stats-card-title">Самые популярные темы</h2>
            <p className="stats-card-sub">по числу ответов</p>
            <HBarChart
              items={(stats.top_topics || []).map((t) => ({
                label: t.title,
                value: t.posts_count,
                to: `/topics/${t.id}`,
              }))}
              colorClass="is-brand"
              valueLabel="сообщ."
            />
          </div>
        </div>
        <div className="col-lg-5">
          <div className="stats-card">
            <h2 className="stats-card-title">Самые активные авторы</h2>
            <p className="stats-card-sub">по числу сообщений</p>
            <HBarChart
              items={(stats.top_authors || []).map((a) => ({
                label: a.username,
                value: a.count,
              }))}
              colorClass="is-accent"
              valueLabel="сообщ."
            />
          </div>
        </div>
        <div className="col-12">
          <div className="stats-card">
            <h2 className="stats-card-title">Активность за последние 14 дней</h2>
            <p className="stats-card-sub">количество новых сообщений по дням</p>
            <ActivityChart activity={stats.activity || []} />
          </div>
        </div>
        <div className="col-12">
          <div className="stats-card">
            <h2 className="stats-card-title">Категории</h2>
            <p className="stats-card-sub">тем / сообщений в каждой категории</p>
            <HBarChart
              items={(stats.categories || []).map((c) => ({
                label: `${c.name} (${c.posts_count} сообщ.)`,
                value: c.topics_count,
                to: `/categories/${c.id}`,
              }))}
              colorClass="is-soft"
              valueLabel="тем"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
