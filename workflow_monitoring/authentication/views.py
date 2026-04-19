from http.client import responses

from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LogoutView
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, reverse
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404

from .models import Profile
from .forms import ProfileForm, CustomUserCreationForm

class ErrorView(View):

    def get(self, request: HttpRequest) -> HttpResponse:

        return render(request, 'authentication/error.html')


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

#создаем view для регистрации пользователя на основе класса CreateView
class RegisterView(CreateView):
    #для юзера уже есть форма с необходимой валидацией, в тч двойная проверка пароля
    form_class = CustomUserCreationForm
    template_name = "authentication/register.html"
    success_url = reverse_lazy("signal1520:index")

    #для того, чтобы после создания формы происходила еще и аутентификация
    # нужно переопределить метод form_valid (в нем поумолчанию происходит сохранение сущности
    #в нем мы просто проделываем аутентификацию вновь созданного пользователя
    def form_valid(self, form):
        response = super().form_valid(form)
        #создаем вместе со стандартным пользователем расширенную модель,
        #которая берем user из self.obkect
        Profile.objects.create(user=self.object)
        username = form.cleaned_data.get("username")
        #используем ключ password1,т.к в опубликованной форме у нас 2 пароля для подтверждения
        password = form.cleaned_data.get("password1")

        user = authenticate(
            self.request,
            username=username,
            password=password
        )
        #выполняем вход пользователя с помощью login
        login(request=self.request, user=user)
        return response


class MyLogoutView(LogoutView):
    next_page = reverse_lazy('authentication:login')

class MyLogoutPage(View):
    def get(self, request):
        logout(request)
        return redirect('authentication:login')
