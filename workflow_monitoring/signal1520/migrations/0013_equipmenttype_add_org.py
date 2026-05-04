from django.db import migrations, models
import django.db.models.deletion


def assign_org_to_existing_types(apps, schema_editor):
    Organization = apps.get_model('signal1520', 'Organization')
    EquipmentType = apps.get_model('signal1520', 'EquipmentType')
    try:
        org = Organization.objects.get(slug='signal1520')
        EquipmentType.objects.filter(organization__isnull=True).update(organization=org)
    except Organization.DoesNotExist:
        pass


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('signal1520', '0012_warehouse_equipment'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipmenttype',
            name='organization',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='equipment_types',
                to='signal1520.organization',
                verbose_name='Организация',
            ),
        ),
        migrations.RunPython(assign_org_to_existing_types, noop),
        migrations.AlterField(
            model_name='equipmenttype',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='equipment_types',
                to='signal1520.organization',
                verbose_name='Организация',
            ),
        ),
    ]