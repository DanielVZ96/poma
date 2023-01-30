import ast

import logging
from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone
from fernet_fields import EncryptedTextField, EncryptedIntegerField

from django_resized import ResizedImageField

from poma.search.semantic import create_corpus, search


User._meta.get_field("email")._unique = True


def is_ascii(value):
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        raise ValidationError("Please only use ascii characters")


class Workspace(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workspaces")
    name = models.CharField(max_length=255, validators=[is_ascii])
    logo = ResizedImageField(
        size=[300, 300], scale=True, default="poma.png", upload_to="workspace_pic",
    )
    description = models.TextField()
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    google_active = models.DateTimeField(default=None, null=True)
    google_token = EncryptedTextField(default=None, null=True)
    google_refresh_token = EncryptedTextField(default=None, null=True)
    google_client_id = EncryptedTextField(default=None, null=True)
    google_client_secret = EncryptedTextField(default=None, null=True)
    google_scopes = EncryptedTextField(default=None, null=True)
    corpus_id = EncryptedIntegerField(default=None, null=True)

    def get_absolute_url(self):
        return reverse("workspace-update", kwargs={"pk": self.pk})

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

    @property
    def is_valid(self):
        return self.name != ""

    def add_google_credentials(self, credentials):
        self.google_token = credentials.token
        self.google_refresh_token = credentials.refresh_token
        self.google_client_id = credentials.client_id
        self.google_client_secret = credentials.client_secret
        self.google_scopes = credentials.scopes

    @property
    def google_credentials(self):
        return {
            "token": self.google_token,
            "refresh_token": self.google_refresh_token,
            "client_id": self.google_client_id,
            "client_secret": self.google_client_secret,
            "scopes": ast.literal_eval(self.google_scopes),
        }

    def activate_google(self):
        self.google_active = timezone.now()
        self.save()

    def create_corpus(self):
        response, success = create_corpus(self.name, f"{self.name}'s Corpus")
        corpus_id = response.json()["corpusId"]
        if success and corpus_id:
            self.corpus_id = corpus_id
            self.save()
        elif success:
            self.corpus_id = None
            logging.error(
                "Corpus Creation failed: %s",
                response.get("status", {}).get("statusDetail", "No reasons found"),
            )

    def search(self, query: str):
        if self.corpus_id:
            return search(query, self.corpus_id)
        return None, "workplace has not been indexed yet", False


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    current_workspace = models.ForeignKey(
        Workspace, on_delete=models.DO_NOTHING, related_name="active_users"
    )
    available_workspaces = models.ManyToManyField(
        Workspace, related_name="allowed_users"
    )

    def is_admin(self):
        return self.user == self.current_workspace.owner

    def logo(self):
        return self.current_workspace.logo.url


class Document(models.Model):
    workspace = models.ForeignKey(
        Workspace, on_delete=models.DO_NOTHING, related_name="documents"
    )
    link = models.URLField()
    title = models.TextField(blank=True)
    identifier = models.CharField(max_length=255, db_index=True)
    size = models.PositiveBigIntegerField()  # size in bytes
    # TODO ADD DOCUMENT PERMISSIONS FOR VALIDATION


class Section(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.DO_NOTHING, related_name="sections"
    )
    word_count = models.PositiveIntegerField()
    section_id = models.PositiveIntegerField(db_index=True)
    text = EncryptedTextField(blank=True)
