"""Middleware: JWT из httpOnly-кук.

Токены передаются в httpOnly-куках (frontend не видит их из JS).
DRF-simplejwt умеет читать токен только из заголовка Authorization,
поэтому middleware достаёт access-токен из куки и подставляет его
в META как HTTP_AUTHORIZATION. Заголовок в запросе имеет приоритет
(для тестов/CLI можно передавать Bearer вручную).
"""


class JwtCookieAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.META.get("HTTP_AUTHORIZATION"):
            token = request.COOKIES.get("forum_access")
            if token:
                request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.get_response(request)
