"""向 canonical StudentProfile 增加可空 phone 字段

v2 API（api/views/student.py）此前把 phone 写进 managed=False 的 legacy `student` 表。
统一到 canonical apps.students.StudentProfile 后，phone 需要作为正式字段存在。
设计决策：字段 nullable，兼容既有档案数据（无 phone 的历史学生档案不受影响）。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0002_alter_studentprofile_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="phone",
            field=models.CharField(
                "电话号码",
                max_length=20,
                null=True,
                blank=True,
            ),
        ),
    ]
