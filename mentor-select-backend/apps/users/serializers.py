"""
认证序列化器
JWT 登录、用户信息序列化
"""
from django.contrib.auth.password_validation import validate_password as django_validate_password
from rest_framework import serializers

from apps.common.enums import UserRole
from apps.users.models import AdminProfile, User


class LoginSerializer(serializers.Serializer):
    """登录序列化器

    仅做字段声明和基本校验，实际认证由 AuthService.login 完成。
    """

    username = serializers.CharField(max_length=64, required=True)
    password = serializers.CharField(
        max_length=128,
        required=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )

    def validate(self, attrs):
        # 基本非空校验由 required=True 完成
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """用户序列化器"""

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )
    # H2: 系统生成的随机密码，仅创建时返回一次给管理员
    generated_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "password",
            "role",
            "role_display",
            "status",
            "status_display",
            "is_active",
            "date_joined",
            "generated_password",
        )
        read_only_fields = ("id", "date_joined", "is_active", "generated_password")

    def get_generated_password(self, obj):
        """返回系统生成的随机密码（仅创建时存在，不持久化）"""
        return getattr(obj, "_generated_password", None)

    def validate_password(self, value):
        """使用 Django 密码强度校验器（空值跳过，由 Service 生成随机密码）"""
        if not value:
            return value
        django_validate_password(value)
        return value

    def validate_username(self, value):
        """用户名格式校验"""
        if not value or not value.strip():
            raise serializers.ValidationError("用户名不能为空")
        if len(value) > 64:
            raise serializers.ValidationError("用户名长度不能超过 64")
        return value

    def validate_role(self, value):
        """角色必须为合法值"""
        if value not in [choice.value for choice in UserRole]:
            raise serializers.ValidationError("角色非法")
        return value

    def create(self, validated_data):
        # 委托给 Service（ViewSet.perform_create 会调用 service.create）
        # 这里保留直接创建逻辑以保持向后兼容
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserUpdateSerializer(serializers.ModelSerializer):
    """用户更新序列化器（密码可选）"""

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        style={"input_type": "password"},
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "password",
            "role",
            "role_display",
            "status",
            "status_display",
        )
        read_only_fields = ("id",)

    def validate_password(self, value):
        if value:
            django_validate_password(value)
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class RefreshTokenRequestSerializer(serializers.Serializer):
    """刷新 Token 请求体序列化器

    缺少 / 空白 ``refresh`` 属于**请求格式错误** → 400（ValidationError），
    而不是 401。401 只保留给「token 无效 / 已过期 / 账号不可用」。
    """

    refresh = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=False,
    )


class ChangePasswordSerializer(serializers.Serializer):
    """修改密码序列化器"""

    old_password = serializers.CharField(
        required=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )
    new_password = serializers.CharField(
        required=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )

    def validate_new_password(self, value):
        django_validate_password(value)
        return value

    def validate(self, attrs):
        if attrs.get("old_password") == attrs.get("new_password"):
            raise serializers.ValidationError(
                {"new_password": "新密码不能与原密码相同"}
            )
        return attrs


class AdminProfileSerializer(serializers.ModelSerializer):
    """管理员档案序列化器"""

    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = AdminProfile
        fields = (
            "user",
            "name",
            "username",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
        )
        read_only_fields = ("version", "created_at", "updated_at", "deleted_at", "username")


class UserProfileSerializer(serializers.Serializer):
    """当前用户完整信息序列化器

    包含基础用户信息及角色对应的档案信息
    """

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    role = serializers.IntegerField(read_only=True)
    role_display = serializers.CharField(read_only=True)
    status = serializers.IntegerField(read_only=True)
    status_display = serializers.CharField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    # 角色对应的档案信息
    student_profile = serializers.SerializerMethodField()
    teacher_profile = serializers.SerializerMethodField()
    admin_profile = serializers.SerializerMethodField()

    def get_student_profile(self, obj):
        if obj.role != UserRole.STUDENT.value:
            return None
        profile = getattr(obj, "student_profile", None)
        if profile is None:
            return None
        return {
            "student_number": profile.student_number,
            "name": profile.name,
            "major": profile.major,
            "class_name": profile.class_name,
        }

    def get_teacher_profile(self, obj):
        if obj.role != UserRole.TEACHER.value:
            return None
        profile = getattr(obj, "teacher_profile", None)
        if profile is None:
            return None
        return {
            "teacher_number": profile.teacher_number,
            "name": profile.name,
            "college": profile.college,
            "title": profile.title,
            "research_area": profile.research_area,
        }

    def get_admin_profile(self, obj):
        if obj.role != UserRole.ADMIN.value:
            return None
        profile = getattr(obj, "admin_profile", None)
        if profile is None:
            return None
        return {
            "name": profile.name,
        }
