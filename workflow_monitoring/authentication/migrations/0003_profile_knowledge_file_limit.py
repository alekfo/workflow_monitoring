from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_add_can_view_users_list_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='knowledge_file_limit',
            field=models.PositiveSmallIntegerField(default=10, verbose_name='Лимит файлов инструкций'),
        ),
    ]
