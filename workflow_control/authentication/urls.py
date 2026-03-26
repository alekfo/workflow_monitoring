from django.urls import path
from django.contrib.auth.views import LoginView

from .views import (MyLogoutView,
                    MyLogoutPage,
                    AboutMeView,
                    ProfileUpdateView,
                    RegisterView,
                    UsersListView,
                    UserDetailView)

app_name = "authentication"

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(
            template_name="authentication/login.html",
            redirect_authenticated_user=True),
        # необходимо для перенаправления пользователя по redirect логина если пользователь уже аутентифицирован
        name="login"),
    # path("logout/", logout_view, name="logout"),
    path("logout/", MyLogoutPage.as_view(), name="logout"),
    path("about_me/", AboutMeView.as_view(), name="about_me"),
    path("update/", ProfileUpdateView.as_view(), name="profile_update"),
    path("register/", RegisterView.as_view(), name="register"),

    path("users/", UsersListView.as_view(), name="users_list"),
    path("user/<int:pk>/", UserDetailView.as_view(), name="user_detail"),


]