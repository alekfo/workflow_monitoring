# CLAUDE.md — Контекст проекта workflow_monitoring

## Что это за проект

Django-приложение для мониторинга рабочих процессов на объектах (станциях).
Основные сущности: объекты (станции), задачи, алармы (справочник), склады, оборудование, пользователи.
Интерфейс — обычные серверные страницы с общим каркасом `base.html`: шапка с логотипом, слева панель значков меню, по клику на значок вправо выезжают кнопки разделов, переход в раздел — обычная ссылка.
Поддерживает несколько организаций (мультиарендность) через URL-префикс `/<org_slug>/`.

---

## Структура проекта

```
workflow_monitoring/        ← корень git-репозитория, здесь лежит manage.py
├── workflow_monitoring/    ← настройки Django (settings.py, urls.py)
├── signal1520/             ← основное приложение
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── mixins.py           ← OrgMixin: проверка доступа и фильтрация по org
│   ├── context_processors.py ← инжектирует org_slug в каждый шаблон
│   ├── templates/signal1520/
│   └── static/signal1520/
│       ├── css/
│       │   ├── styles.css           ← глобальные стили (подключён в base.html)
│       │   └── styles_stations.css  ← стили таблиц, кнопок, пагинации (подключён в base.html)
│       └── js/
│           ├── sidebar.js           ← левая панель значков: раскрытие/сворачивание разделов
│           └── stations.js          ← initTasksToggle (раскрытие задач на станции)
└── authentication/         ← приложение аутентификации
```

---

## Мультиарендность (multi-org архитектура)

### Идея

Каждая организация имеет уникальный `slug` (например, `signal1520`, `metro2024`).
Все URL приложения начинаются с `/<org_slug>/`. Добавить новую организацию = создать запись в БД, никакого кода писать не нужно.

### Как это устроено

**1. Модель `Organization` (signal1520/models.py)**
```python
class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
```

**2. FK на Organization в смежных моделях**
- `Road.organization` — FK → Organization (nullable)
- `System.organization` — FK → Organization (nullable)
- `Station.organization` — FK → Organization
- `EquipmentType.organization` — FK → Organization (обязательный)
- `Warehouse.organization` — FK → Organization (обязательный)
- `Profile.organization` (authentication/models.py) — FK → Organization (через строковую ссылку `'signal1520.Organization'` во избежание circular import)
- Task не имеет прямого FK — фильтруется через `station__organization`
- Equipment не имеет прямого FK — фильтруется через `warehouse__organization`

**3. URL-конфиг (workflow_monitoring/urls.py)**
```python
path('<slug:org_slug>/', include('signal1520.urls')),
```
Все маршруты signal1520 автоматически получают параметр `org_slug` из URL.

**4. OrgMixin (signal1520/mixins.py)**
Примешивается ко всем view в signal1520. Делает три вещи:
- `get_org()` — получает объект Organization по `self.kwargs['org_slug']` (кешируется в `self._org`)
- `dispatch()` — проверяет принадлежность к организации; анонимов пропускает (их перехватит LoginRequiredMixin), суперюзер проходит всегда
- `get_queryset()` — фильтрует QS по организации через `org_filter_field` (по умолчанию `'organization'`)

Для задач, у которых нет прямого FK на орг: `org_filter_field = 'station__organization'`.

**5. Context processor (signal1520/context_processors.py)**
Зарегистрирован в `settings.TEMPLATES`. Автоматически добавляет `{{ org_slug }}` в контекст каждого шаблона — не нужно передавать его вручную из каждого view.
Берёт slug из kwargs URL; на страницах вне org-контекста (`/accounts/...`) — из `request.user.profile.organization`,
чтобы общий каркас мог строить ссылки меню. Пустая строка означает «организации нет».

**6. Шаблоны**
Все `{% url %}` теги используют `org_slug=org_slug`:
```html
{% url 'signal1520:bug_details' pk=bug.pk org_slug=org_slug %}
```

**7. Меню**
Ссылки меню, логотипа и футера строятся в шаблонах (`_sidebar.html`, `base.html`) через `{% url %}` с `org_slug=org_slug`.
JavaScript URL-ы не собирает, переменной `window.ORG_SLUG` больше нет.

---

## Флоу: как определяется принадлежность пользователя к организации

**Пример:** пользователь `vasya` заходит на `/signal1520/bugs/`.

### Шаг 1 — URL resolve
Django сопоставляет `/signal1520/bugs/` с паттерном `<slug:org_slug>/bugs/`.
В `kwargs` появляется `{'org_slug': 'signal1520', 'pk': ...}`.

### Шаг 2 — OrgMixin.dispatch()
`BugsListView` наследует `OrgMixin`. Django вызывает `dispatch(request, org_slug='signal1520')`.

```python
def dispatch(self, request, *args, **kwargs):
    if request.user.is_authenticated and not request.user.is_superuser:
        try:
            if request.user.profile.organization != self.get_org():
                raise PermissionDenied
        except PermissionDenied:
            raise
        except Exception:
            raise PermissionDenied
    return super().dispatch(request, *args, **kwargs)
```

Анонимный пользователь — пропускается мимо (`is_authenticated = False`), его перехватит `LoginRequiredMixin` следующим в MRO.
`get_org()` делает `get_object_or_404(Organization, slug='signal1520')` — находит орг в БД.
Затем сравнивает объект `vasya.profile.organization` с найденным объектом орг (Django сравнивает по pk).
Если не совпадает — `403 Forbidden`.

### Шаг 3 — OrgMixin.get_queryset()
Если доступ разрешён, фильтрует данные:
```python
def get_queryset(self):
    return super().get_queryset().filter(**{self.org_filter_field: self.get_org()})
```
Для `BugsListView` поле `org_filter_field = 'station__organization'`, поэтому запрос:
```sql
SELECT * FROM task WHERE task.station_id IN (
    SELECT id FROM station WHERE station.organization_id = <signal1520.id>
)
```
Vasya видит только задачи своей организации.

### Шаг 4 — Context processor
При рендеринге шаблона context processor добавляет `org_slug = 'signal1520'`.
Все `{% url %}` теги в шаблоне генерируют правильные ссылки вида `/signal1520/...`.

### Шаг 5 — Меню
Ссылки меню в `_sidebar.html` уже отрендерены сервером: `/signal1520/bugs/`, `/signal1520/stations/` и т.д.

---

### Исключения из org-фильтрации

| View | Причина |
|------|---------|
| `AlarmListView` | `AlarmInfo` — глобальный справочник, не привязан к орг |
| `KnowledgeListView` | Инструкции привязаны к пользователю, не к орг |
| `KnowledgeCreateView` / `KnowledgeDeleteView` | То же; у них `get(**kwargs)`, `post(**kwargs)` принимают лишние kwargs явно |

### Фильтрация выпадающих списков в формах

`get_form()` переопределён в view, чтобы пользователь видел в дропдаунах
только объекты своей организации:

| View | Поле формы | Фильтр |
|------|-----------|--------|
| `StationCreateView` | `road`, `system` | `Road/System.objects.filter(organization=org)` |
| `StationUpdateView` | `road`, `system` | то же |
| `BugCreateView` | `station` | `Station.objects.filter(organization=org)` |
| `BugUpdateView` | `station` | то же |
| `WarehouseCreateView` | `responsible_user` | `User.objects.filter(profile__organization=org)` |
| `WarehouseUpdateView` | `responsible_user` | то же |
| `EquipmentCreateView` | `warehouse`, `station`, `type` | `Warehouse/Station/EquipmentType.objects.filter(organization=org)` |
| `EquipmentUpdateView` | `warehouse`, `station`, `type` | то же |

---

### Как добавить новую организацию

1. В Django admin (или через shell) создать `Organization(name='Metro 2024', slug='metro2024')`
2. Назначить дороги: `Road.objects.filter(...).update(organization=new_org)`
3. Назначить системы: `System.objects.filter(...).update(organization=new_org)`
4. Назначить станции: `Station.objects.filter(...).update(organization=new_org)`
5. Назначить пользователей: `profile.organization = new_org; profile.save()`
6. Создать типы оборудования: `EquipmentType.objects.create(organization=new_org, title='...')`
7. Создать склады: `Warehouse.objects.create(organization=new_org, title='...')`
8. Готово — `/<metro2024>/` работает без изменений кода

---

## Модели (signal1520/models.py)

| Модель | Описание |
|--------|----------|
| `Organization` | Организация. Поля: name, slug(unique). FK из Station, Road, System и Profile |
| `Road` | Справочник дорог/линий/районов. Поля: id, organization(FK, nullable), title. FK из Station.road |
| `System` | Справочник систем. Поля: id, organization(FK, nullable), title. FK из Station.system (nullable) |
| `Station` | Объект/станция. Поля: name, road(FK), distance, system(FK, nullable), description, latitude, longitude, created_by(FK User, nullable, `SET_NULL`), organization(FK) |
| `Task` | Задача. Поля: station(FK), description, status(new/in_progress/completed/cancelled), responsible_organization, responsible_user(FK User), due_date. Статус меняется только через `Task.change_status()` — см. «Статусы задач» |
| `TaskStatusChange` | История смены статусов задачи. Поля: task(FK), from_status, to_status, changed_by(FK User, `SET_NULL`), changed_at. Последняя запись — `task.last_status_change` |
| `ActivityEvent` | Событие ленты «Последние изменения» на главной. Поля: organization(FK), kind, user(FK, `SET_NULL`), task(FK, `SET_NULL`), station(FK, `SET_NULL`), text (готовая строка), created_at. Пишется через `ActivityEvent.log()` — см. «Лента изменений» |
| `Comment` | Комментарий к задаче. Поля: task(FK), user(FK), body. Автор может править свой комментарий 24 часа после создания (`Comment.EDIT_WINDOW`, `can_be_edited_by`); изменённый помечается «изменён» (`is_edited`). Удаления нет |
| `Attachment` | Вложение к задаче. Файлы хранятся в `tasks/task_<id>/` внутри MEDIA_ROOT |
| `AlarmInfo` | Справочник алармов. Поля: number(PK), description, explanation. Данные загружаются скриптом migrate_alarms.py |
| `Knowledge` | Единица базы знаний: файл (`file`, путь `knowledge/<filename>`) или внешняя ссылка (`external_link`). Один объект может быть привязан к нескольким пользователям через `UserKnowledge` |
| `UserKnowledge` | Связь User ↔ Knowledge с пользовательскими метаданными: title, description. `unique_together = [('user', 'knowledge')]` |
| `EquipmentType` | Справочник типов оборудования. Поля: organization(FK), title. Фильтруется по орг |
| `Warehouse` | Склад. Поля: organization(FK), title, responsible_user(FK User, nullable), created_at |
| `Equipment` | Единица оборудования. Поля: warehouse(FK), station(FK, nullable), type(FK EquipmentType), factory_number, manufacturer, date_of_manufacture, added_at |
| `Link` | Ссылки пользователей (в разработке) |

## Модель Profile (authentication/models.py)

`Profile` расширяет стандартного `User` через `OneToOneField`.

| Поле | Тип | Описание |
|------|-----|----------|
| `bio` | TextField | Краткая информация о пользователе |
| `agreement_accepted` | BooleanField | Принятие пользовательского соглашения |
| `consent_given_at` | DateTimeField | Дата и время согласия на обработку ПД (ставится при регистрации) |
| `consent_ip` | GenericIPAddressField | IP, с которого дано согласие |
| `consent_policy_version` | CharField | Версия политики на момент согласия (`POLICY_VERSION` из `authentication/views.py`) |
| `avatar` | ImageField | Аватар, хранится в `user/user_<pk>/avatar/` |
| `knowledge_file_limit` | PositiveSmallIntegerField | Максимальное число файлов-инструкций для пользователя (default=10) |
| `organization` | FK → Organization | Принадлежность к организации (nullable). Ссылка через строку `'signal1520.Organization'` |

Разрешение `can_view_users_list` объявлено в `Profile.Meta.permissions`.

---

## URL-маршруты

Все маршруты signal1520 имеют вид `/<org_slug>/...` и требуют параметр `org_slug` при реверсе.

| URL | View | Имя |
|-----|------|-----|
| `/<org_slug>/` | TasksIndexView | `signal1520:index` |
| `/<org_slug>/bugs/` | BugsListView | `signal1520:bugs_list` |
| `/<org_slug>/bugs/my/` | MyBugsListView | `signal1520:bugs_list_my` |
| `/<org_slug>/bugs/<pk>/` | BugDetailView | `signal1520:bug_details` |
| `/<org_slug>/bugs/create/` | BugCreateView | `signal1520:create_bug` |
| `/<org_slug>/bugs/<pk>/update/` | BugUpdateView | `signal1520:bug_update` |
| `/<org_slug>/stations/` | StationListView | `signal1520:station_list` |
| `/<org_slug>/stations/<pk>/` | StationDetailView | `signal1520:station_details` |
| `/<org_slug>/stations/create/` | StationCreateView | `signal1520:create_station` |
| `/<org_slug>/stations/<pk>/update/` | StationUpdateView | `signal1520:station_update` |
| `/<org_slug>/stations/export/` | StationsExportView | `signal1520:stations_export` |
| `/<org_slug>/bugs/export/` | TasksExportView | `signal1520:bugs_export` |
| `/<org_slug>/alarms/` | AlarmListView | `signal1520:alarm_list` |
| `/<org_slug>/knowledge/` | KnowledgeListView | `signal1520:knowledge_list` |
| `/<org_slug>/knowledge/create/` | KnowledgeCreateView | `signal1520:knowledge_create` |
| `/<org_slug>/knowledge/<pk>/delete/` | KnowledgeDeleteView | `signal1520:knowledge_delete` |
| `/<org_slug>/warehouses/` | WarehouseListView | `signal1520:warehouse_list` |
| `/<org_slug>/warehouses/create/` | WarehouseCreateView | `signal1520:warehouse_create` |
| `/<org_slug>/warehouses/<pk>/` | WarehouseDetailView | `signal1520:warehouse_detail` |
| `/<org_slug>/warehouses/<pk>/update/` | WarehouseUpdateView | `signal1520:warehouse_update` |
| `/<org_slug>/warehouses/<pk>/export/` | WarehouseEquipmentExportView | `signal1520:warehouse_equipment_export` |
| `/<org_slug>/equipment/` | EquipmentListView | `signal1520:equipment_list` |
| `/<org_slug>/equipment/create/` | EquipmentCreateView | `signal1520:equipment_create` |
| `/<org_slug>/equipment/<pk>/` | EquipmentDetailView | `signal1520:equipment_detail` |
| `/<org_slug>/equipment/<pk>/update/` | EquipmentUpdateView | `signal1520:equipment_update` |
| `/<org_slug>/equipment/types/create/` | EquipmentTypeCreateView | `signal1520:equipment_type_create` |
| `/<org_slug>/equipment/export/` | EquipmentExportView | `signal1520:equipment_export` |
| `/accounts/...` | authentication app | login, logout, register, profile |

---

## Навигация: шапка и панель значков (sidebar.js)

Правила работы над интерфейсом, дизайн-система и контракты разметки — в `FRONTEND.md` в корне репозитория.
Читать перед любой фронт-задачей.

Каждая страница — обычная полноценная страница: шаблон наследует `signal1520/base.html`,
переход между разделами — обычная ссылка с перезагрузкой. Подгрузки контента через AJAX
(`contentPanel`, `loadContentPanel`, `executeScripts`) больше нет.

Общий каркас `base.html` используют и страницы signal1520, и страницы профиля из `authentication`
(`about_me`, `profile_update_form`, `password_change_form`, `users_list`, `user_detail`).
Вне каркаса остаются `login`, `register`, `locked_out`, `privacy_policy` и карточка «Нет прав» — отдельные экраны.

**«Нет прав»** — один шаблон `templates/403.html` на все случаи. Его рендерят `handler403`
(`workflow_monitoring/urls.py`) и `ErrorView` (`/accounts/error/`, куда редиректят view с `handle_no_permission`).
Флаг `wrong_org` переключает текст: чужая организация (`OrgAccessDenied` из `mixins.py`) или нехватка прав в своей.

**Шапка** (`.site-header`, фиксированная): слева текстовый логотип FieldLog — ссылка на главную
организации (без организации — на профиль), справа «Имя | Организация» и ссылка «Выйти».
**Футер**: ссылка «Связаться с поддержкой» (только при наличии организации).

**Панель значков** (`_sidebar.html`, `.side-rail`) закреплена слева под шапкой. Значки — inline SVG
(`.rail-icon`, обводка `currentColor`). Клик по значку раскрывает вправо ряд кнопок-разделов
(`.rail-flyout`) той же высоты, что и значок, **поверх** страницы; контент не сдвигается.
Клик мимо или `Escape` сворачивает меню обратно до значков. Логика — в `sidebar.js`
(переключает `aria-expanded` на кнопке и класс `is-open` на ряду).

| Значок | Разделы (ссылки) |
|--------|------------------|
| Задачи | `bugs_list`, `bugs_list_my`, `create_bug` |
| Объекты | `station_list`, `create_station` |
| Учет оборудования | `warehouse_list`, `equipment_list` |
| Отчеты, Графики | «В разработке» (неактивный пункт) |
| База знаний | `alarm_list`, `knowledge_list`, `knowledge_create` |
| Мой профиль | `authentication:about_me`, `profile_update`, `users_list` (при праве `can_view_users_list`) |
| Настройки | `authentication:password_change`, `privacy_policy` |

Разделы организации (первые пять строк) показываются только при непустом `org_slug`.
У пользователя без организации в меню только «Мой профиль» и «Настройки».

Значок текущего раздела подсвечивается классом `is-current` — он вычисляется в `_sidebar.html`
по `request.resolver_match.url_name`. **При добавлении нового маршрута** в раздел нужно дописать
его имя в соответствующую строку `{% if name in '...' %}`, иначе значок не подсветится.

### Как устроен шаблон страницы
```html
{% extends 'signal1520/base.html' %}
{% block title %}...{% endblock %}
{% block extra_head %}<!-- свои <style> и <script src> -->{% endblock %}
{% block content %}
<div class="page-content"> ... </div>
{% endblock %}
```
`.page-content` растягивает содержимое на всю ширину справа от панели (`.main-layout` — flex-контейнер).
Классы каркаса (`.logo`, `.logout-btn`, `.rail-*`, `.flyout-link`) глобальные — в `<style>` страниц
их имена переиспользовать нельзя.

### Поиск и пагинация
Работают без JavaScript: форма поиска — обычный `GET` на текущий URL (`?search=`),
кнопки пагинации — обычные ссылки `?page=N&search=...`, «Сбросить» — ссылка `?`.

### Инициализация скриптов
Скрипты страниц выполняются один раз при загрузке, поэтому inline `<script>` в шаблонах допустим.
`stations.js` и `instructions.js` сами вызывают свои `init...()` на `DOMContentLoaded`.

---

## Пагинация

| View | paginate_by |
|------|-------------|
| `BugsListView` | 10 |
| `AlarmListView` | 10 |
| `MyBugsListView` | не включена |
| `WarehouseListView` | 10 |
| `EquipmentListView` | 10 |
| `WarehouseDetailView` | 10 (equipment_page через Paginator вручную) |

Кнопки пагинации используют классы `.pagination-btn` и `.pagination-info` из `styles_stations.css`.

---

## CSS-архитектура

Основные цвета: `#00B7B7` (бирюзовый) и `#333333` (тёмно-серый). Фиолетовый (`#667eea`) нигде не используется.

`styles_stations.css` подключён в `signal1520/base.html` — загружается один раз для всего приложения.
Стили каркаса (`.site-header`, `.logo`, `.side-rail`, `.rail-btn`, `.rail-flyout`, `.flyout-link`) лежат в `styles.css`; размеры — переменные `--header-height`, `--rail-width`, `--rail-btn-size`, на них же завязаны отступы `body`.

---

## Статусы задач

Статус меняется только на карточке задачи (`BugDetailView`, JSON POST) и в админке; из формы
`BugUpdateView` поле `status` убрано. Каждая смена идёт через `Task.change_status(new_status, user)`,
который пишет запись в `TaskStatusChange`. На карточке под статусом показывается последний переход:
дата, время и кто его сделал. У задач, закрытых до появления истории (миграция `0017`), подписи нет.

Допустимые переходы — `Task.allowed_statuses(user)`:

| Из статуса | Куда | Кто |
|------------|------|-----|
| Новая | В работе, Выполнена, Отменена | суперпользователь, `change_task`, ответственный (`Task.can_be_managed_by`) |
| В работе | Выполнена, Отменена | те же |
| Выполнена, Отменена | В работе | только суперпользователь |

В «Новая» вернуть задачу нельзя никому. Недопустимый переход — `403` с текстом ошибки в JSON.

Выполненная и отменённая задача (`Task.is_closed`) закрыта: `BugUpdateView` отдаёт 403 всем, кроме суперпользователя;
загрузка вложения — 403 всем, включая суперпользователя (чтобы добавить файл, он сначала возвращает задачу в работу).
Кнопки и форма вложения на карточке показываются неактивными.
Комментарии к закрытой задаче остаются открытыми — так решено (например, «дефект проявился снова»).

В админке история — раздел «Смены статусов задач» и inline на странице задачи, оба только для просмотра
(добавление и правка запрещены, удаление оставлено, иначе не удалить задачу с историей). Видит его только суперпользователь.

У `TaskStatusChange` нет собственных прав (`default_permissions = ()`): право менять статус — это `change_task`
(«Can change Задача»), и лишние «Can change Смена статуса задачи» в админке с ним путали.

Не закрыто: смена статуса через inline задач на странице станции в админке (`TaskInline`) в историю не попадает.

---

## Лента изменений на главной

Под плитками сводки `TasksIndexView` показывает последние события организации из `ActivityEvent`.

| Событие (`kind`) | Где пишется | Кто видит |
|------------------|-------------|-----------|
| `task_created` | `BugCreateView.form_valid` | `view_task` |
| `task_status` | `Task.change_status` (карточка задачи и админка) | `view_task` |
| `task_comment` | `BugDetailView.post` | `view_task` |
| `task_attachment` | `BugDetailView.post` | `view_task` |
| `station_created` | `StationCreateView.form_valid` | `view_station` |

- Запись делает код явно, через `ActivityEvent.log(kind, user, task=... | station=...)`, а не сигналы:
  сигнал не знает пользователя. Новое ключевое событие = новый `Kind`, строка в `build_text` и вызов `log()`.
- Текст события — готовая строка без текста комментариев («Задача #25, Бутырская — добавлен комментарий»).
  После удаления задачи или объекта событие остаётся, но перестаёт быть ссылкой.
- Правка комментария, правка задачи, учёт оборудования и создание задач/объектов через админку в ленту не попадают.
- Вьюха отдаёт `ACTIVITY_LIMIT = 40` последних; сколько из них показать, решает вёрстка (см. `FRONTEND.md`).
- Миграция `0019` один раз заполнила ленту из существующих данных; у прошлых событий создания задач
  и вложений автора нет (он не хранился) — в ленте вместо имени «—».
- Своих прав у модели нет (`default_permissions = ()`), в админке — только просмотр и удаление.

---

## Раздел Инструкции (Knowledge)

`KnowledgeListView` — список инструкций текущего пользователя.
Шаблон `knowledge_list.html` разделяет вывод на два блока: `docs` (записи с файлом) и `links` (записи с внешней ссылкой).

`KnowledgeCreateView` — форма добавления инструкции. Требует право `signal1520.add_userknowledge`.
Без права — редирект на `/accounts/error/`. Поддерживает три способа:
- загрузить новый файл
- выбрать уже загруженный файл (существующий `Knowledge` с файлом)
- добавить внешнюю ссылку

Перед сохранением файла проверяет лимит: `request.user.profile.knowledge_file_limit` (fallback = 10).

`KnowledgeDeleteView` — AJAX-удаление (`POST /<org_slug>/knowledge/<pk>/delete/`). Требует право `signal1520.delete_userknowledge`. Без права — `JsonResponse({'error': '...'}, status=403)`. Удаляет `UserKnowledge`. Физически удаляет файл и объект `Knowledge` только если больше ни один пользователь на него не ссылается.

---

## Раздел Учёт оборудования (Warehouses & Equipment)

### Модели

`EquipmentType` — справочник типов оборудования, привязан к организации. Заполняется через `EquipmentTypeCreateView` или Django admin. Нельзя удалить, если есть привязанное оборудование (`on_delete=PROTECT`).

`Warehouse` — склад. Привязан к организации. Может иметь ответственного пользователя. В дропдауне `responsible_user` показываются только пользователи той же орг.

`Equipment` — единица оборудования. Привязана к складу (обязательно) и к объекту/станции (опционально). Имеет заводской номер, изготовителя, дату изготовления. Org-фильтрация идёт через `warehouse__organization`.

### View-архитектура

`WarehouseListView` — список складов. `org_filter_field='organization'` (дефолтное). Поиск по названию, имени ответственного.

`WarehouseDetailView` — карточка склада. Пагинированный список оборудования (10 шт.) реализован вручную через `Paginator` в `get_context_data`, а не через `paginate_by` (View — DetailView, не ListView).

`EquipmentListView` — сводный список всего оборудования организации. `org_filter_field='warehouse__organization'`. Поиск по типу, складу, станции.

`EquipmentDetailView` — карточка единицы оборудования. `org_filter_field='warehouse__organization'`.

`EquipmentTypeCreateView` — после создания типа редиректит на `signal1520:index` (не на список), показывает сообщение через `messages.success`.

### Права доступа

| Право | Где проверяется |
|-------|----------------|
| `signal1520.view_warehouse` | WarehouseListView, WarehouseDetailView |
| `signal1520.add_warehouse` | WarehouseCreateView; `can_add_warehouse` в контексте WarehouseListView |
| `signal1520.change_warehouse` | WarehouseUpdateView; `can_edit` в контексте WarehouseDetailView |
| `signal1520.view_equipment` | EquipmentListView, EquipmentDetailView, экспорты |
| `signal1520.add_equipment` | EquipmentCreateView; `can_add_equipment` в контексте WarehouseDetailView и EquipmentListView |
| `signal1520.change_equipment` | EquipmentUpdateView; `can_edit` в контексте EquipmentDetailView |
| `signal1520.add_equipmenttype` | EquipmentTypeCreateView; `can_add_type` в контексте EquipmentListView |

### Экспорт в .xlsx

`EquipmentExportView` — выгружает всё оборудование организации (`GET /<org_slug>/equipment/export/`).
`WarehouseEquipmentExportView` — выгружает оборудование конкретного склада (`GET /<org_slug>/warehouses/<pk>/export/`). Перед выгрузкой проверяет, что склад принадлежит организации через `get_object_or_404(Warehouse, pk=pk, organization=self.get_org())`.

### Навигация в меню

В меню (значок 📦) — ссылки на список складов и список оборудования.
Создание склада, создание оборудования, создание типа — кнопки на самих страницах списков.

---

## Разделы в разработке (заглушки)

В меню значки «Отчёты» и «Графики» раскрывают единственный неактивный пункт «В разработке».

---

## Аутентификация

Приложение `authentication` — кастомная реализация.
`LoginRequiredMixin` используется на всех view.
Права доступа через `UserPassesTestMixin` и `has_perm()`.

Корневой URL `/` редиректит на `/accounts/login/` через `RedirectView` в `workflow_monitoring/urls.py`.

**`OrgLoginView`** (наследует `LoginView`) — после успешного логина редиректит на `/<org_slug>/`,
а не на `?next` из URL. Если у пользователя нет организации — редирект на `about_me`.
`redirect_authenticated_user = True`: уже аутентифицированный пользователь, зашедший на
`/accounts/login/`, сразу перенаправляется по той же логике.

### Флоу регистрации нового пользователя

Регистрация открытая, но новый пользователь не может войти в орг без назначения администратором.

```
POST /accounts/register/
  → RegisterView создаёт User + Profile (без organization)
  → автоматически логинит пользователя
  → get_success_url(): org == None → редирект на /accounts/about_me/

/accounts/about_me/
  → если profile.organization == None → показывается плашка-предупреждение
    «Ожидайте подтверждения регистрации и определения необходимых прав»
  → в меню только «Мой профиль» и «Настройки»

Администратор в Django admin назначает organization пользователю.

  → пользователь логинится → OrgLoginView.get_success_url() → /<org_slug>/
  → плашка исчезает, в меню появляются разделы организации
```

Страницы профиля лежат вне org-контекста (`/accounts/...`), но используют общий каркас:
`org_slug` для них context processor берёт из профиля пользователя. Пока организации нет,
в меню только «Мой профиль» и «Настройки», а логотип ведёт на профиль.

---

## Безопасность

### Защита от брутфорса — django-axes

Подключён `django-axes==8.3.1`. После **5 неудачных попыток входа** аккаунт блокируется на **1 час** (затем снимается автоматически). Блокировка по `username` — ротация IP атакующим не помогает.

Три точки подключения в `settings.py`:
- `INSTALLED_APPS`: `'axes'`
- `MIDDLEWARE`: `'axes.middleware.AxesMiddleware'` — после `AuthenticationMiddleware`
- `AUTHENTICATION_BACKENDS`: `AxesStandaloneBackend` первым, затем `ModelBackend`

Управление блокировками — Django admin → раздел **AXES → Access Attempts**. Удалить запись = разблокировать пользователя немедленно.

При блокировке показывается шаблон `authentication/templates/authentication/locked_out.html`.

### Защита медиафайлов (IDOR)

Медиафайлы (вложения к задачам, файлы базы знаний) **не отдаются Nginx напрямую**. Все запросы к `/media/` проходят через `ProtectedMediaView` (`signal1520/views.py`), который требует аутентификации (`LoginRequiredMixin`).

В продакшне используется `X-Accel-Redirect`: Django проверяет авторизацию → отправляет заголовок → Nginx отдаёт файл из внутреннего location `/protected-media/` (`internal`).

В разработке (`DEBUG=True`) — `FileResponse` напрямую из Django.

Маршрут в `workflow_monitoring/urls.py`: `path('media/<path:path>', ProtectedMediaView.as_view())`.

**Не закрыто:** `ProtectedMediaView` проверяет только аутентификацию, но не организацию — аватар (`user/user_<pk>/avatar/`) или вложение чужой организации доступны любому вошедшему пользователю, знающему путь.

### Доступ к профилям пользователей

`UserDetailView` (`/accounts/user/<pk>/`) и `UsersListView` (`/accounts/users/`) берут queryset из `_visible_users(viewer)` (`authentication/views.py`): сам пользователь + участники его организации. Суперпользователь видит всех, пользователь без организации — только себя. Чужой профиль отдаёт **404, а не 403** — чтобы перебором `pk` нельзя было узнать, какие id существуют. До 02.10.2026 проверки организации не было, и при открытой регистрации любой мог перебором увидеть имя, фамилию и email любого пользователя. Тесты — `authentication/tests.py`.

### Удаление пользователя

`Station.created_by` — `SET_NULL` (миграция `signal1520/0016`). Раньше был `CASCADE`: удаление пользователя (в т.ч. по запросу на удаление персональных данных) уносило созданные им станции вместе с задачами и вложениями. `Task.responsible_user`, `Comment.user`, `Knowledge.created_by`, `Warehouse.responsible_user` — тоже `SET_NULL`; `UserKnowledge.user` и `Link.user` — `CASCADE` (личные записи). Код, читающий `station.created_by`, должен учитывать `None` (см. `StationsExportView`).

### XSS-защита в JavaScript

- `station_form.html` / `station_update_form.html`: список дубликатов станций строится через DOM API (`createElement` + `textContent`), не через конкатенацию строк в `innerHTML`

### Защита регистрации от ботов

Реализована в `authentication/forms.py`, `authentication/views.py` и шаблоне `register.html`. Три уровня:

**1. Honeypot-поле** (`website` в `CustomUserCreationForm`) — невидимое поле, скрытое через CSS (`.hp-field`: `position: absolute; left: -9999px`). Простые боты заполняют все `<input>` формы — `clean_website()` отклоняет форму при непустом значении. Поле исключено из видимого цикла шаблона и рендерится отдельно с `aria-hidden="true"`.

**2. Rate limiting по IP** — `RegisterView.post()` проверяет счётчик обращений через Django cache (`FileBasedCache`, `/tmp/django_cache_workflow`). Лимит: **5 POST-запросов с одного IP за 1 час**. При превышении форма перерисовывается с сообщением об ошибке; логируется `WARNING`.

**3. Блокировка одноразовых email** — `_DISPOSABLE_EMAIL_DOMAINS` (frozenset из 12 доменов: mailinator, guerrillamail и др.) в `forms.py`. `clean_email()` отклоняет регистрацию с такими адресами.

Cache настроен в `settings.py`:
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/tmp/django_cache_workflow',
    }
}
```

### Смена пароля

Реализована через `CustomPasswordChangeView` (`authentication/views.py`). URL: `/accounts/password_change/`. После смены текущая сессия остаётся активной (`update_session_auth_hash` вызывается в родительском `PasswordChangeView`). Ссылка — в меню «Настройки».

### Переменные окружения

- `SECRET_KEY` — при старте проверяется: `if not SECRET_KEY: raise RuntimeError(...)`. Django не запустится без ключа.
- `ALLOWED_HOSTS` — парсится с `.strip()` и фильтрацией пустых строк: `[h.strip() for h in ... if h.strip()]`.

---

## Персональные данные (152-ФЗ)

Состояние, оставшиеся задачи и риски — в `privacy_policy.md` в корне репозитория.

- Политика: `authentication/templates/authentication/privacy_policy.html`, URL `/accounts/privacy/`. Текущая версия — 2.0 от 02.10.2026.
- **При любом изменении текста политики** поднимать `POLICY_VERSION` в `authentication/views.py` и версию/дату в шапке шаблона — версия пишется в `Profile.consent_policy_version` и в письмо о согласии (`RegisterView._send_consent_email`).
- Политика перечисляет фактических получателей данных (хостинг Cloud.ru, почта Яндекса) и утверждает, что трансграничной передачи нет. При подключении любого внешнего сервиса (аналитика, карты, AI, платежи, CDN) политику нужно обновить до выката.
- Оператор — физическое лицо; сервер и база — в России (Cloud.ru).

---

## Запуск тестов

`python manage.py test` — 237 тестов (`signal1520`, `authentication`). Окружение должно соответствовать `requirements.txt` (Django 6.0.3). На Django 4.2 + Python 3.14 около сотни тестов падают с `AttributeError: 'super' object has no attribute 'dicts'`, а `makemigrations` генерирует лишние `AlterField id` по всем моделям — это признак неверного окружения, а не изменений в моделях.

---

## Технологический стек

- **Backend:** Django 6.0.3, Python
- **Frontend:** Vanilla JS (без фреймворков), CSS (без препроцессоров)
- **БД:** SQLite (в разработке), PostgreSQL 16 (прод, через docker-compose)
- **Шаблоны:** Django Templates
- **Деплой:** Docker Compose (контейнеры `web` + `db`), Nginx как reverse proxy
- **Домен и TLS:** `https://www.fieldlog.ru` — HTTPS через Let's Encrypt; Nginx терминирует SSL и проксирует на Gunicorn (порт 8000)

### Важные настройки для HTTPS-окружения

В `settings.py` обязательно должны читаться из `.env`:
```python
CSRF_TRUSTED_ORIGINS = [h.strip() for h in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if h.strip()]
```
В `.env` прописаны оба варианта домена (с `www` и без):
```
CSRF_TRUSTED_ORIGINS=https://fieldlog.ru,https://www.fieldlog.ru
```
Без этого Django блокирует POST-запросы с 403 CSRF при работе по HTTPS.
