from django.urls import path

from app.views import (
    Home,
    RegisterView,
    UpdateWorkspaceView,
    EmailSentView,
    VerifyView,
    GoogleOauth,
    GoogleOauthCallback,
    RevokeGoogleCredentials,
    Search,
    SearchFailure,
)
from django.conf import settings

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("workspace/", UpdateWorkspaceView.as_view(), name="workspace-update"),
    path("sent/", EmailSentView.as_view(), name="email-sent"),
    path("verify/<str:token>/", VerifyView.as_view(), name="verify-email"),
    path("google-oauth/", GoogleOauth.as_view(), name="google-oauth"),
    path(
        "google-oauth-callback/",
        GoogleOauthCallback.as_view(),
        name="google-oauth-callback",
    ),
    path(
        "google-oauth-revoke/",
        RevokeGoogleCredentials.as_view(),
        name="google-oauth-revoke",
    ),
    path("search/", Search.as_view(), name="search"),
    path("search-failure/", SearchFailure.as_view(), name="search-failure"),
    path("", Home.as_view(), name="home"),
]

if settings.DEMO_USERNAME:
    urlpatterns = [
        path("search/", Search.as_view(), name="search"),
        path("search-failure/", SearchFailure.as_view(), name="search-failure"),
        path("", Home.as_view(), name="home"),
    ]
