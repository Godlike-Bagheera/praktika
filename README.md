# Форум-проект (Praktika)

Краткое описание: учебный форум на Django + React с Docker-развёртыванием, JWT-авторизацией в httpOnly куках, системой жалоб с уведомлениями для админа, статистикой, тёмной темой и CI/CD через GitHub Actions.

## Содержание
- [Требования](#требования)
- [Шаг 1. Установка Ubuntu Server на VirtualBox](#шаг-1-установка-ubuntu-server-на-virtualbox)
  - [Настройка виртуальной машины](#настройка-виртуальной-машины)
  - [Установка системы](#установка-системы)
  - [Экран Profile configuration](#экран-profile-configuration)
- [Шаг 2. Настройка проброса портов](#шаг-2-настройка-проброса-портов)
- [Шаг 3. Подключение по SSH](#шаг-3-подключение-по-ssh)
  - [С Windows (PowerShell)](#с-windows-powershell)
  - [С Linux / macOS](#с-linux--macos)
  - [Альтернатива: сетевой мост](#альтернатива-сетевой-мост)
- [Шаг 4. Установка Docker и SSH-сервера](#шаг-4-установка-docker-и-ssh-сервера)
- [Шаг 5. Скачивание и запуск проекта](#шаг-5-скачивание-и-запуск-проекта)
- [Шаг 6. Наполнение базы демо-данными](#шаг-6-наполнение-базы-демо-данными)
- [Шаг 7. Открытие сайта в браузере](#шаг-7-открытие-сайта-в-браузере)
- [Данные для входа](#данные-для-входа)
- [Запуск тестов](#запуск-тестов)
- [Полезные команды](#полезные-команды)
- [Решение типичных проблем](#решение-типичных-проблем)

## Требования

- VirtualBox 7+ (https://www.virtualbox.org/)
- ISO Ubuntu Server 24.04 LTS или 26.04 LTS (https://ubuntu.com/download/server)
- Минимум 2 GB RAM и 2 CPU для виртуальной машины
- 15 GB свободного места на диске
- Git, SSH-клиент (PowerShell на Windows, терминал на Linux/macOS)

## Шаг 1. Установка Ubuntu Server на VirtualBox

### Настройка виртуальной машины

1. Открой VirtualBox, нажми **Создать**
2. Имя: `ubuntu-server`, Тип: `Linux`, Версия: `Ubuntu (64-bit)`
3. Оперативная память: **2048 MB** (можно больше)
4. Жёсткий диск: **Создать новый виртуальный жёсткий диск**, VDI, динамический, **15 GB**
5. После создания ВМ нажми **Настроить**:
   - **Система → Процессор**: выдели 2 CPU
   - **Сеть → Сеть 1**: Тип подключения **NAT**
   - **Сеть → Дополнительно → Проброс портов** → добавь 2 правила (зелёный плюс):
     * Имя: `ssh`, Протокол: `TCP`, IP хоста: `127.0.0.1`, Порт хоста: `2222`, Порт гостя: `22`
     * Имя: `forum`, Протокол: `TCP`, IP хоста: `127.0.0.1`, Порт хоста: `8084`, Порт гостя: `8084`
   - **Носители**: в контроллер IDE добавь скачанный ISO Ubuntu Server

### Установка системы

1. Запусти ВМ — начнётся установка Ubuntu
2. Выбери язык (English или Русский — как удобнее)
3. Раскладка клавиатуры: Russian или English
4. Тип установки: **Ubuntu Server** (без графического интерфейса)
5. Сетевые настройки: оставь по умолчанию (DHCP)
6. Прокси: оставь пустым
7. Зеркало архива: оставь по умолчанию
8. Разметка диска: **Use entire disk** → Continue → Continue

### Экран Profile configuration

После разметки диска появится экран **Profile configuration** с пятью полями. Заполни их так:

- **Ваше имя** (Your name): введи своё имя, например `Student` или любое другое. Это полное имя пользователя, оно не критично.
- **Your server's name** (имя сервера): введи `ubuntu-server` или любое имя без пробелов. Это hostname машины, используется в командной строке как `user@ubuntu-server`.
- **Введите имя пользователя** (Username): введи `ubuntu` (строчными буквами, без пробелов и спецсимволов). Это будет логин для входа в систему и для SSH-подключения.
- **Задайте пароль** (Choose a password): введи надёжный пароль, например `ubuntu12345`. Пароль должен быть минимум 8 символов.
- **Подтвердите пароль** (Confirm your password): введи тот же пароль ещё раз.

После заполнения всех пяти полей нажми **Tab** чтобы перейти к кнопке **Готово** (Done), и нажми **Enter**.

Важно: запомни имя пользователя и пароль — они понадобятся для SSH-подключения. Если забудешь пароль, его можно сбросить через Recovery Mode (см. раздел "Решение типичных проблем").

Дальше установщик предложит настроить SSH Server — обязательно выбери **Install OpenSSH server** (пробелом отметь пункт и нажми Tab → Done). Это позволит подключаться к виртуалке по SSH с хост-машины.

Остальные шаги (Featured Server Snaps) можно пропустить — нажми Done.

После завершения установки нажми **Reboot Now**. При запросе "Please remove the installation medium" просто нажми Enter.

## Шаг 2. Настройка проброса портов

Если ты настраивал проброс портов при создании ВМ (Шаг 1), этот шаг можно пропустить.

Для проверки открой PowerShell на Windows и выполни:
```powershell
VBoxManage list vms
```
Найди имя своей ВМ в кавычках (например `"ubuntu-server"`). Если проброс не настроен, выполни:
```powershell
VBoxManage modifyvm "ubuntu-server" --natpf1 "ssh,tcp,,2222,,22"
VBoxManage modifyvm "ubuntu-server" --natpf1 "forum,tcp,,8084,,8084"
```
ВМ должна быть выключена при выполнении этих команд.

## Шаг 3. Подключение по SSH

### С Windows (PowerShell)

1. Запусти виртуальную машину в VirtualBox
2. Дождись появления приглашения входа в Ubuntu
3. Открой PowerShell на Windows (Win+R → powershell → Enter)
4. Выполни команду:
```powershell
ssh -p 2222 ubuntu@127.0.0.1
```
5. При первом подключении напиши `yes` и нажми Enter
6. Введи пароль, который задавал на экране Profile configuration (символы при вводе не отображаются — это нормально)

Для удобства можно создать файл `C:\Users\<ТвоёИмя>\.ssh\config` с содержимым:
```
Host ubuntu
    HostName 127.0.0.1
    User ubuntu
    Port 2222
```
После этого подключение будет одной командой:
```powershell
ssh ubuntu
```

### С Linux / macOS

Открой терминал и выполни:
```bash
ssh -p 2222 ubuntu@127.0.0.1
```
Или добавь в `~/.ssh/config`:
```
Host ubuntu
    HostName 127.0.0.1
    User ubuntu
    Port 2222
```

### Альтернатива: сетевой мост

Если NAT не работает, можно использовать сетевой мост:
1. В VirtualBox: Настройки ВМ → Сеть → Сеть 1 → Тип подключения: **Сетевой мост (Bridged Adapter)**
2. Запусти ВМ, войди в систему
3. Узнай IP виртуалки:
```bash
ip a
```
Ищи строку вида `inet 192.168.1.45/24` — это и есть IP.
4. Подключись с хост-машины:
```bash
ssh ubuntu@192.168.1.45
```
(замени IP на свой)

## Шаг 4. Установка Docker и SSH-сервера

После подключения по SSH выполни команды по одной, дожидаясь завершения каждой:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Важно: после выполнения команды `usermod` выйди из SSH командой `exit` и подключись заново, чтобы применились права группы docker.

Проверь установку:
```bash
docker --version
docker compose version
```

## Шаг 5. Скачивание и запуск проекта

```bash
# Клонируем репозиторий
git clone https://github.com/Godlike-Bagheera/praktika.git
cd praktika

# Создаём .env из шаблона
cp .env.example .env

# Генерируем секретный ключ и заполняем .env для локальной разработки
NEW_KEY=$(openssl rand -hex 32)
sed -i "s/DJANGO_SECRET_KEY=.*/DJANGO_SECRET_KEY=$NEW_KEY/" .env
sed -i "s/DJANGO_DEBUG=.*/DJANGO_DEBUG=1/" .env
sed -i "s/DJANGO_SECURE_COOKIES=.*/DJANGO_SECURE_COOKIES=0/" .env
sed -i "s/DB_PASSWORD=.*/DB_PASSWORD=localpass123/" .env

# Проверяем что .env заполнен
cat .env | grep -E "SECRET_KEY|DEBUG|SECURE_COOKIES|DB_PASSWORD"

# Запускаем контейнеры (первый раз сборка займёт 2-3 минуты)
docker compose up -d --build

# Применяем миграции
docker compose exec app python manage.py migrate
```

## Шаг 6. Наполнение базы демо-данными

```bash
docker compose exec app python manage.py fill_forum --admin-email admin@gmail.com --admin-username admin --admin-password admin
```

Команда создаст:
- 10 категорий форума
- Около 45 тем с осмысленными названиями
- Около 320 сообщений от 15 демо-пользователей
- Администратора admin@gmail.com / admin

## Шаг 7. Открытие сайта в браузере

- Если использовал проброс портов (NAT): открой в браузере на Windows/Linux **http://localhost:8084**
- Если использовал сетевой мост: **http://<IP_виртуалки>:8084**

Нажми **Ctrl+F5** для жёсткой перезагрузки (сброс кэша браузера).

## Данные для входа

Администратор:
- Email: `admin@gmail.com`
- Пароль: `admin`

Демо-пользователи (создаются скриптом fill_forum):
- `alpha_tester`, `beta_user`, `gamma_dev` и другие
- Пароль у всех: `Test12345`

## Запуск тестов

```bash
docker compose exec app python manage.py test
```

Ожидаемый результат: `Ran 47 tests in XX.XXs` — все тесты проходят (OK). В режиме DEBUG=1 один тест про secure cookies может выдавать предупреждение — это нормально для локальной разработки.

## Полезные команды

```bash
# Посмотреть статус контейнеров
docker compose ps

# Посмотреть логи приложения
docker compose logs -f app

# Посмотреть логи nginx
docker compose logs -f nginx

# Перезапустить контейнеры
docker compose restart

# Полностью остановить и удалить базу данных
docker compose down -v

# Зайти в контейнер приложения
docker compose exec app bash

# Зайти в PostgreSQL
docker compose exec db psql -U forumuser -d forumdb

# Обновить код и пересобрать
cd ~/praktika
git pull
docker compose up -d --build

# Применить новые миграции
docker compose exec app python manage.py migrate

# Выйти из SSH
exit
```

## Решение типичных проблем

### Ошибка "Connection refused" при SSH
- Убедись что виртуальная машина запущена
- Проверь проброс портов: VirtualBox → Настройки ВМ → Сеть → Дополнительно → Проброс портов. Должны быть правила для портов 2222→22 и 8084→8084
- Проверь что ssh-сервер запущен на Ubuntu:
```bash
sudo systemctl status ssh
```
Если не запущен:
```bash
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
```

### Ошибка "Permission denied" при docker compose
Выйди из SSH командой `exit` и подключись заново. Права группы docker применяются только после перелогина.

### Ошибка "env file .env not found"
```bash
cd ~/praktika
cp .env.example .env
```
Заполни обязательные поля в .env: DJANGO_SECRET_KEY, DB_PASSWORD.

### Ошибка миграций "relation already exists" или "column already exists"
Полностью удали базу и создай заново:
```bash
docker compose down -v
docker volume rm praktika_pgdata 2>/dev/null || true
docker compose up -d
sleep 10
docker compose exec app python manage.py migrate
docker compose exec app python manage.py fill_forum --admin-email admin@gmail.com --admin-username admin --admin-password admin
```

### Сайт не открывается в браузере
- Проверь что контейнеры запущены: `docker compose ps`
- Проверь логи nginx: `docker compose logs nginx`
- Убедись что порт 8084 проброшен в VirtualBox
- Нажми Ctrl+F5 в браузере

### Забыл пароль от Ubuntu
1. Перезагрузи ВМ. Сразу после появления логотипа VirtualBox многократно нажимай **Shift** (или **Esc**) чтобы попасть в меню GRUB
2. Выбери **Advanced options for Ubuntu** → строку с **(recovery mode)** → Enter
3. В меню восстановления выбери **root — Drop to root shell prompt** → Enter
4. Нажми Enter для активации командной строки
5. Выполни:
```bash
mount -o remount,rw /
passwd ubuntu
```
6. Введи новый пароль дважды (символы не отображаются)
7. Перезагрузи:
```bash
reboot
```

### Экран Profile configuration — что вводить
Если ты на этапе установки Ubuntu и не знаешь что вводить в поля:
- **Ваше имя**: любое, например `Student`
- **Your server's name**: `ubuntu-server` (без пробелов)
- **Введите имя пользователя**: `ubuntu` (строчными, без пробелов — это будет логин для SSH)
- **Задайте пароль**: придумай пароль минимум 8 символов, например `ubuntu12345`
- **Подтвердите пароль**: тот же пароль ещё раз
После заполнения нажми Tab до кнопки **Готово** и Enter.

## Технологии

- **Backend**: Python 3.12, Django 5, Django REST Framework, PostgreSQL 16, SimpleJWT
- **Frontend**: React 18, Vite, Bootstrap 5.3, React Router
- **DevOps**: Docker, Docker Compose, GitHub Actions (CI), Nginx
- **Безопасность**: JWT в httpOnly куках, rate limiting, защита SECRET_KEY, secure cookies, CSRF-защита, система жалоб с премодерацией

## Лицензия

Учебный проект для практики.
