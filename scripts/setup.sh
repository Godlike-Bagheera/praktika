#!/usr/bin/env bash
# ============================================================
# forum setup — развёртывание проекта «Форум» на НОВОМ Linux-ПК
# (или внутри свежей Ubuntu-ВМ). Идемпотентно.
#
# Использование:
#   1) клонируй репозиторий:  git clone https://github.com/Godlike-Bagheera/praktika
#   2) положи рядом архив бэкапа forum_backup_*.tar.gz
#   3) bash scripts/setup.sh forum_backup_<дата>.tar.gz
#      (без аргумента — поднимется чистый проект + демо-наполнение)
# ============================================================
set -euo pipefail
BACKUP_FILE="${1:-}"
cd "$(dirname "$0")/.."

echo "==> 1. Проверка/установка Docker..."
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y docker.io docker-compose-v2 curl git
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER" || true
  echo "    Docker установлен. Если группа docker добавлена только что — перелогинься и запусти скрипт снова."
else
  echo "    Docker уже есть: $(docker --version)"
fi
docker compose version >/dev/null 2>&1 || { echo "НЕТ docker compose v2"; exit 1; }

echo "==> 2. Проверка .env..."
if [ ! -f .env ]; then
  if [ -n "$BACKUP_FILE" ] && tar tzf "$BACKUP_FILE" 2>/dev/null | grep -q 'env.txt'; then
    TMP=$(mktemp -d); tar xzf "$BACKUP_FILE" -C "$TMP"
    find "$TMP" -name env.txt -exec cp {} .env \;
    rm -rf "$TMP"
    echo "    .env восстановлен из архива бэкапа"
  else
    cp .env.example .env
    sed -i "s|замените_на_случайную_строку|$(head -c 32 /dev/urandom | base64 | tr -d '/+=')|" .env
    sed -i "s|замените_на_случайный_пароль|$(head -c 16 /dev/urandom | base64 | tr -d '/+=')|" .env
    echo "    Создан новый .env со случайными секретами (чистая установка)"
  fi
fi
IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo 127.0.0.1)
sed -i -E "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,${IP},10.0.2.15|" .env
sed -i -E "s|^CSRF_TRUSTED_ORIGINS=.*|CSRF_TRUSTED_ORIGINS=http://${IP}:8084,http://10.0.2.15:8084,http://localhost:8084|" .env
echo "    .env настроен под IP=${IP}"

echo "==> 3. Сборка и запуск контейнеров..."
docker compose up -d --build
echo "    Ожидание готовности БД..."
for i in $(seq 1 30); do
  docker compose ps db 2>/dev/null | grep -qi healthy && break
  sleep 2
done

echo "==> 4. Восстановление базы из бэкапа..."
if [ -n "$BACKUP_FILE" ]; then
  TMP=$(mktemp -d); tar xzf "$BACKUP_FILE" -C "$TMP"
  SQL=$(find "$TMP" -name '*.sql' | head -1)
  if [ -n "$SQL" ]; then
    docker compose stop app
    DB_USER_VAL=$(grep -E '^DB_USER=' .env | cut -d= -f2)
    DB_NAME_VAL=$(grep -E '^DB_NAME=' .env | cut -d= -f2)
    # чистим схему и заливаем дамп
    docker compose exec -T db psql -U "$DB_USER_VAL" -d "$DB_NAME_VAL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null
    cat "$SQL" | docker compose exec -T db psql -U "$DB_USER_VAL" -d "$DB_NAME_VAL" >/dev/null
    docker compose start app
    echo "    База восстановлена из $SQL"
  fi
  rm -rf "$TMP"
else
  echo "    Архив не передан — создаём админа и наполняем демо-контентом..."
  docker compose exec -T app python manage.py shell -c "
from accounts.models import User
u,_=User.objects.get_or_create(username='admin', defaults={'email':'admin@gmail.com','role':'admin'})
u.set_password('admin'); u.is_staff=True; u.is_superuser=True; u.role='admin'; u.save()
print('admin готов')"
  docker compose exec -T app python manage.py fill_forum --admin-email admin@gmail.com --admin-username admin --admin-password admin --backfill || true
fi

echo "==> 5. Финальная проверка..."
sleep 3
CODE=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8084/health || echo 000)
COUNT=$(docker compose exec -T db psql -U "$(grep -E '^DB_USER=' .env | cut -d= -f2)" -d "$(grep -E '^DB_NAME=' .env | cut -d= -f2)" -tAc "SELECT count(*) FROM forumapp_post" 2>/dev/null || echo '?')
echo "    /health -> HTTP ${CODE}"
echo "    Сообщений в базе: ${COUNT}"
echo ""
echo "============================================================"
echo " ГОТОВО. Открой в браузере:  http://${IP}:8084"
echo " Вход: admin@gmail.com / admin"
echo " С другой машины по NAT (VirtualBox):"
echo '   VBoxManage controlvm "Имя_ВМ" natpf1 "forum,tcp,,8084,,8084"'
echo "============================================================"
