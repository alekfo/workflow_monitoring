import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signal1520', '0004_road_system_fk'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Удаляем поле updated_at (убрано из модели)
        migrations.RemoveField(
            model_name='knowledge',
            name='updated_at',
        ),
        # Добавляем user с временным default=1 для существующих строк
        migrations.AddField(
            model_name='knowledge',
            name='user',
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='knowledge',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Пользователь',
            ),
            preserve_default=False,
        ),
        # Обновляем Meta
        migrations.AlterModelOptions(
            name='knowledge',
            options={
                'ordering': ['-created_at'],
                'verbose_name': 'Инструкция',
                'verbose_name_plural': 'Инструкции',
            },
        ),
    ]
