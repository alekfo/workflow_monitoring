from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import Task, Station, Comment, Attachment, Knowledge, Link

class TaskInline(admin.TabularInline):
    """Inline для отображения задач на странице станции"""
    model = Task  # Прямое указание модели
    extra = 1  # Количество пустых форм для добавления
    fields = ('description', 'status', 'responsible_organization',
              'responsible_user', 'due_date')
    show_change_link = True  # Ссылка на полное редактирование


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):

    list_display = "pk", "station", "description", "status", "responsible_organization", "responsible_user", "created_at", "due_date", "updated_at"
    list_display_links = "pk", "station"
    ordering = "-pk",
    search_fields = "station__name", "status"

    def get_queryset(self, request):
        return Task.objects.select_related('responsible_user', 'station')

@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    inlines = [
        TaskInline
    ]

    list_display = "pk", "name", "road", "description", "latitude", "longitude", "created_at", "created_by"
    list_display_links = "pk", "name"
    ordering = "pk",
    search_fields = "name", "road"