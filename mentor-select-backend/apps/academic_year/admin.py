from django.contrib import admin

from apps.academic_year.models import AcademicYear


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__"]
