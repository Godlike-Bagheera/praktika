/**
 * Красивая и удобная пагинация в стиле форума:
 *  - крупные круглые кнопки (первая/последняя, ‹ ›, соседние страницы);
 *  - активная страница подсвечена градиентом бренда;
 *  - «…» при длинных списках.
 *
 * count — всего записей, limit — на страницу, page — текущая страница,
 * onChange(newPage) — колбэк смены страницы.
 */
export default function Pagination({ count, limit, page, onChange }) {
  const pages = Math.max(1, Math.ceil((count || 0) / (limit || 20)));

  if (pages <= 1) return null;

  // Диапазон показываемых номеров вокруг активной страницы
  const windowSize = 2;
  let from = Math.max(1, page - windowSize);
  let to = Math.min(pages, page + windowSize);
  // Подтягиваем окно к центру, если одна из границ упирается в край
  if (page <= windowSize + 1) to = Math.min(pages, windowSize * 2 + 1);
  if (page >= pages - windowSize) from = Math.max(1, pages - windowSize * 2);

  const items = [];
  for (let p = from; p <= to; p += 1) items.push(p);

  const go = (p) => {
    const target = Math.min(Math.max(1, p), pages);
    if (target !== page) onChange(target);
  };

  const btnCls = (extra = '') => `forum-page-btn ${extra}`.trim();

  return (
    <nav aria-label="Пагинация" className="mt-4">
      <div className="forum-pagination-wrap">
        <ul className="forum-pagination mb-0">
          {/* Первая */}
          <li>
            <button
              type="button"
              className={btnCls(page <= 1 ? 'is-disabled' : '')}
              onClick={() => go(1)}
              disabled={page <= 1}
              aria-label="Первая страница"
              title="Первая страница"
            >
              «
            </button>
          </li>
          {/* Назад */}
          <li>
            <button
              type="button"
              className={btnCls(page <= 1 ? 'is-disabled' : '')}
              onClick={() => go(page - 1)}
              disabled={page <= 1}
              aria-label="Предыдущая страница"
              title="Назад"
            >
              ‹
            </button>
          </li>

          {from > 1 && (
            <>
              <li>
                <button type="button" className={btnCls()} onClick={() => go(1)}>1</button>
              </li>
              {from > 2 && <li><span className="forum-page-dots">…</span></li>}
            </>
          )}

          {items.map((p) => (
            <li key={p}>
              <button
                type="button"
                className={btnCls(p === page ? 'is-active' : '')}
                onClick={() => go(p)}
                aria-current={p === page ? 'page' : undefined}
              >
                {p}
              </button>
            </li>
          ))}

          {to < pages - 1 && <li><span className="forum-page-dots">…</span></li>}
          {to < pages && (
            <li>
              <button type="button" className={btnCls()} onClick={() => go(pages)}>{pages}</button>
            </li>
          )}

          {/* Вперёд */}
          <li>
            <button
              type="button"
              className={btnCls(page >= pages ? 'is-disabled' : '')}
              onClick={() => go(page + 1)}
              disabled={page >= pages}
              aria-label="Следующая страница"
              title="Вперёд"
            >
              ›
            </button>
          </li>
          {/* Последняя */}
          <li>
            <button
              type="button"
              className={btnCls(page >= pages ? 'is-disabled' : '')}
              onClick={() => go(pages)}
              disabled={page >= pages}
              aria-label="Последняя страница"
              title="Последняя страница"
            >
              »
            </button>
          </li>
        </ul>
      </div>
    </nav>
  );
}
