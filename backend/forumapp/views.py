"""Views for the Forum API."""
import datetime
import os
import re

from django.db.models import CharField, Count, Exists, Lookup, OuterRef, Q, TextField
from django.db.models.functions import TruncDate
from django.db.utils import OperationalError, ProgrammingError
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
from .models import Category, Post, Topic, UserMention
from .notifications import notify_mentions
from .pagination import ForumPagination
from .permissions import IsAdmin, OwnerOrAdminDelete, OwnerOnlyEdit
from .serializers import (
    CategoryNameConflict,
    CategorySerializer,
    PostPatchSerializer,
    PostSerializer,
    TopicPatchSerializer,
    TopicSerializer,
)


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

        from datetime import timedelta

        from rest_framework_simplejwt.tokens import RefreshToken
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        response = Response({"user": MeSerializer(user).data})
        secure = os.environ.get("DJANGO_SECURE_COOKIES", "0") == "1"
        # access — httpOnly кука на весь сайт; JS её не видит (защита от XSS)
        response.set_cookie(
            "forum_access", access,
            max_age=int(timedelta(hours=24).total_seconds()),
            httponly=True, samesite="Lax", secure=secure, path="/",
        )
        # refresh — только для эндпоинта logout
        response.set_cookie(
            "forum_refresh", str(refresh),
            max_age=int(timedelta(days=7).total_seconds()),
            httponly=True, samesite="Lax", secure=secure,
            path="/",
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
        if not refresh_token:
            # даже без токена чистим куки — сессия всё равно завершается
            response.delete_cookie("forum_access", path="/")
            response.delete_cookie("forum_refresh", path="/")
            return response
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()  # добавляет jti в blacklist
        except Exception:
            response.delete_cookie("forum_access", path="/")
            response.delete_cookie("forum_refresh", path="/")
            return response
        response.delete_cookie("forum_access", path="/")
        response.delete_cookie("forum_refresh", path="/")
        return response


class RefreshView(APIView):
    """Обновление access-куки по refresh-куке (для фронтенда после истечения 24ч)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        from datetime import timedelta

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
            response.delete_cookie("forum_refresh", path="/")
            return response

        secure = os.environ.get("DJANGO_SECURE_COOKIES", "0") == "1"
        response = Response({"user": MeSerializer(user).data})
        response.set_cookie(
            "forum_access", str(new.access_token),
            max_age=int(timedelta(hours=24).total_seconds()),
            httponly=True, samesite="Lax", secure=secure, path="/",
        )
        response.set_cookie(
            "forum_refresh", str(new),
            max_age=int(timedelta(days=7).total_seconds()),
            httponly=True, samesite="Lax", secure=secure,
            path="/",
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
        search = request.query_params.get("search")
        if search:
            # все слова запроса должны присутствовать в тексте сообщения
            qs = qs.filter(_build_search_q(search, ["text"]))
        # Новые сообщения сверху (страница 1 = самые свежие), внутри страницы
        # — по возрастанию времени, чтобы чтение было сверху вниз.
        qs = qs.order_by("-created_at", "-id")
        paginator = ForumPagination()
        page = paginator.paginate_queryset(qs, request)
        items = list(reversed(page))
        return paginator.get_paginated_response(
            PostSerializer(items, many=True).data
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
        notify_mentions(obj)
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


def _topics_with_all_words_in_posts(words):
    """id тем, в СООБЩЕНИЯХ которых встречаются все слова запроса.

    Сначала SQL-фильтр по первому (обычно самому редкому) слову — он
    отсекает большинство сообщений; затем пересечение topic_id по остальным
    словам (покрывает и случай «все слова в одном сообщении», и случай
    «слова в разных сообщениях одной темы»)."""
    ids = set(Post.objects.filter(_contains_q("text", words[0]))
              .values_list("topic_id", flat=True))
    for w in words[1:]:
        if not ids:
            break
        ids &= set(Post.objects.filter(Q(topic_id__in=ids) & _contains_q("text", w))
                   .values_list("topic_id", flat=True))
    return list(ids)


def _build_search_q_topic(query):
    """Поиск тем: все слова запроса должны встречаться либо в названии темы,
    либо в текстах сообщений одной и той же темы.

    ВАЖНО: условие по posts__text оборачивается в подзапрос Exists, а не
    используется как JOIN-условие в основном queryset — иначе .distinct()
    на уровне SQL не схлопывает строки (разные joined-строки различаются),
    и пагинация теряет нужную тему.
    """
    words = _search_words(query)
    if not words:
        return Q(Exists(
            Post.objects.filter(topic=OuterRef("pk")).filter(_contains_q("text", query))
        ))
    title_q = Q()
    for w in words:
        title_q &= _contains_q("title", w)
    # одна тема должна содержать ВСЕ слова в своих сообщениях
    posts_all = Q(Exists(
        Post.objects.filter(topic=OuterRef("pk")).filter(_contains_q("text", words[0]))
    ))
    for w in words[1:]:
        posts_all &= Q(Exists(
            Post.objects.filter(topic=OuterRef("pk")).filter(_contains_q("text", w))
        ))
    return title_q | posts_all


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
            qs = qs.filter(owner=user)
        topic = request.query_params.get("topic")
        if topic:
            qs = qs.filter(topic_id=topic)
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(_build_search_q(search, ["text"]))
        qs = qs.order_by("created_at", "id")

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
    text = serializers.CharField(source="post.text", max_length=2000)
    created_at = serializers.DateTimeField(source="post.created_at")
    read_at = serializers.DateTimeField(allow_null=True)
    from_user = serializers.SerializerMethodField()
    topic_id = serializers.IntegerField(source="post.topic_id")
    topic_title = serializers.CharField(source="post.topic.title", max_length=120)
    category_id = serializers.IntegerField(source="post.topic.category_id")
    category_name = serializers.CharField(source="post.topic.category.name", max_length=100)

    def get_from_user(self, obj):
        return {"id": obj.post.owner_id, "username": obj.post.owner.username}


def _mention_qs(user):
    return (
        UserMention.objects.filter(user=user)
        .select_related("post__owner", "post__topic__category")
        .order_by("-created_at", "-id")
    )


class NotificationListView(APIView):
    """GET /api/notifications?page=N — список уведомлений (с пагинацией).
    GET /api/notifications?unread=1&limit=5 — только непрочитанные (для тостов)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _mention_qs(request.user)
        if request.query_params.get("unread"):
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
