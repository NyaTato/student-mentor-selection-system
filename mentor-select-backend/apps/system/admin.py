from django.contrib import admin

from apps.system.models import StateHistory, SystemState, SystemStateSchedule


@admin.register(SystemState)
class SystemStateAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__"]


@admin.register(SystemStateSchedule)
class SystemStateScheduleAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__"]


@admin.register(StateHistory)
class StateHistoryAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__"]
