import { useNavigate } from 'react-router-dom';

/**
 * Простая пагинация: count — всего записей, limit — на страницу,
 * page — текущая страница. Меняет query-параметр ?page=.
 */
export default function Pagination({ count, limit, page, onChange }) {
  const pages = Math.max(1, Math.ceil((count || 0) / (limit || 20)));
  if (pages <= 1) return null;

  const items = [];
  const from = Math.max(1, page - 2);
  const to = Math.min(pages, page + 2);
  for (let p = from; p <= to; p += 1) items.push(p);

  return (
    <nav aria-label="Пагинация" className="mt-3">
      <ul className="pagination pagination-sm justify-content-center mb-0">
        <li className={`page-item ${page <= 1 ? 'disabled' : ''}`}>
          <button className="page-link" onClick={() => onChange(page - 1)} disabled={page <= 1}>
            ←
          </button>
        </li>
        {from > 1 && (
          <li className="page-item">
            <button className="page-link" onClick={() => onChange(1)}>1</button>
          </li>
        )}
        {from > 2 && <li className="page-item disabled"><span className="page-link">…</span></li>}
        {items.map((p) => (
          <li key={p} className={`page-item ${p === page ? 'active' : ''}`}>
            <button className="page-link" onClick={() => onChange(p)}>{p}</button>
          </li>
        ))}
        {to < pages - 1 && <li className="page-item disabled"><span className="page-link">…</span></li>}
        {to < pages && (
          <li className="page-item">
            <button className="page-link" onClick={() => onChange(pages)}>{pages}</button>
          </li>
        )}
        <li className={`page-item ${page >= pages ? 'disabled' : ''}`}>
          <button className="page-link" onClick={() => onChange(page + 1)} disabled={page >= pages}>
            →
          </button>
        </li>
      </ul>
    </nav>
  );
}
