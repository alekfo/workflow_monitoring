# CLAUDE.md — Контекст проекта workflow_monitoring

## Что это за проект

Django-приложение для мониторинга рабочих процессов на объектах (станциях).
Основные сущности: объекты (станции), задачи, алармы (справочник), склады, оборудование, пользователи.
Интерфейс — одностраничное SPA-подобное приложение: контент грузится в `contentPanel` через AJAX, без перезагрузки страницы.
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
│           ├── index.js             ← главный JS: меню, loadContentPanel, executeScripts
│           ├── main_header.js       ← кнопки шапки (профиль, выход)
│           ├── stations.js          ← initTasksToggle (раскрытие задач на станции)
│           └── bug_filter.js        ← initBugFilter (AJAX-поиск и пагинация в contentPanel)
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
```python
def org_slug(request):
    try:
        slug = request.resolver_match.kwargs.get('org_slug', '')
    except AttributeError:
        slug = ''
    return {'org_slug': slug}
```
Зарегистрирован в `settings.TEMPLATES`. Автоматически добавляет `{{ org_slug }}` в контекст каждого шаблона — не нужно передавать его вручную из каждого view.

**6. Шаблоны**
Все `{% url %}` теги используют `org_slug=org_slug`:
```html
{% url 'signal1520:bug_details' pk=bug.pk org_slug=org_slug %}
```

**7. JavaScript (index.js)**
Статический файл не поддерживает Django-теги, поэтому `base.html` инжектирует переменную:
```html
<script>window.ORG_SLUG = '{{ org_slug }}';</script>
```
`index.js` строит URL-ы динамически:
```js
const _base = '/' + (window.ORG_SLUG || 'signal1520') + '/';
```

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

### Шаг 5 — JavaScript
`base.html` рендерится с `window.ORG_SLUG = 'signal1520'`.
`index.js` строит URL для AJAX-запросов: `'/signal1520/bugs/'`, `'/signal1520/stations/'` и т.д.

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
| `Station` | Объект/станция. Поля: name, road(FK), distance, system(FK, nullable), description, latitude, longitude, created_by, organization(FK) |
| `Task` | Задача. Поля: station(FK), description, status(new/in_progress/completed/cancelled), responsible_organization, responsible_user(FK User), due_date |
| `Comment` | Комментарий к задаче. Поля: task(FK), user(FK), body |
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

## Архитектура SPA (index.js)

Главная страница (`/<org_slug>/`) имеет боковое меню и `<div id="content-panel">`.
Весь контент загружается в `contentPanel` через `window.loadContentPanel(url)`.

### Как работает loadContentPanel
1. Делает `fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })`
2. Вставляет ответ в `contentPanel.innerHTML`
3. Вызывает `executeScripts()` — вырезает `<script>` теги из contentPanel и добавляет в `document.head`
4. Вызывает инициализаторы: `initTasksToggle()`, `initStationTasks()`, `initBugFilter()`, `initInstructions()`

### Словари маршрутов в index.js
- `urlMap_for_contentPanel` — секции, которые грузятся в contentPanel
- `urlMap_for_redirect` — секции, которые делают полный переход

| Ключ (data-section) | Тип | URL |
|---------------------|-----|-----|
| `tasks_all` | contentPanel | `bugs/` |
| `tasks_mine` | contentPanel | `bugs/my/` |
| `objects_all` | contentPanel | `stations/` |
| `alarms` | contentPanel | `alarms/` |
| `warehouses_list` | contentPanel | `warehouses/` |
| `equipment_list` | contentPanel | `equipment/` |
| `instructions` | contentPanel | `knowledge/` |
| `tasks_add` | redirect | `bugs/create/` |
| `objects_add` | redirect | `stations/create/` |
| `instructions_add` | redirect | `knowledge/create/` |
| `warehouses_create` | redirect | `warehouses/create/` |
| `equipment_create` | redirect | `equipment/create/` |
| `equipment_type_create` | redirect | `equipment/types/create/` |

URL-ы строятся динамически через `window.ORG_SLUG`, который инжектируется из `base.html`:
```html
<script>window.ORG_SLUG = '{{ org_slug }}';</script>
```

### ВАЖНО: executeScripts и накопление скриптов
Скрипты из шаблонов копируются в `document.head` и там остаются навсегда.
Поэтому **нельзя** писать логику инициализации прямо в inline `<script>` внутри шаблонов, которые грузятся в contentPanel.
Правильный подход: выносить логику в отдельный JS-файл с функцией `window.initXxx()` и вызывать её из `loadContentPanel`.

---

## bug_filter.js — AJAX-поиск и пагинация

Инициализируется вызовом `window.initBugFilter()` после каждой загрузки контента.
Защита от двойной инициализации: `searchForm.dataset.filterInitialized = 'true'`.

- Ищет форму по `id="search-form"` с атрибутом `data-base-url`
- При сабмите делает fetch и заменяет `.table-and-pagination` (задачи) или `.table-wrapper` (алармы)
- Кнопки пагинации перехватываются и загружают страницу через `window.loadContentPanel(url)`
- Использует `history.replaceState` (не `pushState`) — не засоряет историю браузера

**Шаблоны, где работает фильтр:**
- `bug_list.html` — `data-base-url="{% url 'signal1520:bugs_list' org_slug=org_slug %}"`, контейнер `.table-and-pagination`
- `alarm_list.html` — `data-base-url="{% url 'signal1520:alarm_list' org_slug=org_slug %}"`, контейнер `.table-wrapper`
- `warehouse_list.html` — `data-base-url="{% url 'signal1520:warehouse_list' org_slug=org_slug %}"`, контейнер `.table-and-pagination`
- `equipment_list.html` — `data-base-url="{% url 'signal1520:equipment_list' org_slug=org_slug %}"`, контейнер `.table-and-pagination`

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
Отдельные шаблоны тоже содержат `<link>` на него (для прямого открытия), дублирование безвредно — браузер кеширует.

Когда контент грузится в `contentPanel` через innerHTML, `<link>` теги из `<head>` шаблона **не обрабатываются** браузером. Поэтому все общие стили должны быть подключены в `base.html`.

---

## Раздел Инструкции (Knowledge)

`KnowledgeListView` — список инструкций текущего пользователя, загружается в contentPanel через AJAX.
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

`WarehouseListView` — список складов, грузится в contentPanel через AJAX. `org_filter_field='organization'` (дефолтное). Поиск по названию, имени ответственного.

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

### Навигация в меню (index.js)

Список складов и список оборудования грузятся в contentPanel (не полный редирект).
Создание склада, создание оборудования, создание типа — полный редирект на отдельные страницы.

---

## Разделы в разработке (заглушки)

В меню следующие секции показывают «Раздел в разработке»:
- Отчёты (`reports_download`)
- Ссылки на таблицы (`links_all`), Добавить ссылку (`links_add`)
- Графики (`charts_download`, `charts_add`)
- Разное (`others`)

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
  → кнопка «Меню» скрыта

Администратор в Django admin назначает organization пользователю.

  → пользователь логинится → OrgLoginView.get_success_url() → /<org_slug>/
  → плашка исчезает, кнопка «Меню» появляется
```

Шаблоны `about_me.html` и `error.html` лежат вне org-контекста (`/accounts/...`).
Кнопка «Меню» отображается только при наличии организации:
```html
{% if user.profile.organization %}
<a href="{% url 'signal1520:index' org_slug=user.profile.organization.slug %}">🏠 Меню</a>
{% endif %}
```

---

## Технологический стек

- **Backend:** Django 6.0.3, Python
- **Frontend:** Vanilla JS (без фреймворков), CSS (без препроцессоров)
- **БД:** SQLite (в разработке), PostgreSQL 16 (прод, через docker-compose)
- **Шаблоны:** Django Templates
