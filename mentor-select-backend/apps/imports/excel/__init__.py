"""Excel 导入子模块

提供 Excel 文件解析、字段校验、数据导入、模板生成能力。

依据 DATABASE.md 7.9 Excel 导入流程：
1. 创建 import_task
2. 解析 Excel（Parser）
3. 逐行处理（Importer）：校验 → 创建 user+profile → 记录 import_log
4. 更新 import_task 统计
"""
from apps.imports.excel.importer import ExcelImporter
from apps.imports.excel.parser import ExcelParser
from apps.imports.excel.template import ExcelTemplateGenerator
from apps.imports.excel.validator import RowValidator

__all__ = [
    "ExcelParser",
    "ExcelImporter",
    "ExcelTemplateGenerator",
    "RowValidator",
]
