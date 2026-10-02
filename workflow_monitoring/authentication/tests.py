from django.contrib.auth.models import User, Permission
from django.test import TestCase
from django.urls import reverse

from signal1520.models import Organization, Road, Station
from .models import Profile


def make_user(username, org=None, codenames=(), **extra):
    """Создаёт пользователя с Profile и опциональным набором прав."""
    user = User.objects.create_user(username, password='testpass', **extra)
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    Profile.objects.create(user=user, organization=org)
    return user


class UserProfileAccessTest(TestCase):
    """Профили пользователей доступны только участникам той же организации."""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Org A', slug='org-a')
        cls.other_org = Organization.objects.create(name='Org B', slug='org-b')
        cls.viewer = make_user('viewer', org=cls.org, codenames=['can_view_users_list'])
        cls.colleague = make_user('colleague', org=cls.org, email='colleague@example.com')
        cls.stranger = make_user('stranger', org=cls.other_org, email='stranger@example.com')
        cls.no_org = make_user('no_org')
        cls.superuser = User.objects.create_superuser('root', password='testpass')

    def _detail(self, user):
        return self.client.get(reverse('authentication:user_detail', kwargs={'pk': user.pk}))

    def test_own_profile_visible(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self._detail(self.viewer).status_code, 200)

    def test_same_org_profile_visible(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self._detail(self.colleague).status_code, 200)

    def test_other_org_profile_hidden(self):
        """Профиль пользователя чужой организации отдаёт 404."""
        self.client.force_login(self.viewer)
        self.assertEqual(self._detail(self.stranger).status_code, 404)

    def test_user_without_org_sees_only_self(self):
        """Зарегистрировавшийся, но не привязанный к организации пользователь не видит чужих профилей."""
        self.client.force_login(self.no_org)
        self.assertEqual(self._detail(self.no_org).status_code, 200)
        self.assertEqual(self._detail(self.colleague).status_code, 404)
        self.assertEqual(self._detail(self.stranger).status_code, 404)

    def test_user_without_org_hidden_from_others(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self._detail(self.no_org).status_code, 404)

    def test_superuser_sees_everyone(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self._detail(self.stranger).status_code, 200)
        self.assertEqual(self._detail(self.no_org).status_code, 200)

    def test_anonymous_redirected_to_login(self):
        self.assertEqual(self._detail(self.colleague).status_code, 302)

    def test_users_list_limited_to_own_org(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('authentication:users_list'))
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.context['users'], [self.viewer, self.colleague])

    def test_users_list_superuser_sees_everyone(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('authentication:users_list'))
        self.assertEqual(response.context['users'].count(), User.objects.count())


class UserDeletionTest(TestCase):
    def test_deleting_user_keeps_created_stations(self):
        """Удаление пользователя обнуляет Station.created_by, а не удаляет станцию."""
        org = Organization.objects.create(name='Org A', slug='org-a')
        user = make_user('creator', org=org)
        road = Road.objects.create(title='Дорога', organization=org)
        station = Station.objects.create(name='Ст', road=road, organization=org, created_by=user)

        user.delete()

        station.refresh_from_db()
        self.assertIsNone(station.created_by)
