from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """?page=N&page_size=M (по умолчанию 25, максимум 100)."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
