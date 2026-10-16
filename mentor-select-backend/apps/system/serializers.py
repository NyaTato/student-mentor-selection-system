"""
系统状态序列化器
"""
from rest_framework import serializers

from apps.system.models import StateHistory, SystemState, SystemStateSchedule


class SystemStateSerializer(serializers.ModelSerializer):
    """系统状态序列化器"""

    current_state_display = serializers.CharField(
        source="get_current_state_display", read_only=True
    )
    previous_state_display = serializers.CharField(
        source="get_previous_state_display", read_only=True
    )
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )

    class Meta:
        model = SystemState
        fields = (
            "id",
            "academic_year",
            "academic_year_name",
            "current_state",
            "current_state_display",
            "previous_state",
            "previous_state_display",
            "state_changed_at",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "current_state",
            "previous_state",
            "state_changed_at",
            "version",
            "created_at",
            "updated_at",
            "academic_year_name",
            "current_state_display",
            "previous_state_display",
        )


class StateTransitionSerializer(serializers.Serializer):
    """状态推进/回退请求序列化器"""

    academic_year = serializers.IntegerField(required=True)
    reason = serializers.CharField(
        max_length=512,
        required=False,
        allow_blank=True,
        min_length=10,
        help_text="回退原因（推进时可不填，回退时必填且最少 10 字符）",
    )


class SystemStateScheduleSerializer(serializers.ModelSerializer):
    """自动状态切换配置序列化器"""

    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )

    class Meta:
        model = SystemStateSchedule
        fields = (
            "id",
            "academic_year",
            "academic_year_name",
            "first_round_start_at",
            "first_round_end_at",
            "teacher_review_end_at",
            "second_round_end_at",
            "auto_enabled",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "version",
            "created_at",
            "updated_at",
            "academic_year_name",
        )


class StateHistorySerializer(serializers.ModelSerializer):
    """状态变更历史序列化器"""

    from_state_display = serializers.CharField(
        source="get_from_state_display", read_only=True
    )
    to_state_display = serializers.CharField(
        source="get_to_state_display", read_only=True
    )
    transition_type_display = serializers.CharField(
        source="get_transition_type_display", read_only=True
    )
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    operator_name = serializers.SerializerMethodField()

    class Meta:
        model = StateHistory
        fields = (
            "id",
            "academic_year",
            "academic_year_name",
            "from_state",
            "from_state_display",
            "to_state",
            "to_state_display",
            "transition_type",
            "transition_type_display",
            "reason",
            "operator",
            "operator_name",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def get_operator_name(self, obj):
        if obj.operator is None:
            return None
        return obj.operator.username
