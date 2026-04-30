from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Organization


class OrgMixin:
    """Привязывает view к организации из URL-параметра org_slug.

    Примешивается ко всем view в signal1520. Обеспечивает три вещи:
    - изоляцию доступа: пользователь видит только свою организацию;
    - изоляцию данных: queryset автоматически фильтруется по организации;
    - удобный реверс URL: org_kwargs() добавляет org_slug к kwargs для reverse().

    Порядок в MRO должен быть: OrgMixin, LoginRequiredMixin, View/ListView/...
    Это гарантирует, что OrgMixin.dispatch() вызывается первым, но анонимные
    пользователи всё равно корректно перенаправляются на логин — благодаря
    проверке is_authenticated в начале dispatch().
    """

    org_filter_field = 'organization'
    """Поле для фильтрации queryset по организации.

    По умолчанию 'organization' — подходит для моделей с прямым FK на Organization
    (например, Station). Для моделей без прямого FK переопределяется в конкретном view:
        org_filter_field = 'station__organization'  # Task, BugDetailView и т.д.
    """

    def get_org(self):
        """Возвращает объект Organization для текущего запроса.

        Извлекает org_slug из self.kwargs (который Django заполняет из URL-паттерна
        `<slug:org_slug>/`), делает запрос в БД и кеширует результат в self._org.

        Если организация с таким slug не найдена — возвращает 404.
        Повторные вызовы в рамках одного запроса не делают лишних запросов в БД.
        """
        if not hasattr(self, '_org'):
            self._org = get_object_or_404(Organization, slug=self.kwargs['org_slug'])
        return self._org

    def dispatch(self, request, *args, **kwargs):
        """Проверяет, что аутентифицированный пользователь принадлежит этой организации.

        Логика:
        1. Анонимный пользователь — пропускаем без проверки. LoginRequiredMixin,
           стоящий следующим в MRO, перехватит его и сделает редирект на логин.
           Без этой проверки OrgMixin пытался бы обратиться к request.user.profile
           у AnonymousUser и падал бы с исключением до того, как LoginRequiredMixin
           успевал бы сработать.
        2. Суперпользователь — пропускаем без проверки орга. Суперюзер имеет
           доступ ко всем организациям (удобно для администрирования).
        3. Обычный пользователь — сравниваем user.profile.organization с get_org().
           Django сравнивает объекты моделей по pk, поэтому сравнение корректно.
           Если организации не совпадают — PermissionDenied → 403.
           Если у пользователя нет профиля или profile.organization == None —
           любое исключение кроме PermissionDenied перехватывается и тоже даёт 403.
           PermissionDenied обрабатывается отдельно (re-raise), чтобы он не был
           случайно поглощён блоком except Exception.
        """
        if request.user.is_authenticated and not request.user.is_superuser:
            try:
                if request.user.profile.organization != self.get_org():
                    raise PermissionDenied
            except PermissionDenied:
                raise
            except Exception:
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Фильтрует стандартный queryset по организации текущего запроса.

        Вызывается автоматически Django CBV-механизмом в ListView, DetailView,
        UpdateView, DeleteView — везде, где фреймворк сам запрашивает данные.
        В View и CreateView не вызывается (там нет родительского get_queryset()).

        Использует org_filter_field для построения фильтра:
            .filter(organization=self.get_org())         # по умолчанию
            .filter(station__organization=self.get_org()) # если org_filter_field переопределён

        Это гарантирует, что пользователь никогда не увидит данные чужой организации,
        даже если он вручную подставит чужой org_slug в адресную строку: dispatch()
        заблокирует его на уровне доступа, а get_queryset() — на уровне данных.
        """
        return super().get_queryset().filter(**{self.org_filter_field: self.get_org()})

    def org_kwargs(self, **kwargs):
        """Возвращает словарь kwargs для reverse() с добавленным org_slug.

        Избавляет от необходимости вручную прописывать org_slug в каждом
        get_success_url() и redirect(). Принимает дополнительные kwargs
        (например, pk объекта) и добавляет к ним org_slug из текущего URL.

        Пример использования:
            return reverse('signal1520:station_details', kwargs=self.org_kwargs(pk=self.object.pk))
            # → {'org_slug': 'signal1520', 'pk': 42}
            # → /signal1520/stations/42/
        """
        return {'org_slug': self.kwargs['org_slug'], **kwargs}
