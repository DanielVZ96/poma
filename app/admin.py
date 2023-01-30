from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from app.models import Workspace, Profile, Document, Section


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    exclude = (
        "google_token",
        "google_refresh_token",
        "google_client_id",
        "google_client_secret",
        "google_scopes",
        "corpus_id",
    )


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    pass


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    exclude = ("text",)
