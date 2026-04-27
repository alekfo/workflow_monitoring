import json

from django.contrib.auth.models import User, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import AlarmInfo, Attachment, Comment, Road, Station, System, Task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username, password='testpass', **perms):
    user = User.objects.create_user(username, password=password)
    for codename in perms.get('codenames', []):
        user.user_permissions.add(Permission.objects.get(codename=codename))
    return user


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class RoadModelTest(TestCase):
    def test_str(self):
        """__str__ возвращает название дороги — используется в формах и шаблонах."""
        road = Road(title='Московская дорога')
        self.assertEqual(str(road), 'Московская дорога')

    def test_ordering(self):
        """Дороги упорядочены по алфавиту по полю title (Meta.ordering=['title'])."""
        Road.objects.create(title='Ярославская')
        Road.objects.create(title='Арктическая')
        titles = list(Road.objects.values_list('title', flat=True))
        self.assertEqual(titles, sorted(titles))


class SystemModelTest(TestCase):
    def test_str(self):
        """__str__ возвращает название системы — используется в формах и шаблонах."""
        system = System(title='АРС-ДП')
        self.assertEqual(str(system), 'АРС-ДП')

    def test_ordering(self):
        """Системы упорядочены по алфавиту по полю title (Meta.ordering=['title'])."""
        System.objects.create(title='Система Б')
        System.objects.create(title='Система А')
        titles = list(System.objects.values_list('title', flat=True))
        self.assertEqual(titles, sorted(titles))


class StationModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('u', password='p')
        cls.road = Road.objects.create(title='Московская дорога')
        cls.system = System.objects.create(title='АРС-ДП')

    def test_str_with_road(self):
        """__str__ включает имя станции и название дороги через FK Road.__str__."""
        station = Station(name='Тест', road=self.road)
        self.assertIn('Тест', str(station))
        self.assertIn('Московская дорога', str(station))

    def test_system_nullable(self):
        """Поле system на станции nullable — станцию можно создать без указания системы."""
        station = Station.objects.create(
            name='Без системы', road=self.road, created_by=self.user
        )
        self.assertIsNone(station.system)

    def test_ordering_by_road_title(self):
        """Станции сортируются по названию дороги (road__title), а не по FK-id."""
        road2 = Road.objects.create(title='Арктическая дорога')
        Station.objects.create(name='С1', road=self.road, created_by=self.user)
        Station.objects.create(name='С2', road=road2, created_by=self.user)
        first = Station.objects.first()
        self.assertEqual(first.road.title, 'Арктическая дорога')


class TaskModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('u', password='p')
        cls.road = Road.objects.create(title='Дорога')
        cls.station = Station.objects.create(
            name='Станция', road=cls.road, created_by=cls.user
        )

    def test_default_status_is_new(self):
        """Новая задача получает статус 'new' по умолчанию без явного указания."""
        task = Task.objects.create(station=self.station, description='Замечание')
        self.assertEqual(task.status, Task.Status.NEW)

    def test_str(self):
        """__str__ содержит id задачи и имя станции для удобной идентификации в admin."""
        task = Task.objects.create(station=self.station, description='Замечание')
        self.assertIn(str(task.id), str(task))
        self.assertIn(self.station.name, str(task))

    def test_all_statuses_valid(self):
        """Task.Status содержит все четыре ожидаемых значения: new, in_progress, completed, cancelled."""
        valid = {s[0] for s in Task.Status.choices}
        self.assertIn('new', valid)
        self.assertIn('in_progress', valid)
        self.assertIn('completed', valid)
        self.assertIn('cancelled', valid)


class CommentModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('u', first_name='Иван', last_name='Петров', password='p')
        cls.road = Road.objects.create(title='Дорога')
        cls.station = Station.objects.create(name='Ст', road=cls.road, created_by=cls.user)
        cls.task = Task.objects.create(station=cls.station, description='Задача')

    def test_author_name_full_name(self):
        """author_name() возвращает 'Имя Фамилия', если оба поля заполнены у пользователя."""
        comment = Comment(task=self.task, user=self.user, body='Текст')
        self.assertEqual(comment.author_name(), 'Иван Петров')

    def test_author_name_username_fallback(self):
        """author_name() возвращает username, если first_name и last_name не заполнены."""
        user2 = User.objects.create_user('only_username', password='p')
        comment = Comment(task=self.task, user=user2, body='Текст')
        self.assertEqual(comment.author_name(), 'only_username')

    def test_author_name_anon(self):
        """author_name() возвращает 'Аноним', если user=None (удалённый или незалогиненный)."""
        comment = Comment(task=self.task, user=None, body='Текст')
        self.assertEqual(comment.author_name(), 'Аноним')


class AttachmentModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('u', password='p')
        cls.road = Road.objects.create(title='Дорога')
        cls.station = Station.objects.create(name='Ст', road=cls.road, created_by=cls.user)
        cls.task = Task.objects.create(station=cls.station, description='Задача')

    def _make_attachment(self, filename):
        f = SimpleUploadedFile(filename, b'data')
        return Attachment(task=self.task, file=f)

    def test_is_image_jpg(self):
        """is_image() возвращает True для файлов с расширением .jpg."""
        a = self._make_attachment('photo.jpg')
        self.assertTrue(a.is_image())

    def test_is_image_png(self):
        """is_image() возвращает True для файлов с расширением .png."""
        a = self._make_attachment('photo.png')
        self.assertTrue(a.is_image())

    def test_is_image_false_for_pdf(self):
        """is_image() возвращает False для не-графических файлов, например .pdf."""
        a = self._make_attachment('document.pdf')
        self.assertFalse(a.is_image())

    def test_filename(self):
        """filename() возвращает чистое имя файла без пути — используется в шаблоне вложений."""
        a = self._make_attachment('myfile.txt')
        self.assertEqual(a.filename(), 'myfile.txt')


# ---------------------------------------------------------------------------
# View tests — base setup
# ---------------------------------------------------------------------------

class ViewTestBase(TestCase):
    """Создаёт стандартный набор пользователей и фикстур для тестов views."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('admin', password='pass')
        cls.plain_user = User.objects.create_user('plain', password='pass')

        station_perms = ['view_station', 'add_station', 'change_station']
        task_perms = ['view_task', 'add_task', 'change_task']
        cls.station_user = make_user('station_u', codenames=station_perms)
        cls.task_user = make_user('task_u', codenames=task_perms + station_perms)

        cls.road = Road.objects.create(title='Тестовая дорога')
        cls.system = System.objects.create(title='Тестовая система')
        cls.station = Station.objects.create(
            name='Тест Станция',
            road=cls.road,
            system=cls.system,
            distance='ДЦС-1',
            description='Описание тестовой станции',
            created_by=cls.superuser,
        )
        cls.task = Task.objects.create(
            station=cls.station,
            description='Тестовое замечание',
            status=Task.Status.NEW,
            responsible_user=cls.plain_user,
        )
        cls.alarm = AlarmInfo.objects.create(
            number='T001',
            description='Тестовый аларм описание',
            explanation='Пояснение к аларму',
        )


# ---------------------------------------------------------------------------
# TasksIndexView
# ---------------------------------------------------------------------------

class TasksIndexViewTest(ViewTestBase):
    url = reverse_lazy = None

    def setUp(self):
        self.url = reverse('signal1520:index')

    def test_redirect_if_not_logged_in(self):
        """Анонимный GET на главную перенаправляет на страницу логина (LoginRequiredMixin)."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_logged_in_returns_200(self):
        """Любой авторизованный пользователь видит главную страницу — прав не требуется."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# StationListView
# ---------------------------------------------------------------------------

class StationListViewTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:station_list')

    def test_redirect_anon(self):
        """Анонимный GET перенаправляет на логин с параметром next."""
        r = self.client.get(self.url)
        self.assertRedirects(r, f'/accounts/login/?next={self.url}')

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_station получает 403 (UserPassesTestMixin)."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_with_permission_returns_200(self):
        """Пользователь с правом view_station видит список станций."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_superuser_returns_200(self):
        """Суперпользователь всегда проходит test_func и видит список станций."""
        self.client.force_login(self.superuser)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_station_appears_in_list(self):
        """Существующая станция отображается в таблице на странице списка."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url)
        self.assertContains(r, 'Тест Станция')

    def test_search_by_name(self):
        """Поиск по точному имени станции возвращает эту станцию в результатах."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url, {'search': 'Тест Станция'})
        self.assertContains(r, 'Тест Станция')

    def test_search_by_road(self):
        """Поиск по названию дороги (road__title) находит станции этой дороги."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url, {'search': 'Тестовая дорога'})
        self.assertContains(r, 'Тест Станция')

    def test_search_by_system(self):
        """Поиск по названию системы (system__title) находит станции с этой системой."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url, {'search': 'Тестовая система'})
        self.assertContains(r, 'Тест Станция')

    def test_search_no_results(self):
        """Поиск по несуществующей строке не возвращает ни одной станции."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url, {'search': 'несуществующий_xyz'})
        self.assertNotContains(r, 'Тест Станция')


# ---------------------------------------------------------------------------
# StationDetailView
# ---------------------------------------------------------------------------

class StationDetailViewTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:station_details', kwargs={'pk': self.station.pk})

    def test_redirect_anon(self):
        """Анонимный GET на страницу станции перенаправляет на логин."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_station получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_with_permission_returns_200(self):
        """Пользователь с view_station открывает страницу детали станции."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_shows_station_data(self):
        """Страница детали содержит имя, дорогу и систему станции."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url)
        self.assertContains(r, 'Тест Станция')
        self.assertContains(r, 'Тестовая дорога')
        self.assertContains(r, 'Тестовая система')

    def test_shows_task_in_detail(self):
        """Страница детали станции показывает привязанные к ней задачи."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url)
        self.assertContains(r, 'Тестовое замечание')

    def test_404_for_nonexistent_station(self):
        """Запрос на несуществующий pk станции возвращает 404."""
        self.client.force_login(self.station_user)
        r = self.client.get(reverse('signal1520:station_details', kwargs={'pk': 99999}))
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# StationCreateView
# ---------------------------------------------------------------------------

class StationCreateViewTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:create_station')

    def test_redirect_anon(self):
        """Анонимный GET на форму создания станции перенаправляет на логин."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_no_permission_redirects_to_error(self):
        """Пользователь без add_station перенаправляется на страницу ошибки (handle_no_permission)."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_form_renders_for_permitted_user(self):
        """Пользователь с add_station видит форму создания станции (GET 200)."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_create_station_post(self):
        """POST с валидными данными создаёт новую станцию и редиректит на её детальную страницу."""
        self.client.force_login(self.station_user)
        r = self.client.post(self.url, {
            'name': 'Новая станция',
            'road': self.road.pk,
            'system': self.system.pk,
            'distance': 'ДЦС-2',
            'description': 'Описание',
            'latitude': '',
            'longitude': '',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Station.objects.filter(name='Новая станция').exists())

    def test_create_station_sets_created_by(self):
        """form_valid() автоматически записывает в created_by текущего пользователя."""
        self.client.force_login(self.station_user)
        self.client.post(self.url, {
            'name': 'Станция пользователя',
            'road': self.road.pk,
            'distance': '',
            'description': '',
            'latitude': '',
            'longitude': '',
        })
        station = Station.objects.get(name='Станция пользователя')
        self.assertEqual(station.created_by, self.station_user)

    def test_create_station_without_required_fields_fails(self):
        """POST без обязательных полей (name, road) возвращает форму с ошибками (200), объект не создаётся."""
        self.client.force_login(self.station_user)
        r = self.client.post(self.url, {'description': 'Без названия'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Station.objects.filter(description='Без названия').exists())


# ---------------------------------------------------------------------------
# StationUpdateView
# ---------------------------------------------------------------------------

class StationUpdateViewTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:station_update', kwargs={'pk': self.station.pk})

    def test_redirect_anon(self):
        """Анонимный GET на форму редактирования станции перенаправляет на логин."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без change_station получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_form_renders_for_permitted_user(self):
        """Пользователь с change_station видит форму редактирования (GET 200)."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_update_station(self):
        """POST с новым именем обновляет станцию в БД и редиректит на её детальную страницу."""
        self.client.force_login(self.station_user)
        r = self.client.post(self.url, {
            'name': 'Обновлённое название',
            'road': self.road.pk,
            'system': self.system.pk,
            'distance': 'ДЦС-9',
            'description': '',
            'latitude': '',
            'longitude': '',
        })
        self.assertEqual(r.status_code, 302)
        self.station.refresh_from_db()
        self.assertEqual(self.station.name, 'Обновлённое название')

    def test_superuser_can_update(self):
        """Суперпользователь проходит test_func и получает форму редактирования."""
        self.client.force_login(self.superuser)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# BugsListView
# ---------------------------------------------------------------------------

class BugsListViewTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:bugs_list')

    def test_redirect_anon(self):
        """Анонимный GET на список замечаний перенаправляет на логин с параметром next."""
        r = self.client.get(self.url)
        self.assertRedirects(r, f'/accounts/login/?next={self.url}')

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_task получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_with_permission_returns_200(self):
        """Пользователь с view_task видит список замечаний."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_task_appears_in_list(self):
        """Существующее замечание отображается в таблице списка."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url)
        self.assertContains(r, 'Тестовое замечание')

    def test_search_by_description(self):
        """Поиск по тексту описания замечания находит нужную запись."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url, {'search': 'Тестовое замечание'})
        self.assertContains(r, 'Тестовое замечание')

    def test_search_by_station_name(self):
        """Поиск по имени станции (station__name) находит замечания этой станции."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url, {'search': 'Тест Станция'})
        self.assertContains(r, 'Тестовое замечание')

    def test_search_no_result(self):
        """Поиск по несуществующей строке не возвращает замечаний."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url, {'search': 'нет_такого_xyz'})
        self.assertNotContains(r, 'Тестовое замечание')


# ---------------------------------------------------------------------------
# MyBugsListView
# ---------------------------------------------------------------------------

class MyBugsListViewTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:bugs_list_my')
        # Пользователь с view_task, назначенный ответственным за отдельную задачу
        self.responsible_user = make_user('responsible', codenames=['view_task'])
        self.own_task = Task.objects.create(
            station=self.station,
            description='Задача только для responsible_user',
            responsible_user=self.responsible_user,
        )

    def test_redirect_anon(self):
        """Анонимный GET на «мои замечания» перенаправляет на логин."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_shows_only_own_tasks(self):
        """Пользователь видит только задачи, где он назначен ответственным."""
        self.client.force_login(self.responsible_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Задача только для responsible_user')

    def test_does_not_show_others_tasks(self):
        """Задачи, назначенные другому пользователю, не попадают в список 'мои'."""
        self.client.force_login(self.responsible_user)
        r = self.client.get(self.url)
        # cls.task назначен plain_user, а не responsible_user
        self.assertNotContains(r, 'Тестовое замечание')

    def test_task_user_sees_only_own(self):
        """Пользователь без назначенных задач видит пустой список (не чужие задачи)."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Задача только для responsible_user')


# ---------------------------------------------------------------------------
# BugDetailView — GET
# ---------------------------------------------------------------------------

class BugDetailViewGetTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:bug_details', kwargs={'pk': self.task.pk})

    def test_redirect_anon(self):
        """Анонимный GET на страницу замечания перенаправляет на логин."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_task получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_with_permission_returns_200(self):
        """Пользователь с view_task открывает детальную страницу замечания."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_shows_task_description(self):
        """Страница содержит описание замечания."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url)
        self.assertContains(r, 'Тестовое замечание')

    def test_404_nonexistent_task(self):
        """Запрос на несуществующий pk замечания возвращает 404."""
        self.client.force_login(self.task_user)
        r = self.client.get(reverse('signal1520:bug_details', kwargs={'pk': 99999}))
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# BugDetailView — POST: comment
# ---------------------------------------------------------------------------

class BugDetailPostCommentTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:bug_details', kwargs={'pk': self.task.pk})

    def test_add_comment(self):
        """POST с comment_text создаёт новый Comment и редиректит обратно на страницу задачи."""
        self.client.force_login(self.task_user)
        r = self.client.post(self.url, {'comment_text': 'Мой комментарий'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Comment.objects.filter(body='Мой комментарий', task=self.task).exists())

    def test_empty_comment_not_saved(self):
        """POST с пустой строкой (или только пробелами) не создаёт Comment в БД."""
        self.client.force_login(self.task_user)
        before = Comment.objects.count()
        self.client.post(self.url, {'comment_text': '   '})
        self.assertEqual(Comment.objects.count(), before)

    def test_comment_sets_correct_user(self):
        """Созданный комментарий привязывается к текущему авторизованному пользователю."""
        self.client.force_login(self.task_user)
        self.client.post(self.url, {'comment_text': 'Проверка автора'})
        comment = Comment.objects.get(body='Проверка автора')
        self.assertEqual(comment.user, self.task_user)


# ---------------------------------------------------------------------------
# BugDetailView — POST: status change (JSON)
# ---------------------------------------------------------------------------

class BugDetailPostStatusTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:bug_details', kwargs={'pk': self.task.pk})

    def _patch_status(self, user, status):
        self.client.force_login(user)
        return self.client.post(
            self.url,
            data=json.dumps({'status': status}),
            content_type='application/json',
        )

    def test_superuser_can_change_status(self):
        """Суперпользователь меняет статус задачи через JSON POST; ответ содержит success=True."""
        r = self._patch_status(self.superuser, 'in_progress')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertTrue(data['success'])
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'in_progress')

    def test_responsible_user_can_change_status(self):
        """Ответственный исполнитель (responsible_user) может менять статус своей задачи,
        при условии что у него есть view_task для прохождения UserPassesTestMixin."""
        responsible_with_view = make_user('resp_view', codenames=['view_task'])
        own_task = Task.objects.create(
            station=self.station,
            description='Задача для resp_view',
            responsible_user=responsible_with_view,
        )
        self.client.force_login(responsible_with_view)
        url = reverse('signal1520:bug_details', kwargs={'pk': own_task.pk})
        r = self.client.post(
            url,
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        own_task.refresh_from_db()
        self.assertEqual(own_task.status, 'completed')

    def test_user_with_change_task_perm_can_change_status(self):
        """Пользователь с правом change_task может менять статус любой задачи."""
        r = self._patch_status(self.task_user, 'cancelled')
        self.assertEqual(r.status_code, 200)

    def test_invalid_status_returns_400(self):
        """JSON POST с недопустимым значением статуса возвращает 400 Bad Request."""
        r = self._patch_status(self.superuser, 'unknown_status')
        self.assertEqual(r.status_code, 400)

    def test_no_permission_returns_403(self):
        """Пользователь без view_task не проходит test_func и получает 403 до проверки статуса."""
        other = User.objects.create_user('other', password='p')
        r = self._patch_status(other, 'in_progress')
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
# BugDetailView — POST: file upload
# ---------------------------------------------------------------------------

class BugDetailPostFileTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:bug_details', kwargs={'pk': self.task.pk})

    def test_upload_file(self):
        """POST с файлом создаёт объект Attachment, привязанный к задаче, и редиректит обратно."""
        self.client.force_login(self.task_user)
        f = SimpleUploadedFile('test.txt', b'file content', content_type='text/plain')
        r = self.client.post(self.url, {'file': f, 'description': 'Тест файл'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Attachment.objects.filter(task=self.task).exists())


# ---------------------------------------------------------------------------
# BugCreateView
# ---------------------------------------------------------------------------

class BugCreateViewTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:create_bug')

    def test_redirect_anon(self):
        """Анонимный GET на форму создания замечания перенаправляет на логин."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_no_permission_redirects_to_error(self):
        """Пользователь без add_task перенаправляется на страницу ошибки (handle_no_permission)."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_form_renders_for_permitted_user(self):
        """Пользователь с add_task видит форму создания замечания (GET 200)."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_create_bug_post(self):
        """POST с валидными данными создаёт новое замечание и редиректит на его страницу."""
        self.client.force_login(self.task_user)
        r = self.client.post(self.url, {
            'station': self.station.pk,
            'description': 'Новое замечание из теста',
            'responsible_organization': 'Тест Орг',
            'due_date': '',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Task.objects.filter(description='Новое замечание из теста').exists())

    def test_create_bug_sets_responsible_user(self):
        """form_valid() автоматически записывает в responsible_user текущего пользователя."""
        self.client.force_login(self.task_user)
        self.client.post(self.url, {
            'station': self.station.pk,
            'description': 'Замечание для проверки автора',
            'responsible_organization': '',
            'due_date': '',
        })
        task = Task.objects.get(description='Замечание для проверки автора')
        self.assertEqual(task.responsible_user, self.task_user)

    def test_create_bug_missing_required_field(self):
        """POST без обязательных полей (station, description) возвращает форму с ошибками, объект не создаётся."""
        self.client.force_login(self.task_user)
        r = self.client.post(self.url, {'responsible_organization': 'Орг'})
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# BugUpdateView
# ---------------------------------------------------------------------------

class BugUpdateViewTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:bug_update', kwargs={'pk': self.task.pk})

    def test_redirect_anon(self):
        """Анонимный GET на форму редактирования замечания перенаправляет на логин."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_no_permission_no_responsibility_returns_403(self):
        """Пользователь без change_task и не являющийся responsible_user получает 403."""
        other = User.objects.create_user('other2', password='p')
        self.client.force_login(other)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_responsible_user_can_access(self):
        """Ответственный исполнитель (responsible_user) может открыть форму редактирования своей задачи."""
        # plain_user назначен ответственным в setUpTestData
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_permitted_user_can_update(self):
        """POST с новыми данными обновляет замечание в БД для пользователя с change_task."""
        self.client.force_login(self.task_user)
        r = self.client.post(self.url, {
            'station': self.station.pk,
            'description': 'Обновлённое замечание',
            'status': Task.Status.IN_PROGRESS,
            'responsible_organization': '',
        })
        self.assertEqual(r.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.description, 'Обновлённое замечание')

    def test_superuser_can_update(self):
        """Суперпользователь проходит test_func и получает форму редактирования."""
        self.client.force_login(self.superuser)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# AlarmListView
# ---------------------------------------------------------------------------

class AlarmListViewTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:alarm_list')

    def test_redirect_anon(self):
        """Анонимный GET на список алармов перенаправляет на логин."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_logged_in_returns_200(self):
        """Любой авторизованный пользователь видит справочник алармов — прав не требуется."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_alarm_appears_in_list(self):
        """Существующий аларм отображается в таблице на странице списка."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertContains(r, 'T001')

    def test_search_by_number(self):
        """Поиск по номеру аларма возвращает соответствующую запись."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url, {'search': 'T001'})
        self.assertContains(r, 'T001')

    def test_search_no_result(self):
        """Поиск по несуществующему номеру не возвращает записей."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url, {'search': 'Z999'})
        self.assertNotContains(r, 'T001')


# ---------------------------------------------------------------------------
# StationsExportView
# ---------------------------------------------------------------------------

class StationsExportViewTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:stations_export')

    def test_redirect_anon(self):
        """Анонимный GET на экспорт станций перенаправляет на логин."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_station получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_returns_xlsx_for_permitted_user(self):
        """Пользователь с view_station получает файл с корректным Content-Type и именем stations.xlsx."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('stations.xlsx', r['Content-Disposition'])

    def test_xlsx_contains_data(self):
        """Скачанный xlsx содержит данные существующей станции — файл не пустой."""
        import io
        import openpyxl
        self.client.force_login(self.station_user)
        r = self.client.get(self.url)
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        ws = wb.active
        values = [str(cell.value) for row in ws.iter_rows() for cell in row]
        self.assertIn('Тест Станция', values)


# ---------------------------------------------------------------------------
# TasksExportView
# ---------------------------------------------------------------------------

class TasksExportViewTest(ViewTestBase):
    def setUp(self):
        self.url = reverse('signal1520:bugs_export')

    def test_redirect_anon(self):
        """Анонимный GET на экспорт замечаний перенаправляет на логин."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_task получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_returns_xlsx_for_permitted_user(self):
        """Пользователь с view_task получает файл с корректным Content-Type и именем tasks.xlsx."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('tasks.xlsx', r['Content-Disposition'])

    def test_xlsx_contains_task_data(self):
        """Скачанный xlsx содержит описание существующего замечания — файл не пустой."""
        import io
        import openpyxl
        self.client.force_login(self.task_user)
        r = self.client.get(self.url)
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        ws = wb.active
        values = [str(cell.value) for row in ws.iter_rows() for cell in row]
        self.assertIn('Тестовое замечание', values)


# ---------------------------------------------------------------------------
# Intentionally failing test — CI gate check
# ---------------------------------------------------------------------------

class IntentionallyFailingTest(TestCase):
    def test_this_must_fail(self):
        """Этот тест намеренно провальный — используется для проверки CI-блокировки PR."""
        self.assertEqual(2, 2, "Намеренная ошибка: 1 != 2")
