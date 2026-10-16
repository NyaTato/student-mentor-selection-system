"""
Common 模块测试
"""
import pytest
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.common.enums import (
    AcademicYearStatus,
    ApplicationRound,
    ApplicationStatus,
    AdmissionSource,
    AutoAssignmentStatus,
    ImportRowStatus,
    ImportTaskStatus,
    OperationAction,
    StateTransitionType,
    SystemStateValue,
    UserRole,
    UserStatus,
)
from apps.common.error_codes import ErrorCode, get_http_status
from apps.common.exceptions import (
    BusinessException,
    ConflictError,
    NotFoundError,
    StateTransitionError,
    ValidationError,
)
from apps.common.repositories import BaseRepository, ReadOnlyRepository
from apps.common.response import ApiResponse
from apps.common.validators import (
    validate_academic_year_name,
    validate_chinese_name,
    validate_phone,
    validate_quota,
    validate_research_area,
    validate_student_number,
    validate_teacher_number,
)


class TestEnums:
    """枚举测试"""

    def test_user_role_choices(self):
        assert UserRole.STUDENT.value == 1
        assert UserRole.TEACHER.value == 2
        assert UserRole.ADMIN.value == 3

    def test_user_status_choices(self):
        assert UserStatus.ACTIVE.value == 1
        assert UserStatus.DISABLED.value == 2

    def test_system_state_value_choices(self):
        assert SystemStateValue.INIT.value == 0
        assert SystemStateValue.FIRST_ROUND_OPEN.value == 1
        assert SystemStateValue.TEACHER_REVIEW.value == 2
        assert SystemStateValue.SECOND_ROUND_OPEN.value == 3
        assert SystemStateValue.AUTO_ASSIGN.value == 4
        assert SystemStateValue.FINISHED.value == 5

    def test_application_round_choices(self):
        assert ApplicationRound.FIRST_ROUND.value == 1
        assert ApplicationRound.SECOND_ROUND.value == 2

    def test_application_status_choices(self):
        assert ApplicationStatus.PENDING.value == 1
        assert ApplicationStatus.APPROVED.value == 2
        assert ApplicationStatus.REJECTED.value == 3

    def test_academic_year_status_choices(self):
        assert AcademicYearStatus.INACTIVE.value == 0
        assert AcademicYearStatus.ACTIVE.value == 1
        assert AcademicYearStatus.ARCHIVED.value == 2

    def test_admission_source_choices(self):
        assert AdmissionSource.ADMIT_ROUND1.value == 1
        assert AdmissionSource.MANUAL.value == 3
        assert AdmissionSource.AUTO_ASSIGNED.value == 4

    def test_state_transition_type_choices(self):
        assert StateTransitionType.FORWARD.value == 1
        assert StateTransitionType.ROLLBACK.value == 2
        assert StateTransitionType.AUTO.value == 3

    def test_import_task_status_choices(self):
        assert ImportTaskStatus.PENDING.value == 0
        assert ImportTaskStatus.SUCCESS.value == 2
        assert ImportTaskStatus.FAILED.value == 4

    def test_import_row_status_choices(self):
        assert ImportRowStatus.SUCCESS.value == 1
        assert ImportRowStatus.FAILED.value == 2

    def test_auto_assignment_status_choices(self):
        assert AutoAssignmentStatus.RUNNING.value == 0
        assert AutoAssignmentStatus.SUCCESS.value == 1
        assert AutoAssignmentStatus.REVOKED.value == 4

    def test_operation_action_choices(self):
        assert OperationAction.LOGIN.value == 10
        assert OperationAction.STATE_FORWARD.value == 30
        assert OperationAction.CREATE_ACADEMIC_YEAR.value == 60


class TestErrorCodes:
    """错误码测试"""

    def test_success_code(self):
        assert ErrorCode.SUCCESS == 0

    def test_get_http_status_success(self):
        assert get_http_status(ErrorCode.SUCCESS) == 200

    def test_get_http_status_not_found(self):
        assert get_http_status(ErrorCode.NOT_FOUND) == 404

    def test_get_http_status_auth_failed(self):
        assert get_http_status(ErrorCode.AUTH_FAILED) == 401

    def test_get_http_status_permission_denied(self):
        assert get_http_status(ErrorCode.PERMISSION_DENIED) == 403

    def test_get_http_status_conflict(self):
        assert get_http_status(ErrorCode.CONFLICT) == 409

    def test_get_http_status_default(self):
        """未映射的错误码默认返回 400"""
        assert get_http_status(999999) == 400

    def test_module_error_codes(self):
        """模块错误码范围"""
        assert 20000 <= ErrorCode.USER_NOT_FOUND < 30000
        assert 30000 <= ErrorCode.STUDENT_NOT_FOUND < 40000
        assert 40000 <= ErrorCode.TEACHER_NOT_FOUND < 50000
        assert 50000 <= ErrorCode.APPLICATION_NOT_FOUND < 60000
        assert 80000 <= ErrorCode.ACADEMIC_YEAR_NOT_FOUND < 90000
        assert 90000 <= ErrorCode.SYSTEM_STATE_NOT_FOUND < 100000


class TestExceptions:
    """异常测试"""

    def test_business_exception(self):
        exc = BusinessException("测试错误", code=ErrorCode.BUSINESS_ERROR)
        assert str(exc.detail) == "测试错误"

    def test_not_found_error(self):
        exc = NotFoundError("资源不存在")
        assert "资源不存在" in str(exc.detail)

    def test_conflict_error(self):
        exc = ConflictError("资源冲突")
        assert "资源冲突" in str(exc.detail)

    def test_validation_error(self):
        exc = ValidationError("参数错误")
        assert "参数错误" in str(exc.detail)

    def test_state_transition_error(self):
        exc = StateTransitionError("状态不允许")
        assert "状态不允许" in str(exc.detail)


class TestApiResponse:
    """统一响应测试"""

    def test_success_response(self):
        resp = ApiResponse.success(data={"id": 1}, message="成功")
        assert resp.data["code"] == 0
        assert resp.data["message"] == "成功"
        assert resp.data["data"]["id"] == 1

    def test_error_response(self):
        resp = ApiResponse.error(code=ErrorCode.NOT_FOUND, message="未找到")
        assert resp.data["code"] == ErrorCode.NOT_FOUND
        assert resp.data["message"] == "未找到"

    def test_created_response(self):
        resp = ApiResponse.created(data={"id": 1}, message="创建成功")
        assert resp.data["code"] == 0
        assert resp.data["data"]["id"] == 1

    def test_no_content_response(self):
        resp = ApiResponse.no_content(message="删除成功")
        assert resp.data["code"] == 0


class TestValidators:
    """验证器测试"""

    def test_validate_student_number_valid(self):
        validate_student_number("20240001")  # 不抛异常即通过

    def test_validate_student_number_too_short(self):
        with pytest.raises(DjangoValidationError):
            validate_student_number("123")

    def test_validate_student_number_non_digit(self):
        with pytest.raises(DjangoValidationError):
            validate_student_number("2024abc0001")

    def test_validate_teacher_number_valid(self):
        validate_teacher_number("0001")

    def test_validate_teacher_number_alpha_invalid(self):
        with pytest.raises(DjangoValidationError):
            validate_teacher_number("T0001")

    def test_validate_teacher_number_too_long(self):
        with pytest.raises(DjangoValidationError):
            validate_teacher_number("12345678901")

    def test_validate_phone_valid(self):
        validate_phone("13812345678")

    def test_validate_phone_invalid(self):
        with pytest.raises(DjangoValidationError):
            validate_phone("12345678901")

    def test_validate_chinese_name_valid(self):
        validate_chinese_name("张三")

    def test_validate_chinese_name_empty(self):
        with pytest.raises(DjangoValidationError):
            validate_chinese_name("")

    def test_validate_chinese_name_too_short(self):
        with pytest.raises(DjangoValidationError):
            validate_chinese_name("a")

    def test_validate_academic_year_name_valid(self):
        validate_academic_year_name("2024-2025")

    def test_validate_academic_year_name_invalid_format(self):
        with pytest.raises(DjangoValidationError):
            validate_academic_year_name("2024/2025")

    def test_validate_academic_year_name_invalid_year(self):
        with pytest.raises(DjangoValidationError):
            validate_academic_year_name("2024-2026")

    def test_validate_quota_valid(self):
        validate_quota(5)

    def test_validate_quota_negative(self):
        with pytest.raises(DjangoValidationError):
            validate_quota(-1)

    def test_validate_quota_too_large(self):
        with pytest.raises(DjangoValidationError):
            validate_quota(100)

    def test_validate_research_area_valid(self):
        validate_research_area("人工智能")

    def test_validate_research_area_too_long(self):
        with pytest.raises(DjangoValidationError):
            validate_research_area("a" * 513)


class TestReadOnlyRepository:
    """只读 Repository 测试

    LSP 合规验证：ReadOnlyRepository（= ReadOnlyRepositoryBase）不暴露写方法。
    调用写方法应抛 AttributeError（方法不存在），而非 NotImplementedError。
    """

    def _make_repo(self):
        """创建一个绑定了 Model 的 ReadOnlyRepository"""
        from apps.logs.models import LoginLog

        class TestReadOnlyRepo(ReadOnlyRepository):
            model = LoginLog

        return TestReadOnlyRepo()

    def test_read_only_repository_no_create_method(self):
        """ReadOnlyRepository 不应有 create 方法"""
        repo = self._make_repo()
        assert not hasattr(repo, "create")

    def test_read_only_repository_no_update_method(self):
        """ReadOnlyRepository 不应有 update 方法"""
        repo = self._make_repo()
        assert not hasattr(repo, "update")

    def test_read_only_repository_no_soft_delete_method(self):
        """ReadOnlyRepository 不应有 soft_delete 方法"""
        repo = self._make_repo()
        assert not hasattr(repo, "soft_delete")

    def test_read_only_repository_no_hard_delete_method(self):
        """ReadOnlyRepository 不应有 hard_delete 方法"""
        repo = self._make_repo()
        assert not hasattr(repo, "hard_delete")

    def test_read_only_repository_has_query_methods(self):
        """ReadOnlyRepository 应有查询方法"""
        repo = self._make_repo()
        assert hasattr(repo, "get_by_id")
        assert hasattr(repo, "list")
        assert hasattr(repo, "filter")
        assert hasattr(repo, "exists")
        assert hasattr(repo, "count")

    def test_base_repository_has_write_methods(self):
        """BaseRepository 应有写方法"""
        from apps.common.repositories import BaseRepository
        from apps.logs.models import LoginLog

        class TestReadWriteRepo(BaseRepository):
            model = LoginLog

        repo = TestReadWriteRepo()
        assert hasattr(repo, "create")
        assert hasattr(repo, "update")
        assert hasattr(repo, "soft_delete")
        assert hasattr(repo, "hard_delete")
