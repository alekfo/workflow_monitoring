FROM python:3.12-slim

# Системные зависимости
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала копируем зависимости — слой кешируется если requirements не менялся
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Собираем статику
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Запускаем через gunicorn
CMD ["gunicorn", "workflow_monitoring.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
