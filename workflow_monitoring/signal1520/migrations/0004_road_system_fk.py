import django.db.models.deletion
from django.db import migrations, models


def create_roads_and_systems(apps, schema_editor):
    """
    Для каждой уникальной строки road создаём объект Road,
    для каждой непустой строки system — объект System.
    Затем проставляем FK на каждую станцию.
    """
    Station = apps.get_model('signal1520', 'Station')
    Road = apps.get_model('signal1520', 'Road')
    System = apps.get_model('signal1520', 'System')

    road_cache = {}
    system_cache = {}

    for station in Station.objects.all():
        road_title = station.road or ''
        if road_title not in road_cache:
            road_obj, _ = Road.objects.get_or_create(title=road_title)
            road_cache[road_title] = road_obj
        station.road_ref = road_cache[road_title]

        system_title = station.system or ''
        if system_title:
            if system_title not in system_cache:
                system_obj, _ = System.objects.get_or_create(title=system_title)
                system_cache[system_title] = system_obj
            station.system_ref = system_cache[system_title]
        else:
            station.system_ref = None

        station.save()


class Migration(migrations.Migration):

    dependencies = [
        ('signal1520', '0003_station_distance_station_system'),
    ]

    operations = [
        # 1. Создаём новые справочные таблицы
        migrations.CreateModel(
            name='Road',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100, verbose_name='Название')),
            ],
            options={
                'verbose_name': 'Дорога/линия/район',
                'verbose_name_plural': 'Дороги/линии/районы',
                'ordering': ['title'],
            },
        ),
        migrations.CreateModel(
            name='System',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=50, verbose_name='Название')),
            ],
            options={
                'verbose_name': 'Система',
                'verbose_name_plural': 'Системы',
                'ordering': ['title'],
            },
        ),
        # 2. Добавляем временные nullable FK-поля
        migrations.AddField(
            model_name='station',
            name='road_ref',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='stations',
                to='signal1520.road',
                verbose_name='Дорога/линия/район',
            ),
        ),
        migrations.AddField(
            model_name='station',
            name='system_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='stations',
                to='signal1520.system',
                verbose_name='Система',
            ),
        ),
        # 3. Переносим данные из старых CharField в новые FK
        migrations.RunPython(create_roads_and_systems, migrations.RunPython.noop),
        # 4. Делаем road_ref обязательным (null=False)
        migrations.AlterField(
            model_name='station',
            name='road_ref',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='stations',
                to='signal1520.road',
                verbose_name='Дорога/линия/район',
            ),
        ),
        # 5. Удаляем старые текстовые поля
        migrations.RemoveField(model_name='station', name='road'),
        migrations.RemoveField(model_name='station', name='system'),
        # 6. Переименовываем временные поля в финальные
        migrations.RenameField(model_name='station', old_name='road_ref', new_name='road'),
        migrations.RenameField(model_name='station', old_name='system_ref', new_name='system'),
    ]
