from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from forumapp.models import Category, Topic, Post

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
