#!/usr/bin/env bash
# ============================================================
# forum deploy — РАЗВЁРТЫВАНИЕ проекта на НОВОМ ПК одной командой.
# Использование (на новом Linux/Ubuntu):
#   git clone https://github.com/Godlike-Bagheera/praktika && cd praktika
#   bash scripts/deploy_new_pc.sh /путь/к/forum_backup_<дата>.tar.gz
# Без аргумента — чистый запуск + демо-наполнение fill_forum.
# С флагом --hub — брать готовые образы с Docker Hub (без сборки).
# Всё делает само: Docker, .env, IP, порты, восстановление БД, проверки.
# ============================================================
set -uo pipefail
cd "$(dirname "$0")/.."

ARCHIVE=""; HUB=0
for a in "$@"; do
  case "$a" in
    --hub) HUB=1 ;;
    *.tar.gz) ARCHIVE="$a" ;;
  esac
done

echo "==> 1. Проверка/установка Docker..."
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y docker.io docker-compose-v2 curl git tar || {
    echo "    Пробую официальный скрипт get.docker.com..."; curl -fsSL https://get.docker.com | sudo sh; }
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER" 2>/dev/null || true
fi
docker compose version >/dev/null 2>&1 || { echo "НЕТ docker compose v2. Обновись: sudo apt install docker-compose-v2"; exit 1; }
echo "    Docker OK: $(docker --version)"

echo "==> 2. Настройка .env..."
NEW_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -n "$NEW_IP" ] || NEW_IP=127.0.0.1
if [ -n "$ARCHIVE" ] && tar tzf "$ARCHIVE" 2>/dev/null | grep -q 'env.txt'; then
  TMPD=$(mktemp -d); tar xzf "$ARCHIVE" -C "$TMPD"
  ENVF=$(find "$TMPD" -name env.txt | head -1)
  cp "$ENVF" .env; rm -rf "$TMPD"
  echo "    .env восстановлен из архива бэкапа"
elif [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 50)|" .env
  sed -i "s|^DB_PASSWORD=.*|DB_PASSWORD=$(head -c 16 /dev/urandom | base64 | tr -d '/+=' | head -c 16)|" .env
  echo "    .env создан заново (случайные секреты)"
fi
sed -i "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,${NEW_IP}|" .env
sed -i "s|^CSRF_TRUSTED_ORIGINS=.*|CSRF_TRUSTED_ORIGINS=http://${NEW_IP}:8084,http://localhost:8084|" .env
grep -q '^POSTGRES_PASSWORD=' .env || echo "POSTGRES_PASSWORD=$(grep DB_PASSWORD .env | cut -d= -f2)" >> .env
grep -q '^POSTGRES_USER=' .env || echo "POSTGRES_USER=$(grep DB_USER .env | cut -d= -f2)" >> .env
grep -q '^POSTGRES_DB=' .env || echo "POSTGRES_DB=$(grep DB_NAME .env | cut -d= -f2)" >> .env
echo "    IP подставлен: ${NEW_IP}"

echo "==> 3. Запуск контейнеров..."
if [ "$HUB" = "1" ]; then
  docker compose -f docker-compose.hub.yml up -d
else
  docker compose up -d --build
fi
echo "    Жду healthy базы данных..."
for i in $(seq 1 60); do
  st=$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q db)" 2>/dev/null || echo starting)
  [ "$st" = "healthy" ] && break; sleep 2
done
[ "$st" = "healthy" ] || { echo "ОШИБКА: БД не поднялась"; docker compose logs db | tail -20; exit 1; }
echo "    БД healthy ✓"

echo "==> 4. Восстановление базы данных..."
if [ -n "$ARCHIVE" ]; then
  TMPD=$(mktemp -d); tar xzf "$ARCHIVE" -C "$TMPD"
  SQL=$(find "$TMPD" -name 'forum_backup.sql' | head -1)
  if [ -n "$SQL" ]; then
    # чистим схему, чтобы дамп лёг идеально
    docker compose exec -T db psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" \
      -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null 2>&1
    cat "$SQL" | docker compose exec -T db psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" >/dev/null
    rm -rf "$TMPD"
    echo "    База восстановлена из дампа ✓"
    docker compose restart app >/dev/null
  else
    echo "    В архиве нет forum_backup.sql — пропускаю"
  fi
else
  echo "    Дамп не передан — создаю админа и демо-контент..."
  docker compose exec -T app python manage.py migrate >/dev/null 2>&1 || true
  docker compose exec -T app python manage.py shell -c "
from accounts.models import User
u,_ = User.objects.get_or_create(username='admin', defaults={'email':'admin@gmail.com','role':'admin'})
u.role='admin'; u.is_staff=True; u.is_superuser=True; u.set_password('admin'); u.save()
print('admin ok')" >/dev/null
  docker compose exec -T app python manage.py fill_forum --admin-email admin@gmail.com --admin-username admin --admin-password admin --backfill || true
fi

echo "==> 5. Финальные проверки..."
sleep 3
CODE=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8084/health || echo 000)
CNT=$(docker compose exec -T db psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" -tAc "SELECT count(*) FROM forumapp_post" 2>/dev/null || echo "?")
CATS=$(docker compose exec -T db psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" -tAc "SELECT count(*) FROM forumapp_category" 2>/dev/null || echo "?")
echo ""
echo "============================================================"
if [ "$CODE" = "200" ]; then echo " САЙТ РАБОТАЕТ ✓  (/health -> 200)"; else echo " ВНИМАНИЕ: /health -> $CODE (посмотри: docker compose logs app)"; fi
echo " Категорий: $CATS | Сообщений: $CNT"
echo " Адрес для браузера:  http://${NEW_IP}:8084"
echo " Вход администратора: admin@gmail.com / admin (или тот, что был в дампе)"
echo ""
echo " Если это VirtualBox-NAT и нужен доступ с других машин —"
echo " на Windows-хосте выполни:"
echo "   VBoxManage controlvm \"<Имя_ВМ>\" natpf1 \"forum,tcp,,8084,,8084\""
echo "============================================================"
