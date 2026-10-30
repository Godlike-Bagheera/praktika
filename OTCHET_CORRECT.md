### 1. ТЕХНИЧЕСКОЕ ЗАДАНИЕ НА РАЗРАБОТКУ ИНФОРМАЦИОННОЙ СИСТЕМЫ

В современном цифровом пространстве возрастает потребность в платформах для обмена знаниями и опытом. Несмотря на наличие крупных социальных сетей, тематические форумы остаются востребованным инструментом для узкоспециализированного общения.

Данный проект направлен на создание веб-приложения «Форум», которое представляет собой платформу для публикации тем и обсуждений.

Основной целью является создание удобного, безопасного и функционального веб-приложения, которое позволит:
1. Автоматизировать процесс публикации сообщений и ведения дискуссий.
2. Предоставить пользователям удобный инструмент для создания тем и обмена сообщениями.
3. Обеспечить модерацию контента со стороны администратора (система жалоб).
4. Реализовать систему выгрузки данных для анализа активности.

Для достижения цели необходимо выполнить следующие задачи:
1. Спроектировать реляционную базу данных для хранения информации о пользователях, категориях, темах, сообщениях, жалобах и уведомлениях.
2. Разработать REST API на базе Django REST Framework.
3. Реализовать клиентскую часть (SPA) на React с маршрутизацией и защитой маршрутов.
4. Внедрить JWT-аутентификацию (access + refresh токены в httpOnly куках) и разграничение прав доступа.
5. Реализовать экспорт данных в формат Excel с защитой от инъекций формул.
6. Реализовать систему жалоб на сообщения с отдельной очередью уведомлений для администраторов.
7. Развернуть проект с использованием Docker и Nginx на виртуальной машине Ubuntu Server.

---

### 2. ПРОЕКТИРОВАНИЕ СХЕМЫ ДАННЫХ

Схема данных представляет собой структурированное описание организации и взаимосвязей данных в базе данных. Она включает в себя таблицы, их поля и связи между ними.

Спроектированная схема данных состоит из 7 сущностей, которая представлена на рисунке 1.

**[МЕСТО ДЛЯ РИСУНКА — схема из dbdiagram.io]**

**Рисунок 1 - Схема данных**

В таблице 1 описаны атрибуты сущности «Пользователи».

**Таблица 1 – Пользователи (accounts_user)**
| Наименование атрибута на английском языке | Наименование атрибута на русском языке | Тип атрибута (размер атрибута) |
| :--- | :--- | :--- |
| id | Код пользователя | Число (PK) |
| password | Пароль (хеш PBKDF2) | Строка (128) |
| email | Почта (логин) | Строка (254), unique |
| username | Имя пользователя | Строка (30), unique |
| role | Роль (user/admin) | Строка (10) |
| is_superuser | Суперпользователь | Логическое (Boolean) |
| is_staff | Персонал | Логическое (Boolean) |
| is_active | Активен | Логическое (Boolean) |
| created_at | Дата регистрации | Дата/Время |

В таблице 2 описаны атрибуты сущности «Категории».

**Таблица 2 – Категории (forumapp_category)**
| Наименование атрибута на английском языке | Наименование атрибута на русском языке | Тип атрибута (размер атрибута) |
| :--- | :--- | :--- |
| id | Код категории | Число (PK) |
| name | Название категории | Строка (100), unique |
| name_lower | Название (нижний регистр, ключ) | Строка (100), unique |
| created_at | Дата создания | Дата/Время |

В таблице 3 описаны атрибуты сущности «Темы».

**Таблица 3 – Темы (forumapp_topic)**
| Наименование атрибута на английском языке | Наименование атрибута на русском языке | Тип атрибута (размер атрибута) |
| :--- | :--- | :--- |
| id | Код темы | Число (PK) |
| category_id | Код категории | Число (FK → category.id) |
| owner_id | Код автора | Число (FK → user.id) |
| title | Заголовок темы | Строка (120) |
| created_at | Дата создания | Дата/Время |
| updated_at | Дата изменения | Дата/Время |

В таблице 4 описаны атрибуты сущности «Сообщения».

**Таблица 4 – Сообщения (forumapp_post)**
| Наименование атрибута на английском языке | Наименование атрибута на русском языке | Тип атрибута (размер атрибута) |
| :--- | :--- | :--- |
| id | Код сообщения | Число (PK) |
| topic_id | Код темы | Число (FK → topic.id) |
| owner_id | Код автора | Число (FK → user.id) |
| text | Текст сообщения | Текст (до 2000 символов) |
| is_hidden | Скрыто модератором | Логическое (Boolean) |
| created_at | Дата создания | Дата/Время |
| updated_at | Дата изменения | Дата/Время |

В таблице 5 описаны атрибуты сущности «Жалобы».

**Таблица 5 – Жалобы (forumapp_postreport)**
| Наименование атрибута на английском языке | Наименование атрибута на русском языке | Тип атрибута (размер атрибута) |
| :--- | :--- | :--- |
| id | Код жалобы | Число (PK) |
| user_id | Автор жалобы | Число (FK → user.id) |
| post_id | Сообщение | Число (FK → post.id) |
| reason | Причина (spam/offtopic/insult/other) | Строка (20) |
| status | Статус (pending/resolved/dismissed) | Строка (20) |
| created_at | Дата подачи | Дата/Время |

Уникальность: один пользователь не может пожаловаться на одно сообщение дважды (ограничение `unique_report_per_user_post`).

В таблице 6 описаны атрибуты сущности «Уведомления о жалобах».

**Таблица 6 – Уведомления о жалобах (forumapp_reportnotification)**
| Наименование атрибута на английском языке | Наименование атрибута на русском языке | Тип атрибута (размер атрибута) |
| :--- | :--- | :--- |
| id | Код уведомления | Число (PK) |
| admin_id | Получатель (администратор) | Число (FK → user.id) |
| report_id | Жалоба | Число (FK → postreport.id) |
| read_at | Дата прочтения | Дата/Время (nullable) |
| created_at | Дата создания | Дата/Время |

В таблице 7 описаны атрибуты сущности «Упоминания» (уведомления о @упоминаниях в текстах сообщений).

**Таблица 7 – Упоминания (forumapp_usermention)**
| Наименование атрибута на английском языке | Наименование атрибута на русском языке | Тип атрибута (размер атрибута) |
| :--- | :--- | :--- |
| id | Код упоминания | Число (PK) |
| user_id | Получатель | Число (FK → user.id) |
| post_id | Сообщение, в котором упомянут | Число (FK → post.id) |
| read_at | Дата прочтения | Дата/Время (nullable) |
| created_at | Дата создания | Дата/Время |

---

### 3. СОЗДАНИЕ СТРУКТУРЫ ИНФОРМАЦИОННОЙ СИСТЕМЫ

Для развертывания и запуска веб-приложения был выбран стек технологий на основе Python и фреймворка Django, что обеспечивает быструю разработку и надежность. Система использует реляционную базу данных PostgreSQL, развернутую в контейнере Docker.

В качестве среды для хостинга использовалась виртуальная машина (VirtualBox) с операционной системой Ubuntu Server. Взаимодействие с виртуальной машиной с хост-компьютера настроено через сетевой интерфейс (NAT) с пробросом портов: порт `8084` для доступа к веб-интерфейсу и порт `2222` для удаленного управления по SSH.

**[МЕСТО ДЛЯ РИСУНКА — скриншот структуры папок проекта из VS Code или Проводника]**

**Рисунок 2 - Структура проекта ИС**

Структура приложения содержит:

**Слой бэкенда (`backend/`):**
* `accounts/` — приложение для управления учетными записями. Реализует кастомную модель пользователя (`User`) с логином по email, ролями (user/admin) и сериализаторы регистрации/входа.
* `forumapp/` — основное приложение, содержащее бизнес-логику форума: модели Category, Topic, Post, PostReport, ReportNotification, UserMention; сериализаторы, представления (APIView), права доступа (permissions.py), систему уведомлений (notifications.py) и команду наполнения базы демо-данными `fill_forum`.
* `forum/` — корневая конфигурация серверной части: настройки БД, JWT, CORS, маршрутизация API (api_urls.py), middleware подстановки JWT из httpOnly-кук.

**Слой представления (`frontend/`):**
* `src/` — исходный код SPA-приложения на React 18 (Vite): страницы (`pages/`: главная, категория, тема, вход/регистрация, статистика, уведомления, панель жалоб), компоненты (`components/`: Header, Pagination, ReportButton, ReportToast, ThemeToggle и др.), контексты авторизации и уведомлений, хук темы (`hooks/useTheme.js`), axios-клиент (`api.js`), глобальные стили Bootstrap 5.3 с поддержкой тёмной темы (`styles.css`).
* `Dockerfile`, конфиг Nginx — раздача собранного билда и проксирование `/api/` на Django (gunicorn).

На листинге 1 представлен файл зависимостей бэкенда.

**Листинг 1 - Файл requirements.txt**
```text
Django==5.1.6
djangorestframework==3.15.2
djangorestframework-simplejwt==5.4.0
psycopg[binary]==3.2.4
openpyxl==3.1.5
django-cors-headers==4.6.0
whitenoise==6.8.2
gunicorn==23.0.0
django-ratelimit==4.1.0
python-dotenv==1.0.1
```

---

### 4. СОЗДАНИЕ МОДЕЛЕЙ ДАННЫХ

Модель данных — это абстракция, представляющая структуру данных, их характеристики и взаимосвязи в рамках информационной системы. В контексте веб-разработки с использованием фреймворка Django, модели данных описывают, как данные будут храниться в реляционной базе данных через объектно-реляционное отображение (ORM).

На листинге 2 представлена модель «Пользователь», которая содержит информацию о пользователе и его роли.

**Листинг 2 – Модель «Пользователь» (backend/accounts/models.py)**
```python
class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model with email login and role field."""

    class Role(models.TextChoices):
        USER = "user", "Пользователь"
        ADMIN = "admin", "Администратор"

    email = models.EmailField("email", max_length=254, unique=True, db_index=True)
    username = models.CharField(
        "имя пользователя",
        max_length=30,
        unique=True,
        validators=[username_validator],
    )
    role = models.CharField(
        "роль", max_length=10, choices=Role.choices, default=Role.USER
    )
    is_active = models.BooleanField("активен", default=True)
    is_staff = models.BooleanField("персонал", default=False)
    created_at = models.DateTimeField("дата регистрации", auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def save(self, *args, **kwargs):
        # Суперпользователь автоматически получает роль admin
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser
```

На листинге 3 представлены модели «Тема» и «Сообщение».

**Листинг 3 – Модели «Тема» и «Сообщение» (backend/forumapp/models.py)**
```python
class Topic(models.Model):
    """Тема форума, привязана к категории."""
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="topics")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField("заголовок", max_length=120)
    created_at = models.DateTimeField("дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("дата изменения", auto_now=True)


class Post(models.Model):
    """Сообщение в теме."""
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="posts")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField("текст", validators=[MaxLengthValidator(2000)])
    is_hidden = models.BooleanField("скрыто модератором", default=False)
    created_at = models.DateTimeField("дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("дата изменения", auto_now=True)
```

На листинге 4 представлена модель «Жалоба» — основа системы премодерации.

**Листинг 4 – Модель «Жалоба» (backend/forumapp/models.py)**
```python
class PostReport(models.Model):
    """Жалоба пользователя на сообщение. Модерируется администратором."""

    class Reason(models.TextChoices):
        SPAM = "spam", "Спам"
        OFFTOPIC = "offtopic", "Не по теме"
        INSULT = "insult", "Оскорбление"
        OTHER = "other", "Другое"

    class Status(models.TextChoices):
        PENDING = "pending", "На рассмотрении"
        RESOLVED = "resolved", "Решено"
        DISMISSED = "dismissed", "Отклонено"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="reports_made")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField("причина", max_length=20, choices=Reason.choices)
    status = models.CharField("статус", max_length=20, choices=Status.choices,
                              default=Status.PENDING)
    created_at = models.DateTimeField("дата", auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"],
                                    name="unique_report_per_user_post"),
        ]
```

---

### 5. АУТЕНТИФИКАЦИЯ И АВТОРИЗАЦИЯ ПОЛЬЗОВАТЕЛЕЙ

Для веб-приложений, работающих с персональными данными, организация безопасного доступа пользователей является фундаментальной задачей. Для безопасности используется JWT-аутентификация, при которой сервер выдает два токена и сохраняет их в защищенные httpOnly куки (что предотвращает кражу токенов через XSS): access-токен живёт 15 минут (кука на весь сайт, path=/), refresh-токен — дольше, и его кука намеренно ограничена путём /api/auth/ (сужение поверхности утечки). Включена ротация refresh-токенов с занесением старых в blacklist.

На листинге 5 представлен код регистрации пользователя (валидация на бэкенде).

**Листинг 5 - Сериализатор регистрации (backend/accounts/serializers.py)**
```python
class RegisterSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254)
    username = serializers.CharField(max_length=30)
    password = serializers.CharField(write_only=True, min_length=8, max_length=64)
    password_confirm = serializers.CharField(write_only=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError("Введите корректный email")
        try:
            validate_email(value)
        except DjangoValidationError:
            raise serializers.ValidationError("Введите корректный email")
        return value

    def validate_username(self, value):
        value = value.strip()
        if not USERNAME_RE.match(value):
            raise serializers.ValidationError(
                "Только латиница, цифры и _, от 3 до 30 символов")
        return value

    def validate_password(self, value):
        if len(value) < 8 or len(value) > 64:
            raise serializers.ValidationError("Пароль: от 8 символов, буквы и цифры")
        if not PASSWORD_LETTER_DIGIT_RE.search(value):
            raise serializers.ValidationError("Пароль: от 8 символов, буквы и цифры")
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages[0])
        return value
```

На листинге 6 представлен контроллер авторизации (входа) и выдачи httpOnly куки.

**Листинг 6 - Контроллер входа (backend/forumapp/views.py)**
```python
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if _login_rate_limited(request):
            return Response({"errors": {"detail": "Слишком много попыток. Попробуйте позже"}},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        serializer = LoginSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response({"errors": {"detail": "Неверный email или пароль"}},
                            status=status.HTTP_401_UNAUTHORIZED)

        from rest_framework_simplejwt.tokens import RefreshToken
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        access_life, refresh_life = _jwt_conf()   # 15 мин / 14 дней
        response = Response({"user": MeSerializer(user).data})
        secure = _cookie_secure()                 # Secure=по умолчанию в production
        # access — httpOnly кука на весь сайт; JS её не видит (защита от XSS)
        response.set_cookie(
            "forum_access", access,
            max_age=int(access_life.total_seconds()),
            httponly=True, samesite="Lax", secure=secure, path="/",
        )
        # refresh — только для эндпоинтов /api/auth/* (path сужен)
        response.set_cookie(
            "forum_refresh", str(refresh),
            max_age=int(refresh_life.total_seconds()),
            httponly=True, samesite="Lax", secure=secure,
            path=REFRESH_COOKIE_PATH,             # "/api/auth/"
        )
        return response
```

На листинге 7 представлено middleware, которое перехватывает токен из куки для DRF (SimpleJWT умеет читать токен только из заголовка Authorization).

**Листинг 7 - Middleware JWT из куки (backend/forum/middleware.py)**
```python
class JwtCookieAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.META.get("HTTP_AUTHORIZATION"):
            token = request.COOKIES.get("forum_access")
            if token:
                request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.get_response(request)
```

**[МЕСТО ДЛЯ РИСУНКОВ — скриншоты форм регистрации и входа]**

---

### 6. НАСТРОЙКА АДМИНИСТРАТИВНОЙ ПАНЕЛИ (МОДЕРАЦИЯ)

В соответствии с техническим заданием, отдельная стандартная административная панель Django (/admin) не используется. Функции модератора реализованы непосредственно в пользовательском интерфейсе React-приложения.

При входе под учетной записью с ролью admin в меню профиля появляется пункт «Жалобы» с красным бейджем количества нерассмотренных жалоб, а также ссылка «Статистика». В каждой теме и под каждым сообщением администратору доступны кнопки редактирования/удаления независимо от авторства. За проверку прав на бэкенде отвечает класс IsAdmin.

Система жалоб работает следующим образом: любой пользователь (кроме автора поста) может отправить жалобу на сообщение с указанием причины (спам / не по теме / оскорбление / другое). Повторная жалоба того же пользователя на то же сообщение блокируется на уровне ограничения уникальности. При создании жалобы всем активным администраторам создаётся запись отдельной модели ReportNotification (не смешивается с @упоминаниями), фронтенд опрашивает счётчик непрочитанных и показывает всплывающий тост справа снизу; переход по ссылке открывает страницу /reports со списком всех жалоб и фильтром по статусу. Кнопка «Скрыть пост» меняет статус жалобы на resolved и устанавливает посту флаг is_hidden=True — после такое сообщение исчезает из ленты обычных пользователей, но остаётся видно админу с пометкой. Кнопка «Отклонить» меняет статус на dismissed, пост остаётся видимым.

На листинге 8 представлен класс проверки прав администратора.

**Листинг 8 - Проверка прав администратора (backend/forumapp/permissions.py)**
```python
class IsAdmin(BasePermission):
    """Доступ только для администраторов (role=admin или superuser)."""
    message = "Требуется роль администратора"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and getattr(user, "is_admin_role", False)
        )
```

На листинге 9 представлено создание жалобы с уведомлением всех администраторов.

**Листинг 9 - Создание жалобы и уведомлений (backend/forumapp/views.py)**
```python
class ReportCreateView(APIView):
    """POST /api/posts/<post_id>/report/ — создать жалобу на чужой пост."""
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        post = Post.objects.filter(pk=post_id).first()
        if post is None:
            raise NotFound("Сообщение не найдено")
        data = dict(request.data or {})
        data["post"] = post.pk          # id берём из URL, тело не доверяем
        serializer = PostReportCreateSerializer(data=data, context={"request": request})
        if not serializer.is_valid():
            errs = {f: (v[0] if isinstance(v, list) else v)
                    for f, v in serializer.errors.items()}
            return Response({"errors": errs}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                report = serializer.save(user=request.user)
                # Отдельная система уведомлений о жалобах (не @упоминания)
                admins = get_user_model().objects.filter(role="admin", is_active=True)
                for admin in admins:
                    ReportNotification.objects.get_or_create(admin=admin, report=report)
        except IntegrityError:
            # Гонка: два параллельных запроса жалобы от одного пользователя
            return Response({"errors": {"post": "Вы уже жаловались на это сообщение"}},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Жалоба отправлена"}, status=status.HTTP_201_CREATED)
```

**[МЕСТО ДЛЯ РИСУНКОВ — скриншот главной страницы под админом и страницы /reports]**

---

### 7. СОЗДАНИЕ ПОЛЬЗОВАТЕЛЬСКОГО ИНТЕРФЕЙСА

За время учебной практики были созданы основные страницы веб-приложения «Форум»: «Главная страница (список категорий)», «Страница категории (список тем)», «Страница темы (список сообщений)», «Уведомления», «Статистика», «Панель жалоб», а также страницы входа и регистрации. Интерфейс разработан с учетом различных ролей, обеспечивая интуитивно понятную навигацию и доступ к функционалу. Реализована светлая и тёмная темы (нативный атрибут Bootstrap 5.3 data-bs-theme на элементе html) с сохранением выбора пользователя в localStorage и определением системной темы по умолчанию.

Сообщения в теме выводятся в порядке «новые сверху» (сортировка `-created_at, -id`); скрытые модератором сообщения из ленты обычных пользователей исключаются на уровне запроса.

На листинге 10 представлен компонент кастомной пагинации, который используется на всех страницах со списками.

**Листинг 10 - Компонент пагинации (frontend/src/components/Pagination.jsx)**
```javascript
export default function Pagination({ count, limit, page, onChange }) {
  const pages = Math.max(1, Math.ceil((count || 0) / (limit || 20)));
  if (pages <= 1) return null;

  // Диапазон показываемых номеров вокруг активной страницы
  const windowSize = 2;
  let from = Math.max(1, page - windowSize);
  let to = Math.min(pages, page + windowSize);
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
          <li>
            <button type="button" className={btnCls(page <= 1 ? 'is-disabled' : '')}
                    onClick={() => go(1)} disabled={page <= 1}>«</button>
          </li>
          <li>
            <button type="button" className={btnCls(page <= 1 ? 'is-disabled' : '')}
                    onClick={() => go(page - 1)} disabled={page <= 1}>‹</button>
          </li>
          {from > 1 && (
            <>
              <li><button type="button" className={btnCls()} onClick={() => go(1)}>1</button></li>
              {from > 2 && <li><span className="forum-page-dots">…</span></li>}
            </>
          )}
          {items.map((p) => (
            <li key={p}>
              <button type="button" className={btnCls(p === page ? 'is-active' : '')}
                      onClick={() => go(p)}>{p}</button>
            </li>
          ))}
          {/* симметрично: последняя страница и кнопка › */}
        </ul>
      </div>
    </nav>
  );
}
```

**[МЕСТО ДЛЯ РИСУНКОВ — скриншот главной страницы и страницы с сообщениями]**

---

### 8. РАЗРАБОТКА ФУНКЦИОНАЛА ПОЛЬЗОВАТЕЛЕЙ

Во время учебной практики был реализован функционал для создания тем и общения на форуме, система уведомлений (@упоминания в текстах сообщений с доставкой через polling каждые 20 секунд и всплывающие тосты), а также система выгрузки данных.

Главная особенность проекта — регистронезависимый поиск по кириллице, который корректно работает благодаря кастомному SQL-выражению (Lookup) для PostgreSQL.

**Листинг 11 - Класс кастомного поиска (backend/forumapp/views.py)**
```python
class UniLikeLookup(Lookup):
    """Регистронезависимый «содержит» (Unicode-safe)."""
    lookup_name = "unilike"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        # PostgreSQL: LOWER() корректно работает с кириллицей, ESCAPE '\'
        # делает \% и \_ из _contains_q буквальными символами.
        return f"LOWER({lhs}) LIKE LOWER({rhs}) ESCAPE '\\'", (
            list(lhs_params) + list(rhs_params))


CharField.register_lookup(UniLikeLookup)
TextField.register_lookup(UniLikeLookup)
```

На листинге 12 представлен код выгрузки сообщений в Excel. Реализована защита от инъекций формул (значения, начинающиеся с =, +, -, @, экранируются апострофом), а также фильтрация: обычный пользователь выгружает только собственные непустые скрытые сообщения, администратор — все.

**Листинг 12 - Экспорт в Excel (backend/forumapp/views.py)**
```python
def _clean_formula(value):
    """Защита от инъекций формул: значения, начинающиеся с = + - @,
    записываются с апострофом в начале."""
    if isinstance(value, str) and value.lstrip()[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


class PostsExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from openpyxl import Workbook
        user = request.user
        qs = Post.objects.select_related("owner", "topic")
        if not getattr(user, "is_admin_role", False):
            qs = qs.filter(owner=user, is_hidden=False)

        wb = Workbook()
        ws = wb.active
        ws.title = "Сообщения"
        ws.append(["ID", "Тема", "Автор", "Текст", "Дата создания"])
        ws.freeze_panes = "A2"

        for p in qs.iterator():
            ws.append([
                p.id,
                _clean_formula(p.topic.title),
                _clean_formula(p.owner.username),
                _clean_formula(p.text),   # защита от формул
                p.created_at,
            ])
        # ... автоширина колонок, формат дат ...

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        wb.save(response)
        return response
```

**[МЕСТО ДЛЯ РИСУНКОВ — скриншот скачанного Excel-файла и терминала с запущенными контейнерами (docker compose ps)]**
