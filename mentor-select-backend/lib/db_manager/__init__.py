"""db_manager 模块 - 数据库访问层

所有数据库操作统一通过 db_manager 调用。
一个业务一个文件：user_db.py, student_db.py, teacher_db.py, admin_db.py

职责：仅 CRUD（SELECT/INSERT/UPDATE/DELETE）+ 事务辅助 + 分页
禁止：业务逻辑、权限判断、HTTP、JSON、Serializer
"""
