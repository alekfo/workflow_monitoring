from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('signal1520', '0014_equipment_factory_fields'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='comment',
            options={'ordering': ['created_at'], 'verbose_name': 'Комментарий', 'verbose_name_plural': 'Комментарии'},
        ),
    ]
