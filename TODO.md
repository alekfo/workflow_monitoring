# TODO — Аудит проекта workflow_monitoring

---

## Проблемы и замечания

### Критические

- [ ] **Тесты отсутствуют полностью** — `signal1520/tests.py` и `authentication/tests.py` — пустые
  заглушки. Для production-системы с мультиарендностью и разграничением прав это серьёзный риск:
  регрессии в `OrgMixin` или правах доступа не будут видны.

- [ ] **Утечка данных в `KnowledgeCreateView._existing_qs()`** (`views.py:565-569`) —
  ```python
  def _existing_qs(self):
      used_ids = UserKnowledge.objects.filter(user=self.request.user).values_list(...)
      return Knowledge.objects.filter(file__gt='').exclude(pk__in=used_ids)
  ```
  Возвращает все файлы знаний всех пользователей всех организаций. Пользователь из одной орг
  видит и может привязать к себе файлы из другой орг.

- [ ] **`ContactView.post()` не обрабатывает невалидную форму** (`views.py:931-956`) —
  Если `form.is_valid()` возвращает `False`, функция неявно возвращает `None`. Django упадёт с
  `ValueError`. Нужен `else` с `render(request, self.template_name, {'form': form})`.

---

## Безопасность

### Критические

- [x] **XSS в `index.js`** — строка с `error.message` исправлена: теперь используется DOM API
  (`replaceChildren` + `createElement` + `textContent`). `contentPanel.innerHTML = html` (строка 95)
  оставлен как есть — HTML приходит от доверенного Django-сервера с автоэскейпингом.

- [x] **Stored XSS в проверке дублей станций** (`station_form.html`, `station_update_form.html`) —
  `s.name` и `s.road__title` из JSON вставлялись через конкатенацию строк + `innerHTML`.
  Атакующий мог создать станцию с именем вида `<img src=x onerror="...">` и угнать сессии других
  участников организации. Исправлено: заменено на DOM API (`replaceChildren`, `createElement`,
  `textContent`).

- [x] **IDOR: медиафайлы без авторизации** (`nginx.conf`, `urls.py`, `views.py`) —
  Nginx отдавал `/media/` напрямую без проверки аутентификации. Файлы доступны по предсказуемым
  путям (`tasks/task_<id>/...`), ID — последовательные целые числа. Любой мог скачать чужие
  вложения без логина. Исправлено: добавлен `ProtectedMediaView` (`LoginRequiredMixin` + защита
  от path traversal), маршрут `media/<path>` всегда через Django; Nginx отдаёт файлы только
  через `X-Accel-Redirect` из внутреннего location `/protected-media/`.

### Серьёзные

- [x] **`ALLOWED_HOSTS` при пустой переменной** (`settings.py`) —
  исправлено: `[h.strip() for h in ... if h.strip()]` — пустые строки и пробелы отфильтрованы.

- [x] **`SECRET_KEY` может быть `None`** (`settings.py`) —
  исправлено: добавлена проверка `if not SECRET_KEY: raise RuntimeError(...)` — Django упадёт
  при старте с внятным сообщением, не тихо ломая CSRF/сессии.

- [x] **Нет Rate Limiting** — подключён `django-axes==8.3.1`. После 5 неудачных попыток входа
  аккаунт блокируется на 1 час (автоматически снимается). Блокировка по `username` — ротация IP
  атакующим не помогает. При успешном входе счётчик сбрасывается. Управление через Django admin.

- [x] **Нет логирования** — реализовано: `LOGGING` настроен в `settings.py`, `logger` добавлен
  в `signal1520/views.py` и `authentication/views.py` с вызовами `info`/`warning`/`error`.

- [x] **`bare except` и слишком широкий `except Exception`** — исправлено в 4 местах:
  `bare except` → `json.JSONDecodeError`; `except Exception` → `ObjectDoesNotExist` (×3).
  `except Exception as exc` в send_mail оставлен — там это оправдано для логирования SMTP-ошибок.

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
| ~~XSS в `error.message` (`index.js`)~~ | ✅ Выполнено |
| ~~Stored XSS в дублях станций~~ | ✅ Выполнено |
| ~~IDOR: медиафайлы без авторизации~~ | ✅ Выполнено |
| ~~Логирование~~ | ✅ Выполнено |
| ~~`ALLOWED_HOSTS` и `SECRET_KEY` assertion~~ | ✅ Выполнено |
| ~~Rate Limiting~~ | ✅ Выполнено |
| N+1 в `StationListView` | Скоро |
| Индексы на моделях | Скоро |
| `on_delete=SET_NULL` на nullable FK | При следующей миграции |
| Рефакторинг `test_func` | По мере сил |
| Спиннер, валидация форм, accept на файлах | Улучшения |
