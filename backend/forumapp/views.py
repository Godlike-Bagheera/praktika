"""Views for the Forum API."""
import datetime
import logging
import os
import re

from django.conf import settings
from django.db import transaction
from django.db.models import (
    CharField, Count, Exists, IntegerField, Lookup, OuterRef, Q, TextField, Value,
)
from django.db.models.functions import TruncDate
from django.db.utils import IntegrityError, OperationalError, ProgrammingError
from django.http import HttpResponse
from rest_framework import serializers, status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes, throttle_classes,
)
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import (
    LoginSerializer,
    MeSerializer,
    PostPatchSerializer,
    RegisterSerializer,
    TopicPatchSerializer,
)
from .models import Category, Post, PostReport, Topic, UserMention
from .notifications import notify_admins_about_report, notify_mentions
from .pagination import ForumPagination
from .permissions import IsAdmin, OwnerOrAdminDelete, OwnerOnlyEdit
from .serializers import (
    CategoryNameConflict,
    CategorySerializer,
    PostPatchSerializer,
    PostReportCreateSerializer,
    PostReportSerializer,
    PostSerializer,
    TopicPatchSerializer,
    TopicSerializer,
)

logger = logging.getLogger(__name__)

# Пути куки для refresh-токена: сужаем область (фикс 4) — logout и refresh
# живут под /api/auth/*, поэтому кука отдаётся только туда.
REFRESH_COOKIE_PATH = "/api/auth/"


def _jwt_conf():
    """ACCESS/REFRESH lifetime из настроек SIMPLE_JWT (единственный источник
    правды — синхронно с реальным временем жизни токенов)."""
    conf = getattr(settings, "SIMPLE_JWT", {})
    access = conf.get("ACCESS_TOKEN_LIFETIME", datetime.timedelta(minutes=15))
    refresh = conf.get("REFRESH_TOKEN_LIFETIME", datetime.timedelta(days=7))
    return access, refresh


def _cookie_secure():
    """Secure-флаг куки. По умолчанию ВКЛЮЧЕН (безопасный дефолт);
    отключается только явным DJANGO_SECURE_COOKIES=0 (например, локальная
    http-разработка). При DEBUG=False и secure=False — предупреждение в лог."""
    secure = os.environ.get("DJANGO_SECURE_COOKIES", "1") == "1"
    if not secure and not settings.DEBUG:
        logger.warning(
            "DJANGO_SECURE_COOKIES=0 при DEBUG=False: куки авторизации "
            "передаются без флага Secure (только по HTTPS это безопасно!). "
            "Включите DJANGO_SECURE_COOKIES=1 в production."
        )
    return secure


def _category_conflict_response():
    return Response(
        {"errors": {"name": "Эта категория уже существует"}},
        status=status.HTTP_409_CONFLICT,
    )

# ---------------------------------------------------------------------------
# Rate limiting: no more than 10 login attempts per minute from one IP.
# Implemented with a LocMem cache bucket (custom middleware-style helper).
# ---------------------------------------------------------------------------
_LOGIN_LIMIT = 10
_LOGIN_WINDOW_SECONDS = 60


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _login_rate_limited(request):
    """Return True if the IP exceeded the login rate limit; otherwise record
    a new attempt and return False."""
    from django.core.cache import cache
    key = "login_rl:%s" % _client_ip(request)
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    bucket = cache.get(key)
    if not bucket:
        bucket = {"count": 0, "start": now.isoformat()}
    start = datetime.datetime.fromisoformat(bucket["start"])
    if (now - start).total_seconds() > _LOGIN_WINDOW_SECONDS:
        bucket = {"count": 0, "start": now.isoformat()}
    if bucket["count"] >= _LOGIN_LIMIT:
        return True
    bucket["count"] += 1
    # store for the remainder of the window
    ttl = max(1, _LOGIN_WINDOW_SECONDS - int((now - start).total_seconds()))
    cache.set(key, bucket, ttl)
    return False


# ---------------------------------------------------------------------------
# Healthcheck — accessible to everyone (even guests)
# ---------------------------------------------------------------------------
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health_view(request):
    return Response({"status": "ok"})


# ---------------------------------------------------------------------------
# Authentication endpoints
# ---------------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data or {}
        email = str(data.get("email", "")).strip()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        password_confirm = str(data.get("password_confirm", ""))

        errors = {}
        if not email or not EMAIL_RE.match(email) or len(email) > 254:
            errors["email"] = "Введите корректный email"
        if password != password_confirm:
            errors["password_confirm"] = "Пароли не совпадают"

        if errors:
            return Response({"errors": errors},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = RegisterSerializer(data=data)
        if not serializer.is_valid():
            # Map DRF error lists into {"field": "message"}
            errs = {}
            for field, msgs in serializer.errors.items():
                if isinstance(msgs, list):
                    errs[field] = str(msgs[0])
                else:
                    errs[field] = str(msgs)
            code = status.HTTP_400_BAD_REQUEST
            # Duplicate email -> 409
            email_msg = errs.get("email", "")
            if "занят" in email_msg.lower() or "already" in email_msg.lower():
                code = status.HTTP_409_CONFLICT
            return Response({"errors": errs}, status=code)

        user = serializer.save()
        me = MeSerializer(user).data
        return Response({"user": me}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if _login_rate_limited(request):
            return Response(
                {"errors": {"detail": "Слишком много попыток. Попробуйте позже"}},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        serializer = LoginSerializer(data=request.data or {})
        if not serializer.is_valid():
            errs = {}
            for field, msgs in serializer.errors.items():
                errs[field] = str(msgs[0]) if isinstance(msgs, list) else str(msgs)
            # non-field errors come under key 'non_field_errors'
            if "non_field_errors" in errs:
                errs = {"detail": errs["non_field_errors"]}
            detail = errs.get("detail", "Неверный email или пароль")
            if detail == "Неверный email или пароль":
                return Response({"errors": {"detail": detail}},
                                status=status.HTTP_401_UNAUTHORIZED)
            return Response({"errors": errs},
                            status=status.HTTP_400_BAD_REQUEST)

        from rest_framework_simplejwt.tokens import RefreshToken
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        access_life, refresh_life = _jwt_conf()
        response = Response({"user": MeSerializer(user).data})
        secure = _cookie_secure()
        # access — httpOnly кука на весь сайт; JS её не видит (защита от XSS);
        # max_age синхронизирован с SIMPLE_JWT.ACCESS_TOKEN_LIFETIME (15 мин)
        response.set_cookie(
            "forum_access", access,
            max_age=int(access_life.total_seconds()),
            httponly=True, samesite="Lax", secure=secure, path="/",
        )
        # refresh — только для эндпоинтов /api/auth/* (path сужен, фикс 4)
        response.set_cookie(
            "forum_refresh", str(refresh),
            max_age=int(refresh_life.total_seconds()),
            httponly=True, samesite="Lax", secure=secure,
            path=REFRESH_COOKIE_PATH,
        )
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken

        # refresh теперь приходит из httpOnly-куки (path=/api/auth/),
        # тело запроса — обратная совместимость со старыми клиентами
        refresh_token = (request.COOKIES.get("forum_refresh")
                         or (request.data or {}).get("refresh"))
        response = Response(status=status.HTTP_204_NO_CONTENT)

        def _clear():
            response.delete_cookie("forum_access", path="/")
            response.delete_cookie("forum_refresh", path=REFRESH_COOKIE_PATH)

        if not refresh_token:
            # даже без токена чистим куки — сессия всё равно завершается
            _clear()
            return response
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()  # добавляет jti в blacklist
        except Exception:
            _clear()
            return response
        _clear()
        return response


class RefreshView(APIView):
    """Обновление access-куки по refresh-куке (для фронтенда после истечения
    короткого access-токена — 15 минут)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken

        # refresh-токен живёт в httpOnly-куке даже после истечения access,
        # поэтому эндпоинт доступен без аутентификации (проверяем токен сами)
        refresh_token = (request.COOKIES.get("forum_refresh")
                         or (request.data or {}).get("refresh"))
        if not refresh_token:
            return Response(
                {"errors": {"detail": "Сессия истекла. Войдите снова"}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            from accounts.models import User

            old = RefreshToken(refresh_token)
            user = User.objects.get(pk=old["user_id"])
            if not user.is_active:
                raise Exception("user inactive")
            # ротация: старый refresh в blacklist, выдаём новую пару
            new = RefreshToken.for_user(user)
            old.blacklist()
        except Exception:
            response = Response(
                {"errors": {"detail": "Сессия истекла. Войдите снова"}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            response.delete_cookie("forum_access", path="/")
            response.delete_cookie("forum_refresh", path=REFRESH_COOKIE_PATH)
            return response

        access_life, refresh_life = _jwt_conf()
        secure = _cookie_secure()
        response = Response({"user": MeSerializer(user).data})
        response.set_cookie(
            "forum_access", str(new.access_token),
            max_age=int(access_life.total_seconds()),
            httponly=True, samesite="Lax", secure=secure, path="/",
        )
        response.set_cookie(
            "forum_refresh", str(new),
            max_age=int(refresh_life.total_seconds()),
            httponly=True, samesite="Lax", secure=secure,
            path=REFRESH_COOKIE_PATH,
        )
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


# ---------------------------------------------------------------------------
# Categories (admin-only write, authenticated read)
# ---------------------------------------------------------------------------
class CategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = Category.objects.all()
        # Поиск по названию (частичное совпадение, без учёта регистра)
        search = request.query_params.get("search")
        client_wants_paginated = (
            "page" in request.query_params or "limit" in request.query_params
        )
        if not client_wants_paginated:
            # Обратная совместимость: старые клиенты ждут плоский список.
            # Если таблица categories ещё не создана (свежая БД до migrate) —
            # отдаём пустой список вместо 500.
            try:
                data = list(qs)
            except (OperationalError, ProgrammingError):
                data = []
            return Response(CategorySerializer(data, many=True).data)
        if search:
            qs = qs.filter(_build_search_q(search, ["name"]))
        qs = qs.annotate(topics_count=Count("topics", distinct=True))
        # детерминированный порядок для пагинации (ordering модели — name)
        qs = qs.order_by("name", "id")
        paginator = ForumPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            CategorySerializer(page, many=True).data
        )

    def post(self, request):
        serializer = CategorySerializer(data=request.data or {})
        if not serializer.is_valid():
            errs = {f: (v[0] if isinstance(v, list) else v)
                    for f, v in serializer.errors.items()}
            return Response({"errors": errs},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer.save()
        except ValueError:
            # повторный конфликт имени (обычная ошибка пользователя) -> 400
            return Response(
                {"errors": {"name": "Эта категория уже существует"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CategoryNameConflict:
            # гонка одновременного создания -> 409, а не 500
            return _category_conflict_response()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CategoryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_object(self, pk):
        obj = Category.objects.filter(pk=pk).first()
        if obj is None:
            raise NotFound("Категория не найдена")
        return obj

    def put(self, request, pk):
        obj = self.get_object(pk)
        serializer = CategorySerializer(obj, data=request.data or {}, partial=False)
        if not serializer.is_valid():
            errs = {f: (v[0] if isinstance(v, list) else v)
                    for f, v in serializer.errors.items()}
            return Response({"errors": errs},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer.save()
        except ValueError:
            # переименование в уже занятое имя (ошибка пользователя) -> 400
            return Response(
                {"errors": {"name": "Эта категория уже существует"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CategoryNameConflict:
            # гонка одновременного переименования в одно имя -> 409, а не 500
            return _category_conflict_response()
        return Response(serializer.data)

    def delete(self, request, pk):
        self.get_object(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------
class TopicListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Topic.objects.select_related("category", "owner").annotate(
            posts_count=Count("posts", distinct=True)
        )
        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category_id=category)
        search = request.query_params.get("search")
        if search:
            # слова запроса ищем в названии темы ИЛИ в тексте её сообщений
            qs = qs.filter(_build_search_q_topic(search)).distinct()
        qs = qs.order_by("-created_at")
        paginator = ForumPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = TopicSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        data = dict(request.data or {})
        serializer = TopicSerializer(data=data)
        if not serializer.is_valid():
            errs = {f: (v[0] if isinstance(v, list) else v)
                    for f, v in serializer.errors.items()}
            return Response({"errors": errs},
                            status=status.HTTP_400_BAD_REQUEST)
        topic = serializer.save(owner=request.user)
        return Response(TopicSerializer(topic).data,
                        status=status.HTTP_201_CREATED)


class TopicDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        obj = Topic.objects.select_related("category", "owner").annotate(
            posts_count=Count("posts", distinct=True)
        ).filter(pk=pk).first()
        if obj is None:
            raise NotFound("Тема не найдена")
        return obj

    def get(self, request, pk):
        obj = self.get_object(pk)
        return Response(TopicSerializer(obj).data)

    def put(self, request, pk):
        obj = self.get_object(pk)
        # Редактировать тему может только её владелец (не админ для чужих)
        if obj.owner_id != request.user.id:
            raise PermissionDenied("Нельзя редактировать чужую тему")
        serializer = TopicPatchSerializer(data=dict(request.data or {}))
        if not serializer.is_valid():
            errs = {f: (v[0] if isinstance(v, list) else v)
                    for f, v in serializer.errors.items()}
            return Response({"errors": errs},
                            status=status.HTTP_400_BAD_REQUEST)
        obj.title = serializer.validated_data["title"]
        obj.save(update_fields=["title", "updated_at"])
        return Response(TopicSerializer(obj).data)

    def delete(self, request, pk):
        obj = self.get_object(pk)
        if obj.owner_id != request.user.id and not getattr(
                request.user, "is_admin_role", False):
            raise PermissionDenied("Нельзя удалить чужую тему")
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# Nested posts collection under a topic
class TopicPostsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get_topic(self, pk):
        topic = Topic.objects.filter(pk=pk).first()
        if topic is None:
            raise NotFound("Тема не найдена")
        return topic

    def get(self, request, pk):
        topic = self.get_topic(pk)
        qs = Post.objects.filter(topic=topic).select_related("owner")
        # Скрытые модератором посты не показываются обычным пользователям;
        # админ видит их с пометкой is_hidden (см. PostSerializer).
        if not getattr(request.user, "is_admin_role", False):
            qs = qs.filter(is_hidden=False)
        search = request.query_params.get("search")
        if search:
            # все слова запроса должны присутствовать в тексте сообщения
            qs = qs.filter(_build_search_q(search, ["text"]))
        # Новые сообщения всегда сверху (сортировка по убыванию времени)
        qs = qs.order_by("-created_at", "-id")
        # Вспомогательный параметр для «перелёта» к посту из уведомления
        # (?post=<id>): count при limit=1 отдаёт число сообщений, более новых,
        # чем целевой пост — по нему фронт вычисляет нужную страницу.
        after = request.query_params.get("after")
        if after:
            try:
                target = Post.objects.only("created_at", "id").get(pk=int(after))
            except (Post.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"count": 0, "pages": 1, "page": 1, "limit": 1,
                     "next": None, "previous": None, "results": []},
                )
            qs = qs.filter(created_at__gt=target.created_at)
        paginator = ForumPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            PostSerializer(page, many=True).data
        )

    def post(self, request, pk):
        topic = self.get_topic(pk)
        data = dict(request.data or {})
        data.pop("topic", None)
        serializer = PostSerializer(data=data)
        if not serializer.is_valid():
            errs = {f: (v[0] if isinstance(v, list) else v)
                    for f, v in serializer.errors.items()}
            return Response({"errors": errs},
                            status=status.HTTP_400_BAD_REQUEST)
        post = serializer.save(topic=topic, owner=request.user)
        notify_mentions(post)
        return Response(PostSerializer(post).data,
                        status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Posts (standalone edit/delete)
# ---------------------------------------------------------------------------
class PostDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        obj = Post.objects.select_related("owner", "topic").filter(pk=pk).first()
        if obj is None:
            raise NotFound("Сообщение не найдено")
        return obj

    def get(self, request, pk):
        return Response(PostSerializer(self.get_object(pk)).data)

    def put(self, request, pk):
        obj = self.get_object(pk)
        # Редактировать сообщение может только владелец
        if obj.owner_id != request.user.id:
            raise PermissionDenied("Нельзя редактировать чужое сообщение")
        serializer = PostPatchSerializer(data=dict(request.data or {}))
        if not serializer.is_valid():
            errs = {f: (v[0] if isinstance(v, list) else v)
                    for f, v in serializer.errors.items()}
            return Response({"errors": errs},
                            status=status.HTTP_400_BAD_REQUEST)
        obj.text = serializer.validated_data["text"]
        obj.save(update_fields=["text", "updated_at"])
        # При редактировании синхронизируем уведомления с новым текстом:
        # добавляем свежие упоминания и удаляем уведомления за упоминания,
        # которых в новом тексте больше нет (иначе «убрал @username» — а
        # тост/уведомление висит; «добавил повторно» — дубль не создаётся).
        old_mentions = set(
            UserMention.objects.filter(post=obj)
            .values_list("user_id", flat=True)
        )
        new_mentions = notify_mentions(obj)
        removed = old_mentions - new_mentions
        if removed:
            UserMention.objects.filter(post=obj, user_id__in=removed).delete()
        return Response(PostSerializer(obj).data)

    def delete(self, request, pk):
        obj = self.get_object(pk)
        is_admin = getattr(request.user, "is_admin_role", False)
        if obj.owner_id != request.user.id and not is_admin:
            raise PermissionDenied("Нельзя удалить чужое сообщение")
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Поиск (search)
# ---------------------------------------------------------------------------
# Поиск должен быть регистронезависимым в том числе для кириллицы.
# Django `icontains` строит UPPER(col) LIKE ...%UPPER(pattern)% ESCAPE,
# что на некоторых локалях/коллпейшенах ломает частичное совпадение.
# Поэтому используется свой lookup `unilike`: LOWER(col) LIKE LOWER(pattern),
# с экранированием спецсимволов LIKE (% _ \) в запросе.
# ---------------------------------------------------------------------------


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


def _contains_q(field, value):
    """Q для регистронезависимого «содержит» (Unicode-safe, PostgreSQL).

    Экранируем спецсимволы LIKE (%, _, \\), чтобы поисковый запрос
    интерпретировался как обычный текст."""
    escaped = re.sub(r"([%_\\])", r"\\\1", value or "")
    return Q(**{field + "__unilike": "%" + escaped + "%"})


def _search_words(query):
    """Разбивает поисковый запрос на слова (по 2+ символа)."""
    return [w for w in re.split(r"\s+", (query or "").strip()) if len(w) >= 2]


def _build_search_q(query, fields):
    """Строит Q для «хорошего» поиска: каждое слово запроса должно
    встречаться в одном из полей (AND между словами — как в Google).
    Совпадение регистронезависимое и частичное (Unicode-safe).
    Если слов нет (запрос короче 2 символов) — поиск по всей строке."""
    words = _search_words(query) or ([query.strip()] if query and query.strip() else [])
    result = Q()
    for w in words:
        word_q = Q()
        for f in fields:
            word_q |= _contains_q(f, w)
        result &= word_q
    return result


def _build_search_q_topic(query):
    """Поиск тем: все слова запроса должны встречаться либо в названии темы,
    либо в текстах сообщений одной и той же темы (слова могут быть в разных
    сообщениях — прежняя семантика, на которой написаны тесты).

    Архитектура сохранена: фильтр строится как Q с EXISTS/IN, совместимый с
    пагинацией DRF. Внутри условие по постам вынесено в один некоррелированный
    подзапрос (_topics_with_all_words_in_posts), а не N correlated EXISTS на
    каждую строку тем."""
    words = _search_words(query)
    if not words:
        # Пустой/короткий запрос (< 2 символов): одна проверка «вся строка
        # встречается в тексте поста темы» — без разбивки на слова.
        stripped = (query or "").strip()
        if not stripped:
            return ~Q(pk__in=[])  # пустой запрос матчит всё (нейтральный фильтр)
        return Q(Exists(
            Post.objects.filter(topic=OuterRef("pk")).filter(_contains_q("text", stripped))
        ))
    title_q = Q()
    for w in words:
        title_q &= _contains_q("title", w)
    if len(words) == 1:
        # Короткая версия для одного слова: единственный EXISTS-подзапрос
        # (проверять распределение слов по разным постам не нужно).
        posts_q = Q(Exists(
            Post.objects.filter(topic=OuterRef("pk")).filter(_contains_q("text", words[0]))
        ))
    else:
        posts_q = Q(pk__in=_topics_with_all_words_in_posts(words))
    return title_q | posts_q


def _topics_with_all_words_in_posts(words):
    """id тем, в СООБЩЕНИЯХ которых встречаются все слова запроса
    (слова могут быть распределены по разным сообщениям одной темы).

    Оптимизация вместо N correlated EXISTS-подзапросов на каждую строку
    таблицы тем: первое (обычно самое редкое) слово отсекается одним
    SQL-фильтром сразу по всем постам, и дальнейшие проверки слов делаются
    только внутри оставшихся candidate-тем (`topic_id__in` — один IN-запрос
    на слово по маленькому множеству). Таблица posts сканируется целиком
    ровно один раз за весь поиск."""
    n = len(words)
    # 1) Один проход по posts: темы, где есть первое слово.
    candidates = set(
        Post.objects.filter(_contains_q("text", words[0]))
        .values_list("topic_id", flat=True)
    )
    if not candidates or n == 1:
        return list(candidates)
    # 2) Оставшиеся слова проверяем только по candidate-темам:
    # каждое слово даёт один некоррелированный IN-запрос по маленькому
    # множеству вместо EXISTS-подзапроса на каждую тему списка.
    for w in words[1:]:
        found = set(
            Post.objects.filter(topic_id__in=candidates)
            .filter(_contains_q("text", w))
            .values_list("topic_id", flat=True)
        )
        candidates &= found
        if not candidates:
            break
    return list(candidates)


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
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter

        user = request.user
        is_admin = getattr(user, "is_admin_role", False)
        qs = Post.objects.select_related("owner", "topic")
        if not is_admin:
            # Обычный пользователь: только свои посты, скрытые модератором — не его.
            qs = qs.filter(owner=user, is_hidden=False)
        # Админ: все посты (скрытые тоже, для аудита).
        topic = request.query_params.get("topic")
        if topic:
            qs = qs.filter(topic_id=topic)
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(_build_search_q(search, ["text"]))
        # Порядок на сайте — новые сверху (см. PostListView); экспорт
        # приводим к тому же порядку, чтобы нумерация строк в Excel
        # совпадала с темой на форуме.
        qs = qs.order_by("-created_at", "-id")

        count = qs.count()
        if count > 10000:
            return Response(
                {"errors": {"detail": "Слишком много записей для экспорта "
                                      "(максимум 10 000)"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        wb = Workbook()
        ws = wb.active
        ws.title = "Сообщения"

        headers = ["ID", "Тема", "Автор", "Текст", "Дата создания"]
        ws.append(headers)
        bold = Font(bold=True)
        for cell in ws[1]:
            cell.font = bold
        ws.freeze_panes = "A2"
        # Автофильтр включаем после заполнения данных (см. ниже), чтобы ref
        # соответствовал реальному числу строк.

        date_fmt = "DD.MM.YYYY"
        widths = [len(h) for h in headers]
        for p in qs.iterator():
            # Переводим UTC-время в локальное (Europe/Moscow), чтобы дата в
            # файле совпадала с тем, что видит пользователь в списке.
            local_dt = p.created_at.astimezone(
                datetime.timezone(datetime.timedelta(hours=3))
            )
            created = datetime.datetime.combine(
                local_dt.date(), local_dt.time()
            )
            row = [
                p.id,
                _clean_formula(p.topic.title),
                _clean_formula(p.owner.username),
                _clean_formula(p.text),
                created,
            ]
            ws.append(row)
            ws.cell(row=ws.max_row, column=5).number_format = date_fmt
            for i, val in enumerate(row, start=1):
                s = str(val) if not isinstance(val, datetime.datetime) else \
                    val.strftime(date_fmt)
                if widths[i - 1] < len(s):
                    widths[i - 1] = min(len(s), 80)

        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w + 2

        # Автофильтр по фактическому числу строк (заголовок + данные)
        ws.auto_filter.ref = f"A1:E{max(ws.max_row, 2)}"

        today = datetime.date.today().strftime("%Y-%m-%d")
        filename = f"forum_posts_{today}.xlsx"

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument."
                         "spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response


# ---------------------------------------------------------------------------
# Статистика форума (только для администратора) — диаграммы на странице
# «Статистика» в выпадающем меню профиля.
# ---------------------------------------------------------------------------
class ForumStatsView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        days = min(max(int(request.query_params.get("days", 14) or 14), 1), 90)

        topics_total = Topic.objects.count()
        posts_total = Post.objects.count()
        users_total = request.user.__class__.objects.count()

        top_topics = (
            Topic.objects.annotate(posts_count=Count("posts"))
            .order_by("-posts_count", "-created_at")[:10]
            .values("id", "title", "posts_count")
        )

        top_authors = (
            Post.objects.select_related("owner")
            .annotate(posts_count=Count("id"))
            .order_by("-posts_count")[:10]
            .values("owner__username", "posts_count")
        )

        categories = (
            Category.objects.annotate(
                topics_count=Count("topics", distinct=True),
                posts_count=Count("topics__posts", distinct=True),
            )
            .order_by("-topics_count")
            .values("id", "name", "topics_count", "posts_count")
        )

        since = datetime.datetime.now(
            datetime.timezone.utc
        ) - datetime.timedelta(days=days)
        activity_raw = (
            Post.objects.filter(created_at__gte=since)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        counts = {str(a["day"]): a["count"] for a in activity_raw if a["day"]}
        activity = []
        today = datetime.date.today()
        for i in range(days - 1, -1, -1):
            d = (today - datetime.timedelta(days=i)).isoformat()
            activity.append({"date": d, "count": counts.get(d, 0)})

        return Response({
            "totals": {
                "topics": topics_total,
                "posts": posts_total,
                "users": users_total,
                "categories": Category.objects.count(),
            },
            "top_topics": list(top_topics),
            "top_authors": [
                {"username": a["owner__username"], "count": a["posts_count"]}
                for a in top_authors
            ],
            "categories": list(categories),
            "activity": activity,
        })


# ---------------------------------------------------------------------------
# Notifications (упоминания @username)
# ---------------------------------------------------------------------------
class NotificationSerializer(serializers.Serializer):
    """Сериализатор уведомления об упоминании."""

    id = serializers.IntegerField()
    post_id = serializers.IntegerField(source="post.id")
    text = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source="post.created_at")
    read_at = serializers.DateTimeField(allow_null=True)
    from_user = serializers.SerializerMethodField()
    topic_id = serializers.IntegerField(source="post.topic_id")
    topic_title = serializers.CharField(source="post.topic.title", max_length=120)
    category_id = serializers.IntegerField(source="post.topic.category_id")
    category_name = serializers.CharField(source="post.topic.category.name", max_length=100)

    def get_text(self, obj):
        """Текст уведомления.

        Если уведомление создано из-за жалобы (на посте есть жалоба от ДРУГОГО
        пользователя) — показываем понятный текст о жалобе вместо сырого текста
        поста; иначе — обычный текст поста (упоминание @username)."""
        report = obj.post.reports.exclude(user=obj.user).order_by(
            "-created_at").first()
        if report is not None:
            reason = dict(PostReport.Reason.choices).get(
                report.reason, report.reason)
            return (f"Пользователь {report.user.username} пожаловался "
                    f"({reason}) на это сообщение.")
        return obj.post.text

    def get_from_user(self, obj):
        return {"id": obj.post.owner_id, "username": obj.post.owner.username}


def _mention_qs(user):
    return (
        UserMention.objects.filter(user=user)
        .select_related("post__owner", "post__topic__category", "user")
        .prefetch_related("post__reports__user")
        .order_by("-created_at", "-id")
    )


class NotificationListView(APIView):
    """GET /api/notifications?page=N — список уведомлений (с пагинацией).
    GET /api/notifications?unread=1&limit=5 — только непрочитанные (для тостов)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _mention_qs(request.user)
        # unread=1|true — только непрочитанные; пустое значение (unread=) — все
        unread = request.query_params.get("unread")
        if unread and unread.lower() not in ("0", "false"):
            qs = qs.filter(read_at__isnull=True)
        paginator = ForumPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                NotificationSerializer(page, many=True).data
            )
        return Response(NotificationSerializer(qs, many=True).data)


class NotificationUnreadCountView(APIView):
    """GET /api/notifications/count — количество непрочитанных."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"count": _mention_qs(request.user).filter(
            read_at__isnull=True).count()})


class NotificationMarkReadView(APIView):
    """POST /api/notifications/read — отметить прочитанными.

    Тело: {} — все; {"ids": [1,2]} — выборочно (используется всплывающими
    тостами справа снизу, чтобы не помечать всё сразу)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = (request.data or {}).get("ids")
        now = datetime.datetime.now(datetime.timezone.utc)
        qs = UserMention.objects.filter(user=request.user, read_at__isnull=True)
        if isinstance(ids, list) and ids:
            try:
                ids = [int(i) for i in ids]
            except (TypeError, ValueError):
                return Response({"errors": {"ids": "Некорректный формат"}},
                                status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(id__in=ids)
        updated = qs.update(read_at=now)
        return Response({"updated": updated})


# ---------------------------------------------------------------------------
# Post reports (жалобы на сообщения) + модерация (только админ)
# ---------------------------------------------------------------------------
class ReportCreateView(APIView):
    """POST /api/posts/<post_id>/report/ — создать жалобу на чужой пост."""

    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        post = Post.objects.filter(pk=post_id).first()
        if post is None:
            raise NotFound("Сообщение не найдено")
        data = dict(request.data or {})
        # Идентификатор поста берём из URL; поле post в теле игнорируется.
        data["post"] = post.pk
        serializer = PostReportCreateSerializer(
            data=data, context={"request": request},
        )
        if not serializer.is_valid():
            errs = {f: (v[0] if isinstance(v, list) else v)
                    for f, v in serializer.errors.items()}
            return Response({"errors": errs},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                report = serializer.save(user=request.user)
                # Уведомляем ВСЕХ активных админов о новой жалобе через
                # существующую систему (UserMention → колокольчик в хедере).
                print(f"Report created: user={request.user.username}, "
                      f"post={report.post.id}")
                notify_admins_about_report(report.post, request.user)
        except IntegrityError:
            # Гонка: два параллельных запроса жалобы от одного пользователя.
            return Response(
                {"errors": {"post": "Вы уже жаловались на это сообщение"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Жалоба отправлена"},
                        status=status.HTTP_201_CREATED)


class UserReportStatusView(APIView):
    """GET /api/posts/<post_id>/my-reports/ — жаловался ли текущий юзер на пост."""

    permission_classes = [IsAuthenticated]

    def get(self, request, post_id):
        has_reported = PostReport.objects.filter(
            user=request.user,
            post_id=post_id,
        ).exists()
        return Response({"has_reported": has_reported})


class ReportListView(APIView):
    """GET /api/reports/?status=pending — список жалоб (админ)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        qs = PostReport.objects.select_related(
            "user", "post__owner", "post__topic",
        ).all()
        status_filter = request.query_params.get("status")
        if status_filter:
            if status_filter not in PostReport.Status.values:
                return Response(
                    {"errors": {"status": "Неизвестный статус"}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_filter)
        return Response(PostReportSerializer(qs, many=True).data)


class ReportActionView(APIView):
    """POST /api/reports/<pk>/action/ — resolve (скрыть пост) / dismiss."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        report = PostReport.objects.filter(pk=pk).first()
        if report is None:
            raise NotFound("Жалоба не найдена")
        action = (request.data or {}).get("action")
        if action == "resolve":
            report.status = PostReport.Status.RESOLVED
            report.post.is_hidden = True
            report.post.save(update_fields=["is_hidden"])
        elif action == "dismiss":
            report.status = PostReport.Status.DISMISSED
        else:
            return Response({"error": "Неизвестное действие"},
                            status=status.HTTP_400_BAD_REQUEST)
        report.save(update_fields=["status"])
        return Response(PostReportSerializer(report).data)


class PendingReportsCountView(APIView):
    """GET /api/reports/pending-count/ — число жалоб на рассмотрении."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        count = PostReport.objects.filter(
            status=PostReport.Status.PENDING,
        ).count()
        return Response({"count": count})
