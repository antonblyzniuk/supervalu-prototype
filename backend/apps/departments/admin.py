from django.contrib import admin

from .models import Department, StoreDepartment


class StoreDepartmentInline(admin.TabularInline):
    model = StoreDepartment
    extra = 0
    fields = ("store", "manager", "slug")
    readonly_fields = ("slug",)
    autocomplete_fields = ("manager",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "description")
    readonly_fields = ("slug",)
    inlines = (StoreDepartmentInline,)


@admin.register(StoreDepartment)
class StoreDepartmentAdmin(admin.ModelAdmin):
    list_display = ("department", "store", "manager")
    list_filter = ("store", "department")
    search_fields = ("department__name", "department__code", "store__name")
    autocomplete_fields = ("manager", "department")
    readonly_fields = ("slug",)
