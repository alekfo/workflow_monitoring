from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import ActivityEvent, Task, TaskStatusChange, Station, Comment, Attachment, Knowledge, UserKnowledge, Link, Road, System, Organization, EquipmentType, Warehouse, Equipment


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


class TaskStatusChangeInline(admin.TabularInline):
    """История смены статусов: только просмотр, записи создаются при смене статуса"""
    model = TaskStatusChange
    extra = 0
    fields = readonly_fields = ('from_status', 'to_status', 'changed_by', 'changed_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TaskStatusChange)
class TaskStatusChangeAdmin(admin.ModelAdmin):
    """История смены статусов: только просмотр. Удаление оставлено, иначе админка не даст удалить задачу с историей"""
    list_display = 'pk', 'task', 'from_status', 'to_status', 'changed_by', 'changed_at'
    list_display_links = 'pk', 'task'
    list_filter = ('to_status', 'task__station__organization')
    search_fields = ('task__description', 'task__station__name', 'changed_by__username')
    ordering = ('-changed_at',)
    list_select_related = ('task__station', 'changed_by')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    """Лента изменений на главной: только просмотр и удаление"""
    list_display = 'pk', 'created_at', 'organization', 'user', 'kind', 'text'
    list_display_links = 'pk', 'created_at'
    list_filter = ('organization', 'kind')
    search_fields = ('text', 'user__username')
    ordering = ('-created_at',)
    list_select_related = ('organization', 'user')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    inlines = [TaskStatusChangeInline, CommentInline, AttachmentInline]

    def save_model(self, request, obj, form, change):
        # смена статуса через админку тоже попадает в историю
        if change and 'status' in form.changed_data:
            new_status = obj.status
            obj.status = form.initial['status']
            super().save_model(request, obj, form, change)
            obj.change_status(new_status, request.user)
        else:
            super().save_model(request, obj, form, change)

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