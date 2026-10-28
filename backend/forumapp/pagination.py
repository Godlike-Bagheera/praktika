from collections import OrderedDict

from django.core.paginator import Paginator
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ClampingPaginator(Paginator):
    """Пагинатор, который «прижимает» слишком большой номер страницы к
    последней существующей вместо выбрасывания EmptyPage (404)."""

    def page(self, number):
        try:
            number = self.validate_number(number)
        except Exception:
            # некорректный/слишком большой номер -> последняя страница
            number = self.num_pages if self.num_pages else 1
        return self._get_page(number, self)


class ForumPagination(PageNumberPagination):
    """Пагинация: по 20 записей на страницу (limit по умолчанию 20)."""

    page_size = 20
    page_size_query_param = "limit"
    max_page_size = 100
    page_query_param = "page"
    paginator_class = ClampingPaginator

    def paginate_queryset(self, queryset, request, view=None):
        """DRF по умолчанию отдаёт 404 при OutOfRange. Мы делаем мягкое
        поведение: page > num_pages -> последняя страница; нечисловой page
        или page < 1 -> первая страница."""
        self.request = request
        page_size = self.get_page_size(request)
        if not page_size:
            return None
        paginator = self.django_paginator_class(queryset, page_size)
        raw = request.query_params.get(self.page_query_param)
        try:
            page_number = int(raw)
        except (TypeError, ValueError):
            page_number = 1
        if page_number < 1:
            page_number = 1
        try:
            self.page = paginator.page(page_number)
        except Exception:
            self.page = paginator.page(paginator.num_pages)
        return list(self.page)

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ("count", self.page.paginator.count),
            ("pages", self.page.paginator.num_pages),
            ("page", self.page.number),
            ("limit", self.get_page_size(self.request)),
            ("next", self.get_next_link()),
            ("previous", self.get_previous_link()),
            ("results", data),
        ]))
