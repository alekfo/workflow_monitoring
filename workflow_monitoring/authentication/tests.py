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


class ProfileUpdateTest(TestCase):
    """Форма редактирования профиля: имя и фамилия пишутся в User, остальное — в Profile."""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('editor', first_name='Иван', last_name='Старов')
        Profile.objects.filter(user=cls.user).update(agreement_accepted=True)

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('authentication:profile_update')

    def test_form_shows_current_name_and_no_agreement_checkbox(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'value="Иван"')
        self.assertContains(r, 'value="Старов"')
        self.assertNotContains(r, 'agreement_accepted')

    def test_post_updates_name_and_bio(self):
        r = self.client.post(self.url, {'first_name': 'Пётр', 'last_name': 'Новиков', 'bio': 'Инженер'})
        self.assertRedirects(r, reverse('authentication:about_me'))
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name), ('Пётр', 'Новиков'))
        self.assertEqual(self.user.profile.bio, 'Инженер')
        # согласие, данное при регистрации, форма больше не трогает
        self.assertTrue(self.user.profile.agreement_accepted)

    def test_empty_name_is_rejected(self):
        r = self.client.post(self.url, {'first_name': '', 'last_name': 'Новиков', 'bio': ''})
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Иван')


class PasswordRecoveryTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            'recover-user', email='recover@example.com', password='Old-password-817!'
        )

    def test_login_has_recovery_link(self):
        response = self.client.get(reverse('authentication:login'))
        self.assertContains(response, reverse('authentication:password_reset'))

    def test_email_link_resets_password_and_cannot_be_reused(self):
        import re
        from django.core import mail

        response = self.client.post(reverse('authentication:password_reset'),
                                    {'email': 'RECOVER@example.com'},
                                    HTTP_X_FORWARDED_PROTO='https')
        self.assertRedirects(response, reverse('authentication:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Fieldlog', mail.outbox[0].subject)
        link = re.search(r'https?://[^\s]+', mail.outbox[0].body).group()
        self.assertTrue(link.startswith('https://'))
        response = self.client.get(link, follow=True)
        self.assertTrue(response.context['validlink'])
        form_url = response.request['PATH_INFO']
        response = self.client.post(form_url, {
            'new_password1': 'New-password-914!',
            'new_password2': 'different-password',
        })
        self.assertTrue(response.context['form'].errors)
        response = self.client.post(form_url, {
            'new_password1': 'New-password-914!',
            'new_password2': 'New-password-914!',
        })
        self.assertRedirects(response, reverse('authentication:password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-password-914!'))
        self.assertFalse(self.user.check_password('Old-password-817!'))
        response = self.client.get(link, follow=True)
        self.assertFalse(response.context['validlink'])

    def test_unknown_and_inactive_email_get_same_response_without_mail(self):
        from django.core import mail

        self.user.is_active = False
        self.user.save()
        for email in ['missing@example.com', self.user.email]:
            response = self.client.post(reverse('authentication:password_reset'),
                                        {'email': email})
            self.assertRedirects(response, reverse('authentication:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_expired_link_is_rejected(self):
        from datetime import timedelta
        from unittest.mock import patch
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        now = default_token_generator._now()
        with patch.object(default_token_generator, '_now', return_value=now - timedelta(hours=2)):
            token = default_token_generator.make_token(self.user)
        response = self.client.get(reverse('authentication:password_reset_confirm', kwargs={
            'uidb64': urlsafe_base64_encode(force_bytes(self.user.pk)),
            'token': token,
        }))
        self.assertFalse(response.context['validlink'])

    def test_invalid_link_shows_retry(self):
        response = self.client.get(reverse('authentication:password_reset_confirm', kwargs={
            'uidb64': 'invalid', 'token': 'invalid',
        }))
        self.assertContains(response, 'Запросить новую ссылку')
