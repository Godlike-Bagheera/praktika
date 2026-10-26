#!/usr/bin/env bash
# ============================================================
# forum one-command backup — сохраняет ВСЁ максимально полно.
# Запускать ВНУТРИ ВМ на сервере:  bash scripts/one_command.sh [dockerhub_пароль]
#
# Делает:
#   1) вызывает scripts/backup.sh (SQL-дамп БД + .env -> forum_backup_<дата>.tar.gz)
#   2) собирает и пушит образы app/nginx на Docker Hub (если есть docker CLI),
#      чтобы на новом ПК проект поднимался БЕЗ сборки;
#   3) пишет в архив инструкцию для нового ПК;
#   4) подсказывает команду экспорта ВМ в .ova на Windows-хосте (полная копия ОС).
# ============================================================
set -uo pipefail
cd "$(dirname "$0")/.."

DH_USER="testbagheera666"
DH_PASS="${1:-${DOCKER_PASSWORD:-}}"

echo "==> 1. Резервная копия данных (БД + .env)..."
bash scripts/backup.sh || { echo "backup.sh упал — продолжаем с тем, что есть"; }
ARCHIVE=$(ls -t forum_backup_*.tar.gz 2>/dev/null | head -1)
[ -n "$ARCHIVE" ] || { echo "ОШИБКА: архив бэкапа не создан"; exit 1; }
echo "    Архив: $ARCHIVE"

echo "==> 2. Сборка актуальных образов..."
docker compose build 2>&1 | tail -2 || echo "    (сборка не удалась — пропуск)"

if [ -n "$DH_PASS" ]; then
  echo "==> 3. Логин и пуш образов на Docker Hub (${DH_USER})..."
  if echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin; then
    docker tag praktika-app:latest   "${DH_USER}/forum-app:latest"   && docker push "${DH_USER}/forum-app:latest"   &
    P1=$!
    docker tag praktika-nginx:latest "${DH_USER}/forum-nginx:latest" && docker push "${DH_USER}/forum-nginx:latest" &
    P2=$!
    wait $P1 && echo "    forum-app: pushed ✓"  || echo "    forum-app: НЕ запушен"
    wait $P2 && echo "    forum-nginx: pushed ✓" || echo "    forum-nginx: НЕ запушен"
  else
    echo "    Логин Docker Hub не удался — пропускаю пуш."
  fi
else
  echo "==> 3. Пароль Docker Hub не передан — пропускаю пуш образов."
  echo "    (можно позже: bash scripts/push_images.sh ${DH_USER})"
fi

echo "==> 4. Добавляю инструкцию внутрь архива..."
TMP=$(mktemp -d)
cat > "$TMP/RESTORE_INSTRUCTIONS.txt" << INS
============================================================
 ВОССТАНОВЛЕНИЕ ПРОЕКТА «ФОРУМ» НА НОВОМ КОМПЬЮТЕРЕ
============================================================
Вариант А — чистый Linux/Docker (рекомендуется):
  1) Скопируй этот архив (*.tar.gz) на новый ПК.
  2) git clone https://github.com/Godlike-Bagheera/praktika && cd praktika
  3) bash scripts/setup.sh /путь/к/${ARCHIVE}
     Скрипт сам: установит Docker, восстановит .env и базу,
     подставит новый IP в ALLOWED_HOSTS, запустит контейнеры,
     проверит /health и количество сообщений.
  4) Сайт: http://IP_новой_машины:8084  (вход admin@gmail.com)

Вариант Б — без сборки, с готовых образов Docker Hub:
  docker compose -f docker-compose.hub.yml up -d db
  # подождать healthy, затем восстановить дамп из архива:
  tar xzf ${ARCHIVE}
  cat forum_backup_*/forum_backup.sql | docker compose exec -T db psql -U forumuser -d forumdb
  docker compose -f docker-compose.hub.yml up -d

Вариант В — полная копия всей ВМ (самый полный):
  На Windows (ВМ должна быть ВЫКЛЮЧЕНА):
  VBoxManage export "<Имя_ВМ>" --output forum_full.ova
  На новом ПК: VirtualBox -> File -> Import Appliance -> forum_full.ova
  Всё (ОС, Docker, образы, база, настройки) восстановится 1-в-1.
  После импорта: bash scripts/setup.sh (подправит IP, если сменился).
============================================================
INS
tar rzf "/tmp/with_instr.tar.gz" -C "$TMP" RESTORE_INSTRUCTIONS.txt 2>/dev/null || true
# пересобираем архив с инструкцией
GZ_TMP=$(mktemp -d); tar xzf "$ARCHIVE" -C "$GZ_TMP"
cp "$TMP/RESTORE_INSTRUCTIONS.txt" "$GZ_TMP/$(basename "$ARCHIVE" .tar.gz)/"
tar czf "$ARCHIVE" -C "$GZ_TMP" "$(basename "$ARCHIVE" .tar.gz)"
rm -rf "$TMP" "$GZ_TMP"
echo "    Инструкция добавлена в $ARCHIVE"

VM_NAME=$(hostname)
echo ""
echo "============================================================"
echo " ГОТОВО! Сохранено:"
echo "   • $ARCHIVE — база данных + секреты + инструкция"
if [ -n "$DH_PASS" ]; then
echo "   • Образы на Docker Hub: ${DH_USER}/forum-app, ${DH_USER}/forum-nginx"
fi
echo ""
echo " ФИНАЛЬНЫЙ ШАГ (полный образ ВМ) — выполнить на Windows-хосте,"
echo " предварительно ВЫКЛЮЧИВ виртуалку:"
echo "   VBoxManage export \"$VM_NAME\" --output forum_full.ova"
echo " (имя ВМ может отличаться — смотри VBoxManage list vms)"
echo ""
echo " Скачай $ARCHIVE (и .ova, когда сделаешь) на флешку/облако."
echo "============================================================"
