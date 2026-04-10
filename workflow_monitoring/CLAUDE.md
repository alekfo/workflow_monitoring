# CLAUDE.md — Контекст проекта workflow_monitoring

## Что это за проект

Django-приложение для мониторинга рабочих процессов на объектах (станциях).
Основные сущности: объекты (станции), замечания (задачи), алармы (справочник), пользователи.
Интерфейс — одностраничное SPA-подобное приложение: контент грузится в `contentPanel` через AJAX, без перезагрузки страницы.

---

## Структура проекта

```
workflow_monitoring/        ← корень, здесь лежит manage.py
├── workflow_monitoring/    ← настройки Django (settings.py, urls.py)
├── signal1520/             ← основное приложение
│   ├── models.py
│   ├── views.py
│   ├── urls.py
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

## Модели (signal1520/models.py)

| Модель | Описание |
|--------|----------|
| `Station` | Объект/станция. Поля: name, road, description, latitude, longitude, created_by |
| `Task` | Замечание. Поля: station(FK), description, status(new/in_progress/completed/cancelled), responsible_organization, responsible_user(FK User), due_date |
| `Comment` | Комментарий к замечанию. Поля: task(FK), user(FK), body |
| `Attachment` | Вложение к замечанию. Файлы хранятся в `tasks/task_<id>/` |
| `AlarmInfo` | Справочник алармов. Поля: number(PK), description, explanation. Данные загружаются скриптом migrate_alarms.py |
| `Knowledge` | База знаний (в разработке) |
| `Link` | Ссылки пользователей (в разработке) |

---

## URL-маршруты

| URL | View | Имя |
|-----|------|-----|
| `/signal1520/` | TasksIndexView | `signal1520:index` |
| `/signal1520/bugs/` | BugsListView | `signal1520:bugs_list` |
| `/signal1520/bugs/my/` | MyBugsListView | `signal1520:bugs_list_my` |
| `/signal1520/bugs/<pk>/` | BugDetailView | `signal1520:bug_details` |
| `/signal1520/bugs/create/` | BugCreateView | `signal1520:create_bug` |
| `/signal1520/bugs/<pk>/update/` | BugUpdateView | `signal1520:bug_update` |
| `/signal1520/stations/` | StationListView | `signal1520:station_list` |
| `/signal1520/stations/<pk>/` | StationDetailView | `signal1520:station_details` |
| `/signal1520/stations/create/` | StationCreateView | `signal1520:create_station` |
| `/signal1520/stations/<pk>/update/` | StationUpdateView | `signal1520:station_update` |
| `/signal1520/alarms/` | AlarmListView | `signal1520:alarm_list` |
| `/accounts/...` | authentication app | login, logout, register, profile |

---

## Архитектура SPA (index.js)

Главная страница (`/signal1520/`) имеет боковое меню и `<div id="content-panel">`.
Весь контент загружается в `contentPanel` через `window.loadContentPanel(url)`.

### Как работает loadContentPanel
1. Делает `fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })`
2. Вставляет ответ в `contentPanel.innerHTML`
3. Вызывает `executeScripts()` — вырезает `<script>` теги из contentPanel и добавляет в `document.head` (иначе браузер не выполняет скрипты из innerHTML)
4. Вызывает инициализаторы: `initTasksToggle()`, `initStationTasks()`, `initBugFilter()`

### Словари маршрутов в index.js
- `urlMap_for_contentPanel` — секции, которые грузятся в contentPanel (tasks_all, tasks_mine, objects_all, alarms)
- `urlMap_for_redirect` — секции, которые делают полный переход (tasks_add, objects_add)

### ВАЖНО: executeScripts и накопление скриптов
Скрипты из шаблонов копируются в `document.head` и там остаются навсегда.
Поэтому **нельзя** писать логику инициализации прямо в inline `<script>` внутри шаблонов, которые грузятся в contentPanel — скрипты будут накапливаться и дублировать обработчики.
Правильный подход: выносить логику в отдельный JS-файл с функцией `window.initXxx()` и вызывать её из `loadContentPanel`.

---

## bug_filter.js — AJAX-поиск и пагинация

Инициализируется вызовом `window.initBugFilter()` после каждой загрузки контента.
Защита от двойной инициализации: `searchForm.dataset.filterInitialized = 'true'`.

- Ищет форму по `id="search-form"` с атрибутом `data-base-url`
- При сабмите делает fetch и заменяет `.table-and-pagination` (замечания) или `.table-wrapper` (алармы)
- Кнопки пагинации перехватываются и загружают страницу через `window.loadContentPanel(url)`
- Использует `history.replaceState` (не `pushState`) — не засоряет историю браузера

**Шаблоны, где работает фильтр:**
- `bug_list.html` — `data-base-url="{% url 'signal1520:bugs_list' %}"`, контейнер `.table-and-pagination`
- `alarm_list.html` — `data-base-url="{% url 'signal1520:alarm_list' %}"`, контейнер `.table-wrapper`

---

## Пагинация

| View | paginate_by |
|------|-------------|
| `BugsListView` | 10 |
| `AlarmListView` | 10 |
| `MyBugsListView` | не включена |

Кнопки пагинации используют классы `.pagination-btn` и `.pagination-info` из `styles_stations.css`.

---

## CSS-архитектура

`styles_stations.css` подключён в `signal1520/base.html` — загружается один раз для всего приложения.
Отдельные шаблоны тоже содержат `<link>` на него (для прямого открытия страниц), дублирование безвредно — браузер кеширует.

Когда контент грузится в `contentPanel` через innerHTML, `<link>` теги из `<head>` шаблона **не обрабатываются** браузером. Поэтому все общие стили должны быть подключены в `base.html`.

---

## Разделы в разработке (заглушки)

В меню следующие секции показывают «Раздел в разработке»:
- Склады (`warehouses_stock`)
- Отчёты (`reports_download`)
- Ссылки на таблицы (`links_all`), Добавить ссылку (`links_add`)
- Графики (`charts_download`, `charts_add`)
- Инструкции (`instructions`)
- Разное (`others`)

---

## Аутентификация

Приложение `authentication` — кастомная реализация.
`LoginRequiredMixin` используется на всех view.
Права доступа через `UserPassesTestMixin` и `has_perm()`.
После логина редирект на `/signal1520/`.

---

## Технологический стек

- **Backend:** Django 6.0.3, Python
- **Frontend:** Vanilla JS (без фреймворков), CSS (без препроцессоров)
- **БД:** SQLite (в разработке)
- **Шаблоны:** Django Templates
