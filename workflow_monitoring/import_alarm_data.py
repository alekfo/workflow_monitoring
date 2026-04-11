import csv
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'workflow_monitoring.settings')
django.setup()

from signal1520.models import AlarmInfo

def import_alarm_data(csv_path='/app/alarm_data.csv'):
    created_count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        for row in reader:
            if len(row) >= 3:
                number = row[0].strip()
                description = row[1].strip()
                explanation = row[2].strip()
                
                obj, created = AlarmInfo.objects.get_or_create(
                    number=number,
                    defaults={
                        'description': description,
                        'explanation': explanation
                    }
                )
                
                if created:
                    created_count += 1
                    print(f"✓ Добавлен Alarm {number}")
    
    print(f"\nИмпортировано {created_count} записей")

if __name__ == '__main__':
    import_alarm_data()
