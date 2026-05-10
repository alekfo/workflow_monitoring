# Деплой на сервер с HTTPS

## Предварительные требования

- Сервер с Ubuntu 22.04
- Установлены: Docker, Docker Compose, git
- Куплен домен, в DNS-настройках регистратора прописаны A-записи:
  - `@` → IP сервера
  - `www` → IP сервера

---

## Структура на сервере

```
/home/alek_fo/
├── workflow_monitoring_git/        ← git clone репозитория
│   └── workflow_monitoring/        ← здесь docker-compose.yml
│       ├── docker-compose.yml
│       ├── .env                    ← создать вручную (не в git)
│       └── nginx/
│           └── nginx.conf
├── dumps/                          ← создать вручную
└── logs/                           ← создать вручную
```

---

## Шаг 1 — Клонировать репозиторий

```bash
git clone <url-репозитория> /home/alek_fo/workflow_monitoring_git
mkdir -p /home/alek_fo/dumps /home/alek_fo/logs
```

---

## Шаг 2 — Создать .env

```bash
cp /home/alek_fo/workflow_monitoring_git/workflow_monitoring/.env.example \
   /home/alek_fo/workflow_monitoring_git/workflow_monitoring/.env
nano /home/alek_fo/workflow_monitoring_git/workflow_monitoring/.env
```

Заполнить обязательные поля:

```env
SECRET_KEY=<случайная строка 50+ символов>
DEBUG=False
ALLOWED_HOSTS=fieldlog.ru,www.fieldlog.ru,localhost
CSRF_TRUSTED_ORIGINS=https://fieldlog.ru,https://www.fieldlog.ru

DATABASE_URL=postgres
DB_NAME=workflow_db
DB_USER=workflow_user
DB_PASSWORD=<надёжный пароль>
DB_HOST=db
DB_PORT=5432
```

---

## Шаг 3 — Убедиться что DNS работает

Перед получением сертификата домен должен резолвиться в IP сервера:

```bash
nslookup fieldlog.ru
# Должно вернуть IP сервера, а не NXDOMAIN
```

Если NXDOMAIN — ждать, DNS распространяется до 24 часов (обычно 15–60 минут).

---

## Шаг 4 — Получить SSL-сертификат (один раз)

Certbot должен занять порт 80, поэтому nginx нужно остановить:

```bash
# Если контейнеры уже запущены — остановить nginx
docker compose -f /home/alek_fo/workflow_monitoring_git/workflow_monitoring/docker-compose.yml stop nginx

# Установить certbot (если ещё нет)
sudo apt update && sudo apt install -y certbot

# Получить сертификат
sudo certbot certonly --standalone -d fieldlog.ru -d www.fieldlog.ru
```

Сертификат сохранится в `/etc/letsencrypt/live/fieldlog.ru/` автоматически.

---

## Шаг 5 — Запустить все контейнеры

```bash
cd /home/alek_fo/workflow_monitoring_git/workflow_monitoring
docker compose up -d
```

Проверить что всё запустилось:

```bash
docker compose ps
```

Все три контейнера (`db`, `web`, `nginx`) должны быть в статусе `running`.

---

## Шаг 6 — Настроить автообновление сертификата (один раз)

Сертификаты Let's Encrypt живут 90 дней. Crontab продлевает их автоматически:

```bash
sudo crontab -e
```

Добавить строку:

```
0 3 1 * * docker compose -f /home/alek_fo/workflow_monitoring_git/workflow_monitoring/docker-compose.yml stop nginx && certbot renew --quiet && docker compose -f /home/alek_fo/workflow_monitoring_git/workflow_monitoring/docker-compose.yml start nginx
```

---

## Последующие деплои

Выполняются автоматически через GitHub Actions при пуше в `main`.
Вручную (если нужно):

```bash
cd /home/alek_fo/workflow_monitoring_git
git pull origin main
cd workflow_monitoring
docker compose build --no-cache web
docker compose up -d
```

---

## Ключевые настройки

### docker-compose.yml — nginx-сервис

```yaml
nginx:
  image: nginx:alpine
  restart: always
  ports:
    - "80:80"      # HTTP (редирект на HTTPS)
    - "443:443"    # HTTPS
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    - static_files:/app/static:ro
    - media_files:/app/media:ro
    - /etc/letsencrypt:/etc/letsencrypt:ro       # сертификаты Let's Encrypt
    - /var/www/certbot:/var/www/certbot:ro        # ACME-challenge для обновления
  depends_on:
    - web
```

### nginx/nginx.conf — структура

```nginx
upstream django {
    server web:8000;
}

# Блок 1: весь HTTP → редирект на HTTPS
# server_name _  означает "поймать любой хост" — включая прямой доступ по IP
server {
    listen 80;
    server_name _;

    # Пропускаем ACME-challenge для обновления сертификата без даунтайма
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://fieldlog.ru$request_uri;
    }
}

# Блок 2: HTTPS — основной сервер
server {
    listen 443 ssl;
    server_name fieldlog.ru www.fieldlog.ru;

    ssl_certificate     /etc/letsencrypt/live/fieldlog.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/fieldlog.ru/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    client_max_body_size 20M;

    location /static/ {
        alias /app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # internal — Nginx отдаёт файлы только по X-Accel-Redirect от Django
    location /protected-media/ {
        internal;
        alias /app/media/;
    }

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

---

## Диагностика

```bash
# Логи nginx
docker compose logs nginx

# Логи Django
docker compose logs web

# Проверить сертификат
sudo certbot certificates

# Проверить DNS
nslookup fieldlog.ru
nslookup fieldlog.ru 8.8.8.8   # через Google DNS

# Перезапустить nginx без пересборки (после правки nginx.conf)
docker compose restart nginx
```