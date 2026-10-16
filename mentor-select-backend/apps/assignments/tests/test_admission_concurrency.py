"""录取名额「最后一个座位」并发测试（仅 MySQL）

为什么只在 MySQL 上跑
---------------------
本项目依赖两条 MySQL 特有语义来防止超卖：
1. ``SELECT ... FOR UPDATE`` 行级锁（SQLite 无真正的行锁，
   在 SQLite 上并发写会退化为「database is locked」而不是排队等待）
2. REPEATABLE READ 下「当前读 vs 快照读」的区别
   （SQLite 的隔离/快照语义不同，无法复现过期快照导致的超卖）

因此：
- 非 MySQL 后端（如本项目默认的 SQLite 测试库）**显式 skip**，
  并在 skip reason 中写明原因。SQLite 上的结果**不能**被当作行锁的证明。
- 测试使用 ``transaction=True``（TransactionTestCase 语义）以确保
  事务真正提交、锁真正生效。
- 每个工作线程使用**独立数据库连接**，绝不共享 APIClient / 连接。

失败面（本文件刻意收紧的部分）
------------------------------
* 线程里**只把 ``BusinessException`` 当作「预期业务拒绝」**；
  任何其它异常（``OperationalError`` / ``DatabaseError`` / 线程异常……）
  一律记为 ``unexpected`` 并让断言失败 —— 历史版本的
  ``except Exception`` 会把数据库故障伪装成「没抢到座位」的通过。
* 每个线程在**栅栏之前、自己的独立事务内**先做一次**普通（非加锁）快照读**，
  把 MySQL REPEATABLE READ 的读视图钉在并发提交之前。
  若实现依赖普通 SELECT 计数，就会读到过期快照而放行超额录取；
  该测试因此同时验证「实现用的是当前读（``select_for_update``）」。
* 线程 join 后断言**没有存活线程**，避免死锁/连接泄漏被静默忽略。

运行方式（需指向 MySQL 测试库）：
    DJANGO_SETTINGS_MODULE=config.settings.test \
    DB_ENGINE=django.db.backends.mysql \
    pytest apps/assignments/tests/test_admission_concurrency.py -v

作者侧未执行本文件（无 shell 权限），需由 Codex 在 MySQL 环境运行验证。
"""
from __future__ import annotations

import threading

import pytest
from django.db import connections, transaction
from django.utils import timezone

from apps.academic_year.models import AcademicYear
from apps.applications.models import Application
from apps.applications.services import ApplicationService
from apps.assignments.models import Admission
from apps.assignments.services import AdmissionService
from apps.common.enums import (
    AdmissionSource,
    ApplicationRound,
    ApplicationStatus,
    SystemStateValue,
    UserRole,
)
from apps.common.error_codes import ErrorCode
from apps.common.exceptions import BusinessException
from apps.students.models import StudentProfile
from apps.system.models import SystemState
from apps.teachers.models import TeacherProfile, TeacherQuota
from apps.users.models import User

# --- 后端能力探测 -----------------------------------------------------------

try:
    _VENDOR = connections["default"].vendor
except Exception:  # pragma: no cover - 配置缺失时
    _VENDOR = "unknown"

requires_mysql = pytest.mark.skipif(
    _VENDOR != "mysql",
    reason=(
        f"当前测试库后端为 {_VENDOR!r}，非 MySQL："
        "SQLite 不支持 SELECT ... FOR UPDATE 行级锁，且隔离/快照语义不同，"
        "无法验证『并发争抢最后一个名额』的行锁正确性。"
        "本测试不降级为 SQLite 运行，以免把非行锁环境的结果误当作行锁证明。"
    ),
)

pytestmark = [pytest.mark.django_db(transaction=True), requires_mysql]

# 栅栏等待 / 线程 join 超时（秒）
BARRIER_TIMEOUT = 30
THREAD_TIMEOUT = 60


# --- 工厂 -------------------------------------------------------------------


def _make_year(name="2025-2026"):
    return AcademicYear.objects.create(name=name, start_year=2025, end_year=2026, status=1)


def _make_users(n_students: int, *, suffix: str = ""):
    teacher_user = User.objects.create_user(
        username=f"conc_teacher{suffix}",
        password="pass12345",
        role=UserRole.TEACHER.value,
        status=1,
    )
    TeacherProfile.objects.create(
        user=teacher_user,
        teacher_number=f"CT{suffix or '0001'}",
        name="并发导师",
        college="计算机学院",
    )
    students = []
    for i in range(n_students):
        user = User.objects.create_user(
            username=f"conc_stu{suffix}_{i}",
            password="pass12345",
            role=UserRole.STUDENT.value,
            status=1,
        )
        profile = StudentProfile.objects.create(
            user=user,
            student_number=f"CS{suffix}{i:05d}",
            name=f"并发学生{i}",
            major="计算机科学",
            class_name="并发班",
        )
        students.append(profile)
    return teacher_user, students


def _init_state(academic_year, state_value):
    """初始化学年系统状态"""
    SystemState.objects.create(
        academic_year=academic_year,
        current_state=state_value,
        state_changed_at=timezone.now(),
    )


# --- 线程结果记录：只把 BusinessException 当作预期拒绝 -----------------------


def _record(results, index, exc):
    """记录线程结果。

    - 无异常           -> ``{"status": "ok"}``
    - ``BusinessException`` -> ``{"status": "business-rejected", ...}``（**预期**业务拒绝）
    - 其它异常         -> ``{"status": "unexpected", ...}``（**必须让测试失败**）

    绝不使用 ``except Exception`` 把数据库/锁故障吞成「未抢到座位」。
    """
    if exc is None:
        results[index] = {"status": "ok"}
        return
    if isinstance(exc, BusinessException):
        results[index] = {
            "status": "business-rejected",
            "error_code": getattr(exc, "default_code", None),
            "error_type": type(exc).__name__,
            "message": str(getattr(exc, "detail", exc)),
        }
        return
    results[index] = {
        "status": "unexpected",
        "error_type": type(exc).__name__,
        "message": str(exc),
    }


def _statuses(results):
    return [r["status"] for r in results]


def _rejected_error_codes(results):
    return [r["error_code"] for r in results if r["status"] == "business-rejected"]


def _assert_no_unexpected(results):
    """断言没有线程记录缺失、也没有任何非业务异常被吞掉"""
    missing = [i for i, r in enumerate(results) if r is None]
    assert not missing, f"线程 {missing} 未写入结果（可能未执行到记录点）：{results!r}"
    unexpected = [r for r in results if r["status"] == "unexpected"]
    assert not unexpected, (
        "出现非业务异常（数据库 / 锁 / 线程错误不得被当作『未抢到座位』吞掉）："
        f"unexpected={unexpected!r}；全部结果={results!r}"
    )


def _run_threads(threads, timeout=THREAD_TIMEOUT):
    """启动、join 并断言所有线程都已结束（防死锁 / 连接泄漏被静默忽略）"""
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=timeout)
    alive = [t.name for t in threads if t.is_alive()]
    assert not alive, f"线程未在 {timeout}s 内结束（疑似死锁或连接泄漏）：{alive}"


# --- 事务内「普通快照读」：复现 MySQL REPEATABLE READ 过期快照 ---------------


def _open_ordinary_snapshot(academic_year_id: int, teacher_id: int) -> None:
    """在**当前事务内、栅栏之前**执行普通（非加锁）快照读。

    MySQL REPEATABLE READ 下，事务的一致性读视图在第一次普通 SELECT 时建立。
    这里先读一次 quota 与 admission 计数，把读视图钉在并发事务提交**之前**：
    如果名额判定用的是普通 SELECT（快照读），后续就会看到过期计数而超额录取。
    """
    TeacherQuota.objects.filter(
        academic_year_id=academic_year_id, teacher_id=teacher_id
    ).values_list("max_quota", flat=True).first()
    Admission.objects.filter(
        academic_year_id=academic_year_id, teacher_id=teacher_id
    ).count()


# --- 线程主体 ---------------------------------------------------------------


def _worker(
    *,
    index: int,
    results: list,
    barrier: threading.Barrier,
    body,
    snapshot: tuple[int, int] | None = None,
):
    """线程主体：独立连接 + 独立事务 + 栅栏同步。

    事务内顺序（刻意如此）：
      1. 普通快照读（把 REPEATABLE READ 读视图钉在并发提交之前）
      2. ``barrier.wait()`` —— 让所有线程真正同时进入临界区
      3. ``body()`` —— 被测业务调用

    Returns 之前一律关闭本线程的连接。
    """
    try:
        with transaction.atomic():
            if snapshot is not None:
                _open_ordinary_snapshot(*snapshot)
            try:
                barrier.wait(timeout=BARRIER_TIMEOUT)
            except threading.BrokenBarrierError as exc:
                # 栅栏破裂属于测试基础设施故障，**不是**业务拒绝
                _record(results, index, exc)
                return
            body()
        _record(results, index, None)
    except Exception as exc:  # noqa: BLE001 - 分类记录，由断言决定成败
        _record(results, index, exc)
    finally:
        # 每个线程用完立刻关闭自己的连接，避免连接泄漏影响后续断言
        connections.close_all()


def _allocate_body(academic_year_id: int, student_id: int, teacher_id: int):
    """构造一次人工分配调用（线程 body）"""

    def body():
        AdmissionService().allocate(
            academic_year_id=academic_year_id,
            student_id=student_id,
            teacher_id=teacher_id,
            source=AdmissionSource.MANUAL.value,
        )

    return body


def _round2_body(academic_year_id: int, student: StudentProfile, teacher: TeacherProfile):
    """构造一次第二轮申请提交（线程 body）"""

    def body():
        ApplicationService().create(
            {
                "academic_year": academic_year_id,
                "student": student,
                "teacher": teacher,
                "round": ApplicationRound.SECOND_ROUND.value,
            }
        )

    return body


# --- 测试 -------------------------------------------------------------------


def test_last_seat_only_one_of_two_concurrent_allocations_wins():
    """quota=1，两个不同学生并发争抢同一导师的最后一个名额：恰好一个成功。

    断言的是**数据库事实**（admission 行数 == 1），而不是异常类型；同时要求
    失败方必须是**已知业务拒绝**，任何其它异常都会让测试失败。
    """
    year = _make_year()
    teacher_user, students = _make_users(2)
    TeacherQuota.objects.create(academic_year=year, teacher_id=teacher_user.id, max_quota=1)

    barrier = threading.Barrier(2)
    results = [None, None]
    snapshot = (year.id, teacher_user.id)
    threads = [
        threading.Thread(
            name=f"allocate-{i}",
            target=_worker,
            kwargs={
                "index": i,
                "results": results,
                "barrier": barrier,
                "snapshot": snapshot,
                "body": _allocate_body(year.id, students[i].user_id, teacher_user.id),
            },
        )
        for i in range(2)
    ]
    _run_threads(threads)
    _assert_no_unexpected(results)

    # 连接关闭后重新查询（新连接 -> 最新已提交数据）
    admitted = Admission.objects.filter(academic_year=year, teacher_id=teacher_user.id)
    assert admitted.count() == 1, (
        f"quota=1 但产生了 {admitted.count()} 条录取记录 —— 行锁/当前读失效（超卖）。"
        f" 线程结果={results!r}"
    )
    assert _statuses(results).count("ok") == 1, f"应恰好一个线程成功，实际={results!r}"
    assert _rejected_error_codes(results) == [ErrorCode.ADMISSION_QUOTA_FULL], (
        "失败方必须是『名额已满』的业务拒绝，实际="
        f"{_rejected_error_codes(results)!r}（全部结果={results!r}）"
    )


def test_concurrent_duplicate_allocation_for_same_student_yields_one_row():
    """同一学生并发两次分配：学生行锁 + DB 唯一约束保证只有一条记录。"""
    year = _make_year()
    teacher_user, students = _make_users(1)
    TeacherQuota.objects.create(academic_year=year, teacher_id=teacher_user.id, max_quota=5)
    student_id = students[0].user_id

    barrier = threading.Barrier(2)
    results = [None, None]
    snapshot = (year.id, teacher_user.id)
    threads = [
        threading.Thread(
            name=f"dup-{i}",
            target=_worker,
            kwargs={
                "index": i,
                "results": results,
                "barrier": barrier,
                "snapshot": snapshot,
                "body": _allocate_body(year.id, student_id, teacher_user.id),
            },
        )
        for i in range(2)
    ]
    _run_threads(threads)
    _assert_no_unexpected(results)

    rows = Admission.objects.filter(academic_year=year, student_id=student_id)
    assert rows.count() == 1, f"同一学生产生了 {rows.count()} 条录取记录，结果={results!r}"


def test_concurrent_allocation_without_quota_never_succeeds():
    """未配置名额时并发分配：任何线程都不得成功（未配置 = 关闭）。"""
    year = _make_year()
    teacher_user, students = _make_users(2)
    # 故意不创建 TeacherQuota

    barrier = threading.Barrier(2)
    results = [None, None]
    snapshot = (year.id, teacher_user.id)
    threads = [
        threading.Thread(
            name=f"noquota-{i}",
            target=_worker,
            kwargs={
                "index": i,
                "results": results,
                "barrier": barrier,
                "snapshot": snapshot,
                "body": _allocate_body(year.id, students[i].user_id, teacher_user.id),
            },
        )
        for i in range(2)
    ]
    _run_threads(threads)
    _assert_no_unexpected(results)

    assert Admission.objects.filter(academic_year=year).count() == 0
    assert _statuses(results).count("ok") == 0, f"未配置名额却分配成功，结果={results!r}"
    assert _rejected_error_codes(results) == [
        ErrorCode.QUOTA_NOT_FOUND,
        ErrorCode.QUOTA_NOT_FOUND,
    ], f"两个线程都应因『未配置名额』被拒，实际={results!r}"


def test_quota_lowering_is_serialized_against_admission():
    """并发「录取」与「降低名额」：结束后 admitted <= max_quota 恒成立。

    这是名额服务与录取服务使用同一把行锁的直接验证。
    """
    from apps.teachers.services import TeacherQuotaService

    year = _make_year()
    teacher_user, students = _make_users(1)
    quota = TeacherQuota.objects.create(
        academic_year=year, teacher_id=teacher_user.id, max_quota=2
    )
    student_id = students[0].user_id

    barrier = threading.Barrier(2)
    results = [None, None]
    snapshot = (year.id, teacher_user.id)

    def lower_quota():
        TeacherQuotaService().update(quota.id, {"max_quota": 1})

    threads = [
        threading.Thread(
            name="allocate",
            target=_worker,
            kwargs={
                "index": 0,
                "results": results,
                "barrier": barrier,
                "snapshot": snapshot,
                "body": _allocate_body(year.id, student_id, teacher_user.id),
            },
        ),
        threading.Thread(
            name="lower-quota",
            target=_worker,
            kwargs={
                "index": 1,
                "results": results,
                "barrier": barrier,
                "snapshot": snapshot,
                "body": lower_quota,
            },
        ),
    ]
    _run_threads(threads)
    _assert_no_unexpected(results)
    assert _statuses(results) == ["ok", "ok"], f"两侧都应成功，实际={results!r}"

    quota.refresh_from_db()
    admitted = Admission.objects.filter(
        academic_year=year, teacher_id=teacher_user.id
    ).count()
    assert admitted <= quota.max_quota, (
        f"不变量被破坏：admitted={admitted} > max_quota={quota.max_quota}，结果={results!r}"
    )


def test_round2_concurrent_last_seat_yields_single_approved_application():
    """第二轮真正的并发『抢最后一个座位』（ApplicationService.create 端到端）。

    场景：quota=1，系统状态 SECOND_ROUND_OPEN，两个学生第一轮均 REJECTED，
    两个线程各自独立事务 + 普通快照读 + 栅栏后同时提交第二轮申请。

    期望：
    - 恰好 1 条 APPROVED 第二轮申请 + 恰好 1 条 ADMIT_ROUND2 录取
    - 失败方是**已知名额业务拒绝**（ADMISSION_QUOTA_FULL），不是任何其它异常
    - 失败方事务回滚，不留任何第二轮申请行（无半成品脏数据）
    """
    year = _make_year()
    teacher_user, students = _make_users(2)
    teacher = TeacherProfile.objects.get(pk=teacher_user.id)
    TeacherQuota.objects.create(academic_year=year, teacher_id=teacher_user.id, max_quota=1)
    _init_state(year, SystemStateValue.SECOND_ROUND_OPEN.value)

    # 两个学生第一轮均被拒绝（满足 R5 第二轮资格）
    for profile in students:
        Application.objects.create(
            academic_year=year,
            student=profile,
            teacher=teacher,
            round=ApplicationRound.FIRST_ROUND.value,
            status=ApplicationStatus.REJECTED.value,
        )

    barrier = threading.Barrier(2)
    results = [None, None]
    snapshot = (year.id, teacher_user.id)
    threads = [
        threading.Thread(
            name=f"round2-{i}",
            target=_worker,
            kwargs={
                "index": i,
                "results": results,
                "barrier": barrier,
                "snapshot": snapshot,
                "body": _round2_body(year.id, students[i], teacher),
            },
        )
        for i in range(2)
    ]
    _run_threads(threads)
    _assert_no_unexpected(results)

    round2_apps = Application.objects.filter(
        academic_year=year, round=ApplicationRound.SECOND_ROUND.value
    )
    assert round2_apps.count() == 1, (
        f"第二轮应恰好 1 条申请，实际 {round2_apps.count()}（超卖/重复）。结果={results!r}"
    )
    winner_app = round2_apps.get()
    assert winner_app.status == ApplicationStatus.APPROVED.value, (
        f"第二轮申请应直接 APPROVED（R3-02 先到先得），实际={winner_app.status}"
    )

    admissions = Admission.objects.filter(academic_year=year)
    assert admissions.count() == 1, (
        f"应恰好 1 条录取记录，实际 {admissions.count()}。结果={results!r}"
    )
    winner_admission = admissions.get()
    assert winner_admission.source == AdmissionSource.ADMIT_ROUND2.value
    assert winner_admission.application_id == winner_app.id
    assert winner_admission.student_id == winner_app.student_id

    assert _statuses(results).count("ok") == 1, f"应恰好一个线程成功，实际={results!r}"
    assert _rejected_error_codes(results) == [ErrorCode.ADMISSION_QUOTA_FULL], (
        "失败方必须是『名额已满』业务拒绝，实际="
        f"{_rejected_error_codes(results)!r}（全部结果={results!r}）"
    )

    # 回滚检查：失败方不得留下任何第二轮申请行（半成品）
    loser = next(s for s in students if s.user_id != winner_app.student_id)
    assert not Application.objects.filter(
        academic_year=year,
        student=loser,
        round=ApplicationRound.SECOND_ROUND.value,
    ).exists(), "失败方的第二轮申请未被回滚，留下了脏数据"
    assert not Admission.objects.filter(
        academic_year=year, student=loser
    ).exists(), "失败方不应有录取记录"


def test_round2_cancel_releases_exact_seat_then_other_student_claims_it():
    """approved2 取消后恰好释放一个座位，另一个符合条件的学生可立即抢占。

    同时验证取消路径仍然**只删除与该申请精确绑定的那条录取记录**
    （不按学生删除，避免误删人工/自动分配结果）。
    """
    year = _make_year()
    teacher_user, students = _make_users(2, suffix="2")
    teacher = TeacherProfile.objects.get(pk=teacher_user.id)
    TeacherQuota.objects.create(academic_year=year, teacher_id=teacher_user.id, max_quota=1)
    _init_state(year, SystemStateValue.SECOND_ROUND_OPEN.value)
    for profile in students:
        Application.objects.create(
            academic_year=year,
            student=profile,
            teacher=teacher,
            round=ApplicationRound.FIRST_ROUND.value,
            status=ApplicationStatus.REJECTED.value,
        )

    service = ApplicationService()
    first, second = students
    round2_payload = {
        "academic_year": year.id,
        "round": ApplicationRound.SECOND_ROUND.value,
        "teacher": teacher,
    }

    # 1. 第一个学生抢占座位
    app1 = service.create({**round2_payload, "student": first})
    assert app1.status == ApplicationStatus.APPROVED.value
    admission1 = Admission.objects.get(application_id=app1.id)
    assert admission1.source == AdmissionSource.ADMIT_ROUND2.value
    assert Admission.objects.filter(academic_year=year).count() == 1

    # 2. 名额已满：第二个学生被业务拒绝，且不留第二轮申请行
    with pytest.raises(BusinessException) as excinfo:
        service.create({**round2_payload, "student": second})
    assert getattr(excinfo.value, "default_code", None) == ErrorCode.ADMISSION_QUOTA_FULL
    assert not Application.objects.filter(
        academic_year=year,
        student=second,
        round=ApplicationRound.SECOND_ROUND.value,
    ).exists()

    # 3. 取消第二轮申请：恰好释放与该申请绑定的那一条录取记录
    cancelled = service.cancel_second_round(app1.id, operator_user=first.user)
    # Django clears the returned instance's primary key after delete().
    assert cancelled.student_id == first.user_id
    assert cancelled.round == ApplicationRound.SECOND_ROUND.value
    assert not Admission.objects.filter(pk=admission1.pk).exists(), (
        "取消第二轮申请必须删除与之精确关联的录取记录（释放恰好一个名额）"
    )
    assert not Application.objects.filter(pk=app1.pk).exists(), "取消后应删除该申请行"
    assert Admission.objects.filter(
        academic_year=year, teacher_id=teacher_user.id
    ).count() == 0, "取消后该导师本学年应为 0 条录取"

    # 4. 座位释放后，另一个符合条件的学生可以抢占
    app2 = service.create({**round2_payload, "student": second})
    assert app2.status == ApplicationStatus.APPROVED.value
    remaining = Admission.objects.filter(academic_year=year)
    assert remaining.count() == 1
    assert remaining.get().student_id == second.user_id
