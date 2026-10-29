# Форум (Web-приложение «Форум»)

Полноценное веб-приложение форума: backend на **Django 5 + Django REST Framework** (PostgreSQL 16, JWT-аутентификация SimpleJWT, экспорт в Excel через openpyxl), frontend на **React 18 + Vite + Bootstrap**, развёрнутые через **Docker Compose** (три контейнера: `db`, `app`, `nginx`). Наружу открыт только порт **8084**.

## Возможности

- Регистрация, вход (JWT access+refresh, срок жизни access-токена — 24 часа), logout с blacklist refresh-токена.
- Роли: гость (только /register и /login), пользователь, администратор.
- Категории (создаёт/редактирует/удаляет только админ), темы (пользователь создаёт, редактирует только свои; админ может удалять любые), сообщения (пагинация по 20, редактирование — только владельцем, удаление — владельцем или админом).
- Поиск по заголовкам тем и тексту сообщений, фильтр по категории, сортировка: темы — новые сверху; в теме сообщения — новые сверху (последние ответы в начале, `order_by("-created_at", "-id")`).
- Экспорт сообщений в `.xlsx`: жирная закреплённая строка заголовков, автофильтр, даты ДД.ММ.ГГГГ, защита от инъекций формул (префикс `'`), лимит 10 000 строк; пользователь экспортирует только свои сообщения, админ — все.
- Ограничение попыток входа: не более 10 в минуту с одного IP (429).
- Валидация на клиенте и сервере, ошибки в формате `{"errors": {"поле": "сообщение"}}`.
- Healthcheck: `GET /health` → 200 без авторизации.

## Структура репозитория

```
/
├── backend/          # Django + DRF (Dockerfile, requirements.txt)
├── frontend/         # React + Vite (Dockerfile, nginx.conf)
├── docker-compose.yml
├── .env.example
└── README.md
```

## Локальный запуск (Docker Compose)

Требуются Docker и Docker Compose.

```bash
cp .env.example .env
# отредактируйте .env: DJANGO_SECRET_KEY, DB_PASSWORD, DJANGO_ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS

docker compose up -d --build

# создание тестовых данных (админ, пользователь, категории, темы, сообщения):
# если не запускать seed_demo, категорий не будет — сайт покажет «Пока нет категорий»;
# категории после этого создаёт администратор вручную на главной странице
docker compose exec app python manage.py seed_demo

# массовое наполнение форума "живым" контентом (10 категорий, 45 тем, ~320 сообщений,
# 15 пользователей; два треда длиннее 20 сообщений — для проверки пагинации).
# Команда идемпотентна: существующие объекты не дублируются, админу обновляет роль/пароль.
docker compose exec app python manage.py fill_forum \
    --admin-email admin@gmail.com --admin-username admin --admin-password admin
```

Приложение доступно: **http://localhost:8084** (или http://IP_сервера:8084). Django-админка: http://IP:8084/admin/ (через прокси nginx путь `/admin` не проброшен — используйте API; при локальной отладке backend — :8000).

### Тестовые учётные данные (после `seed_demo`)

| Роль | Email | Пароль |
|------|-------|--------|
| Администратор | `admin@example.com` | `Admin12345` |
| Пользователь | `user@example.com` | `Demo12345` |

После `fill_forum` также доступен администратор с указанными вами параметрами
(по умолчанию `admin@gmail.com` / пароль `admin`), а также 15 демо-пользователей
(`coder_42@example.com` и т.д., пароль `Demo12345`).

Смену пароля администратора выполните сразу после первого входа.

## Деплой на Ubuntu Server 22.04/24.04 LTS

Требования к серверу: 2 vCPU, 2 ГБ RAM, 20 ГБ диска, сеть Bridge; открыты порты 22, 80, 443, 8084/tcp (порт 5432 наружу не открывать).

```bash
# 1. Установить Docker и Docker Comose plugin
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER && newgrp docker

# 2. Клонировать репозиторий
git clone <URL_репозитория> forum && cd forum

# 3. Настроить окружение
cp .env.example .env
nano .env   # DJANGO_SECRET_KEY (openssl rand -hex 32), DB_PASSWORD,
            # DJANGO_ALLOWED_HOSTS=localhost,<IP_VM>,
            # CSRF_TRUSTED_ORIGINS=http://<IP_VM>:8084

# 4. Запуск
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 8084/tcp
docker compose up -d --build
# если не запускать seed_demo, категорий не будет — сайт покажет «Пока нет категорий»;
# категории после этого создаёт администратор вручную на главной странице
docker compose exec app python manage.py seed_demo

# 5. Проверка
curl http://localhost:8084/health   # → 200
docker compose ps                    # три сервиса в состоянии running/healthy
```

Данные сохраняются в volume `pgdata` — `docker compose restart` и перезагрузка VM не теряют пользователей, категории, темы и сообщения.


## Перенос проекта на новый компьютер (автоматически)

**Сохранение всего (на текущем сервере, внутри ВМ):**
```bash
cd praktika && git pull
bash scripts/one_command.sh <пароль_docker_hub>
```
Скрипт сам: проверит контейнеры, сделает SQL-дамп базы + .env в архив
`forum_backup_<дата>.tar.gz`, соберёт и запушит образы app/nginx на Docker Hub
(testbagheera666/forum-app, testbagheera666/forum-nginx), положит инструкцию
восстановления внутрь архива.

Для ПОЛНОЙ копии всей виртуальной машины (ОС + Docker + данные 1-в-1):
выключи ВМ и на Windows выполни:
```powershell
VBoxManage export "<Имя_ВМ>" --output forum_full.ova
```
(имя смотри через `VBoxManage list vms`). На новом ПК: VirtualBox → File → Import Appliance.

**Развёртывание на НОВОМ компьютере (нужна только Ubuntu/Linux с git):**
```bash
git clone https://github.com/Godlike-Bagheera/praktika && cd praktika
bash scripts/deploy_new_pc.sh /путь/к/forum_backup_<дата>.tar.gz
```
Скрипт сам установит Docker, восстановит .env и базу из дампа, подставит новый IP
в ALLOWED_HOSTS/CSRF, запустит контейнеры, проверит /health и выведет адрес сайта.
Без аргумента — чистый запуск с автоматическим демо-наполнением.
Флаг `--hub` — использовать готовые образы с Docker Hub без сборки.

Последний ручной шаг (только при NAT VirtualBox, на Windows-хосте):
```powershell
VBoxManage controlvm "<Имя_ВМ>" natpf1 "forum,tcp,,8084,,8084"
```

## Скриншоты основных экранов

> Скриншоты делаются после развёртывания (файлы в `docs/screenshots/`):
> 1. `01_login.png` — страница входа
> 2. `02_home.png` — список категорий (админ видит кнопку «Создать категорию»)
> 3. `03_category.png` — темы категории с поиском и пагинацией
> 4. `04_topic.png` — карточка темы, сообщения, кнопка «Скачать Excel»
> 5. `05_register.png` — регистрация с ошибками валидации под полями

## Разработка без Docker

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DB_HOST=localhost DB_NAME=forumdb DB_USER=forumuser DB_PASSWORD=pass DJANGO_SECRET_KEY=dev
python manage.py migrate && python manage.py seed_demo
python manage.py runserver 8000

# Frontend
cd frontend
npm install
npm run dev    # http://localhost:5173, прокси /api → :8000
```

## API (кратко)

| Метод | Путь | Доступ |
|-------|------|--------|
| POST | /api/auth/register | гость |
| POST | /api/auth/login | гость |
| POST | /api/auth/logout | пользователь |
| GET | /api/auth/me | пользователь |
| GET | /api/categories | пользователь |
| POST/PUT/DELETE | /api/categories[/:id] | админ |
| GET/POST | /api/topics (category, search, page, limit) | пользователь |
| GET/PUT/DELETE | /api/topics/:id | пользователь (PUT — владелец, DELETE — владелец/админ) |
| GET/POST | /api/topics/:id/posts (page, limit) | пользователь |
| PUT/DELETE | /api/posts/:id | владелец (DELETE — также админ) |
| GET | /api/posts/export/?topic=&search= | пользователь (свои)/админ (все) |
| GET | /health | все |

## Резервное копирование и перенос проекта

### Сохранить всё (на сервере):
```bash
bash scripts/backup.sh
```
Получите архив `forum_backup_<дата>.tar.gz` — внутри дамп всей базы (пользователи, категории, темы, сообщения), файл `.env` и хеш коммита кода. Скачайте его на свой компьютер (WinSCP/scp, порт 2222).

### Восстановить на новом компьютере (Linux / Ubuntu ВМ):
```bash
git clone https://github.com/Godlike-Bagheera/praktika.git
cd praktika
# положи рядом архив бэкапа
bash scripts/setup.sh forum_backup_<дата>.tar.gz
```
Скрипт сам установит Docker, создаст .env, соберёт контейнеры, восстановит базу из дампа и проверит /health. Без аргумента поднимет чистый проект и наполнит демо-контентом.

### Windows-хост (VirtualBox NAT):
```bat
scripts\setup.bat
```
Запустит ВМ, пробросит порт 8084 и подскажет команды восстановления внутри ВМ.

### Полный клон ВМ (альтернатива):
Выключить ВМ → VirtualBox меню «Экспорт конфигурации виртуальной машины» (.ova) → на новом ПК «Импорт конфигурации». Внутри OVA будет вся ОС со всеми настройками вместе с проектом.

### Публикация образов на Docker Hub (запуск без сборки):
```bash
docker compose build                                   # собрать образы app и nginx
docker login -u testbagheera666                        # пароль с https://hub.docker.com
bash scripts/push_images.sh testbagheera666            # пуш forum-app и forum-nginx
```
На любом новом ПК после этого проект поднимается за секунды, без npm/pip-сборки:
```bash
git clone https://github.com/Godlike-Bagheera/praktika.git
cd praktika && cp .env.example .env                    # заполнить DB_PASSWORD
docker compose -f docker-compose.hub.yml up -d         # образы тянутся с Docker Hub
bash scripts/setup.sh forum_backup_<дата>.tar.gz       # восстановить базу из дампа (опционально)
```

### Важно про секреты
Никогда не коммить `.env` и не публикуй пароли в публичных репозиториях/образах. Для приватных образов используй `docker push` в приватный репозиторий Docker Hub и `docker login` перед запуском.

## Code review fixes (2026-10-29)

Пакет правок по результатам code review (ветка `fix/code-review-batch`):

1. **Уведомления при редактировании поста** (`PostDetailView.put`): перед сохранением
   запоминаются старые `UserMention`, после сохранения `notify_mentions()` возвращает
   актуальный set упомянутых; уведомления за убранные упоминания удаляются, дубли при
   повторном упоминании не создаются. Покрыто тестами (`test_edit_post_*`).
2. **Сортировка в README приведена к коду**: сообщения в теме — новые сверху
   (`order_by("-created_at", "-id")`), как и реализовано в `TopicPostsListView`.
3. **Поиск тем оптимизирован** (`_build_search_q_topic`): вместо N correlated
   EXISTS-подзапросов на строку — один проход по таблице posts для первого слова +
   некоррелированные IN-проверки остальных слов по candidate-темам; добавлена
   короткая ветка для одного слова. Семантика (все слова в сообщениях одной темы)
   сохранена.
4. **CI (GitHub Actions)**: `.github/workflows/test.yml` — pytest на PostgreSQL 16
   service-контейнере + сборка фронтенда на push/PR в main.
5. **CORS в production**: `CORS_ALLOW_ALL_ORIGINS` жёстко `False` при `DEBUG=False`;
   если в проде выставлен `CORS_ALLOW_ALL=true` — предупреждение в лог при старте
   (сервер не падает); whitelist задаётся через `CORS_ALLOWED_ORIGINS`
   (пример в `.env.example`).
