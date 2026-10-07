import datetime
import io
import json

import openpyxl
from django.contrib.auth.models import User, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authentication.models import Profile
from .models import (
    ActivityEvent, AlarmInfo, Attachment, Comment, Equipment, EquipmentType,
    Knowledge, Organization, Road, Station, System, Task,
    UserKnowledge, Warehouse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username, password='testpass', org=None, codenames=()):
    """Создаёт пользователя с Profile и опциональным набором прав."""
    user = User.objects.create_user(username, password=password)
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    Profile.objects.create(user=user, organization=org)
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
        task = Task.objects.create(station=self.station, description='Задача')
        self.assertEqual(task.status, Task.Status.NEW)

    def test_str(self):
        """__str__ содержит id задачи и имя станции для удобной идентификации в admin."""
        task = Task.objects.create(station=self.station, description='Задача')
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

ORG_SLUG = 'testorg'


class ViewTestBase(TestCase):
    """Создаёт организацию, пользователей с профилями и фикстуры для тестов views."""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Test Org', slug=ORG_SLUG)

        cls.superuser = User.objects.create_superuser('admin', password='pass')
        Profile.objects.create(user=cls.superuser, organization=cls.org)

        cls.plain_user = User.objects.create_user('plain', password='pass')
        Profile.objects.create(user=cls.plain_user, organization=cls.org)

        station_perms = ['view_station', 'add_station', 'change_station']
        task_perms = ['view_task', 'add_task', 'change_task']
        cls.station_user = make_user('station_u', org=cls.org, codenames=station_perms)
        cls.task_user = make_user('task_u', org=cls.org, codenames=task_perms + station_perms)

        cls.road = Road.objects.create(title='Тестовая дорога', organization=cls.org)
        cls.system = System.objects.create(title='Тестовая система', organization=cls.org)
        cls.station = Station.objects.create(
            name='Тест Станция',
            road=cls.road,
            system=cls.system,
            distance='ДЦС-1',
            description='Описание тестовой станции',
            created_by=cls.superuser,
            organization=cls.org,
        )
        cls.task = Task.objects.create(
            station=cls.station,
            description='Тестовая задача',
            status=Task.Status.NEW,
            responsible_user=cls.plain_user,
        )
        cls.alarm = AlarmInfo.objects.create(
            number='T001',
            description='Тестовый аларм описание',
            explanation='Пояснение к аларму',
        )

    def url(self, name, **kwargs):
        """Строит URL с org_slug='testorg' плюс дополнительные kwargs."""
        return reverse(name, kwargs={'org_slug': ORG_SLUG, **kwargs})


# ---------------------------------------------------------------------------
# OrgMixin — изоляция по организации
# ---------------------------------------------------------------------------

class OrgIsolationTest(ViewTestBase):
    def test_user_from_other_org_gets_403(self):
        """Пользователь из другой организации не может открыть страницу этой орги — 403."""
        other_org = Organization.objects.create(name='Other', slug='other')
        other_user = make_user('other_u', org=other_org, codenames=['view_station'])
        self.client.force_login(other_user)
        r = self.client.get(self.url('signal1520:station_list'))
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, 'нет доступа к этой организации', status_code=403)

    def test_no_permission_in_own_org_is_not_reported_as_foreign_org(self):
        """Нехватка прав в своей организации — «Нет прав», а не сообщение о чужой организации."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:station_list'))
        self.assertContains(r, 'Нет прав', status_code=403)
        self.assertNotContains(r, 'нет доступа к этой организации', status_code=403)

    def test_anon_gets_login_redirect(self):
        """Анонимный пользователь перенаправляется на логин, а не получает 403."""
        r = self.client.get(self.url('signal1520:station_list'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])


# ---------------------------------------------------------------------------
# TasksIndexView
# ---------------------------------------------------------------------------

class TasksIndexViewTest(ViewTestBase):
    def test_redirect_if_not_logged_in(self):
        """Анонимный GET на главную перенаправляет на страницу логина (LoginRequiredMixin)."""
        r = self.client.get(self.url('signal1520:index'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_logged_in_returns_200(self):
        """Любой авторизованный пользователь своей орги видит главную страницу."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:index'))
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# StationListView
# ---------------------------------------------------------------------------

class StationListViewTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET перенаправляет на логин с параметром next."""
        u = self.url('signal1520:station_list')
        r = self.client.get(u)
        self.assertRedirects(r, f'/accounts/login/?next={u}')

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_station получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:station_list'))
        self.assertEqual(r.status_code, 403)

    def test_with_permission_returns_200(self):
        """Пользователь с правом view_station видит список станций."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:station_list'))
        self.assertEqual(r.status_code, 200)

    def test_superuser_returns_200(self):
        """Суперпользователь всегда проходит test_func и видит список станций."""
        self.client.force_login(self.superuser)
        r = self.client.get(self.url('signal1520:station_list'))
        self.assertEqual(r.status_code, 200)

    def test_station_appears_in_list(self):
        """Существующая станция отображается в таблице на странице списка."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:station_list'))
        self.assertContains(r, 'Тест Станция')

    def test_search_by_name(self):
        """Поиск по точному имени станции возвращает эту станцию в результатах."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:station_list'), {'search': 'Тест Станция'})
        self.assertContains(r, 'Тест Станция')

    def test_search_by_road(self):
        """Поиск по названию дороги (road__title) находит станции этой дороги."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:station_list'), {'search': 'Тестовая дорога'})
        self.assertContains(r, 'Тест Станция')

    def test_search_by_system(self):
        """Поиск по названию системы (system__title) находит станции с этой системой."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:station_list'), {'search': 'Тестовая система'})
        self.assertContains(r, 'Тест Станция')

    def test_search_no_results(self):
        """Поиск по несуществующей строке не возвращает ни одной станции."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:station_list'), {'search': 'несуществующий_xyz'})
        self.assertNotContains(r, 'Тест Станция')


# ---------------------------------------------------------------------------
# StationDetailView
# ---------------------------------------------------------------------------

class StationDetailViewTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на страницу станции перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:station_details', pk=self.station.pk))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_station получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:station_details', pk=self.station.pk))
        self.assertEqual(r.status_code, 403)

    def test_with_permission_returns_200(self):
        """Пользователь с view_station открывает страницу детали станции."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:station_details', pk=self.station.pk))
        self.assertEqual(r.status_code, 200)

    def test_shows_station_data(self):
        """Страница детали содержит имя, дорогу и систему станции."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:station_details', pk=self.station.pk))
        self.assertContains(r, 'Тест Станция')
        self.assertContains(r, 'Тестовая дорога')
        self.assertContains(r, 'Тестовая система')

    def test_shows_task_in_detail(self):
        """Страница детали станции показывает привязанные к ней задачи."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:station_details', pk=self.station.pk))
        self.assertContains(r, 'Тестовая задача')

    def test_404_for_nonexistent_station(self):
        """Запрос на несуществующий pk станции возвращает 404."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:station_details', pk=99999))
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# StationCreateView
# ---------------------------------------------------------------------------

class StationCreateViewTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на форму создания станции перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:create_station'))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_redirects_to_error(self):
        """Пользователь без add_station перенаправляется на страницу ошибки."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:create_station'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_form_renders_for_permitted_user(self):
        """Пользователь с add_station видит форму создания станции (GET 200)."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:create_station'))
        self.assertEqual(r.status_code, 200)

    def test_form_contains_only_org_roads(self):
        """Выпадающий список road содержит только дороги своей организации."""
        other_org = Organization.objects.create(name='Other', slug='other2')
        Road.objects.create(title='Чужая дорога', organization=other_org)
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:create_station'))
        self.assertContains(r, 'Тестовая дорога')
        self.assertNotContains(r, 'Чужая дорога')

    def test_create_station_post(self):
        """POST с валидными данными создаёт новую станцию и редиректит на её детальную страницу."""
        self.client.force_login(self.station_user)
        r = self.client.post(self.url('signal1520:create_station'), {
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
        self.client.post(self.url('signal1520:create_station'), {
            'name': 'Станция пользователя',
            'road': self.road.pk,
            'distance': '',
            'description': '',
            'latitude': '',
            'longitude': '',
        })
        station = Station.objects.get(name='Станция пользователя')
        self.assertEqual(station.created_by, self.station_user)

    def test_create_station_sets_org(self):
        """form_valid() автоматически записывает organization из URL."""
        self.client.force_login(self.station_user)
        self.client.post(self.url('signal1520:create_station'), {
            'name': 'Станция с оргой',
            'road': self.road.pk,
            'distance': '',
            'description': '',
            'latitude': '',
            'longitude': '',
        })
        station = Station.objects.get(name='Станция с оргой')
        self.assertEqual(station.organization, self.org)

    def test_create_station_without_required_fields_fails(self):
        """POST без обязательных полей возвращает форму с ошибками, объект не создаётся."""
        self.client.force_login(self.station_user)
        r = self.client.post(self.url('signal1520:create_station'), {'description': 'Без названия'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Station.objects.filter(description='Без названия').exists())


# ---------------------------------------------------------------------------
# StationUpdateView
# ---------------------------------------------------------------------------

class StationUpdateViewTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на форму редактирования станции перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:station_update', pk=self.station.pk))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без change_station получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:station_update', pk=self.station.pk))
        self.assertEqual(r.status_code, 403)

    def test_form_renders_for_permitted_user(self):
        """Пользователь с change_station видит форму редактирования (GET 200)."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:station_update', pk=self.station.pk))
        self.assertEqual(r.status_code, 200)

    def test_update_station(self):
        """POST с новым именем обновляет станцию в БД."""
        self.client.force_login(self.station_user)
        r = self.client.post(self.url('signal1520:station_update', pk=self.station.pk), {
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
        r = self.client.get(self.url('signal1520:station_update', pk=self.station.pk))
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# BugsListView
# ---------------------------------------------------------------------------

class BugsListViewTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на список задач перенаправляет на логин с параметром next."""
        u = self.url('signal1520:bugs_list')
        r = self.client.get(u)
        self.assertRedirects(r, f'/accounts/login/?next={u}')

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_task получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:bugs_list'))
        self.assertEqual(r.status_code, 403)

    def test_with_permission_returns_200(self):
        """Пользователь с view_task видит список задач."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:bugs_list'))
        self.assertEqual(r.status_code, 200)

    def test_task_appears_in_list(self):
        """Существующая задача отображается в таблице списка."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:bugs_list'))
        self.assertContains(r, 'Тестовая задача')

    def test_search_by_description(self):
        """Поиск по тексту описания задачи находит нужную запись."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:bugs_list'), {'search': 'Тестовая задача'})
        self.assertContains(r, 'Тестовая задача')

    def test_search_by_station_name(self):
        """Поиск по имени станции (station__name) находит задачи этой станции."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:bugs_list'), {'search': 'Тест Станция'})
        self.assertContains(r, 'Тестовая задача')

    def test_search_no_result(self):
        """Поиск по несуществующей строке не возвращает задач."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:bugs_list'), {'search': 'нет_такого_xyz'})
        self.assertNotContains(r, 'Тестовая задача')


# ---------------------------------------------------------------------------
# MyBugsListView
# ---------------------------------------------------------------------------

class MyBugsListViewTest(ViewTestBase):
    def setUp(self):
        self.responsible_user = make_user(
            'responsible', org=self.org, codenames=['view_task']
        )
        self.own_task = Task.objects.create(
            station=self.station,
            description='Задача resp_user',
            responsible_user=self.responsible_user,
        )

    def test_redirect_anon(self):
        """Анонимный GET на «мои задачи» перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:bugs_list_my'))
        self.assertEqual(r.status_code, 302)

    def test_shows_only_own_tasks(self):
        """Пользователь видит только задачи, где он назначен ответственным."""
        self.client.force_login(self.responsible_user)
        r = self.client.get(self.url('signal1520:bugs_list_my'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Задача resp_user')

    def test_does_not_show_others_tasks(self):
        """Задачи, назначенные другому пользователю, не попадают в список 'мои'."""
        self.client.force_login(self.responsible_user)
        r = self.client.get(self.url('signal1520:bugs_list_my'))
        self.assertNotContains(r, 'Тестовая задача')

    def test_task_user_sees_only_own(self):
        """Пользователь без назначенных задач видит пустой список."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:bugs_list_my'))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Задача resp_user')


# ---------------------------------------------------------------------------
# BugDetailView — GET
# ---------------------------------------------------------------------------

class BugDetailViewGetTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на страницу задачи перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:bug_details', pk=self.task.pk))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_task получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:bug_details', pk=self.task.pk))
        self.assertEqual(r.status_code, 403)

    def test_with_permission_returns_200(self):
        """Пользователь с view_task открывает детальную страницу задачи."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:bug_details', pk=self.task.pk))
        self.assertEqual(r.status_code, 200)

    def test_shows_task_description(self):
        """Страница содержит описание задачи."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:bug_details', pk=self.task.pk))
        self.assertContains(r, 'Тестовая задача')

    def test_404_nonexistent_task(self):
        """Запрос на несуществующий pk задачи возвращает 404."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:bug_details', pk=99999))
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# BugDetailView — POST: comment
# ---------------------------------------------------------------------------

class BugDetailPostCommentTest(ViewTestBase):
    def test_add_comment(self):
        """POST с comment_text создаёт новый Comment и редиректит обратно на задачу."""
        self.client.force_login(self.task_user)
        r = self.client.post(
            self.url('signal1520:bug_details', pk=self.task.pk),
            {'comment_text': 'Мой комментарий'},
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Comment.objects.filter(body='Мой комментарий', task=self.task).exists())

    def test_empty_comment_not_saved(self):
        """POST с пустой строкой не создаёт Comment в БД."""
        self.client.force_login(self.task_user)
        before = Comment.objects.count()
        self.client.post(
            self.url('signal1520:bug_details', pk=self.task.pk),
            {'comment_text': '   '},
        )
        self.assertEqual(Comment.objects.count(), before)

    def test_comment_sets_correct_user(self):
        """Созданный комментарий привязывается к текущему авторизованному пользователю."""
        self.client.force_login(self.task_user)
        self.client.post(
            self.url('signal1520:bug_details', pk=self.task.pk),
            {'comment_text': 'Проверка автора'},
        )
        comment = Comment.objects.get(body='Проверка автора')
        self.assertEqual(comment.user, self.task_user)


# ---------------------------------------------------------------------------
# BugDetailView — POST: comment edit
# ---------------------------------------------------------------------------

class BugDetailEditCommentTest(ViewTestBase):
    def setUp(self):
        self.comment = Comment.objects.create(task=self.task, user=self.task_user, body='Исходный текст')

    def _edit(self, user, text, comment=None):
        self.client.force_login(user)
        return self.client.post(
            self.url('signal1520:bug_details', pk=self.task.pk),
            {'edit_comment_id': (comment or self.comment).pk, 'edit_comment_text': text},
        )

    def _age_comment(self, hours):
        """Сдвигает created_at и updated_at в прошлое в обход auto_now."""
        moment = timezone.now() - datetime.timedelta(hours=hours)
        Comment.objects.filter(pk=self.comment.pk).update(created_at=moment, updated_at=moment)

    def test_author_edits_own_comment(self):
        """Автор меняет текст своего комментария; новый комментарий не создаётся."""
        r = self._edit(self.task_user, 'Новый текст')
        self.assertEqual(r.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, 'Новый текст')
        self.assertEqual(Comment.objects.count(), 1)

    def test_other_user_cannot_edit(self):
        """Чужой комментарий править нельзя даже с правом change_task — 403, текст прежний."""
        other = make_user('other_task_u', org=self.org, codenames=['view_task', 'change_task'])
        r = self._edit(other, 'Чужая правка')
        self.assertEqual(r.status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, 'Исходный текст')

    def test_cannot_edit_after_window(self):
        """Через 24 часа после создания автор править комментарий уже не может."""
        self._age_comment(hours=25)
        r = self._edit(self.task_user, 'Поздняя правка')
        self.assertEqual(r.status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, 'Исходный текст')

    def test_can_edit_within_window(self):
        """За час до истечения окна правка ещё проходит."""
        self._age_comment(hours=23)
        self._edit(self.task_user, 'Успел')
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, 'Успел')

    def test_empty_text_keeps_comment(self):
        """Пустой текст не затирает комментарий."""
        r = self._edit(self.task_user, '   ')
        self.assertEqual(r.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, 'Исходный текст')

    def test_comment_of_other_task_returns_404(self):
        """Комментарий другой задачи через адрес этой задачи не правится."""
        other_task = Task.objects.create(station=self.station, description='Другая задача')
        foreign = Comment.objects.create(task=other_task, user=self.task_user, body='Чужая задача')
        r = self._edit(self.task_user, 'Правка', comment=foreign)
        self.assertEqual(r.status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.body, 'Чужая задача')

    def test_edited_mark_shown_only_after_edit(self):
        """Пометка «изменён» появляется только у отредактированного комментария."""
        self._age_comment(hours=2)
        url = self.url('signal1520:bug_details', pk=self.task.pk)
        self.client.force_login(self.task_user)
        self.assertNotContains(self.client.get(url), 'comment-edited')
        self._edit(self.task_user, 'Исправлено')
        self.assertContains(self.client.get(url), 'comment-edited')

    def test_edit_button_only_for_author_within_window(self):
        """Кнопка правки видна автору в пределах окна и не видна остальным и после окна."""
        url = self.url('signal1520:bug_details', pk=self.task.pk)
        self.client.force_login(self.task_user)
        self.assertContains(self.client.get(url), 'name="edit_comment_id"')
        self.client.force_login(self.superuser)
        self.assertNotContains(self.client.get(url), 'name="edit_comment_id"')
        self._age_comment(hours=25)
        self.client.force_login(self.task_user)
        self.assertNotContains(self.client.get(url), 'name="edit_comment_id"')


# ---------------------------------------------------------------------------
# BugDetailView — POST: status change (JSON)
# ---------------------------------------------------------------------------

class BugDetailPostStatusTest(ViewTestBase):
    def _patch_status(self, user, status):
        self.client.force_login(user)
        return self.client.post(
            self.url('signal1520:bug_details', pk=self.task.pk),
            data=json.dumps({'status': status}),
            content_type='application/json',
        )

    def test_superuser_can_change_status(self):
        """Суперпользователь меняет статус задачи через JSON POST."""
        r = self._patch_status(self.superuser, 'in_progress')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(json.loads(r.content)['success'])
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'in_progress')

    def test_responsible_user_can_change_status(self):
        """Ответственный исполнитель с view_task может менять статус своей задачи."""
        responsible = make_user('resp_view', org=self.org, codenames=['view_task'])
        own_task = Task.objects.create(
            station=self.station,
            description='Задача для resp_view',
            responsible_user=responsible,
        )
        self.client.force_login(responsible)
        r = self.client.post(
            self.url('signal1520:bug_details', pk=own_task.pk),
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
        """JSON POST с недопустимым значением статуса возвращает 400."""
        r = self._patch_status(self.superuser, 'unknown_status')
        self.assertEqual(r.status_code, 400)

    def test_no_permission_returns_403(self):
        """Пользователь без view_task не проходит test_func и получает 403."""
        no_perm = make_user('no_perm_u', org=self.org)
        r = self._patch_status(no_perm, 'in_progress')
        self.assertEqual(r.status_code, 403)

    def _set_status(self, status):
        Task.objects.filter(pk=self.task.pk).update(status=status)

    def test_change_is_recorded_in_history(self):
        """Смена статуса создаёт запись истории: из какого статуса, в какой и кем."""
        self._patch_status(self.task_user, 'in_progress')
        change = self.task.status_changes.get()
        self.assertEqual(change.from_status, 'new')
        self.assertEqual(change.to_status, 'in_progress')
        self.assertEqual(change.changed_by, self.task_user)

    def test_rejected_change_is_not_recorded(self):
        """Отклонённый переход не меняет статус и не попадает в историю."""
        self._set_status('in_progress')
        r = self._patch_status(self.task_user, 'new')
        self.assertEqual(r.status_code, 403)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'in_progress')
        self.assertFalse(self.task.status_changes.exists())

    def test_cannot_return_to_new(self):
        """Вернуть задачу в «Новая» не может никто, включая суперпользователя."""
        self._set_status('in_progress')
        self.assertEqual(self._patch_status(self.superuser, 'new').status_code, 403)
        self._set_status('completed')
        self.assertEqual(self._patch_status(self.superuser, 'new').status_code, 403)

    def test_closed_task_locked_for_non_superuser(self):
        """Выполненную и отменённую задачу не переоткрывают ни обладатель change_task, ни ответственный."""
        for closed in ('completed', 'cancelled'):
            self._set_status(closed)
            for user in (self.task_user, self.plain_user):
                r = self._patch_status(user, 'in_progress')
                self.assertEqual(r.status_code, 403)
            self.task.refresh_from_db()
            self.assertEqual(self.task.status, closed)

    def test_superuser_reopens_closed_task(self):
        """Суперпользователь возвращает закрытую задачу в работу, но не меняет один закрытый статус на другой."""
        self._set_status('completed')
        self.assertEqual(self._patch_status(self.superuser, 'cancelled').status_code, 403)
        self.assertEqual(self._patch_status(self.superuser, 'in_progress').status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'in_progress')

    def test_reopened_task_is_manageable_again(self):
        """После переоткрытия суперпользователем задачу снова закрывает обладатель change_task без ответственности."""
        changer = make_user('only_change', org=self.org, codenames=['view_task', 'change_task'])
        self.assertEqual(self._patch_status(self.task_user, 'completed').status_code, 200)
        self.assertEqual(self._patch_status(self.superuser, 'in_progress').status_code, 200)
        self.client.force_login(changer)
        r = self.client.get(self.url('signal1520:bug_details', pk=self.task.pk))
        self.assertTrue(r.context['can_manage'])
        self.assertEqual([s['value'] for s in r.context['allowed_statuses']], ['completed', 'cancelled'])
        self.assertNotContains(r, 'class="is-locked" disabled')
        self.assertEqual(self._patch_status(changer, 'cancelled').status_code, 200)

    def test_admin_change_is_recorded_in_history(self):
        """Смена статуса через админку тоже пишется в историю."""
        self.client.force_login(self.superuser)
        data = {
            'station': self.station.pk,
            'description': self.task.description,
            'status': 'completed',
            'responsible_organization': '',
            'responsible_user': self.plain_user.pk,
            'due_date': '',
        }
        for prefix in ('status_changes', 'comments', 'attachments'):
            data[f'{prefix}-TOTAL_FORMS'] = 0
            data[f'{prefix}-INITIAL_FORMS'] = 0
        r = self.client.post(reverse('admin:signal1520_task_change', args=[self.task.pk]), data)
        self.assertEqual(r.status_code, 302)
        change = self.task.status_changes.get()
        self.assertEqual((change.from_status, change.to_status), ('new', 'completed'))
        self.assertEqual(change.changed_by, self.superuser)

    def test_admin_history_is_read_only(self):
        """В админке история статусов открывается списком и карточкой, но не создаётся и не правится."""
        change = self.task.change_status('in_progress', self.task_user)
        self.client.force_login(self.superuser)
        r = self.client.get(reverse('admin:signal1520_taskstatuschange_changelist'))
        self.assertContains(r, 'task_u')
        change_url = reverse('admin:signal1520_taskstatuschange_change', args=[change.pk])
        self.assertEqual(self.client.get(change_url).status_code, 200)
        self.assertEqual(self.client.post(change_url, {'to_status': 'completed'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:signal1520_taskstatuschange_add')).status_code, 403)
        # задача с историей по-прежнему удаляется из админки
        r = self.client.post(reverse('admin:signal1520_task_delete', args=[self.task.pk]), {'post': 'yes'})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())

    def test_card_shows_last_change(self):
        """На карточке под статусом — кто сделал последний переход; у задачи без истории подписи нет."""
        url = self.url('signal1520:bug_details', pk=self.task.pk)
        self.client.force_login(self.task_user)
        self.assertNotContains(self.client.get(url), 'id="status-change-info"')
        self._patch_status(self.task_user, 'in_progress')
        self._patch_status(self.task_user, 'completed')
        r = self.client.get(url)
        self.assertContains(r, 'id="status-change-info"')
        self.assertEqual(r.context['last_status_change'].to_status, 'completed')
        self.assertContains(r, 'task_u')

    def test_status_button_disabled_on_closed_task(self):
        """У закрытой задачи кнопка смены статуса неактивна для всех, кроме суперпользователя."""
        self._set_status('cancelled')
        url = self.url('signal1520:bug_details', pk=self.task.pk)
        self.client.force_login(self.task_user)
        r = self.client.get(url)
        self.assertEqual(r.context['allowed_statuses'], [])
        self.assertContains(r, 'class="is-locked" disabled')
        self.client.force_login(self.superuser)
        r = self.client.get(url)
        self.assertEqual([s['value'] for s in r.context['allowed_statuses']], ['in_progress'])
        self.assertNotContains(r, 'class="is-locked" disabled')


# ---------------------------------------------------------------------------
# BugDetailView — POST: file upload
# ---------------------------------------------------------------------------

class BugDetailPostFileTest(ViewTestBase):
    def test_upload_file(self):
        """POST с файлом создаёт объект Attachment, привязанный к задаче."""
        self.client.force_login(self.task_user)
        f = SimpleUploadedFile('test.txt', b'file content', content_type='text/plain')
        r = self.client.post(
            self.url('signal1520:bug_details', pk=self.task.pk),
            {'file': f, 'description': 'Тест файл'},
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Attachment.objects.filter(task=self.task).exists())

    def _upload(self, user):
        self.client.force_login(user)
        f = SimpleUploadedFile('closed.txt', b'file content', content_type='text/plain')
        return self.client.post(self.url('signal1520:bug_details', pk=self.task.pk), {'file': f})

    def test_upload_blocked_on_closed_task(self):
        """К выполненной и отменённой задаче вложение не добавляет никто, включая суперпользователя."""
        for closed in ('completed', 'cancelled'):
            Task.objects.filter(pk=self.task.pk).update(status=closed)
            for user in (self.task_user, self.superuser):
                self.assertEqual(self._upload(user).status_code, 403)
            self.assertFalse(Attachment.objects.filter(task=self.task).exists())

    def test_upload_allowed_after_reopen(self):
        """После возврата задачи в работу вложения снова добавляются."""
        Task.objects.filter(pk=self.task.pk).update(status='completed')
        self.task.refresh_from_db()
        self.task.change_status('in_progress', self.superuser)
        self.assertEqual(self._upload(self.superuser).status_code, 302)
        self.assertTrue(Attachment.objects.filter(task=self.task).exists())

    def test_comment_allowed_on_closed_task(self):
        """Комментарии к закрытой задаче остаются открытыми."""
        Task.objects.filter(pk=self.task.pk).update(status='completed')
        self.client.force_login(self.task_user)
        self.client.post(
            self.url('signal1520:bug_details', pk=self.task.pk),
            {'comment_text': 'Дефект проявился снова'},
        )
        self.assertTrue(Comment.objects.filter(task=self.task, body='Дефект проявился снова').exists())


# ---------------------------------------------------------------------------
# BugCreateView
# ---------------------------------------------------------------------------

class BugCreateViewTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на форму создания задачи перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:create_bug'))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_redirects_to_error(self):
        """Пользователь без add_task перенаправляется на страницу ошибки."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:create_bug'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_form_renders_for_permitted_user(self):
        """Пользователь с add_task видит форму создания задачи (GET 200)."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:create_bug'))
        self.assertEqual(r.status_code, 200)

    def test_form_contains_only_org_stations(self):
        """Выпадающий список station содержит только станции своей организации."""
        other_org = Organization.objects.create(name='Other', slug='other3')
        other_road = Road.objects.create(title='Дорога 2', organization=other_org)
        other_station = Station.objects.create(
            name='Чужая станция', road=other_road,
            created_by=self.superuser, organization=other_org,
        )
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:create_bug'))
        self.assertContains(r, 'Тест Станция')
        self.assertNotContains(r, 'Чужая станция')

    def test_create_bug_post(self):
        """POST с валидными данными создаёт новую задачу и редиректит на её страницу."""
        self.client.force_login(self.task_user)
        r = self.client.post(self.url('signal1520:create_bug'), {
            'station': self.station.pk,
            'description': 'Новая задача из теста',
            'responsible_organization': 'Тест Орг',
            'due_date': '',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Task.objects.filter(description='Новая задача из теста').exists())

    def test_create_bug_sets_responsible_user(self):
        """form_valid() автоматически записывает в responsible_user текущего пользователя."""
        self.client.force_login(self.task_user)
        self.client.post(self.url('signal1520:create_bug'), {
            'station': self.station.pk,
            'description': 'Задача для проверки автора',
            'responsible_organization': '',
            'due_date': '',
        })
        task = Task.objects.get(description='Задача для проверки автора')
        self.assertEqual(task.responsible_user, self.task_user)

    def test_create_bug_missing_required_field(self):
        """POST без обязательных полей возвращает форму с ошибками, объект не создаётся."""
        self.client.force_login(self.task_user)
        r = self.client.post(self.url('signal1520:create_bug'), {'responsible_organization': 'Орг'})
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# BugUpdateView
# ---------------------------------------------------------------------------

class BugUpdateViewTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на форму редактирования задачи перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:bug_update', pk=self.task.pk))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_no_responsibility_returns_403(self):
        """Пользователь без change_task и не являющийся responsible_user получает 403."""
        other = make_user('other2', org=self.org)
        self.client.force_login(other)
        r = self.client.get(self.url('signal1520:bug_update', pk=self.task.pk))
        self.assertEqual(r.status_code, 403)

    def test_responsible_user_can_access(self):
        """Ответственный исполнитель может открыть форму редактирования своей задачи."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:bug_update', pk=self.task.pk))
        self.assertEqual(r.status_code, 200)

    def test_permitted_user_can_update(self):
        """POST с новыми данными обновляет задачу в БД для пользователя с change_task."""
        self.client.force_login(self.task_user)
        r = self.client.post(self.url('signal1520:bug_update', pk=self.task.pk), {
            'station': self.station.pk,
            'description': 'Обновлённая задача',
            'status': Task.Status.IN_PROGRESS,
            'responsible_organization': '',
        })
        self.assertEqual(r.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.description, 'Обновлённая задача')

    def test_superuser_can_update(self):
        """Суперпользователь проходит test_func и получает форму редактирования."""
        self.client.force_login(self.superuser)
        r = self.client.get(self.url('signal1520:bug_update', pk=self.task.pk))
        self.assertEqual(r.status_code, 200)

    def test_status_not_changed_through_form(self):
        """Статус из формы убран: значение из POST игнорируется."""
        self.client.force_login(self.task_user)
        self.client.post(self.url('signal1520:bug_update', pk=self.task.pk), {
            'station': self.station.pk,
            'description': 'Правка без статуса',
            'status': Task.Status.COMPLETED,
            'responsible_organization': '',
        })
        self.task.refresh_from_db()
        self.assertEqual(self.task.description, 'Правка без статуса')
        self.assertEqual(self.task.status, Task.Status.NEW)

    def test_closed_task_editable_only_by_superuser(self):
        """Закрытую задачу правит только суперпользователь; остальным — 403 и неактивная кнопка на карточке."""
        Task.objects.filter(pk=self.task.pk).update(status=Task.Status.COMPLETED)
        update_url = self.url('signal1520:bug_update', pk=self.task.pk)
        detail_url = self.url('signal1520:bug_details', pk=self.task.pk)
        for user in (self.task_user, self.plain_user):
            self.client.force_login(user)
            self.assertEqual(self.client.get(update_url).status_code, 403)
        self.client.force_login(self.task_user)
        self.assertNotContains(self.client.get(detail_url), update_url)
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(update_url).status_code, 200)
        self.assertContains(self.client.get(detail_url), update_url)


# ---------------------------------------------------------------------------
# AlarmListView
# ---------------------------------------------------------------------------

class AlarmListViewTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на список алармов перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:alarm_list'))
        self.assertEqual(r.status_code, 302)

    def test_logged_in_returns_200(self):
        """Любой авторизованный пользователь видит справочник алармов."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:alarm_list'))
        self.assertEqual(r.status_code, 200)

    def test_alarm_appears_in_list(self):
        """Существующий аларм отображается в таблице на странице списка."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:alarm_list'))
        self.assertContains(r, 'T001')

    def test_search_by_number(self):
        """Поиск по номеру аларма возвращает соответствующую запись."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:alarm_list'), {'search': 'T001'})
        self.assertContains(r, 'T001')

    def test_search_no_result(self):
        """Поиск по несуществующему номеру не возвращает записей."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:alarm_list'), {'search': 'Z999'})
        self.assertNotContains(r, 'T001')


# ---------------------------------------------------------------------------
# KnowledgeCreateView
# ---------------------------------------------------------------------------

class KnowledgeCreateViewTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET перенаправляется на логин."""
        r = self.client.get(self.url('signal1520:knowledge_create'))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_redirects_to_error(self):
        """Пользователь без add_userknowledge перенаправляется на страницу ошибки."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:knowledge_create'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_with_permission_returns_200(self):
        """Пользователь с add_userknowledge видит форму добавления инструкции."""
        user = make_user('know_user', org=self.org, codenames=['add_userknowledge'])
        self.client.force_login(user)
        r = self.client.get(self.url('signal1520:knowledge_create'))
        self.assertEqual(r.status_code, 200)

    def test_superuser_can_access(self):
        """Суперпользователь проходит test_func без проверки прав."""
        self.client.force_login(self.superuser)
        r = self.client.get(self.url('signal1520:knowledge_create'))
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# KnowledgeDeleteView
# ---------------------------------------------------------------------------

class KnowledgeDeleteViewTest(ViewTestBase):
    def setUp(self):
        self.know_user = make_user(
            'know_del', org=self.org,
            codenames=['add_userknowledge', 'delete_userknowledge'],
        )
        knowledge = Knowledge.objects.create(
            created_by=self.know_user,
            external_link='https://example.com',
        )
        self.uk = UserKnowledge.objects.create(
            user=self.know_user,
            knowledge=knowledge,
            title='Тестовая инструкция',
        )

    def test_no_permission_returns_403_json(self):
        """Пользователь без delete_userknowledge получает JSON 403."""
        self.client.force_login(self.plain_user)
        r = self.client.post(self.url('signal1520:knowledge_delete', pk=self.uk.pk))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['error'], 'Недостаточно прав')

    def test_owner_with_permission_can_delete(self):
        """Владелец с delete_userknowledge может удалить свою инструкцию."""
        self.client.force_login(self.know_user)
        r = self.client.post(self.url('signal1520:knowledge_delete', pk=self.uk.pk))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])
        self.assertFalse(UserKnowledge.objects.filter(pk=self.uk.pk).exists())


# ---------------------------------------------------------------------------
# StationsExportView
# ---------------------------------------------------------------------------

class StationsExportViewTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на экспорт станций перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:stations_export'))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_station получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:stations_export'))
        self.assertEqual(r.status_code, 403)

    def test_returns_xlsx_for_permitted_user(self):
        """Пользователь с view_station получает файл stations.xlsx."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:stations_export'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('stations.xlsx', r['Content-Disposition'])

    def test_xlsx_contains_data(self):
        """Скачанный xlsx содержит данные существующей станции."""
        self.client.force_login(self.station_user)
        r = self.client.get(self.url('signal1520:stations_export'))
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        values = [str(cell.value) for row in wb.active.iter_rows() for cell in row]
        self.assertIn('Тест Станция', values)


# ---------------------------------------------------------------------------
# TasksExportView
# ---------------------------------------------------------------------------

class TasksExportViewTest(ViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на экспорт задач перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:bugs_export'))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_task получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:bugs_export'))
        self.assertEqual(r.status_code, 403)

    def test_returns_xlsx_for_permitted_user(self):
        """Пользователь с view_task получает файл tasks.xlsx."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:bugs_export'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('tasks.xlsx', r['Content-Disposition'])

    def test_xlsx_contains_task_data(self):
        """Скачанный xlsx содержит описание существующей задачи."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:bugs_export'))
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        values = [str(cell.value) for row in wb.active.iter_rows() for cell in row]
        self.assertIn('Тестовая задача', values)


# ---------------------------------------------------------------------------
# Учёт оборудования — базовая установка
# ---------------------------------------------------------------------------

XLSX_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class WarehouseViewTestBase(ViewTestBase):
    """Расширяет ViewTestBase: добавляет склад, тип и единицу оборудования."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        warehouse_perms = ['view_warehouse', 'add_warehouse', 'change_warehouse']
        equipment_perms = ['view_equipment', 'add_equipment', 'change_equipment', 'add_equipmenttype']
        cls.warehouse_user = make_user(
            'warehouse_u', org=cls.org, codenames=warehouse_perms + equipment_perms
        )
        cls.equipment_viewer = make_user(
            'eq_viewer', org=cls.org, codenames=['view_equipment', 'view_warehouse']
        )

        cls.eq_type = EquipmentType.objects.create(
            organization=cls.org, title='Тестовый тип'
        )
        cls.warehouse = Warehouse.objects.create(
            organization=cls.org,
            title='Тестовый склад',
            responsible_user=cls.superuser,
        )
        cls.equipment = Equipment.objects.create(
            warehouse=cls.warehouse,
            station=cls.station,
            type=cls.eq_type,
            factory_number='SN-001',
            manufacturer='Тест Завод',
        )


# ---------------------------------------------------------------------------
# Model tests — EquipmentType, Warehouse, Equipment
# ---------------------------------------------------------------------------

class EquipmentTypeModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Org', slug='org-model')

    def test_str(self):
        """__str__ возвращает название типа — используется в формах и шаблонах."""
        t = EquipmentType(organization=self.org, title='Реле')
        self.assertEqual(str(t), 'Реле')

    def test_ordering(self):
        """Типы оборудования упорядочены по алфавиту (Meta.ordering=['title'])."""
        EquipmentType.objects.create(organization=self.org, title='Ящик')
        EquipmentType.objects.create(organization=self.org, title='Антенна')
        titles = list(EquipmentType.objects.filter(organization=self.org).values_list('title', flat=True))
        self.assertEqual(titles, sorted(titles))


class WarehouseModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Org', slug='org-wh')

    def test_str(self):
        """__str__ возвращает название склада."""
        w = Warehouse(organization=self.org, title='Центральный склад')
        self.assertEqual(str(w), 'Центральный склад')

    def test_ordering(self):
        """Склады упорядочены по алфавиту (Meta.ordering=['title'])."""
        Warehouse.objects.create(organization=self.org, title='Южный')
        Warehouse.objects.create(organization=self.org, title='Аварийный')
        titles = list(Warehouse.objects.filter(organization=self.org).values_list('title', flat=True))
        self.assertEqual(titles, sorted(titles))


class EquipmentModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Org', slug='org-eq')
        cls.eq_type = EquipmentType.objects.create(organization=cls.org, title='Блок')
        cls.warehouse = Warehouse.objects.create(organization=cls.org, title='Склад')

    def test_str(self):
        """__str__ содержит тип и склад оборудования."""
        eq = Equipment(type=self.eq_type, warehouse=self.warehouse)
        s = str(eq)
        self.assertIn('Блок', s)
        self.assertIn('Склад', s)

    def test_station_nullable(self):
        """Equipment можно сохранить без привязки к станции."""
        eq = Equipment.objects.create(
            warehouse=self.warehouse, type=self.eq_type
        )
        self.assertIsNone(eq.station)


# ---------------------------------------------------------------------------
# WarehouseListView
# ---------------------------------------------------------------------------

class WarehouseListViewTest(WarehouseViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на список складов редиректит на страницу ошибки (handle_no_permission в view)."""
        r = self.client.get(self.url('signal1520:warehouse_list'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_no_permission_redirects_to_error(self):
        """Авторизованный пользователь без view_warehouse перенаправляется на страницу ошибки."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:warehouse_list'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_with_permission_returns_200(self):
        """Пользователь с view_warehouse видит список складов."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_list'))
        self.assertEqual(r.status_code, 200)

    def test_superuser_returns_200(self):
        """Суперпользователь видит список складов."""
        self.client.force_login(self.superuser)
        r = self.client.get(self.url('signal1520:warehouse_list'))
        self.assertEqual(r.status_code, 200)

    def test_warehouse_appears_in_list(self):
        """Существующий склад отображается в таблице."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_list'))
        self.assertContains(r, 'Тестовый склад')

    def test_search_by_title(self):
        """Поиск по названию склада возвращает нужную запись."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_list'), {'search': 'Тестовый'})
        self.assertContains(r, 'Тестовый склад')

    def test_search_no_results(self):
        """Поиск по несуществующей строке не возвращает складов."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_list'), {'search': 'несуществующий_xyz'})
        self.assertNotContains(r, 'Тестовый склад')

    def test_can_add_warehouse_true_for_permitted(self):
        """can_add_warehouse=True передаётся пользователю с правом add_warehouse."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_list'))
        self.assertTrue(r.context['can_add_warehouse'])

    def test_can_add_warehouse_false_without_permission(self):
        """can_add_warehouse=False передаётся пользователю без права add_warehouse."""
        self.client.force_login(self.equipment_viewer)
        r = self.client.get(self.url('signal1520:warehouse_list'))
        self.assertFalse(r.context['can_add_warehouse'])

    def test_other_org_warehouse_not_visible(self):
        """Склады другой организации не попадают в список."""
        other_org = Organization.objects.create(name='Other', slug='wh-other1')
        Warehouse.objects.create(organization=other_org, title='Чужой склад')
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_list'))
        self.assertNotContains(r, 'Чужой склад')


# ---------------------------------------------------------------------------
# WarehouseDetailView
# ---------------------------------------------------------------------------

class WarehouseDetailViewTest(WarehouseViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на карточку склада перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:warehouse_detail', pk=self.warehouse.pk))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_warehouse получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:warehouse_detail', pk=self.warehouse.pk))
        self.assertEqual(r.status_code, 403)

    def test_with_permission_returns_200(self):
        """Пользователь с view_warehouse открывает карточку склада."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_detail', pk=self.warehouse.pk))
        self.assertEqual(r.status_code, 200)

    def test_shows_warehouse_title(self):
        """Карточка склада содержит его название."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_detail', pk=self.warehouse.pk))
        self.assertContains(r, 'Тестовый склад')

    def test_shows_equipment_in_list(self):
        """Карточка склада показывает привязанное оборудование."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_detail', pk=self.warehouse.pk))
        self.assertContains(r, 'Тестовый тип')

    def test_can_edit_true_for_permitted(self):
        """can_edit=True передаётся пользователю с правом change_warehouse."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_detail', pk=self.warehouse.pk))
        self.assertTrue(r.context['can_edit'])

    def test_can_edit_false_without_permission(self):
        """can_edit=False передаётся пользователю без change_warehouse."""
        self.client.force_login(self.equipment_viewer)
        r = self.client.get(self.url('signal1520:warehouse_detail', pk=self.warehouse.pk))
        self.assertFalse(r.context['can_edit'])

    def test_can_add_equipment_true_for_permitted(self):
        """can_add_equipment=True передаётся пользователю с add_equipment."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_detail', pk=self.warehouse.pk))
        self.assertTrue(r.context['can_add_equipment'])

    def test_404_for_nonexistent_warehouse(self):
        """Запрос на несуществующий pk склада возвращает 404."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_detail', pk=99999))
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# WarehouseCreateView
# ---------------------------------------------------------------------------

class WarehouseCreateViewTest(WarehouseViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на форму создания склада перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:warehouse_create'))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_redirects_to_error(self):
        """Пользователь без add_warehouse перенаправляется на страницу ошибки."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:warehouse_create'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_with_permission_returns_200(self):
        """Пользователь с add_warehouse видит форму создания склада."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_create'))
        self.assertEqual(r.status_code, 200)

    def test_form_contains_only_org_users(self):
        """Дропдаун responsible_user содержит только пользователей своей организации."""
        other_org = Organization.objects.create(name='Other', slug='wh-other2')
        other_user = make_user('outsider', org=other_org)
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_create'))
        self.assertNotContains(r, 'outsider')

    def test_create_warehouse_post(self):
        """POST с валидными данными создаёт склад и редиректит на его карточку."""
        self.client.force_login(self.warehouse_user)
        r = self.client.post(self.url('signal1520:warehouse_create'), {
            'title': 'Новый склад из теста',
            'responsible_user': '',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Warehouse.objects.filter(title='Новый склад из теста').exists())

    def test_create_warehouse_sets_org(self):
        """form_valid() автоматически записывает organization из URL."""
        self.client.force_login(self.warehouse_user)
        self.client.post(self.url('signal1520:warehouse_create'), {
            'title': 'Склад с оргой',
            'responsible_user': '',
        })
        w = Warehouse.objects.get(title='Склад с оргой')
        self.assertEqual(w.organization, self.org)

    def test_missing_title_fails(self):
        """POST без обязательного поля title возвращает форму с ошибками."""
        self.client.force_login(self.warehouse_user)
        r = self.client.post(self.url('signal1520:warehouse_create'), {'responsible_user': ''})
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# WarehouseUpdateView
# ---------------------------------------------------------------------------

class WarehouseUpdateViewTest(WarehouseViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на форму редактирования склада перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:warehouse_update', pk=self.warehouse.pk))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_redirects_to_error(self):
        """Авторизованный пользователь без change_warehouse перенаправляется на страницу ошибки."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:warehouse_update', pk=self.warehouse.pk))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_with_permission_returns_200(self):
        """Пользователь с change_warehouse видит форму редактирования."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_update', pk=self.warehouse.pk))
        self.assertEqual(r.status_code, 200)

    def test_update_warehouse(self):
        """POST с новым названием обновляет склад в БД."""
        self.client.force_login(self.warehouse_user)
        r = self.client.post(
            self.url('signal1520:warehouse_update', pk=self.warehouse.pk),
            {'title': 'Переименованный склад', 'responsible_user': ''},
        )
        self.assertEqual(r.status_code, 302)
        self.warehouse.refresh_from_db()
        self.assertEqual(self.warehouse.title, 'Переименованный склад')

    def test_superuser_can_access(self):
        """Суперпользователь проходит test_func и получает форму редактирования."""
        self.client.force_login(self.superuser)
        r = self.client.get(self.url('signal1520:warehouse_update', pk=self.warehouse.pk))
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# EquipmentListView
# ---------------------------------------------------------------------------

class EquipmentListViewTest(WarehouseViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на список оборудования редиректит на страницу ошибки (handle_no_permission в view)."""
        r = self.client.get(self.url('signal1520:equipment_list'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_no_permission_redirects_to_error(self):
        """Авторизованный пользователь без view_equipment перенаправляется на страницу ошибки."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:equipment_list'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_with_permission_returns_200(self):
        """Пользователь с view_equipment видит список оборудования."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_list'))
        self.assertEqual(r.status_code, 200)

    def test_equipment_appears_in_list(self):
        """Существующая единица оборудования отображается в таблице."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_list'))
        self.assertContains(r, 'Тестовый тип')

    def test_search_by_type(self):
        """Поиск по названию типа находит нужное оборудование."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_list'), {'search': 'Тестовый тип'})
        self.assertContains(r, 'Тестовый тип')

    def test_search_by_warehouse(self):
        """Поиск по названию склада находит оборудование этого склада."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_list'), {'search': 'Тестовый склад'})
        self.assertContains(r, 'Тестовый тип')

    def test_search_no_results(self):
        """Поиск по несуществующей строке не возвращает записей."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_list'), {'search': 'несуществующий_xyz'})
        self.assertNotContains(r, 'Тестовый тип')

    def test_other_org_equipment_not_visible(self):
        """Оборудование другой организации не попадает в список."""
        other_org = Organization.objects.create(name='Other', slug='eq-other1')
        other_type = EquipmentType.objects.create(organization=other_org, title='Чужой тип')
        other_wh = Warehouse.objects.create(organization=other_org, title='Чужой склад')
        Equipment.objects.create(warehouse=other_wh, type=other_type)
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_list'))
        self.assertNotContains(r, 'Чужой тип')

    def test_can_add_equipment_true_for_permitted(self):
        """can_add_equipment=True передаётся пользователю с правом add_equipment."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_list'))
        self.assertTrue(r.context['can_add_equipment'])

    def test_can_add_type_true_for_permitted(self):
        """can_add_type=True передаётся пользователю с правом add_equipmenttype."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_list'))
        self.assertTrue(r.context['can_add_type'])

    def test_can_add_flags_false_without_permission(self):
        """can_add_equipment и can_add_type — False у пользователя с только view_equipment."""
        viewer = make_user('eq_only_viewer', org=self.org, codenames=['view_equipment'])
        self.client.force_login(viewer)
        r = self.client.get(self.url('signal1520:equipment_list'))
        self.assertFalse(r.context['can_add_equipment'])
        self.assertFalse(r.context['can_add_type'])


# ---------------------------------------------------------------------------
# EquipmentDetailView
# ---------------------------------------------------------------------------

class EquipmentDetailViewTest(WarehouseViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на карточку оборудования перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:equipment_detail', pk=self.equipment.pk))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_equipment получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:equipment_detail', pk=self.equipment.pk))
        self.assertEqual(r.status_code, 403)

    def test_with_permission_returns_200(self):
        """Пользователь с view_equipment открывает карточку оборудования."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_detail', pk=self.equipment.pk))
        self.assertEqual(r.status_code, 200)

    def test_shows_equipment_data(self):
        """Карточка содержит тип, завод-изготовитель и заводской номер."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_detail', pk=self.equipment.pk))
        self.assertContains(r, 'Тестовый тип')
        self.assertContains(r, 'Тест Завод')
        self.assertContains(r, 'SN-001')

    def test_can_edit_true_for_permitted(self):
        """can_edit=True передаётся пользователю с правом change_equipment."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_detail', pk=self.equipment.pk))
        self.assertTrue(r.context['can_edit'])

    def test_can_edit_false_without_permission(self):
        """can_edit=False передаётся пользователю без change_equipment."""
        self.client.force_login(self.equipment_viewer)
        r = self.client.get(self.url('signal1520:equipment_detail', pk=self.equipment.pk))
        self.assertFalse(r.context['can_edit'])

    def test_can_view_warehouse_true_for_permitted(self):
        """can_view_warehouse=True передаётся пользователю с правом view_warehouse."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_detail', pk=self.equipment.pk))
        self.assertTrue(r.context['can_view_warehouse'])

    def test_can_view_warehouse_false_without_permission(self):
        """can_view_warehouse=False у пользователя только с view_equipment."""
        viewer = make_user('eq_no_wh', org=self.org, codenames=['view_equipment'])
        self.client.force_login(viewer)
        r = self.client.get(self.url('signal1520:equipment_detail', pk=self.equipment.pk))
        self.assertFalse(r.context['can_view_warehouse'])

    def test_404_for_nonexistent_equipment(self):
        """Запрос на несуществующий pk оборудования возвращает 404."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_detail', pk=99999))
        self.assertEqual(r.status_code, 404)

    def test_other_org_equipment_returns_404(self):
        """Оборудование из другой организации возвращает 404 (фильтрация по org)."""
        other_org = Organization.objects.create(name='Other', slug='eq-other2')
        other_type = EquipmentType.objects.create(organization=other_org, title='Чужой тип')
        other_wh = Warehouse.objects.create(organization=other_org, title='Чужой склад')
        other_eq = Equipment.objects.create(warehouse=other_wh, type=other_type)
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_detail', pk=other_eq.pk))
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# EquipmentCreateView
# ---------------------------------------------------------------------------

class EquipmentCreateViewTest(WarehouseViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на форму создания оборудования перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:equipment_create'))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_redirects_to_error(self):
        """Пользователь без add_equipment перенаправляется на страницу ошибки."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:equipment_create'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_with_permission_returns_200(self):
        """Пользователь с add_equipment видит форму создания оборудования."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_create'))
        self.assertEqual(r.status_code, 200)

    def test_form_contains_only_org_warehouses(self):
        """Дропдаун warehouse содержит только склады своей организации."""
        other_org = Organization.objects.create(name='Other', slug='eq-other3')
        Warehouse.objects.create(organization=other_org, title='Чужой склад в форме')
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_create'))
        self.assertContains(r, 'Тестовый склад')
        self.assertNotContains(r, 'Чужой склад в форме')

    def test_form_contains_only_org_types(self):
        """Дропдаун type содержит только типы оборудования своей организации."""
        other_org = Organization.objects.create(name='Other', slug='eq-other4')
        EquipmentType.objects.create(organization=other_org, title='Чужой тип в форме')
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_create'))
        self.assertContains(r, 'Тестовый тип')
        self.assertNotContains(r, 'Чужой тип в форме')

    def test_create_equipment_post(self):
        """POST с валидными данными создаёт оборудование и редиректит на его карточку."""
        self.client.force_login(self.warehouse_user)
        r = self.client.post(self.url('signal1520:equipment_create'), {
            'warehouse': self.warehouse.pk,
            'station': '',
            'type': self.eq_type.pk,
            'factory_number': 'SN-NEW',
            'manufacturer': '',
            'date_of_manufacture': '',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Equipment.objects.filter(factory_number='SN-NEW').exists())

    def test_missing_required_field_fails(self):
        """POST без обязательных полей возвращает форму с ошибками."""
        self.client.force_login(self.warehouse_user)
        r = self.client.post(self.url('signal1520:equipment_create'), {'factory_number': 'SN-FAIL'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Equipment.objects.filter(factory_number='SN-FAIL').exists())


# ---------------------------------------------------------------------------
# EquipmentUpdateView
# ---------------------------------------------------------------------------

class EquipmentUpdateViewTest(WarehouseViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на форму редактирования оборудования перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:equipment_update', pk=self.equipment.pk))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_redirects_to_error(self):
        """Авторизованный пользователь без change_equipment перенаправляется на страницу ошибки."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:equipment_update', pk=self.equipment.pk))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_with_permission_returns_200(self):
        """Пользователь с change_equipment видит форму редактирования."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_update', pk=self.equipment.pk))
        self.assertEqual(r.status_code, 200)

    def test_update_equipment(self):
        """POST с новыми данными обновляет запись об оборудовании в БД."""
        self.client.force_login(self.warehouse_user)
        r = self.client.post(
            self.url('signal1520:equipment_update', pk=self.equipment.pk),
            {
                'warehouse': self.warehouse.pk,
                'station': '',
                'type': self.eq_type.pk,
                'factory_number': 'SN-UPDATED',
                'manufacturer': 'Новый завод',
                'date_of_manufacture': '',
            },
        )
        self.assertEqual(r.status_code, 302)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.factory_number, 'SN-UPDATED')

    def test_superuser_can_access(self):
        """Суперпользователь проходит test_func и получает форму редактирования."""
        self.client.force_login(self.superuser)
        r = self.client.get(self.url('signal1520:equipment_update', pk=self.equipment.pk))
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# EquipmentTypeCreateView
# ---------------------------------------------------------------------------

class EquipmentTypeCreateViewTest(WarehouseViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:equipment_type_create'))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_redirects_to_error(self):
        """Пользователь без add_equipmenttype перенаправляется на страницу ошибки."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:equipment_type_create'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error', r['Location'])

    def test_with_permission_returns_200(self):
        """Пользователь с add_equipmenttype видит форму."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_type_create'))
        self.assertEqual(r.status_code, 200)

    def test_create_type_post(self):
        """POST создаёт тип оборудования с привязкой к организации из URL."""
        self.client.force_login(self.warehouse_user)
        r = self.client.post(
            self.url('signal1520:equipment_type_create'), {'title': 'Новый тип из теста'}
        )
        self.assertEqual(r.status_code, 302)
        t = EquipmentType.objects.get(title='Новый тип из теста')
        self.assertEqual(t.organization, self.org)

    def test_missing_title_fails(self):
        """POST без title возвращает форму с ошибками."""
        self.client.force_login(self.warehouse_user)
        r = self.client.post(self.url('signal1520:equipment_type_create'), {})
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# EquipmentExportView
# ---------------------------------------------------------------------------

class EquipmentExportViewTest(WarehouseViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET на экспорт оборудования перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:equipment_export'))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_equipment получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:equipment_export'))
        self.assertEqual(r.status_code, 403)

    def test_returns_xlsx_for_permitted_user(self):
        """Пользователь с view_equipment получает файл equipment.xlsx."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_export'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], XLSX_CONTENT_TYPE)
        self.assertIn('equipment.xlsx', r['Content-Disposition'])

    def test_xlsx_contains_equipment_data(self):
        """Скачанный xlsx содержит данные существующего оборудования."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:equipment_export'))
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        values = [str(cell.value) for row in wb.active.iter_rows() for cell in row]
        self.assertIn('Тестовый тип', values)
        self.assertIn('Тестовый склад', values)


# ---------------------------------------------------------------------------
# WarehouseEquipmentExportView
# ---------------------------------------------------------------------------

class WarehouseEquipmentExportViewTest(WarehouseViewTestBase):
    def test_redirect_anon(self):
        """Анонимный GET перенаправляет на логин."""
        r = self.client.get(self.url('signal1520:warehouse_equipment_export', pk=self.warehouse.pk))
        self.assertEqual(r.status_code, 302)

    def test_no_permission_returns_403(self):
        """Авторизованный пользователь без view_equipment получает 403."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:warehouse_equipment_export', pk=self.warehouse.pk))
        self.assertEqual(r.status_code, 403)

    def test_returns_xlsx_for_permitted_user(self):
        """Пользователь с view_equipment получает xlsx-файл оборудования склада."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_equipment_export', pk=self.warehouse.pk))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], XLSX_CONTENT_TYPE)

    def test_xlsx_contains_warehouse_equipment(self):
        """Скачанный xlsx содержит оборудование именно этого склада."""
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_equipment_export', pk=self.warehouse.pk))
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        values = [str(cell.value) for row in wb.active.iter_rows() for cell in row]
        self.assertIn('Тестовый тип', values)

    def test_other_org_warehouse_returns_404(self):
        """Экспорт оборудования склада из другой организации возвращает 404."""
        other_org = Organization.objects.create(name='Other', slug='exp-other1')
        other_wh = Warehouse.objects.create(organization=other_org, title='Чужой склад')
        self.client.force_login(self.warehouse_user)
        r = self.client.get(self.url('signal1520:warehouse_equipment_export', pk=other_wh.pk))
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# Задача без ответственного (пользователь удалён, responsible_user = NULL)
# ---------------------------------------------------------------------------

class TaskWithoutResponsibleUserTest(ViewTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.orphan_task = Task.objects.create(
            station=cls.station,
            description='Задача без ответственного',
            status=Task.Status.NEW,
            responsible_user=None,
        )

    def test_list_renders(self):
        """Список задач открывается, если у задачи нет ответственного."""
        self.client.force_login(self.superuser)
        r = self.client.get(self.url('signal1520:bugs_list'))
        self.assertContains(r, 'Задача без ответственного')

    def test_detail_renders(self):
        """Карточка задачи открывается, если у задачи нет ответственного."""
        self.client.force_login(self.superuser)
        r = self.client.get(self.url('signal1520:bug_details', pk=self.orphan_task.pk))
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# Главная: сводка
# ---------------------------------------------------------------------------

class IndexSummaryTest(ViewTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        today = datetime.date.today()
        for description, due_date, status in [
            ('Просроченная', today - datetime.timedelta(days=3), Task.Status.NEW),
            ('Скоро срок', today + datetime.timedelta(days=5), Task.Status.IN_PROGRESS),
            ('Далёкий срок', today + datetime.timedelta(days=90), Task.Status.NEW),
            ('Закрытая просроченная', today - datetime.timedelta(days=3), Task.Status.COMPLETED),
        ]:
            Task.objects.create(
                station=cls.station, description=description, status=status,
                due_date=due_date, responsible_user=cls.task_user,
            )

    def test_counts_for_user_with_task_permission(self):
        """Открытые и выполненные считаются отдельно; свои и всей организации — тоже."""
        self.client.force_login(self.task_user)
        r = self.client.get(self.url('signal1520:index'))
        self.assertEqual(r.context['my_tasks'], {'open': 3, 'overdue': 1, 'due_soon': 1, 'completed': 1})
        # в базовых фикстурах есть ещё одна открытая задача без срока на plain_user
        self.assertEqual(r.context['org_tasks'], {'open': 4, 'overdue': 1, 'due_soon': 1, 'completed': 1})
        self.assertContains(r, 'выполнено мной: 1')
        self.assertContains(r, 'выполнено организацией: 1')
        self.assertEqual(r.context['stations_count'], 1)

    def test_no_permissions_shows_no_numbers(self):
        """Без прав на разделы сводка не раскрывает количество задач и объектов."""
        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:index'))
        self.assertEqual(r.status_code, 200)
        for key in ('my_tasks', 'org_tasks', 'stations_count', 'equipment_count', 'warehouses_count'):
            self.assertNotIn(key, r.context)
        self.assertContains(r, 'Выберите раздел в меню')


# ---------------------------------------------------------------------------
# Главная: лента последних изменений
# ---------------------------------------------------------------------------

class ActivityFeedTest(ViewTestBase):
    def _texts(self, user):
        self.client.force_login(user)
        r = self.client.get(self.url('signal1520:index'))
        return [event.text for event in r.context.get('activity_events', [])]

    def test_task_actions_are_logged(self):
        """Создание задачи, комментарий, вложение и смена статуса попадают в ленту с автором."""
        self.client.force_login(self.task_user)
        self.client.post(self.url('signal1520:create_bug'), {
            'station': self.station.pk, 'description': 'Задача для ленты',
            'responsible_organization': '', 'due_date': '',
        })
        task = Task.objects.get(description='Задача для ленты')
        detail_url = self.url('signal1520:bug_details', pk=task.pk)
        self.client.post(detail_url, {'comment_text': 'Комментарий'})
        self.client.post(detail_url, {'file': SimpleUploadedFile('a.txt', b'x', content_type='text/plain')})
        self.client.post(detail_url, data=json.dumps({'status': 'completed'}), content_type='application/json')

        events = ActivityEvent.objects.filter(task=task).order_by('pk')
        prefix = f'Задача #{task.pk}, Тест Станция — '
        self.assertEqual([e.text for e in events], [
            prefix + 'создана',
            prefix + 'добавлен комментарий',
            prefix + 'добавлено вложение',
            prefix + 'статус «Выполнена»',
        ])
        for event in events:
            self.assertEqual(event.user, self.task_user)
            self.assertEqual(event.organization, self.org)

    def test_station_creation_is_logged(self):
        """Создание объекта попадает в ленту."""
        self.client.force_login(self.station_user)
        self.client.post(self.url('signal1520:create_station'), {
            'name': 'Новый объект', 'road': self.road.pk, 'distance': 'ДЦС-2',
            'system': self.system.pk, 'description': '', 'latitude': '', 'longitude': '',
        })
        event = ActivityEvent.objects.get(kind=ActivityEvent.Kind.STATION_CREATED)
        self.assertEqual(event.text, 'Объект «Новый объект» — создан')
        self.assertEqual(event.user, self.station_user)

    def test_rejected_actions_are_not_logged(self):
        """Пустой комментарий, правка комментария и отклонённая смена статуса событий не создают."""
        comment = Comment.objects.create(task=self.task, user=self.task_user, body='Текст')
        detail_url = self.url('signal1520:bug_details', pk=self.task.pk)
        self.client.force_login(self.task_user)
        self.client.post(detail_url, {'comment_text': '   '})
        self.client.post(detail_url, {'edit_comment_id': comment.pk, 'edit_comment_text': 'Правка'})
        self.client.post(detail_url, data=json.dumps({'status': 'new'}), content_type='application/json')
        self.assertFalse(ActivityEvent.objects.exists())

    def test_feed_respects_section_permissions(self):
        """События по задачам видны при view_task, по объектам — при view_station; без прав блока нет."""
        ActivityEvent.log(ActivityEvent.Kind.TASK_CREATED, self.task_user, task=self.task)
        ActivityEvent.log(ActivityEvent.Kind.STATION_CREATED, self.station_user, station=self.station)
        task_text = f'Задача #{self.task.pk}, Тест Станция — создана'
        station_text = 'Объект «Тест Станция» — создан'

        self.assertEqual(self._texts(self.task_user), [station_text, task_text])
        self.assertEqual(self._texts(self.station_user), [station_text])
        only_tasks = make_user('only_tasks', org=self.org, codenames=['view_task'])
        self.assertEqual(self._texts(only_tasks), [task_text])

        self.client.force_login(self.plain_user)
        r = self.client.get(self.url('signal1520:index'))
        self.assertNotIn('activity_events', r.context)
        self.assertNotContains(r, 'Последние изменения')

    def test_feed_shows_only_own_organization(self):
        """События другой организации в ленту не попадают."""
        other_org = Organization.objects.create(name='Other', slug='feed-other')
        other_road = Road.objects.create(title='Дорога 2', organization=other_org)
        other_station = Station.objects.create(
            name='Чужая станция', road=other_road, created_by=self.superuser, organization=other_org,
        )
        ActivityEvent.log(ActivityEvent.Kind.STATION_CREATED, self.superuser, station=other_station)
        self.assertEqual(self._texts(self.task_user), [])
        self.assertContains(self.client.get(self.url('signal1520:index')), 'Изменений пока нет')

    def test_event_survives_task_deletion(self):
        """После удаления задачи событие остаётся в ленте, но уже не ссылка."""
        ActivityEvent.log(ActivityEvent.Kind.TASK_CREATED, self.task_user, task=self.task)
        detail_url = self.url('signal1520:bug_details', pk=self.task.pk)
        self.client.force_login(self.task_user)
        self.assertContains(self.client.get(self.url('signal1520:index')), f'href="{detail_url}"')
        self.task.delete()
        r = self.client.get(self.url('signal1520:index'))
        self.assertContains(r, 'Тест Станция — создана')
        self.assertNotContains(r, f'href="{detail_url}"')

    def test_feed_is_newest_first_and_limited(self):
        """Лента идёт от новых к старым и отдаёт не больше ACTIVITY_LIMIT строк."""
        for _ in range(45):
            ActivityEvent.log(ActivityEvent.Kind.TASK_COMMENT, self.task_user, task=self.task)
        newest = ActivityEvent.log(ActivityEvent.Kind.TASK_ATTACHMENT, self.task_user, task=self.task)
        self.client.force_login(self.task_user)
        events = list(self.client.get(self.url('signal1520:index')).context['activity_events'])
        self.assertEqual(len(events), 40)
        self.assertEqual(events[0], newest)
