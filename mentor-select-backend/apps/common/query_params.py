"""查询参数序列化器（安全解析）

背景
----
View 层此前普遍使用 `int(request.query_params.get("x"))` 直接转换。
非法输入（如 `?academic_year=abc`）会抛 ValueError，被全局异常处理器
当作未预期异常处理，返回 500 SYSTEM_ERROR —— 既是错误的状态码，
也把参数错误伪装成服务端故障。

本模块为常用查询参数提供 DRF Serializer，非法输入统一返回 400
（DRF ValidationError → 全局 handler → code=19000/400），
View 层不再出现裸 int() 转换。

QueryDict 归一化（DRF BooleanField 省略语义）
------------------------------------------------
DRF 的 ``Serializer.to_internal_value`` 通过 ``Field.get_value(dictionary)``
取值，而 ``get_value`` 第一件事就是 ``html.is_html_input(dictionary)``：
凡是带有 ``getlist`` 的输入（Django ``QueryDict``）都被当作 **HTML 表单**。
在该分支里，字段**缺失**时返回 ``field.default_empty_html`` ——
``BooleanField.default_empty_html = False``（HTML 表单里「未勾选的 checkbox 就是 False」）。

后果：``parse_query(AnnouncementListQuerySerializer, request.query_params)``
在**没有传** ``is_published`` 时，会得到 ``is_published=False`` 而不是「未提供」，
于是管理员的公告列表被静默过滤成「仅草稿」、已发布公告 ``get_object()`` 变 404、
发布/取消发布的用例全部 404。``is_revoked`` 等布尔过滤同理。

因此 :func:`parse_query` 在校验前先把输入**压平为普通标量 dict**
（每键取最后一个标量值，缺失的键保持缺失），普通 dict 不触发 HTML 表单分支，
「未提供」与「显式 False」因此可以被区分：
未提供 → 字段被 SkipField 跳过（不在 validated_data 里）；
``is_published=false`` → False；``is_published=true`` → True；
``is_published=abc`` → 400。

用法：
    from apps.common.query_params import parse_query, ApplicationListQuerySerializer
    data = parse_query(ApplicationListQuerySerializer, request.query_params)
    academic_year_id = data.get("academic_year")   # int | None
"""
from __future__ import annotations

from rest_framework import serializers


class BaseQueryParamSerializer(serializers.Serializer):
    """查询参数序列化器基类

    DRF Serializer 会忽略未声明的字段，因此 query_params 中的
    分页参数、排序参数不会导致校验失败。
    """


class AcademicYearQuerySerializer(BaseQueryParamSerializer):
    """仅含 academic_year 的查询"""

    academic_year = serializers.IntegerField(required=False, min_value=1)


class ApplicationListQuerySerializer(BaseQueryParamSerializer):
    """申请列表查询（applications 列表 / my / teacher）"""

    academic_year = serializers.IntegerField(required=False, min_value=1)
    round = serializers.IntegerField(required=False, min_value=1, max_value=2)
    status = serializers.IntegerField(required=False, min_value=1, max_value=3)


class AdmissionListQuerySerializer(BaseQueryParamSerializer):
    """录取结果列表查询"""

    academic_year = serializers.IntegerField(required=False, min_value=1)
    teacher = serializers.IntegerField(required=False, min_value=1)
    student = serializers.IntegerField(required=False, min_value=1)


class AutoAssignmentLogListQuerySerializer(BaseQueryParamSerializer):
    """自动分配日志列表查询"""

    academic_year = serializers.IntegerField(required=False, min_value=1)
    status = serializers.IntegerField(required=False, min_value=0, max_value=4)
    is_revoked = serializers.BooleanField(required=False)


class AnnouncementListQuerySerializer(BaseQueryParamSerializer):
    """公告列表查询"""

    academic_year = serializers.IntegerField(required=False, min_value=1)
    is_published = serializers.BooleanField(required=False)


class StudentDirectoryQuerySerializer(BaseQueryParamSerializer):
    """学生列表/详情查询（角色裁剪需要 academic_year）"""

    academic_year = serializers.IntegerField(required=False, min_value=1)
    keyword = serializers.CharField(required=False, allow_blank=True)
    major = serializers.CharField(required=False, allow_blank=True)
    class_name = serializers.CharField(required=False, allow_blank=True)


class ToggleAutoSerializer(BaseQueryParamSerializer):
    """启停自动切换请求体"""

    academic_year = serializers.IntegerField(min_value=1)
    enabled = serializers.BooleanField()


class AcademicYearIdSerializer(BaseQueryParamSerializer):
    """仅含必填 academic_year 的请求体解析"""

    academic_year = serializers.IntegerField(min_value=1)


def normalize_query_data(query_params) -> dict:
    """把查询输入压平为「标量值」的普通 dict

    - ``QueryDict`` / ``MultiValueDict``（有 ``lists()``）：每键取**最后一个**值
      （与浏览器表单后提交覆盖语义一致），**不保留列表**；
    - 普通 dict：值若为 list/tuple 则取最后一个元素；空列表的键直接丢弃；
    - 缺失的键**保持缺失**（不会补 False），这是修复 DRF BooleanField
      HTML 表单语义的关键。

    Args:
        query_params: request.query_params / request.data / 普通 dict / None

    Returns:
        普通 dict，值均为标量
    """
    if query_params is None:
        return {}

    if hasattr(query_params, "lists"):
        return {
            key: values[-1]
            for key, values in query_params.lists()
            if values
        }

    data: dict = {}
    for key, value in dict(query_params).items():
        if isinstance(value, (list, tuple)):
            if not value:
                continue
            value = value[-1]
        data[key] = value
    return data


def parse_query(serializer_cls, query_params) -> dict:
    """解析查询参数；非法输入抛 DRF ValidationError（→ 400）。

    输入先经 :func:`normalize_query_data` 压平为普通标量 dict，
    避免 QueryDict 触发 DRF BooleanField 的 HTML 表单语义
    （字段缺失被反序列化成 False、非法布尔值被吞掉）。

    Args:
        serializer_cls: BaseQueryParamSerializer 子类
        query_params: request.query_params 或普通 dict

    Returns:
        validated_data（仅包含已声明且已提供、类型正确的字段）
    """
    serializer = serializer_cls(data=normalize_query_data(query_params))
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def parse_body(serializer_cls, data) -> dict:
    """解析请求体（与 parse_query 相同语义，语义化命名）"""
    return parse_query(serializer_cls, data)
