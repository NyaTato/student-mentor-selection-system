from django.contrib import admin

from apps.assignments.models import Admission, AutoAssignmentLog


@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__"]


@admin.register(AutoAssignmentLog)
class AutoAssignmentLogAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__"]
