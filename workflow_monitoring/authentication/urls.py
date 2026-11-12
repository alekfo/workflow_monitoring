from django.urls import path
from django.contrib.auth.views import PasswordResetDoneView, PasswordResetCompleteView

from .views import PasswordRecoveryView, PasswordRecoveryConfirmView

from .views import (MyLogoutView,
                    MyLogoutPage,
                    OrgLoginView,
                    AboutMeView,
                    ProfileUpdateView,
                    RegisterView,
                    UsersListView,
                    UserDetailView,
                    ErrorView,
                    CustomPasswordChangeView,
                    PrivacyPolicyView,)

app_name = "authentication"

urlpatterns = [
    path("login/", OrgLoginView.as_view(), name="login"),
    path("password-reset/", PasswordRecoveryView.as_view(), name="password_reset"),
    path("password-reset/done/", PasswordResetDoneView.as_view(
        template_name="authentication/password_reset_done.html",
    ), name="password_reset_done"),
    path("password-reset/complete/", PasswordResetCompleteView.as_view(
        template_name="authentication/password_reset_complete.html",
    ), name="password_reset_complete"),
    path("password-reset/<uidb64>/<token>/", PasswordRecoveryConfirmView.as_view(),
         name="password_reset_confirm"),

    # path("logout/", logout_view, name="logout"),
    path("logout/", MyLogoutPage.as_view(), name="logout"),
    path("about_me/", AboutMeView.as_view(), name="about_me"),
    path("update/", ProfileUpdateView.as_view(), name="profile_update"),
    path("register/", RegisterView.as_view(), name="register"),
    path("error/", ErrorView.as_view(), name="error"),

    path("password_change/", CustomPasswordChangeView.as_view(), name="password_change"),

    path("users/", UsersListView.as_view(), name="users_list"),
    path("user/<int:pk>/", UserDetailView.as_view(), name="user_detail"),
    path("privacy/", PrivacyPolicyView.as_view(), name="privacy_policy"),


]