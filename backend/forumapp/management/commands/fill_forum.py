"""Массовое наполнение форума демо-контентом.

Создаёт администраторов из переданных email, пул пользователей,
категории, темы и сообщения (включая длинные треды для проверки
пагинации по 20 сообщений на страницу).

Использование:
    python manage.py fill_forum --admin-email admin@gmail.com --admin-password admin
"""
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from forumapp.models import Category, Post, Topic

CATEGORIES = [
    "Общий раздел",
    "Программирование",
    "Веб-разработка",
    "Python и Django",
    "Базы данных",
    "Linux и сервера",
    "Помощь и вопросы",
    "Объявления",
    "Игры",
    "Флудилка",
    "Мобильная разработка",
    "Безопасность",
]

USERNAMES = [
    "coder_42", "neon_viper", "sunny_day", "dark_horse", "pixel_witch",
    "byte_master", "quantum_fox", "iron_panda", "swift_river", "moon_walker",
    "cyber_cat", "green_toad", "lucky_star", "thunder_bird", "quiet_storm",
    "dev_null", "kernel_panic", "null_pointer", "sudo_maker", "root_access",
    "binary_soul", "hex_dump", "stack_overflow", "seg_fault", "daemon_prc",
]

TOPICS_BY_CATEGORY = {
    "Общий раздел": [
        "Добро пожаловать на форум!",
        "Правила форума — прочитайте перед публикацией",
        "Представьтесь в этой теме",
        "Как у вас настроение сегодня?",
        "Какие сайты посещаете каждый день?",
        "Обсуждение обновлений форума",
        "Что бы вы хотели видеть на форуме?",
    ],
    "Программирование": [
        "С какого языка начать изучение программирования?",
        "Best practices для чистого кода",
        "Как проходить собеседования по алгоритмам",
        "Git: полезные команды, о которых вы не знали",
        "Ошибки новичков при первом пет-проекте",
        "Стоит ли учить Rust в 2026 году?",
        "Как читать чужой код и не сойти с ума",
    ],
    "Веб-разработка": [
        "React vs Vue vs Svelte — что выбрать?",
        "Tailwind или обычный CSS?",
        "Как ускорить загрузку страницы",
        "JWT против сессий: что безопаснее?",
        "Прокси и CORS при локальной разработке",
        "SSR или CSR: когда что использовать",
        "Гибкая верстка: flexbox против grid",
    ],
    "Python и Django": [
        "Django REST Framework: сериализаторы и валидация",
        "Оптимизация запросов ORM (select_related/prefetch_related)",
        "Как настроить SimpleJWT и blacklist для logout",
        "Миграции Django: частые проблемы",
        "Gunicorn + Nginx: деплой Django приложения",
        "Виртуальные окружения: venv против poetry",
        "Асинхронщина в Django: ASGI и Channels",
    ],
    "Базы данных": [
        "PostgreSQL vs MySQL — что использовать?",
        "Индексы: когда они действительно помогают",
        "ON DELETE CASCADE: как не потерять данные зря",
        "Нормализация или денормализация?",
        "Резервное копирование PostgreSQL в Docker",
        "Транзакции и уровни изоляции простыми словами",
        "SQL-запросы, которые должны быть в арсенале каждого",
    ],
    "Linux и сервера": [
        "Ubuntu Server: базовая настройка после установки",
        "Docker Compose: связываем контейнеры",
        "Настройка firewall ufw — какие порты открывать",
        "Systemd-сервисы: как это работает",
        "Nginx: reverse proxy для SPA и API",
        "SSH: ключи вместо паролей",
        "Хостинг сайта дома на VirtualBox — опыт и грабли",
    ],
    "Помощь и вопросы": [
        "Не открывается сайт по IP виртуальной машины",
        "Ошибка 502 Bad Gateway при деплое",
        "Как сменить роль пользователя на администратора",
        "Почему спиннер загрузки не исчезает?",
        "Docker пересобрать образ после git pull — как правильно",
        "Помогите с CORS при локальном запуске",
    ],
    "Объявления": [
        "Обновление форума: добавлен экспорт в Excel",
        "План работ на следующий месяц",
        "Ищем модераторов раздела Программирование",
        "Изменились правила публикации тем",
    ],
    "Игры": [
        "Во что играете в свободное время?",
        "Подборка инди-игр этого года",
        "Киберспорт: смотреть или играть?",
        "Игры на слабом ПК — что посоветуете?",
    ],
    "Флудилка": [
        "Тред для офтопа",
        "Поделитесь мемом дня",
        "Кофе или чай? Вечный спор",
        "Что послушать во время кодинга?",
        "Ваше рабочее место — фото и рассказы",
    ],
    "Мобильная разработка": [
        "Flutter или React Native в 2026?",
        "Kotlin для Android: с чего начать",
        "Как опубликовать приложение в Google Play",
        "PWA вместо нативного приложения — реальный опыт",
        "Отладка мобильных приложений: инструменты",
    ],
    "Безопасность": [
        "OWASP Top 10: как не стать статистикой",
        "Пароли: хеширование и salt на пальцах",
        "Как защитить API от брутфорса и DDoS",
        "HTTPS: Let's Encrypt за 10 минут",
        "Утечки данных: чек-лист для разработчика",
    ],
}

POST_TEXTS = [
    "Полностью поддерживаю автора темы, сам столкнулся с этим недавно.",
    "Отличный вопрос! У меня есть пара мыслей на этот счёт.",
    "Могу посоветовать официальную документацию — там всё подробно расписано.",
    "У меня было ровно так же, пока я не перепробовал три разных подхода.",
    "Спасибо, очень полезно! Сохранил тему в закладки.",
    "Не согласен — зависит от конкретной задачи и контекста проекта.",
    "Попробуйте разбить проблему на части и проверить каждую отдельно.",
    "Это классическая ошибка, встречается у большинства новичков.",
    "Кстати, в последней версии это уже исправили, обновитесь.",
    "+1, хотел написать то же самое.",
    "Приведу пример из своей практики: на продакшене используем именно такой стек.",
    "А можно подробнее? Не совсем понял, к чему вы клоните.",
    "Лучший способ разобраться — сделать свой мини-проект по этой теме.",
    "Главное не сдаваться, через месяц станет заметно легче.",
    "Есть нюанс: на Windows это работает иначе, чем на Linux.",
    "Ссылка на решение: поищите по ключевым словам из сообщения выше.",
    "Проверьте логи, там почти всегда видна настоящая причина ошибки.",
    "Хорошая тема, давно пора было её поднять.",
    "IMHO, стоит добавить больше примеров кода.",
    "Работает! Спасибо огромное, потратил на эту проблему весь вечер.",
    "Автор, уточните версию — поведение сильно отличается между релизами.",
    "Использую третий год подряд, проблем не возникало.",
    "Кажется, вы имеете в виду немного другое. Уточню свою мысль...",
    "Отличная подборка, добавил себе в заметки.",
]

REPLY_PREFIXES = [
    "", "Согласен. ", "Небольшое дополнение: ", "По опыту скажу — ",
    "Важный момент: ", "К тому же, ", "Актуализирую тему: ",
]

# Стартовый пост автора темы (первый в каждом треде)
OPENING_TEXTS = [
    "Открываю тему, потому что тема назрела. Делитесь мнением и опытом, мне правда интересно, как у других.",
    "Накопилось несколько вопросов по этой теме — давайте разберёмся вместе. Начинаю с самого простого случая.",
    "Предлагаю обсуждение. Ниже опишу контекст, а вы дополняйте своими историями и ссылками.",
    "Столкнулся с этим на практике и решил вынести вопрос на форум. Буду рад любым комментариям и контраргументам.",
    "Собрал в одном месте то, что удалось узнать по теме. Если есть замечания или дополнения — пишите, обновлю первый пост.",
    "Давно хотел поднять этот вопрос. Начну с примера из собственной практики, а дальше посмотрим на ваши варианты.",
]


class Command(BaseCommand):
    help = "Массово наполняет форум категориями, темами и сообщениями"

    def add_arguments(self, parser):
        parser.add_argument("--admin-email", default="admin@gmail.com")
        parser.add_argument("--admin-username", default="admin")
        parser.add_argument("--admin-password", default="admin")
        parser.add_argument("--users", type=int, default=25)
        parser.add_argument("--user-password", default="Demo12345")
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument(
            "--backfill", action="store_true",
            help="Дописать стартовые посты и ответы во ВСЕ существующие темы "
                 "(даже созданные ранее), а не только в новые",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        n_users = max(3, options["users"])

        # --- Администратор ---
        admin = User.objects.filter(email__iexact=options["admin_email"]).first()
        if admin is None:
            admin = User.objects.create_superuser(
                email=options["admin_email"],
                username=options["admin_username"],
                password=options["admin_password"],
            )
            self.stdout.write(self.style.SUCCESS(
                f"Создан администратор: {admin.email} / {options['admin_password']}"
            ))
        else:
            admin.role = User.Role.ADMIN
            admin.is_staff = True
            admin.is_superuser = True
            admin.set_password(options["admin_password"])
            admin.save()
            self.stdout.write(
                f"Администратор {admin.email} найден, роль и пароль обновлены"
            )

        # --- Пользователи ---
        users = [admin]
        created_users = 0
        for i, uname in enumerate(USERNAMES[:n_users]):
            u = User.objects.filter(username=uname).first()
            if u is None:
                u = User.objects.create_user(
                    email=f"{uname}@example.com",
                    username=uname,
                    password=options["user_password"],
                )
                created_users += 1
            users.append(u)
        self.stdout.write(self.style.SUCCESS(
            f"Пользователей в базе (с админами): {len(users)}, новых создано: {created_users}"
        ))

        # --- Категории ---
        cats = {}
        new_cats = 0
        for name in CATEGORIES:
            cat = Category.objects.filter(name__iexact=name).first()
            if cat is None:
                cat = Category.objects.create(name=name)
                new_cats += 1
            cats[name] = cat
        self.stdout.write(self.style.SUCCESS(
            f"Категорий: {len(cats)} (новых создано: {new_cats})"
        ))

        # --- Темы и сообщения ---
        new_topics = 0
        new_posts = 0

        def populate(topic, cat_name):
            """Наполняет тему: стартовый пост автора + цепочка ответов."""
            nonlocal new_posts
            n_existing = Post.objects.filter(topic=topic).count()
            if n_existing == 0:
                Post.objects.create(
                    topic=topic, owner=topic.owner,
                    text=rng.choice(OPENING_TEXTS),
                )
                new_posts += 1
                n_existing = 1
            target = rng.randint(4, 10)
            if cat_name == "Общий раздел" and "представьтесь" in topic.title.lower():
                target = 30  # длинный тред для проверки пагинации (>20)
            if cat_name == "Флудилка" and topic.title == "Тред для офтопа":
                target = 35  # ещё один тред > 20 сообщений
            for _ in range(max(0, target - n_existing)):
                author = rng.choice(users)
                text = rng.choice(REPLY_PREFIXES) + rng.choice(POST_TEXTS)
                if rng.random() < 0.15:
                    text += " " + rng.choice(POST_TEXTS)
                Post.objects.create(topic=topic, owner=author, text=text)
                new_posts += 1

        for cat_name, titles in TOPICS_BY_CATEGORY.items():
            cat = cats[cat_name]
            for title in titles:
                topic = Topic.objects.filter(category=cat, title=title).first()
                if topic is not None:
                    if options["backfill"]:
                        populate(topic, cat_name)
                    continue
                owner = rng.choice(users)
                topic = Topic.objects.create(category=cat, owner=owner, title=title)
                new_topics += 1
                populate(topic, cat_name)

        # При --backfill дописываем ответы и в темы, созданные вне шаблонов
        # (например, seed_demo или вручную пользователями) — но только те,
        # где вообще нет ни одного сообщения.
        if options["backfill"]:
            empty_topics = Topic.objects.filter(posts__isnull=True).select_related("category")
            for topic in empty_topics:
                populate(topic, topic.category.name)

        self.stdout.write(self.style.SUCCESS(
            f"Новых тем создано: {new_topics}, новых сообщений: {new_posts}"
        ))
        self.stdout.write(self.style.SUCCESS(
            "Форум наполнен! Обновите страницу в браузере."
        ))
