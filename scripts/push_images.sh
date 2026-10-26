#!/usr/bin/env bash
# ============================================================
# forum push-images — публикация готовых Docker-образов проекта
# на Docker Hub, чтобы на НОВОМ компьютере проект поднимался
# без сборки (быстро и без интернета для npm/pip).
#
# Использование:
#   1) собери образы:            docker compose build
#   2) залогинься в Docker Hub:  docker login -u <логин>   (или укажи DOCKER_USER/DOCKER_PASSWORD)
#   3) запусти скрипт:           bash scripts/push_images.sh [namespace]
#      namespace по умолчанию: имя аккаунта из переменной DOCKER_USER или аргумент.
#
# После пуша на любом ПК достаточно:
#   docker compose -f docker-compose.hub.yml up -d
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

NS="${1:-${DOCKER_NAMESPACE:-}}"
if [ -z "$NS" ]; then
  echo "Укажи namespace Docker Hub: bash scripts/push_images.sh testbagheera666"
  exit 1
fi

# логин, если переданы переменные
if [ -n "${DOCKER_USER:-}" ] && [ -n "${DOCKER_PASSWORD:-}" ]; then
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USER" --password-stdin
fi

TAG="${TAG:-latest}"

echo "==> Проверка собранных образов..."
docker image inspect praktika-app:latest >/dev/null || { echo "Сначала: docker compose build"; exit 1; }
docker image inspect praktika-nginx:latest >/dev/null || { echo "Сначала: docker compose build"; exit 1; }

echo "==> Тегирование для Docker Hub (${NS})..."
docker tag praktika-app:latest   "${NS}/forum-app:${TAG}"
docker tag praktika-nginx:latest "${NS}/forum-nginx:${TAG}"

echo "==> Пуш образов..."
docker push "${NS}/forum-app:${TAG}"
docker push "${NS}/forum-nginx:${TAG}"

echo ""
echo "============================================================"
echo " ГОТОВО!"
echo "   docker.io/${NS}/forum-app:${TAG}"
echo "   docker.io/${NS}/forum-nginx:${TAG}"
echo ""
echo " Запуск на новом ПК БЕЗ сборки:"
echo "   git clone https://github.com/Godlike-Bagheera/praktika && cd praktika"
echo "   cp .env.example .env   # заполнить DB_PASSWORD и т.д."
echo "   docker compose -f docker-compose.hub.yml up -d"
echo "   (база восстановится из дампа: bash scripts/setup.sh forum_backup_*.tar.gz)"
echo "============================================================"
