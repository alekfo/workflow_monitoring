# TODO — Аудит проекта workflow_monitoring

---

## Безопасность

### Критические

- [ ] **XSS в `index.js`** — `contentPanel.innerHTML = html` вставляет сырой HTML без санитизации.
  Особенно опасна строка с ошибкой: `` contentPanel.innerHTML = `<p>Ошибка: ${error.message}</p>` `` —
  сообщение об ошибке вставляется без экранирования, возможен DOM-based XSS.
  Решение: использовать `textContent` для текстовых данных; рассмотреть DOMPurify для HTML от сервера.

- [ ] **`.env` не должен быть в git** — если файл попадал в историю хотя бы однажды, нужно
  провернуть `git filter-branch` / `git-filter-repo` и ротировать все секреты (DB_PASSWORD, SECRET_KEY и т.д.).
  В репо должен лежать только `.env.example` с заглушками.

### Серьёзные

- [ ] **`ALLOWED_HOSTS` при пустой переменной** (`settings.py`) —
  `os.environ.get('ALLOWED_HOSTS', '').split(',')` возвращает `['']`, а не `[]`.
  Пустая строка — не защита от Host Header Injection.
  Решение: `ALLOWED_HOSTS = [h for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h]`

- [ ] **`SECRET_KEY` может быть `None`** (`settings.py`) —
  `os.environ.get('SECRET_KEY')` без fallback. Django не упадёт, но CSRF/сессии сломаются тихо.
  Решение: добавить в settings.py после чтения переменных:
  ```python
  assert SECRET_KEY, "SECRET_KEY не установлен в переменных окружения"
  ```

- [ ] **Нет Rate Limiting** — на логин, регистрацию, создание задач. Брутфорс паролей ничем не ограничен.
  Решение: подключить `django-axes` (блокировка по IP/логину) или `django-ratelimit`.

- [ ] **Нет логирования** — ни одного вызова `logging` во всём проекте. Попытки несанкционированного
  доступа, 403-ошибки, исключения — всё исчезает. Решение: настроить `LOGGING` в settings.py,
  добавить `logger = logging.getLogger(__name__)` в views.py и authentication/views.py.

- [ ] **`bare except` и слишком широкий `except Exception`** (`views.py`, `authentication/views.py`) —
  скрывают реальные ошибки, делают отладку сложной.
  Решение: заменить на конкретные типы исключений (`json.JSONDecodeError`, `AttributeError` и т.д.).

---

## Производительность

- [ ] **N+1 в `StationListView`** (`views.py`) — `prefetch_related('tasks')` есть, но в шаблоне
  `station.tasks.all|length` делает отдельный запрос на каждую станцию.
  Решение: добавить `annotate(task_count=Count('tasks'))` в queryset view,
  использовать `{{ station.task_count }}` в шаблоне вместо `station.tasks.all|length`.

- [ ] **N+1 в `BugDetailView`** (`views.py`) — `prefetch_related('comments')` есть, но нет
  `prefetch_related('comments__user')`. При 10 комментариях — 10 лишних запросов на пользователей.
  Решение: добавить `'comments__user'` в `prefetch_related`.

- [ ] **Нет индексов на часто фильтруемых полях** (`models.py`) — при росте данных запросы замедлятся.
  Добавить `db_index=True`:
  - `Task.status` (фильтруется в `BugsListView`)
  - `Task.responsible_user` (фильтруется в `MyBugsListView`)
  - `Task.due_date` (используется для сортировки)
  - `Station.organization`, `Road.organization`, `System.organization`

---

## Модели

- [ ] **`on_delete=CASCADE` на nullable FK** (`models.py`) — поля `Road.organization` и
  `System.organization` объявлены как `null=True`, но при удалении Organization все связанные
  дороги и системы будут удалены. Правильнее `on_delete=models.SET_NULL`, чтобы при удалении
  организации поле просто обнулилось, а объект остался.

---

## Качество кода

- [ ] **Дублирование `test_func` в ~8 view** (`views.py`) — один и тот же паттерн повторяется:
  ```python
  def test_func(self):
      if self.request.user.is_superuser:
          return True
      return self.request.user.has_perm('signal1520.some_perm')
  ```
  Решение: вынести в параметризованный миксин, например `SuperuserOrPermMixin(perm='...')`.

---

## UX

- [ ] **Нет спиннера при загрузке контента** (`index.js`) — `contentPanel` показывает только
  текст "Загрузка..." без визуального индикатора прогресса.

- [ ] **Нет ограничения типов файлов на форме вложений** — нет атрибута `accept` на
  `<input type="file">`. Nginx режет по размеру (20M), но тип файла не проверяется на клиенте.
  Решение: добавить `accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg"`.

---

## Приоритеты

| Задача | Срочность |
|--------|-----------|
| XSS в `error.message` (`index.js`) | Сейчас |
| `ALLOWED_HOSTS` и `SECRET_KEY` assertion | Сейчас |
| N+1 в `StationListView` | Скоро |
| Индексы на моделях | Скоро |
| Rate Limiting + логирование | Важно |
| `on_delete=SET_NULL` на nullable FK | При следующей миграции |
| Рефакторинг `test_func` | По мере сил |
| Спиннер, валидация форм, accept на файлах | Улучшения |
