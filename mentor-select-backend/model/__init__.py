"""Model 模块 - 数据库映射层

职责：仅负责映射数据库字段，不包含业务逻辑、SQL、HTTP。
所有 Model 统一继承 BaseModel，字段与 SQL 100% 一致。

使用 Django Model 定义，managed=False，不依赖 Migration。
表结构由 model/sql/ 下的手写 SQL 创建。
"""
