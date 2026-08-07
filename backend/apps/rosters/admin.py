from django.contrib import admin

from .models import Shift


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("date", "user", "store", "start_time", "end_time", "break_minutes")
    list_filter = ("store", "date", "break_paid")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)
    date_hierarchy = "date"
