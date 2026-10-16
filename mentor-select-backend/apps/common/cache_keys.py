"""
Redis 缓存 Key 构建器

依据 DATABASE.md 8.1 缓存对象表，定义所有 14 个缓存 Key 的构建方式。

Key 命名规范（DATABASE.md 8.2）：
- 分层：{模块}:{标识}:{子标识}
- 分隔符：冒号 :
- 全小写，不使用中文
- 所有业务缓存 Key 必须包含 academic_year_id，保证学年隔离

TTL 策略（秒）：
- year:active / state / quota：不过期（None）
- teacher:info：30 min
- teacher:list：10 min
- announcement：5 min
- import:task：1 hour
- 分布式锁：10-300 sec（自动过期）
- 幂等 Token：5 min（自动过期）
"""
from __future__ import annotations


# ===== TTL 常量（秒） =====
TTL_NONE = None  # 不过期
TTL_TEACHER_INFO = 30 * 60  # 30 分钟
TTL_TEACHER_LIST = 10 * 60  # 10 分钟
TTL_ANNOUNCEMENT = 5 * 60  # 5 分钟
TTL_IMPORT_TASK = 60 * 60  # 1 小时
TTL_IDEMPOTENT = 5 * 60  # 5 分钟

# ===== 分布式锁 TTL（秒） =====
LOCK_TTL_APPLICATION = 10  # 防并发重复申请
LOCK_TTL_ADMISSION = 30  # 防并发超额录取
LOCK_TTL_STATE_TRANSITION = 10  # 防并发状态切换
LOCK_TTL_STATE_AUTO_TRANSITION = 30  # 防自动与手动切换并发
LOCK_TTL_ACADEMIC_YEAR_ACTIVATE = 30  # 防并发学年激活
LOCK_TTL_AUTO_ASSIGN = 300  # 防并发自动分配


# ===== Key 构建器 =====


def year_active() -> str:
    """当前 ACTIVE 学年 Key"""
    return "year:active"


def state(academic_year_id: int) -> str:
    """该学年的系统状态 Key"""
    return f"state:{academic_year_id}"


def teacher_info(academic_year_id: int, teacher_id: int) -> str:
    """导师详情缓存 Key（30 min TTL）"""
    return f"teacher:{academic_year_id}:{teacher_id}:info"


def teacher_quota(academic_year_id: int, teacher_id: int) -> str:
    """导师剩余名额缓存 Key（不过期，录取/撤销时删除）"""
    return f"teacher:{academic_year_id}:{teacher_id}:quota"


def teacher_list(academic_year_id: int) -> str:
    """导师列表缓存 Key（10 min TTL）"""
    return f"teacher:{academic_year_id}:list"


def announcement_published(academic_year_id: int) -> str:
    """已发布公告列表缓存 Key（5 min TTL）"""
    return f"announcement:{academic_year_id}:published"


def import_task(task_id: int) -> str:
    """导入任务状态缓存 Key（1 hour TTL）"""
    return f"import:task:{task_id}"


# ===== 分布式锁 Key 构建器 =====


def lock_application(academic_year_id: int, student_id: int, round_num: int) -> str:
    """防并发重复申请锁 Key"""
    return f"lock:application:{academic_year_id}:{student_id}:{round_num}"


def lock_admission(academic_year_id: int, teacher_id: int) -> str:
    """防并发超额录取锁 Key"""
    return f"lock:admission:{academic_year_id}:{teacher_id}"


def lock_state_transition(academic_year_id: int) -> str:
    """防并发状态切换锁 Key"""
    return f"lock:state:transition:{academic_year_id}"


def lock_state_auto_transition(academic_year_id: int) -> str:
    """防自动与手动切换并发锁 Key"""
    return f"lock:state:auto_transition:{academic_year_id}"


def lock_academic_year_activate() -> str:
    """防并发学年激活锁 Key"""
    return "lock:academic_year:activate"


def lock_auto_assign(academic_year_id: int) -> str:
    """防并发自动分配锁 Key"""
    return f"lock:auto_assign:{academic_year_id}"


# ===== 幂等 Token Key 构建器 =====


def idempotent(request_id: str) -> str:
    """幂等 Token Key"""
    return f"idempotent:{request_id}"


# ===== 批量失效辅助 =====


def teacher_pattern(academic_year_id: int) -> str:
    """该学年所有导师相关缓存 Key 的 glob 模式（用于学年切换批量删除）"""
    return f"teacher:{academic_year_id}:*"


def all_year_patterns(academic_year_id: int) -> list[str]:
    """该学年所有需要批量删除的 Key glob 模式

    用于学年切换时批量删除旧学年的所有缓存 Key（DATABASE.md 8.5 第 5 条）。
    """
    return [
        f"state:{academic_year_id}",
        f"teacher:{academic_year_id}:*",
        f"announcement:{academic_year_id}:*",
    ]
