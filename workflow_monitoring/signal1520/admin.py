from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import Task, Station, Comment, Attachment, Knowledge, UserKnowledge, Link, Road, System, Organization, EquipmentType, Warehouse, Equipment


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = 'pk', 'name', 'slug'
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ('user', 'body', 'created_at')
    readonly_fields = ('created_at',)


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ('file', 'description', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = 'pk', 'task', 'user', 'short_body', 'created_at'
    list_display_links = 'pk', 'task'
    search_fields = ('body', 'user__username', 'task__description')
    ordering = ('-created_at',)

    @admin.display(description='Текст')
    def short_body(self, obj):
        return (obj.body or '')[:60] + ('...' if obj.body and len(obj.body) > 60 else '')


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = 'pk', 'task', 'description', 'uploaded_at'
    list_display_links = 'pk', 'task'
    search_fields = ('description', 'task__description')
    ordering = ('-uploaded_at',)


class UserKnowledgeInline(admin.TabularInline):
    model = UserKnowledge
    extra = 0
    fields = ('user', 'title', 'description', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Knowledge)
class KnowledgeAdmin(admin.ModelAdmin):
    list_display = 'pk', 'created_by', 'file', 'external_link', 'created_at'
    list_display_links = 'pk',
    search_fields = ('file', 'external_link', 'created_by__username')
    ordering = ('-created_at',)
    inlines = [UserKnowledgeInline]


@admin.register(Road)
class RoadAdmin(admin.ModelAdmin):
    list_display = 'pk', 'organization', 'title'
    list_filter = ('organization',)
    search_fields = ('title',)
    ordering = ('organization', 'title')


@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = 'pk', 'organization', 'title'
    list_filter = ('organization',)
    search_fields = ('title',)
    ordering = ('organization', 'title')

class TaskInline(admin.TabularInline):
    """Inline для отображения задач на странице станции"""
    model = Task  # Прямое указание модели
    extra = 1  # Количество пустых форм для добавления
    fields = ('description', 'status', 'responsible_organization',
              'responsible_user', 'due_date')
    show_change_link = True  # Ссылка на полное редактирование


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    inlines = [CommentInline, AttachmentInline]

    list_display = "pk", "station", "short_description", "status", "responsible_organization", "responsible_user", "created_at", "due_date", "updated_at"
    list_display_links = "pk", "station"
    ordering = "-pk",
    search_fields = "station__name", "status"

    @admin.display(description='Описание')
    def short_description(self, obj):
        if len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description

    def get_queryset(self, request):
        return Task.objects.select_related('responsible_user', 'station')

@admin.register(EquipmentType)
class EquipmentTypeAdmin(admin.ModelAdmin):
    list_display = 'pk', 'organization', 'title'
    list_filter = ('organization',)
    search_fields = ('title',)
    ordering = ('organization', 'title')


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = 'pk', 'title', 'organization', 'responsible_user', 'created_at'
    list_display_links = 'pk', 'title'
    list_filter = ('organization',)
    search_fields = ('title',)
    ordering = ('organization', 'title')


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = 'pk', 'type', 'warehouse', 'station', 'added_at'
    list_display_links = 'pk', 'type'
    list_filter = ('warehouse', 'type')
    search_fields = ('type__title', 'warehouse__title', 'station__name')
    ordering = ('-added_at',)


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    inlines = [
        TaskInline
    ]

    list_display = "pk", "name", "road", "distance", "system", "latitude", "longitude", "created_at", "created_by"
    list_display_links = "pk", "name"
    ordering = "pk",
    search_fields = "name", "road__title", "system__title"