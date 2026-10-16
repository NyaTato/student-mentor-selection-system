"""
标准分页

配合 BaseApiResponseViewSet 使用：
- list 操作返回统一分页格式 {list, total, page, page_size, total_pages}
- 支持前端通过 page / page_size 查询参数控制分页
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPageNumberPagination(PageNumberPagination):
    """标准分页

    查询参数：
    - page: 页码，从 1 开始
    - page_size: 每页数量，默认 20，最大 100
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        """返回统一格式的分页响应"""
        return Response(
            {
                "code": 0,
                "message": "查询成功",
                "data": {
                    "list": data,
                    "total": self.page.paginator.count,
                    "page": self.page.number,
                    "page_size": self.page.paginator.per_page,
                    "total_pages": self.page.paginator.num_pages,
                },
            }
        )

    def get_paginated_response_schema(self, schema):
        """OpenAPI schema 定义"""
        return {
            "type": "object",
            "properties": {
                "code": {"type": "integer", "example": 0},
                "message": {"type": "string", "example": "查询成功"},
                "data": {
                    "type": "object",
                    "properties": {
                        "list": schema,
                        "total": {"type": "integer", "example": 100},
                        "page": {"type": "integer", "example": 1},
                        "page_size": {"type": "integer", "example": 20},
                        "total_pages": {"type": "integer", "example": 5},
                    },
                },
            },
        }
