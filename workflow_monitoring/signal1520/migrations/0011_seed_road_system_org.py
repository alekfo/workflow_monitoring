from django.db import migrations


def seed_road_system_org(apps, schema_editor):
    Organization = apps.get_model('signal1520', 'Organization')
    Road = apps.get_model('signal1520', 'Road')
    System = apps.get_model('signal1520', 'System')

    try:
        org = Organization.objects.get(slug='signal1520')
    except Organization.DoesNotExist:
        return

    Road.objects.filter(organization__isnull=True).update(organization=org)
    System.objects.filter(organization__isnull=True).update(organization=org)


class Migration(migrations.Migration):

    dependencies = [
        ('signal1520', '0010_road_system_org_fk'),
    ]

    operations = [
        migrations.RunPython(seed_road_system_org, migrations.RunPython.noop),
    ]
