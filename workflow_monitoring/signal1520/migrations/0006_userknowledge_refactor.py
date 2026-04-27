import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_to_user_knowledge(apps, schema_editor):
    Knowledge = apps.get_model('signal1520', 'Knowledge')
    UserKnowledge = apps.get_model('signal1520', 'UserKnowledge')
    for k in Knowledge.objects.all():
        if k.user_id:
            UserKnowledge.objects.get_or_create(
                user_id=k.user_id,
                knowledge=k,
                defaults={
                    'title': k.title or '',
                    'description': k.description or '',
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('signal1520', '0005_knowledge_user_alter_knowledge_meta'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Создаём UserKnowledge
        migrations.CreateModel(
            name='UserKnowledge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Название')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')),
                ('knowledge', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='user_knowledge',
                    to='signal1520.knowledge',
                    verbose_name='Материал',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='user_knowledge',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Пользователь',
                )),
            ],
            options={
                'verbose_name': 'Инструкция пользователя',
                'verbose_name_plural': 'Инструкции пользователей',
                'ordering': ['-created_at'],
                'unique_together': {('user', 'knowledge')},
            },
        ),
        # 2. Переносим существующие данные
        migrations.RunPython(migrate_to_user_knowledge, migrations.RunPython.noop),
        # 3. Убираем старые поля из Knowledge
        migrations.RemoveField(model_name='knowledge', name='user'),
        migrations.RemoveField(model_name='knowledge', name='title'),
        migrations.RemoveField(model_name='knowledge', name='description'),
        # 4. Обновляем Meta
        migrations.AlterModelOptions(
            name='knowledge',
            options={
                'verbose_name': 'Файл/ссылка базы знаний',
                'verbose_name_plural': 'Файлы/ссылки базы знаний',
                'ordering': ['-created_at'],
            },
        ),
    ]
