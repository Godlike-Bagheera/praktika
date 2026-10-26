from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ForumPagination(PageNumberPagination):
    """Пагинация: по 20 записей на страницу (limit по умолчанию 20)."""

    page_size = 20
    page_size_query_param = "limit"
    max_page_size = 100
    page_query_param = "page"

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
