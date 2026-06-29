import logging
from http.client import responses

from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LogoutView, LoginView, PasswordChangeView
from django.contrib import messages
from django.utils import timezone
from django.core.mail import EmailMessage
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, reverse
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse_lazy, reverse as url_reverse
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404

from .models import Profile
from .forms import ProfileForm, CustomUserCreationForm

logger = logging.getLogger('authentication')

POLICY_VERSION = '1.0'
_REGISTER_RATE_LIMIT = 5  # попыток регистрации с одного IP за час


class OrgLoginView(LoginView):
    """После успешного логина редиректит на организацию из профиля, игнорируя ?next."""
    template_name = 'authentication/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        try:
            org = self.request.user.profile.organization
            if org:
                return url_reverse('signal1520:index', kwargs={'org_slug': org.slug})
        except ObjectDoesNotExist:
            pass
        return reverse_lazy('authentication:about_me')

    def form_invalid(self, form):
        username = form.data.get('username', '—')
        ip = self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR', '—'))
        logger.warning('Неудачная попытка входа: username="%s", ip=%s', username, ip)
        return super().form_invalid(form)


class ErrorView(View):

    def get(self, request: HttpRequest) -> HttpResponse:

        return render(request, 'authentication/error.html')


class PrivacyPolicyView(TemplateView):
    template_name = 'authentication/privacy_policy.html'


class AboutMeView(LoginRequiredMixin, TemplateView):
    """"Посмотреть инфу о текущем пользователе"""

    template_name = "authentication/about_me.html"

class UsersListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """"Посмотреть список всех пользователей"""

    model = User
    template_name = 'authentication/users_list.html'
    context_object_name = 'users'
    ordering = ['username']

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('authentication.can_view_users_list')

class UserDetailView(LoginRequiredMixin, DetailView):
    """"Посмотреть детальную инфу о любом пользователе"""

    model = User
    template_name = 'authentication/user_detail.html'
    context_object_name = 'user_obj'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Проверяем, может ли текущий пользователь редактировать этого пользователя
        context['can_edit'] = (
                self.request.user.is_authenticated and
                (self.request.user == self.object or self.request.user.is_staff)
        )
        return context

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """"Обновить весь профиль"""

    model = Profile
    form_class = ProfileForm
    template_name = 'authentication/profile_update_form.html'

    success_url = reverse_lazy('authentication:about_me')

    def get_object(self, queryset=None):
        profile, created = Profile.objects.get_or_create(user=self.request.user)
        return profile

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info('Профиль обновлён: username="%s"', self.request.user.username)
        return response

#создаем view для регистрации пользователя на основе класса CreateView
class RegisterView(CreateView):
    #для юзера уже есть форма с необходимой валидацией, в тч двойная проверка пароля
    form_class = CustomUserCreationForm
    template_name = "authentication/register.html"

    def post(self, request, *args, **kwargs):
        ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR', '')
        )
        rate_key = f'register_attempts_{ip}'
        attempts = cache.get(rate_key, 0)
        if attempts >= _REGISTER_RATE_LIMIT:
            logger.warning('Registration rate limit hit: ip=%s', ip)
            messages.error(request, 'Слишком много попыток регистрации с вашего адреса. Попробуйте позже.')
            return self.get(request, *args, **kwargs)
        cache.set(rate_key, attempts + 1, timeout=3600)
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        try:
            org = self.object.profile.organization
            if org:
                from django.urls import reverse
                return reverse('signal1520:index', kwargs={'org_slug': org.slug})
        except ObjectDoesNotExist:
            pass
        return reverse_lazy('authentication:about_me')

    #для того, чтобы после создания формы происходила еще и аутентификация
    # нужно переопределить метод form_valid (в нем поумолчанию происходит сохранение сущности
    #в нем мы просто проделываем аутентификацию вновь созданного пользователя
    def form_valid(self, form):
        response = super().form_valid(form)
        ip = (
            self.request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or self.request.META.get('REMOTE_ADDR')
        )
        consent_dt = timezone.now()
        Profile.objects.create(
            user=self.object,
            agreement_accepted=True,
            consent_given_at=consent_dt,
            consent_ip=ip or None,
            consent_policy_version=POLICY_VERSION,
        )
        username = form.cleaned_data.get("username")
        password = form.cleaned_data.get("password1")
        user = authenticate(self.request, username=username, password=password)
        login(request=self.request, user=user)
        logger.info('Новый пользователь зарегистрирован: username="%s"', username)
        self._send_consent_email(self.object, consent_dt)
        return response

    def _send_consent_email(self, user, consent_dt):
        if not user.email:
            return
        subject = 'Подтверждение регистрации в сервисе Fieldlog'
        message = (
            f'Здравствуйте, {user.get_full_name() or user.username}!\n\n'
            f'Вы успешно зарегистрировались в сервисе Fieldlog.\n\n'
            f'При регистрации вы ознакомились и согласились с Политикой '
            f'конфиденциальности (версия {POLICY_VERSION}) и дали согласие '
            f'на обработку персональных данных.\n\n'
            f'Дата и время: {consent_dt.strftime("%d.%m.%Y %H:%M:%S UTC")}\n\n'
            f'Если вы не регистрировались в сервисе — проигнорируйте это письмо.\n\n'
            f'Для отзыва согласия обратитесь: {settings.SUPPORT_EMAIL}'
        )
        try:
            EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.EMAIL_HOST_USER,
                to=[user.email],
                bcc=[settings.EMAIL_HOST_USER],
            ).send(fail_silently=False)
        except Exception:
            logger.exception('Не удалось отправить письмо о согласии пользователю "%s"', user.username)


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'authentication/password_change_form.html'
    success_url = reverse_lazy('authentication:about_me')

    def form_valid(self, form):
        # update_session_auth_hash вызывается внутри родительского form_valid —
        # текущая сессия остаётся активной после смены пароля
        response = super().form_valid(form)
        messages.success(self.request, 'Пароль успешно изменён.')
        logger.info('Пароль изменён: username="%s"', self.request.user.username)
        return response


class MyLogoutView(LogoutView):
    next_page = reverse_lazy('authentication:login')

class MyLogoutPage(View):
    def get(self, request):
        logout(request)
        return redirect('authentication:login')
