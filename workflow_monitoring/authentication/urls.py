from django.urls import path

from .views import (MyLogoutView,
                    MyLogoutPage,
                    OrgLoginView,
                    AboutMeView,
                    ProfileUpdateView,
                    RegisterView,
                    UsersListView,
                    UserDetailView,
                    ErrorView,
                    CustomPasswordChangeView,)

app_name = "authentication"

urlpatterns = [
    path("login/", OrgLoginView.as_view(), name="login"),
    # path("logout/", logout_view, name="logout"),
    path("logout/", MyLogoutPage.as_view(), name="logout"),
    path("about_me/", AboutMeView.as_view(), name="about_me"),
    path("update/", ProfileUpdateView.as_view(), name="profile_update"),
    path("register/", RegisterView.as_view(), name="register"),
    path("error/", ErrorView.as_view(), name="error"),

    path("password_change/", CustomPasswordChangeView.as_view(), name="password_change"),

    path("users/", UsersListView.as_view(), name="users_list"),
    path("user/<int:pk>/", UserDetailView.as_view(), name="user_detail"),


]