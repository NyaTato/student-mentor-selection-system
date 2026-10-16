"""Excel 文件解析器

将上传的 Excel 文件解析为行数据列表。

特性：
- 支持 .xlsx 格式
- 自动跳过表头行和说明行（前 3 行）
- 跳过空行
- 按列定义映射字段
- 支持文件大小和行数限制校验
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import load_workbook

from apps.common.error_codes import ErrorCode
from apps.common.exceptions import BusinessException
from apps.imports.excel.constants import (
    MAX_FILE_SIZE,
    MAX_ROW_COUNT,
    get_columns,
    get_headers,
)


class ExcelParser:
    """Excel 文件解析器"""

    # 数据起始行（跳过表头 + 示例 + 说明）
    DATA_START_ROW = 4

    @classmethod
    def parse(cls, file_content: bytes, role: int) -> list[dict[str, Any]]:
        """解析 Excel 文件内容

        Args:
            file_content: Excel 文件二进制内容
            role: UserRole 枚举值

        Returns:
            行数据列表，每行为 {字段名: 值} 的字典

        Raises:
            BusinessException: 文件格式错误、大小超限、行数超限
        """
        # 1. 校验文件大小
        file_size = len(file_content)
        if file_size > MAX_FILE_SIZE:
            raise BusinessException(
                f"文件大小 {file_size / 1024 / 1024:.2f}MB 超过限制 {MAX_FILE_SIZE / 1024 / 1024:.0f}MB",
                code=ErrorCode.IMPORT_FILE_INVALID,
            )

        # 2. 加载工作簿
        try:
            wb = load_workbook(BytesIO(file_content), read_only=True, data_only=True)
        except Exception as exc:
            raise BusinessException(
                f"Excel 文件解析失败: {exc}",
                code=ErrorCode.IMPORT_FILE_INVALID,
            ) from exc

        ws = wb.active
        if ws is None:
            raise BusinessException(
                "Excel 文件无有效工作表",
                code=ErrorCode.IMPORT_FILE_INVALID,
            )

        # 3. 校验表头
        headers = get_headers(role)
        columns = get_columns(role)
        field_names = [col[0] for col in columns]

        # 4. 读取数据行
        rows: list[dict[str, Any]] = []
        for row_idx, row in enumerate(
            ws.iter_rows(min_row=cls.DATA_START_ROW, values_only=True), start=cls.DATA_START_ROW
        ):
            # 跳过完全空白的行
            if all(cell is None or str(cell).strip() == "" for cell in row):
                continue

            # 按列顺序映射字段
            row_data: dict[str, Any] = {}
            for col_idx, field_name in enumerate(field_names):
                value = row[col_idx] if col_idx < len(row) else None
                # 统一转为字符串并去除首尾空白
                if value is not None:
                    value = str(value).strip()
                row_data[field_name] = value
            row_data["_row_number"] = row_idx - cls.DATA_START_ROW + 1
            rows.append(row_data)

        # 5. 校验行数
        if len(rows) > MAX_ROW_COUNT:
            raise BusinessException(
                f"数据行数 {len(rows)} 超过限制 {MAX_ROW_COUNT}",
                code=ErrorCode.IMPORT_FILE_INVALID,
            )

        wb.close()
        return rows

    @classmethod
    def validate_headers(cls, file_content: bytes, role: int) -> bool:
        """校验 Excel 表头是否匹配角色模板

        Args:
            file_content: Excel 文件二进制内容
            role: UserRole 枚举值

        Returns:
            True 如果表头匹配
        """
        try:
            wb = load_workbook(BytesIO(file_content), read_only=True, data_only=True)
        except Exception:
            return False

        ws = wb.active
        if ws is None:
            return False

        expected_headers = get_headers(role)
        actual_headers = []
        for cell in next(ws.iter_rows(min_row=1, max_row=1, values_only=True), []):
            if cell is None:
                break
            # 去除必填标记星号
            header = str(cell).strip().rstrip("*")
            actual_headers.append(header)

        wb.close()
        return actual_headers == expected_headers
