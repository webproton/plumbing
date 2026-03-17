# from urllib import response
from rest_framework.response import Response
from rest_framework import pagination

class CustomPagination(pagination.PageNumberPagination):
    """dont use mb"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'p'

    
    def get_paginated_response(self, data):
        total_pages = self.page.paginator.num_pages
        
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),

            'count': self.page.paginator.count,
            'results': data,
            'total_pages': total_pages,

        })
