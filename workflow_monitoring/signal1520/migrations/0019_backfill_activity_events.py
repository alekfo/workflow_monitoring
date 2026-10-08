from django.db import migrations

STATUS_LABELS = {
    'new': 'Новая',
    'in_progress': 'В работе',
    'completed': 'Выполнена',
    'cancelled': 'Отменена',
}


def backfill(apps, schema_editor):
    """Заполняет ленту событиями из уже существующих данных, чтобы на выкате она не была пустой.
    У задач и вложений автор не хранится — такие события остаются без пользователя.
    Строки собираются так же, как в ActivityEvent.build_text."""
    ActivityEvent = apps.get_model('signal1520', 'ActivityEvent')
    Station = apps.get_model('signal1520', 'Station')
    Task = apps.get_model('signal1520', 'Task')
    TaskStatusChange = apps.get_model('signal1520', 'TaskStatusChange')
    Comment = apps.get_model('signal1520', 'Comment')
    Attachment = apps.get_model('signal1520', 'Attachment')

    events = []

    for station in Station.objects.all():
        events.append(ActivityEvent(
            organization_id=station.organization_id, kind='station_created', user_id=station.created_by_id,
            station_id=station.pk, text=f'Объект «{station.name}» — создан'[:300], created_at=station.created_at,
        ))

    def task_event(task, kind, action, created_at, user_id=None):
        return ActivityEvent(
            organization_id=task.station.organization_id, kind=kind, user_id=user_id,
            task_id=task.pk, station_id=task.station_id,
            text=f'Задача #{task.pk}, {task.station.name} — {action}'[:300], created_at=created_at,
        )

    for task in Task.objects.select_related('station'):
        events.append(task_event(task, 'task_created', 'создана', task.created_at))
    for change in TaskStatusChange.objects.select_related('task__station'):
        label = STATUS_LABELS.get(change.to_status, change.to_status)
        events.append(task_event(change.task, 'task_status', f'статус «{label}»', change.changed_at, change.changed_by_id))
    for comment in Comment.objects.select_related('task__station'):
        events.append(task_event(comment.task, 'task_comment', 'добавлен комментарий', comment.created_at, comment.user_id))
    for attachment in Attachment.objects.select_related('task__station'):
        events.append(task_event(attachment.task, 'task_attachment', 'добавлено вложение', attachment.uploaded_at))

    ActivityEvent.objects.bulk_create(events, batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('signal1520', '0018_activity_event'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
