# AGENTS.md — workflow_monitoring / FieldLog

Проверено по исходникам 12.11.2026. Область действия: весь репозиторий.
Основа — CLAUDE.md; ниже собран рабочий контекст для следующих сессий.
При расхождении документации с кодом сначала проверь исходники и сообщи о расхождении.

## Обязательное согласование изменений

- Не создавай, не изменяй, не переименовывай и не удаляй файлы проекта без предварительного явного одобрения пользователя в терминале.
- Перед каждой записью покажи полный unified diff конкретного файла, включая новые файлы, и кратко объясни цель.
- Запроси отдельное подтверждение для каждого файла и каждой следующей правки. Поручение выполнить задачу само по себе не заменяет подтверждение diff.
- Применяй только одобренный diff. Если содержимое файла изменилось после просмотра, заново покажи diff и запроси подтверждение.
- Используй интерактивное подтверждение инструмента в терминале; не обходи его через другой инструмент или заранее разрешённый префикс.
- Если подтверждение недоступно, оставь изменения предложением и остановись до получения одобрения. Молчание не является согласием.
- Чтение и анализ разрешены. Команды, способные записать файлы проекта (форматирование, генерация миграций, тестовые артефакты), также требуют предварительного согласования.
- Сохраняй существующие незакоммиченные изменения. Не откатывай и не коммить их без отдельного указания.
- Перед записью прочитай навык .agents/skills/approved-file-edits/SKILL.md. Это правило действует и для AGENTS.md, CLAUDE.md и самих навыков.

## Структура и запуск

Корень Git — каталог с этим AGENTS.md, CLAUDE.md, FRONTEND.md, DEPLOY.md и .github/.
manage.py находится на уровень ниже: workflow_monitoring/manage.py.

- workflow_monitoring/workflow_monitoring/ — settings.py, urls.py, WSGI/ASGI.
- workflow_monitoring/signal1520/ — модели, формы, views, URL, admin, тесты, шаблоны и статика основного приложения.
- workflow_monitoring/authentication/ — стандартный Django User, профиль, вход, регистрация, смена и восстановление пароля.
- workflow_monitoring/templates/403.html — общая страница отказа в доступе.
- workflow_monitoring/nginx/nginx.conf, Dockerfile, docker-compose.yml — инфраструктура.
- .venv/ — локальное Python-окружение. Не считай системный Python окружением проекта.

В requirements.txt закреплён Django 6.0.3; локально 12.11.2026 установлен 6.0.4, Python 3.12.3.
CI использует Python 3.12 и устанавливает requirements.txt. Не меняй версии автоматически.
Для запуска требуется SECRET_KEY из окружения. Не выводи .env, ключи и пароли.

Команды из корня (с учётом согласования побочных записей):
```bash
.venv/bin/python workflow_monitoring/manage.py check
.venv/bin/python workflow_monitoring/manage.py test authentication --noinput
.venv/bin/python workflow_monitoring/manage.py test signal1520 authentication --noinput
```

Последняя проверка authentication: 18 тестов прошли 12.11.2026.
Полный набор в этой сессии не запускался; не выдавай старое количество тестов из CLAUDE.md за актуальное.
CI сейчас запускает только signal1520, а не authentication.

## Организации и доступ

URL основного приложения: /<org_slug>/; аутентификация: /accounts/; админка: /admin/; защищённые файлы: /media/.
OrgMixin в signal1520/mixins.py ставится перед LoginRequiredMixin:
dispatch проверяет организацию пользователя, get_queryset фильтрует данные.
Суперпользователь проходит проверку принадлежности; фильтр queryset по организации URL сохраняется.

- Organization: name и уникальный slug.
- Road, System — nullable FK на организацию; Station, EquipmentType, Warehouse — прямые FK.
- Task фильтруется через station__organization; Equipment — через warehouse__organization.
- Profile.organization может быть пустым. Новая регистрация создаёт User + Profile без организации.
- Пользователи и выпадающие списки форм должны оставаться ограниченными своей организацией.
- AlarmInfo — глобальный справочник; Knowledge/UserKnowledge — личные инструкции.
- org_slug добавляет context processor: из URL, а на /accounts/ — из профиля.
- Для reverse и {% url %} маршрутов signal1520 передавай org_slug; во views есть org_kwargs().
- Несовпадение организаций даёт OrgAccessDenied → 403. Чужие профили и недоступные файлы скрываются за 404.
- _visible_users(): сам пользователь и участники своей организации; без организации — только сам; суперпользователь — все.

## Основные сущности и ограничения

Task связан со Station; TaskStatusChange хранит историю; ActivityEvent — события организации.
Comment привязан к задаче, редактируется автором 24 часа, удаления через интерфейс нет.
Attachment хранит файлы в tasks/task_<id>/.
Knowledge содержит файл или внешнюю ссылку, UserKnowledge — личные название и описание.
Equipment принадлежит Warehouse, опционально Station, и имеет EquipmentType; удаление используемого типа запрещено.
Profile расширяет User: организация, bio, avatar, лимит файлов инструкций (10), согласие с политикой, дата/IP/версия согласия.

Статус задачи меняй через Task.change_status(new_status, user); допустимость перехода проверяет вызывающий код через allowed_statuses().
Новая → В работе/Выполнена/Отменена; В работе → Выполнена/Отменена.
Закрытую задачу переоткрывает только суперпользователь, только в «В работе»; вернуть в «Новая» нельзя.
Править закрытую задачу может суперпользователь, добавлять вложения нельзя никому до переоткрытия; комментарии доступны.
TaskInline в админке станции пока обходит историю статусов — известное ограничение, не исправлять попутно.
ActivityEvent.log() вызывается явно, без сигналов; главная выбирает последние 40 событий.
При удалении автора станции сохраняются (created_by=SET_NULL); учитывай None.

## Аутентификация и пароли

OrgLoginView игнорирует ?next: после входа направляет на главную организации, без организации — на профиль.
Регистрация открытая, автоматически выполняет вход; организацию и права назначает администратор.
Защита регистрации: honeypot website, 5 попыток с IP в час через cache, запрет временных email.
django-axes: 5 неудачных попыток входа, блокировка username на час.
Восстановление пароля не снимает блокировку axes автоматически.

Смена известного пароля: /accounts/password_change/, CustomPasswordChangeView.
Требует входа и текущего пароля; текущая сессия сохраняется; после успеха — профиль.

Восстановление забытого пароля (добавлено 12.11.2026, на эту дату ещё не закоммичено):
1. /accounts/password-reset/ — PasswordRecoveryView / PasswordResetView, ввод email и отправка письма.
2. /accounts/password-reset/done/ — информационная страница с одинаковым ответом для существующего и неизвестного email.
3. /accounts/password-reset/<uidb64>/<token>/ — PasswordRecoveryConfirmView / PasswordResetConfirmView, проверка ссылки и установка пароля.
4. /accounts/password-reset/complete/ — сообщение об успехе, ссылка на вход.

Django использует PasswordResetForm и SetPasswordForm, штатный token_generator и валидаторы пароля.
Письмо получают активные пользователи с подходящим email и пригодным паролем.
uidb64 — кодирование ID, token — подписанный токен; смена пароля делает ссылку непригодной для повторного использования.
При открытии Django сохраняет токен в сессии и заменяет его в адресе на set-password.
PASSWORD_RESET_TIMEOUT=3600; автоматического входа после восстановления нет.
Русские формы и CSS-классы задаёт RussianAuthFormMixin; шаблоны password_reset_* используют отдельный password_reset_base.html.
SMTP уже используется регистрацией. DEFAULT_FROM_EMAIL=EMAIL_HOST_USER, EMAIL_TIMEOUT=10.
SECURE_PROXY_SSL_HEADER учитывает X-Forwarded-Proto, который перезаписывает Nginx; Gunicorn не должен быть доступен в обход доверенного proxy.
Доставку через реальный SMTP не проверяли. Отдельного ограничения частоты запросов восстановления пока нет.
User.email не уникален: несколько аккаунтов с одним адресом могут получить отдельные письма. Не вводи уникальность без согласования.

## Медиа и безопасность

ProtectedMediaView проверяет доступ по точному пути и записи в БД.
Задачи: своя организация + view_task; инструкции: личная связь UserKnowledge или автор; аватар: доступ как к профилю.
DEBUG=True: FileResponse; production: X-Accel-Redirect в Nginx location /protected-media/ (internal).
Не добавляй прямую раздачу MEDIA_ROOT. Для нового FileField нужна ветка проверки доступа.
Inline разрешены JPG, PNG, GIF, WebP, PDF; потенциально активные документы скачиваются; сохраняй nosniff.
Для недоступного файла — 404. Дубликаты станций выводятся через DOM/textContent, не innerHTML.

Политика: authentication/templates/authentication/privacy_policy.html; POLICY_VERSION=2.0 в views.py.
При согласованной правке политики обновляй версию и дату шаблона и POLICY_VERSION.
Упомянутого в CLAUDE.md файла privacy_policy.md в корне сейчас нет; не считай его доступным источником.

## Интерфейс

Перед фронтенд-задачей прочитай FRONTEND.md.
Django Templates, обычные страницы и ссылки; Vanilla JS/CSS, без npm, фреймворков и CDN.
Каркас — signal1520/base.html, фиксированная шапка, sidebar.js и _sidebar.html, футер.
Страницы профиля используют каркас; вход, регистрация, восстановление, политика, блокировка и 403 — отдельные экраны.
org_slug нужен ссылкам меню; новый URL раздела добавляй в условие подсветки is-current.
Не переиспользуй глобальные классы каркаса в стилях отдельных страниц.
styles.css — каркас; styles_stations.css — таблицы и списки; auth_styles.css — аутентификация.
Бирюзовые кнопки #0f8f93, hover #0b777b; фон #d5e0e5 → #5fcaca; шапки карточек #14a3a5 → #34545b.
Не возвращай тёмную рамку и отвергнутые варианты из FRONTEND.md. Варианты внешнего вида показывай до согласованной записи кода.
Адаптив: 768px; поиск и пагинация — GET. StationListView, BugsListView, MyBugsListView, AlarmListView, WarehouseListView, EquipmentListView — по 10.
WarehouseDetailView использует отдельный Paginator по 10. Отчёты и графики пока заглушки.

## Деплой

SQLite локально; DATABASE_URL=postgres включает PostgreSQL; Docker Compose содержит db (PostgreSQL 16), web и nginx.
web при старте выполняет migrate, collectstatic, затем Gunicorn.
GitHub Actions проверяет PR/push в main/release; push в main запускает деплой после тестов.
Деплой сохраняет дамп и логи, выполняет git pull и пересобирает web; не запускай его без указания пользователя.
Nginx терминирует TLS для fieldlog.ru/www.fieldlog.ru; после правок его конфигурации нужен restart контейнера.
ALLOWED_HOSTS и CSRF_TRUSTED_ORIGINS читаются из окружения; для HTTPS нужны доверенные origins обоих доменов.
Подробнее — DEPLOY.md; сверяй команды с текущим docker-compose.yml и .github/workflows/ci.yml.
