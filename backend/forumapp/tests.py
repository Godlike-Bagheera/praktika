from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from forumapp.models import Category, Topic, Post
from forumapp.serializers import CategorySerializer

User = get_user_model()

class ApiTests(TestCase):
    def setUp(self):
        self.c = Client()
        self.admin = User.objects.create_user(email="a@a.com", username="admin1", password="Zx9Kp7mQ2wLtr4!v", role="admin")
        self.u1 = User.objects.create_user(email="u1@u.com", username="user1", password="Zx9Kp7mQ2wLtr4!v")
        self.u2 = User.objects.create_user(email="u2@u.com", username="user2", password="Zx9Kp7mQ2wLtr4!v")
        self.cat = Category.objects.create(name="Общий")
        self.topic = Topic.objects.create(category=self.cat, owner=self.u1, title="Тест темы")
        self.post = Post.objects.create(topic=self.topic, owner=self.u1, text="Ок текст")

    def login(self, u):
        # rate-limit входа: 10 попыток в минуту на IP — чистим бакет перед логином
        from django.core.cache import cache
        cache.clear()
        r = self.c.post("/api/auth/login", data={"email": u.email, "password": "Zx9Kp7mQ2wLtr4!v"}, content_type="application/json")
        assert r.status_code == 200, r.content
        # JWT передаётся в httpOnly-куке; для тестового клиента подставляем заголовок
        return {"HTTP_AUTHORIZATION": "Bearer " + r.cookies["forum_access"].value}

    def test_guest_401(self):
        self.assertEqual(self.c.get("/api/categories").status_code, 401)
        self.assertEqual(self.c.get("/health").status_code, 200)

    def test_register_login_flow(self):
        r = self.c.post("/api/auth/register", data={"email":"n@n.com","username":"newuser","password":"Zx9Kp7mQ2wLtr4!v","password_confirm":"Zx9Kp7mQ2wLtr4!v"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        r2 = self.c.post("/api/auth/register", data={"email":"N@N.COM","username":"newuser2","password":"Zx9Kp7mQ2wLtr4!v","password_confirm":"Zx9Kp7mQ2wLtr4!v"}, content_type="application/json")
        self.assertEqual(r2.status_code, 409)

    def test_bad_login_message(self):
        r = self.c.post("/api/auth/login", data={"email":"u1@u.com","password":"wrong"}, content_type="application/json")
        self.assertEqual(r.status_code, 401)

    def test_permissions(self):
        h = self.login(self.u2)
        self.assertEqual(self.c.put(f"/api/posts/{self.post.id}", data={"text":"новый ок"}, content_type="application/json", **h).status_code, 403)
        self.assertEqual(self.c.delete(f"/api/topics/{self.topic.id}", **h).status_code, 403)
        a = self.login(self.admin)
        self.assertEqual(self.c.post("/api/categories", data={"name":"Новая"}, content_type="application/json", **a).status_code, 201)
        self.assertEqual(self.c.delete(f"/api/posts/{self.post.id}", **a).status_code, 204)

    def test_profanity_blocked(self):
        h = self.login(self.u1)
        r = self.c.post(f"/api/topics/{self.topic.id}/posts", data={"text":"ты хуй"}, content_type="application/json", **h)
        self.assertEqual(r.status_code, 400)
        r2 = self.c.post(f"/api/topics/{self.topic.id}/posts", data={"text":"ты huy"}, content_type="application/json", **h)
        self.assertEqual(r2.status_code, 400)
        r3 = self.c.post(f"/api/topics/{self.topic.id}/posts", data={"text":"нормальное сообщение"}, content_type="application/json", **h)
        self.assertEqual(r3.status_code, 201)

    def test_profanity_dolbaeb_forms(self):
        from forumapp.profanity import contains_profanity
        # все формы и обфускации мат-корня «долбаеб» блокируются
        for w in ["долбаеб", "долбоеб", "долбоёб", "долбаёб", "задолбоеб",
                  "долбоебы", "долбаебов", "долбаёбом", "долбоебу",
                  "дол@ба@еб", "д.о.л.б.а.е.б", "дол6а3аб",
                  "долбящий", "долбля", "долбаный", "долбануть"]:
            self.assertTrue(contains_profanity(w, strict=True), f"пропуск: {w}")
        # транслит (в т.ч. верхний регистр и в составе предложения)
        for w in ["dolboyob", "DOLBOYOB", "dolbyoby", "dolbaeb", "dolboeb",
                  "some dolboyob here", "Ты долбоебы все"]:
            self.assertTrue(contains_profanity(w, strict=True), f"пропуск: {w}")
        # легальные слова не блокируются
        for w in ["долбить", "долблю", "долбит", "долбят", "долбил",
                  "наддолбите", "поддолбя", "обдолбятся", "задолбался",
                  "долблёнка", "долбление", "долдон", "доллар", "долото",
                  "долбоебыч", "dollywood", "doll", "dobby", "dolby",
                  "nobody", "lobby", "dolphin", "goldberg", "balboa"]:
            self.assertFalse(contains_profanity(w, strict=True), f"ложное срабатывание: {w}")

    def test_pagination_20(self):
        h = self.login(self.u1)
        for i in range(25):
            Post.objects.create(topic=self.topic, owner=self.u1, text=f"post {i}")
        r = self.c.get(f"/api/topics/{self.topic.id}/posts", **h)
        self.assertEqual(len(r.json()["results"]), 20)

    def test_superuser_gets_admin_role(self):
        # createsuperuser ставит только is_superuser; save() должен проставить role=admin
        su = User.objects.create_superuser(email="su@su.com", username="super1", password="Zx9Kp7mQ2wLtr4!v")
        su.refresh_from_db()
        self.assertEqual(su.role, User.Role.ADMIN)
        self.assertTrue(su.is_admin_role)

    def test_formula_protection_lstrip(self):
        # значения с ведущими пробелами тоже должны экранироваться
        from forumapp.views import _clean_formula
        self.assertEqual(_clean_formula("   =1+1"), "'   =1+1")
        self.assertEqual(_clean_formula("\t@SUM(A1)"), "'\t@SUM(A1)")
        self.assertEqual(_clean_formula("обычный текст"), "обычный текст")

    def test_refresh_flow(self):
        # вход -> куки access+refresh; имитируем истечение access (удаляем заголовок),
        # refresh-кука остаётся -> /auth/refresh выдаёт новую access-куку
        r = self.c.post("/api/auth/login", data={"email": self.u1.email, "password": "Zx9Kp7mQ2wLtr4!v"}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("forum_refresh", r.cookies)
        # Django Client хранит куки между запросами: без access-заголовка запросы
        # идут с куками (middleware подставит access из куки) — сначала убедимся, что me работает
        r_me = self.c.get("/api/auth/me")
        self.assertEqual(r_me.status_code, 200)
        # теперь «протухший» access: чистим куку access у клиента
        self.c.cookies.pop("forum_access", None)
        r_401 = self.c.get("/api/categories")
        self.assertEqual(r_401.status_code, 401)
        r_ref = self.c.post("/api/auth/refresh", data={}, content_type="application/json")
        self.assertEqual(r_ref.status_code, 200, r_ref.content)
        self.assertIn("forum_access", r_ref.cookies)
        # после ротации старый refresh заблокирован — повторный refresh тем же токеном не пройдёт.
        # Отдельный client БЕЗ куки-джара: иначе view возьмёт новый (неротированный) refresh из куки.
        from django.test import Client as _Client
        old_refresh = r.cookies["forum_refresh"].value
        r_bad = _Client().post("/api/auth/refresh", data={"refresh": old_refresh}, content_type="application/json")
        self.assertEqual(r_bad.status_code, 401)

    def test_search_icontains_partial(self):
        h = self.login(self.u1)
        Topic.objects.create(category=self.cat, owner=self.u1, title="Программа для VirtualBox")
        r = self.c.get("/api/topics?category=%s&search=virtual" % self.cat.id, **h)
        titles = [t["title"] for t in r.json()["results"]]
        self.assertIn("Программа для VirtualBox", titles)
        rp = self.c.get(f"/api/topics/{self.topic.id}/posts?search=Ок тек", **h)
        self.assertEqual(len(rp.json()["results"]), 1)

    def test_category_unique_iexact(self):
        a = self.login(self.admin)
        Category.objects.create(name="Новости")
        r = self.c.post("/api/categories", data={"name": "новости"}, content_type="application/json", **a)
        self.assertEqual(r.status_code, 400)

    def test_export_ok_and_rows_match_list(self):
        h = self.login(self.u1)
        r = self.c.get("/api/posts/export?topic=%s" % self.topic.id, **h)
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
        # список тех же постов
        rl = self.c.get(f"/api/topics/{self.topic.id}/posts?limit=10000", **h)
        n_visible = rl.json()["count"]
        import io
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(r.content))
        ws = wb.active
        self.assertEqual(ws.max_row - 1, n_visible)
        self.assertEqual(ws.freeze_panes, "A2")
        self.assertIsNotNone(ws.auto_filter.ref)

    def test_categories_pagination(self):
        # логин до создания категорий: rate-limit входа — 10 попыток в минуту на IP
        h = self.login(self.u1)
        # без page/limit — обратная совместимость: плоский список
        r0 = self.c.get("/api/categories", **h)
        self.assertEqual(r0.status_code, 200)
        self.assertIsInstance(r0.json(), list)
        for i in range(6):
            Category.objects.create(name=f"Категория {i}")
        total = Category.objects.count()  # 7 (Общий + 6 новых)
        r = self.c.get("/api/categories?page=1&limit=3", **h)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("results", data)
        self.assertEqual(data["count"], total)
        self.assertEqual(len(data["results"]), 3)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["pages"], (total + 2) // 3)
        # topics_count в карточке категории
        self.assertTrue(all("topics_count" in c for c in data["results"]))
        # вторая страница отличается от первой
        r2 = self.c.get("/api/categories?page=2&limit=3", **h)
        ids1 = [c["id"] for c in data["results"]]
        ids2 = [c["id"] for c in r2.json()["results"]]
        self.assertFalse(set(ids1) & set(ids2))
        # поиск по категориям + пагинация (6 созданных «Категория i»)
        rs = self.c.get("/api/categories?limit=3&search=%D0%9A%D0%B0%D1%82%D0%B5%D0%B3%D0%BE%D1%80%D0%B8%D1%8F", **h)
        ds = rs.json()
        self.assertEqual(ds["count"], 6)
        self.assertEqual(len(ds["results"]), 3)
        # выход за последнюю страницу -> 404
        r_bad = self.c.get("/api/categories?page=99&limit=3", **h)
        self.assertEqual(r_bad.status_code, 404)

    def test_topics_pagination_page(self):
        # логин первым: rate-limit входа — 10 попыток в минуту на IP
        h = self.login(self.u1)
        for i in range(25):
            Topic.objects.create(category=self.cat, owner=self.u1, title=f"Тема {i}")
        r = self.c.get(f"/api/topics?category={self.cat.id}&page=1", **h)
        data = r.json()
        self.assertEqual(data["count"], 26)  # 25 новых + исходная
        self.assertEqual(len(data["results"]), 20)
        self.assertEqual(data["pages"], 2)
        r2 = self.c.get(f"/api/topics?category={self.cat.id}&page=2", **h)
        self.assertEqual(len(r2.json()["results"]), 6)

    def test_search_multiword_posts(self):
        # «хороший» поиск по сообщениям: все слова запроса должны
        # встречаться в тексте (в любом регистре, частичное совпадение)
        h = self.login(self.u1)
        t2 = Topic.objects.create(category=self.cat, owner=self.u1, title="Вторая тема")
        Post.objects.create(topic=t2, owner=self.u1, text="Привет Мир всем")
        Post.objects.create(topic=t2, owner=self.u1, text="приветствие без второго слова")
        # два слова — только первое сообщение
        r = self.c.get(f"/api/topics/{t2.id}/posts?search=приве мир", **h)
        results = r.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertIn("Привет Мир", results[0]["text"])
        # порядок слов не важен
        r = self.c.get(f"/api/topics/{t2.id}/posts?search=мир%20ПРИВЕ", **h)
        self.assertEqual(len(r.json()["results"]), 1)
        # несуществующее слово — пусто
        r = self.c.get(f"/api/topics/{t2.id}/posts?search=приве несуществует", **h)
        self.assertEqual(r.json()["count"], 0)

    def test_search_topics_by_title_or_posts(self):
        # поиск тем ищет и в названии, и в текстах сообщений темы
        h = self.login(self.u1)
        t2 = Topic.objects.create(category=self.cat, owner=self.u1, title="Отчёт за квартал")
        Post.objects.create(topic=t2, owner=self.u1, text="данные по выручке собраны")
        # по названию
        r = self.c.get(f"/api/topics?category={self.cat.id}&search=отчё", **h)
        titles = [t["title"] for t in r.json()["results"]]
        self.assertIn("Отчёт за квартал", titles)
        # по тексту сообщения (в названии слова нет)
        r = self.c.get(f"/api/topics?category={self.cat.id}&search=выручк", **h)
        titles = [t["title"] for t in r.json()["results"]]
        self.assertIn("Отчёт за квартал", titles)
        # несколько слов: оба встречаются в ТЕКСТЕ одной темы — тема находится
        Post.objects.create(topic=t2, owner=self.u1, text="собрали квартальные выгрузки")
        r = self.c.get(f"/api/topics?category={self.cat.id}&search=кварт%20выручк", **h)
        self.assertEqual(r.json()["count"], 1)
        # слова из РАЗНЫХ тем не должны складываться
        r = self.c.get(f"/api/topics?category={self.cat.id}&search=Тест%20выручк", **h)
        self.assertEqual(r.json()["count"], 0)
        # distinct: тема с двумя подходящими сообщениями возвращается один раз
        Post.objects.create(topic=t2, owner=self.u1, text="ещё немного про выручку")
        r = self.c.get(f"/api/topics?category={self.cat.id}&search=выручк", **h)
        ids = [t["id"] for t in r.json()["results"]]
        self.assertEqual(ids.count(t2.id), 1)

    def test_categories_search_pagination_words(self):
        h = self.login(self.u1)
        Category.objects.create(name="Новости технологий")
        Category.objects.create(name="Новости рынка")
        Category.objects.create(name="Спорт")
        r = self.c.get("/api/categories?page=1&limit=2&search=новости", **h)
        data = r.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["results"]), 2)
        # два слова — только «Новости технологий»/«Новости рынка» содержат оба
        r = self.c.get("/api/categories?page=1&limit=5&search=%D0%BD%D0%BE%D0%B2%D0%BE%D1%81%D1%82%D0%B8%20%D1%82%D0%B5%D1%85", **h)
        self.assertEqual(r.json()["count"], 1)


    # ---- Edge-case пагинации: page/limit из URL недоверенные ----
    def test_pagination_edge_cases(self):
        h = self.login(self.u1)
        for i in range(3):
            Topic.objects.create(category=self.cat, owner=self.u1, title=f"T{i}")
        base = f"/api/topics?category={self.cat.id}"
        # page=0 и page=-1 не должны давать 500 (EmptyPage)
        r = self.c.get(base + "&page=0", **h)
        self.assertIn(r.status_code, (200, 404), r.content)
        r = self.c.get(base + "&page=-1", **h)
        self.assertIn(r.status_code, (200, 404), r.content)
        # заведомо несуществующая страница — не 500
        r = self.c.get(base + "&page=999999", **h)
        self.assertIn(r.status_code, (200, 404), r.content)
        # мусор вместо числа — не 500
        r = self.c.get(base + "&page=abc", **h)
        self.assertIn(r.status_code, (200, 404), r.content)
        # limit больше max_page_size(100) должен ограничиваться, а не пробрасываться
        r = self.c.get(base + "&limit=100000", **h)
        self.assertEqual(r.status_code, 200)
        self.assertLessEqual(r.json()["limit"], 100)
        # отрицательный/нулевой limit — не 500
        r = self.c.get(base + "&limit=-5", **h)
        self.assertIn(r.status_code, (200, 404), r.content)
        # то же для категорий и сообщений
        r = self.c.get("/api/categories?page=0&limit=3", **h)
        self.assertIn(r.status_code, (200, 404), r.content)
        r = self.c.get(f"/api/posts?topic={self.topic.id}&page=999999", **h)
        self.assertIn(r.status_code, (200, 404), r.content)

    # ---- Rate limiting ----
    def test_login_rate_limit(self):
        from django.core.cache import cache
        cache.clear()
        # лимит: 10 неуспешных попыток на IP в минуту
        for _ in range(10):
            self.c.post("/api/auth/login", data={"email": "u1@u.com", "password": "bad"}, content_type="application/json")
        r = self.c.post("/api/auth/login", data={"email": "u1@u.com", "password": "Zx9Kp7mQ2wLtr4!v"}, content_type="application/json")
        self.assertEqual(r.status_code, 429)

    # ---- Поведение при протухшем/битом refresh-токене ----
    def test_refresh_invalid_or_expired(self):
        # без куки
        r = self.c.post("/api/auth/refresh", content_type="application/json")
        self.assertEqual(r.status_code, 401)
        # битый токен
        self.c.cookies["forum_refresh"] = "not.a.jwt"
        r = self.c.post("/api/auth/refresh", content_type="application/json")
        self.assertEqual(r.status_code, 401)
        # кука должна быть очищена (пустое значение), а не содержать токен
        self.assertEqual(self.c.cookies.get("forum_access").value if "forum_access" in self.c.cookies else "", "")
        # корректный флоу: вход -> refresh выдаёт новый access
        h = self.login(self.u1)
        r = self.c.post("/api/auth/refresh", content_type="application/json")
        self.assertEqual(r.status_code, 200)
        new_token = self.c.cookies["forum_access"].value
        r2 = self.c.get("/api/categories?page=1", HTTP_AUTHORIZATION="Bearer " + new_token)
        self.assertEqual(r2.status_code, 200)

    # ---- Загрузка файлов отсутствует по дизайну (аватар = gravatar-хэш из сессии) ----
    def test_no_upload_endpoints(self):
        h = self.login(self.u1)
        for path in ("/api/upload", "/api/avatar", "/api/users/me/avatar"):
            r = self.c.post(path, data={}, content_type="multipart/form-data", **h)
            self.assertIn(r.status_code, (404, 405), path)

    def test_category_race_returns_409_not_500(self):
        """Гонка создания одноимённых категорий: проигравший получает 409.

        Симулируем состояние «проверка iexact прошла, но параллельный запрос
        уже вставил категорию»: unique-индекс name_lower даёт IntegrityError.
        Раньше это превращалось в нечитаемый 500; теперь — 409 Conflict.
        """
        from unittest import mock
        from django.db import IntegrityError
        from forumapp.models import Category as _Cat

        h = self.login(self.admin)
        _Cat.objects.create(name="Гонка")

        # Как при настоящей гонке: на момент validate_name конкурента «нет»,
        # а INSERT падает по unique-индексу name_lower. Патчим сам метод
        # валидации, не трогая другие запросы (счёт/рендер идут как обычно).
        orig_validate = CategorySerializer.validate_name

        def fake_validate(self_, value):
            return orig_validate(self_, "Уникальное имя без конкурента №1")

        conflict = IntegrityError(
            'duplicate key value violates unique constraint '
            '"forumapp_category_name_lower_key"'
        )
        with mock.patch.object(_Cat, "save", side_effect=conflict), \
             mock.patch.object(CategorySerializer, "validate_name", fake_validate):
            r = self.c.post("/api/categories", data={"name": "гонка"},
                            content_type="application/json", **h)
        self.assertEqual(r.status_code, 409)
        self.assertIn("name", r.json()["errors"])
        self.assertEqual(_Cat.objects.filter(name__iexact="гонка").count(), 1)

    def test_category_other_integrity_error_not_swallowed(self):
        """IntegrityError НЕ про name_lower пробрасывается (не маскируется под 409/400)."""
        from django.db import IntegrityError
        from unittest import mock
        from forumapp.serializers import CategoryNameConflict, CategorySerializer

        with mock.patch(
            "forumapp.serializers.transaction.atomic",
            side_effect=IntegrityError("violates not-null constraint \"owner_id\""),
        ):
            s = CategorySerializer(data={"name": "Что-то"})
            self.assertTrue(s.is_valid())
            with self.assertRaises(IntegrityError):
                s.save()
        # а «наш» конфликт — отдельный класс исключения
        with mock.patch(
            "forumapp.serializers.transaction.atomic",
            side_effect=IntegrityError('duplicate key value violates unique constraint "forumapp_category_name_lower_key"'),
        ):
            s = CategorySerializer(data={"name": "Чоуто"})
            self.assertTrue(s.is_valid())
            with self.assertRaises(CategoryNameConflict):
                s.save()
class SearchPaginationPageTest(TestCase):
    """Регрессия: при комбинированном фильтре ?search=X&page=N номер страницы
    должен сохраняться (не теряться и не сбрасываться на 1)."""

    def setUp(self):
        self.c = Client()
        from django.core.cache import cache
        cache.clear()
        self.u1 = User.objects.create_user(email="sp@u.com", username="spuser",
                                           password="Zx9Kp7mQ2wLtr4!v")
        r = self.c.post("/api/auth/login",
                        data={"email": "sp@u.com", "password": "Zx9Kp7mQ2wLtr4!v"},
                        content_type="application/json")
        assert r.status_code == 200, r.content
        self.h = {"HTTP_AUTHORIZATION": "Bearer " + r.cookies["forum_access"].value}
        self.cat = Category.objects.create(name="Тестовая")
        # 25 тем с общим словом в названии -> 2 страницы по 20
        for i in range(25):
            Topic.objects.create(title=f"Флуд тема {i}", category=self.cat,
                                 owner=self.u1)
        t = Topic.objects.create(title="Отдельная", category=self.cat,
                                 owner=self.u1)
        for i in range(25):
            Post.objects.create(topic=t, owner=self.u1,
                                text=f"упоминание keyword-{i}")
        self.topic_with_posts = t

    def test_topics_search_keeps_page(self):
        r = self.c.get(f"/api/topics?category={self.cat.id}&search=Флуд&page=2&limit=20", **self.h)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(body["page"], 2)
        self.assertEqual(len(body["results"]), 5)

    def test_posts_search_keeps_page(self):
        r = self.c.get(f"/api/topics/{self.topic_with_posts.id}/posts?search=упоминание&page=2", **self.h)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["page"], 2)

    def test_categories_search_keeps_page(self):
        for i in range(13):
            Category.objects.create(name=f"Категория {i}")
        r = self.c.get("/api/categories?search=Категория&page=2&limit=12", **self.h)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["page"], 2)
