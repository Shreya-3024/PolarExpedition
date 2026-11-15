from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from operations import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/logout/", views.logout_view, name="logout"),
    path("accounts/register/", views.register, name="register"),
    path(
        "accounts/password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            success_url="/accounts/password-reset/sent/",
        ),
        name="password_reset",
    ),
    path(
        "accounts/password-reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url="/accounts/reset/complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("", views.dashboard, name="dashboard"),
    path("search/", views.global_search, name="global_search"),
    path("reports/", views.reports, name="reports"),
    path("reports/export.csv", views.report_export, name="report_export"),
    path("notifications/", views.notifications, name="notifications"),
    path("settings/", views.settings_page, name="settings"),
    path("", include("operations.urls")),
]
