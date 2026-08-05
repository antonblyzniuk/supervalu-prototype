from django.contrib import admin

from .models import Docket, DocketLine, DocketPhoto, DocketSignature


class DocketLineInline(admin.TabularInline):
    model = DocketLine
    extra = 0


class DocketSignatureInline(admin.TabularInline):
    model = DocketSignature
    extra = 0


class DocketPhotoInline(admin.TabularInline):
    model = DocketPhoto
    extra = 0


@admin.register(Docket)
class DocketAdmin(admin.ModelAdmin):
    list_display = ("docket_type", "store", "effective_date", "reference", "total", "created_at")
    list_filter = ("docket_type", "store", "created_at")
    search_fields = ("reference", "docket_number", "supplier", "manager_name")
    date_hierarchy = "created_at"
    autocomplete_fields = ()
    inlines = (DocketLineInline, DocketSignatureInline, DocketPhotoInline)
    readonly_fields = ("total", "created_at", "updated_at")
