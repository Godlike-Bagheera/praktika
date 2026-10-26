#!/usr/bin/env bash
# ============================================================
# forum backup — резервная копия проекта «Форум» целиком.
# Запускать в корне репозитория на сервере:  bash scripts/backup.sh
# Результат: forum_backup_<дата>.tar.gz  (код-ссылка + дамп БД + .env)
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

TS=$(date +%Y-%m-%d_%H%M%S)
OUT="forum_backup_${TS}"
mkdir -p "$OUT"

echo "==> 1. Проверка контейнеров..."
docker compose ps
for s in db app nginx; do
  st=$(docker inspect -f '{{.State.Status}}' "praktika-${s}-1" 2>/dev/null || echo missing)
  [ "$st" = "running" ] || { echo "ОШИБКА: сервис $s не запущен ($st). Сначала: docker compose up -d"; rm -rf "$OUT"; exit 1; }
done

echo "==> 2. Health-check приложения..."
if curl -sf http://localhost:8084/health >/dev/null 2>&1 || curl -sf http://localhost/health >/dev/null 2>&1; then
  echo "    /health -> OK"
else
  echo "    ВНИМАНИЕ: /health не отвечает, продолжаем (БД всё равно можно дампнуть)"
fi

echo "==> 3. Дамп базы данных PostgreSQL..."
DB_USER_VAL=$(grep -E '^DB_USER=' .env | cut -d= -f2)
DB_NAME_VAL=$(grep -E '^DB_NAME=' .env | cut -d= -f2)
docker compose exec -T db pg_dump -U "$DB_USER_VAL" "$DB_NAME_VAL" > "$OUT/forum_backup.sql"
[ -s "$OUT/forum_backup.sql" ] || { echo "ОШИБКА: дамп пустой!"; rm -rf "$OUT"; exit 1; }
LINES=$(wc -l < "$OUT/forum_backup.sql")
echo "    Дамп OK: ${LINES} строк SQL"

echo "==> 4. Проверка содержимого дампа (таблицы с данными)..."
for t in accounts_user forumapp_category forumapp_topic forumapp_post; do
  if grep -q "COPY public.${t} " "$OUT/forum_backup.sql"; then
    echo "    $t — есть данные ✓"
  else
    echo "    ВНИМАНИЕ: $t пуста или отсутствует"
  fi
done

echo "==> 5. Копирование .env и информации о коде..."
cp .env "$OUT/env.txt"
git rev-parse HEAD > "$OUT/git_commit.txt" 2>/dev/null || echo "unknown" > "$OUT/git_commit.txt"
git remote get-url origin > "$OUT/git_remote.txt" 2>/dev/null || echo "https://github.com/Godlike-Bagheera/praktika" > "$OUT/git_remote.txt"

echo "==> 6. Создание архива..."
tar czf "${OUT}.tar.gz" "$OUT"
rm -rf "$OUT"

echo ""
echo "============================================================"
echo " ГОТОВО: ${OUT}.tar.gz"
echo " Внутри: forum_backup.sql (вся база), env.txt (.env),"
echo "         git_commit.txt, git_remote.txt"
echo ""
echo " Скачай файл на Windows, например:"
echo "   scp -P 2222 ${OUT}.tar.gz user@10.0.2.15/C:/forum/"
echo " или через WinSCP/FileZilla (SSH, порт 2222)."
echo "============================================================"
