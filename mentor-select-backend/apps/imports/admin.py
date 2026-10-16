from django.contrib import admin

from apps.imports.models import ImportLog, ImportTask


@admin.register(ImportTask)
class ImportTaskAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__"]


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__"]
