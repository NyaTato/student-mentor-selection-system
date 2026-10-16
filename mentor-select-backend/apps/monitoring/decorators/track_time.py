"""@track_time 装饰器

自动测量函数执行时间并记录到对应的 Prometheus metric，同时创建 OpenTelemetry Span。

特性：
- 支持同步与异步函数
- 支持类方法、实例方法、静态方法、普通函数
- 支持 4 种 metric_type：
  - "service"：记录到 SERVICE_DURATION（labels: service, method）
  - "repository"：记录到 REPOSITORY_DURATION（labels: repository, method）
  - "celery"：记录到 CELERY_TASK_DURATION + CELERY_TASK_TOTAL（labels: task, status）
  - "import"：记录到 EXCEL_DURATION（labels: stage）
- 异常时也记录耗时和失败状态，便于监控失败请求的耗时分布
- 运行时从 self.__class__ 提取实际子类名（子类调用父类方法时标签更精确）
- 缓存 inspect.signature 结果避免重复计算
- 自动创建 OpenTelemetry Span（与 Jaeger 集成），Span Name = "{ClassName}.{method_name}"
- sync / async wrapper 通过 _ObservationContext 共享逻辑，避免重复代码

使用示例：
    # Service 方法（自动记录到 SERVICE_DURATION + 创建 Span）
    @track_time()
    def login(self, username, password): ...

    # Repository 方法
    @track_time(metric_type="repository")
    def get_by_id(self, pk): ...

    # Celery 任务（记录到 CELERY_TASK_DURATION + CELERY_TASK_TOTAL）
    @track_time(metric_type="celery")
    def run_auto_assignment(self, year_id): ...

    # Excel 导入阶段
    @track_time(metric_type="import", labels={"stage": "parse"})
    def parse_excel(self, file_path): ...
"""
from __future__ import annotations

import functools
import inspect
import logging
import time
import weakref
from typing import Any, Callable

from apps.monitoring.services import MetricsService

logger = logging.getLogger(__name__)

# signature 缓存：使用 WeakKeyDictionary 避免 id() 复用和内存泄漏
# 函数对象是 weakly referenceable 的，GC 后自动清理对应条目
_sig_cache: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

# OpenTelemetry Tracer（延迟初始化，避免循环导入）
_tracer: Any = None


def _get_tracer() -> Any:
    """获取 OpenTelemetry Tracer（单例，延迟初始化）

    Returns:
        Tracer 实例，若 OpenTelemetry 未安装则返回 None
    """
    global _tracer
    if _tracer is not None:
        return _tracer
    try:
        from opentelemetry import trace

        _tracer = trace.get_tracer(__name__)
    except Exception as e:
        logger.debug("OpenTelemetry tracer unavailable: %s", e)
        _tracer = None  # type: ignore[assignment]
    return _tracer


def _get_signature(func: Callable[..., Any]) -> inspect.Signature | None:
    """获取函数签名（带缓存）

    使用 WeakKeyDictionary 以函数对象本身为 key，
    GC 后自动清理，避免内存泄漏。

    Args:
        func: 被装饰的函数

    Returns:
        函数签名（若可获取），否则 None
    """
    if func not in _sig_cache:
        try:
            _sig_cache[func] = inspect.signature(func)
        except Exception as e:
            logger.debug("Cannot inspect signature of %s: %s", func, e)
            _sig_cache[func] = None  # type: ignore[assignment]
    return _sig_cache[func]


def _extract_runtime_class(args: tuple, func: Callable[..., Any]) -> str | None:
    """从运行时参数中提取实例的类名

    当子类调用继承自基类的方法时，func.__qualname__ 仍是基类名，
    通过 args[0]（即 self）可获取实际子类名，使 metric 标签更精确。

    Args:
        args: 调用时传入的位置参数
        func: 被装饰的函数

    Returns:
        实际类名（若可提取），否则 None
    """
    sig = _get_signature(func)
    if sig is None:
        return None
    params = list(sig.parameters.values())
    # 第一个参数名为 self → 实例方法，args[0] 即实例
    if params and params[0].name == "self" and args:
        return args[0].__class__.__name__
    return None


def _extract_class_name(func: Callable[..., Any]) -> str | None:
    """从函数对象提取类名（静态解析）

    Args:
        func: 被装饰的函数

    Returns:
        类名（若存在），否则 None
    """
    qualname = getattr(func, "__qualname__", "")
    if "." in qualname:
        parts = qualname.split(".")
        if len(parts) >= 2 and not parts[-2].startswith("<"):
            return parts[-2]
    return None


def _get_class_name(metric_type: str, func: Callable[..., Any], args: tuple) -> str:
    """获取类名（统一入口，避免重复表达式）

    优先级：
    1. 运行时类名（子类调用父类方法时更精确）
    2. 静态类名（从 __qualname__ 解析）
    3. 默认值（repository → "Repository"，其他 → "Service"）

    Args:
        metric_type: metric 类型
        func: 被装饰的函数
        args: 调用参数

    Returns:
        类名字符串
    """
    return (
        _extract_runtime_class(args, func)
        or _extract_class_name(func)
        or ("Repository" if metric_type == "repository" else "Service")
    )


def _get_celery_task_name(func: Callable[..., Any], args: tuple) -> str:
    """获取 Celery 任务名称

    优先级：
    1. Celery 任务的 name 属性（如 "imports.process_excel_import"）
    2. 函数的 __name__

    Args:
        func: 被装饰的函数
        args: 调用参数

    Returns:
        任务名称
    """
    # Celery shared_task 会将任务对象包装到函数上
    # 尝试从 bound task 的 self 获取任务名
    if args and hasattr(args[0], "name"):
        task_obj = args[0]
        name_val = getattr(task_obj, "name", None)
        if isinstance(name_val, str):
            return name_val
    # 从函数的 celery 属性获取
    celery_name = getattr(func, "name", None)
    if isinstance(celery_name, str) and "." in celery_name:
        return celery_name
    # 降级到函数名
    return func.__name__


def _build_span_name(
    metric_type: str,
    func: Callable[..., Any],
    args: tuple,
) -> str:
    """构建 OpenTelemetry Span 名称

    Span Name 格式：
    - service：{ClassName}.{method_name}
    - repository：{ClassName}.{method_name}
    - celery：{task_name}
    - import：excel_import.{stage}

    Args:
        metric_type: metric 类型
        func: 被装饰的函数
        args: 调用参数

    Returns:
        Span 名称
    """
    if metric_type == "celery":
        return _get_celery_task_name(func, args)

    if metric_type == "import":
        # import 类型的 span name 在调用时由 labels 决定
        return "excel_import"

    # service / repository
    class_name = _get_class_name(metric_type, func, args)
    return f"{class_name}.{func.__name__}"


def _set_span_attributes(
    span: Any,
    metric_type: str,
    func: Callable[..., Any],
    args: tuple,
    labels: dict[str, str] | None,
) -> None:
    """设置 OpenTelemetry Span 属性

    Args:
        span: OpenTelemetry Span 实例
        metric_type: metric 类型
        func: 被装饰的函数
        args: 调用参数
        labels: 自定义 labels
    """
    try:
        span.set_attribute("metric.type", metric_type)
        span.set_attribute("method.name", func.__name__)

        if metric_type == "celery":
            span.set_attribute("task.name", _get_celery_task_name(func, args))
        elif metric_type == "import":
            stage = (labels or {}).get("stage", "total")
            span.set_attribute("import.stage", stage)
        else:
            class_name = _get_class_name(metric_type, func, args)
            span.set_attribute("class.name", class_name)
            if metric_type == "repository":
                span.set_attribute("repository.name", class_name)
            else:
                span.set_attribute("service.name", class_name)
    except Exception as e:
        logger.debug("Failed to set span attributes: %s", e)


def _observe_metric(
    metric_type: str,
    duration: float,
    func: Callable[..., Any],
    args: tuple,
    success: bool,
    labels: dict[str, str] | None = None,
) -> None:
    """记录耗时到对应类型的 metric

    通过 MetricsService 统一访问底层 metric，确保所有记录路径
    都经过 @_safe 异常保护，避免未来加采样/多租户标签时需改两处。

    根据 metric_type 选择目标 metric：
    - "service"：MetricsService.record_service（labels: service, method）
    - "repository"：MetricsService.record_repository（labels: repository, method）
    - "celery"：MetricsService.record_celery_task（labels: task, status）
    - "import"：MetricsService.record_excel_import（labels: stage）

    Args:
        metric_type: metric 类型
        duration: 耗时（秒）
        func: 被装饰的函数
        args: 调用参数（用于提取运行时类名）
        success: 是否成功执行
        labels: 自定义 labels（仅 "import" 类型使用 stage label）
    """
    if metric_type == "celery":
        task_name = _get_celery_task_name(func, args)
        MetricsService.record_celery_task(task_name, success, duration)

    elif metric_type == "import":
        stage = (labels or {}).get("stage", "total")
        MetricsService.record_excel_import(stage, duration)

    elif metric_type == "repository":
        class_name = _get_class_name(metric_type, func, args)
        MetricsService.record_repository(class_name, func.__name__, duration)

    else:  # "service"（默认）
        class_name = _get_class_name(metric_type, func, args)
        MetricsService.record_service(class_name, func.__name__, duration)


def _record_span_error(span: Any, exception: Exception) -> None:
    """在 Span 中记录异常

    Args:
        span: OpenTelemetry Span 实例
        exception: 捕获的异常
    """
    try:
        from opentelemetry.trace import Status, StatusCode

        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR, str(exception)))
    except Exception as e:
        logger.debug("Failed to record span error: %s", e)


def _set_span_duration(span: Any, duration: float) -> None:
    """在 Span 中记录执行耗时

    Args:
        span: OpenTelemetry Span 实例
        duration: 耗时（秒）
    """
    try:
        span.set_attribute("duration.ms", duration * 1000)
    except Exception as e:
        logger.debug("Failed to set span duration: %s", e)


class _ObservationContext:
    """Span 生命周期 + Metric 记录的统一上下文管理器

    将 sync_wrapper 和 async_wrapper 的共享逻辑抽取到此上下文管理器：
    - __enter__：启动计时，若 tracer 可用则创建 Span 并设置属性
    - __exit__：记录异常（若有）、设置 duration、关闭 Span、记录 Metric

    通过此抽象，sync_wrapper 和 async_wrapper 仅需 2-3 行代码，
    避免了约 70 行重复逻辑。
    """

    __slots__ = (
        "_metric_type",
        "_func",
        "_args",
        "_labels",
        "_start",
        "_success",
        "_tracer",
        "_span_cm",
        "_span",
    )

    def __init__(
        self,
        metric_type: str,
        func: Callable[..., Any],
        args: tuple,
        labels: dict[str, str] | None,
    ) -> None:
        self._metric_type = metric_type
        self._func = func
        self._args = args
        self._labels = labels
        self._start = time.perf_counter()
        self._success = True
        self._tracer = _get_tracer()
        self._span_cm: Any = None
        self._span: Any = None

    def __enter__(self) -> "_ObservationContext":
        if self._tracer is not None:
            span_name = _build_span_name(self._metric_type, self._func, self._args)
            self._span_cm = self._tracer.start_as_current_span(span_name)
            self._span = self._span_cm.__enter__()
            _set_span_attributes(
                self._span, self._metric_type, self._func, self._args, self._labels
            )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_val is not None:
            self._success = False
            if self._span is not None:
                _record_span_error(self._span, exc_val)
        duration = time.perf_counter() - self._start
        if self._span is not None:
            _set_span_duration(self._span, duration)
        if self._span_cm is not None:
            self._span_cm.__exit__(exc_type, exc_val, exc_tb)
        _observe_metric(
            self._metric_type,
            duration,
            self._func,
            self._args,
            self._success,
            self._labels,
        )
        return False  # 不抑制异常


def track_time(
    metric_type: str = "service",
    labels: dict[str, str] | None = None,
) -> Callable[..., Any]:
    """通用耗时统计装饰器

    Args:
        metric_type: metric 类型，可选值：
            - "service"（默认）：记录到 SERVICE_DURATION
            - "repository"：记录到 REPOSITORY_DURATION
            - "celery"：记录到 CELERY_TASK_DURATION + CELERY_TASK_TOTAL
            - "import"：记录到 EXCEL_DURATION
        labels: 自定义 labels（仅 "import" 类型使用 stage label）

    Returns:
        装饰器函数
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                """异步函数包装器"""
                with _ObservationContext(metric_type, func, args, labels):
                    return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """同步函数包装器"""
            with _ObservationContext(metric_type, func, args, labels):
                return func(*args, **kwargs)

        return sync_wrapper

    return decorator
