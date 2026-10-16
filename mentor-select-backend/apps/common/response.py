"""
统一响应

所有 API 响应都遵循统一格式：
{
    "code": 0,            # 业务错误码，0 表示成功
    "message": "success", # 文案
    "data": {...}         # 数据载荷，可为 null
}

分页响应格式：
{
    "code": 0,
    "message": "查询成功",
    "data": {
        "list": [...],
        "total": 100,
        "page": 1,
        "page_size": 20,
        "total_pages": 5
    }
}
"""
from rest_framework import status as http_status
from rest_framework.response import Response


class ApiResponse:
    """统一 API 响应工具类"""

    @staticmethod
    def success(data=None, message="success", headers=None):
        """200 成功响应"""
        return Response(
            {"code": 0, "message": message, "data": data},
            status=http_status.HTTP_200_OK,
            headers=headers,
        )

    @staticmethod
    def created(data=None, message="created", headers=None):
        """201 创建成功响应"""
        return Response(
            {"code": 0, "message": message, "data": data},
            status=http_status.HTTP_201_CREATED,
            headers=headers,
        )

    @staticmethod
    def accepted(data=None, message="accepted"):
        """202 已接受（异步任务）"""
        return Response(
            {"code": 0, "message": message, "data": data},
            status=http_status.HTTP_202_ACCEPTED,
        )

    @staticmethod
    def no_content(message="deleted"):
        """204 无内容（删除）"""
        return Response(
            {"code": 0, "message": message, "data": None},
            status=http_status.HTTP_200_OK,  # 仍保留 body 以保持统一格式
        )

    @staticmethod
    def error(
        code=1,
        message="error",
        data=None,
        http_status_code=http_status.HTTP_400_BAD_REQUEST,
    ):
        """错误响应

        Args:
            code: 业务错误码（推荐使用 ErrorCode 常量）
            message: 错误信息
            data: 附加数据（如字段级错误）
            http_status_code: HTTP 状态码
        """
        return Response(
            {"code": code, "message": message, "data": data},
            status=http_status_code,
        )

    @staticmethod
    def paginated(serializer_data, page, message="查询成功"):
        """分页响应

        Args:
            serializer_data: 已分页、已序列化的列表数据
            page: DRF Page 实例（paginate_queryset 返回的对象）
            message: 文案
        """
        return Response(
            {
                "code": 0,
                "message": message,
                "data": {
                    "list": serializer_data,
                    "total": page.paginator.count,
                    "page": page.number,
                    "page_size": page.paginator.per_page,
                    "total_pages": page.paginator.num_pages,
                },
            },
            status=http_status.HTTP_200_OK,
        )
