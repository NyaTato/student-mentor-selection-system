from django.contrib import admin

from apps.teachers.models import TeacherProfile, TeacherQuota


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "__str__"]


@admin.register(TeacherQuota)
class TeacherQuotaAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__"]
