import secrets
import urllib.parse
import logging
from typing import Any, Dict
from django.urls import reverse_lazy, reverse
from django import views
from django.conf import settings
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from django.views.generic.edit import UpdateView
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, AccessMixin
from app.forms import WorkspaceForm, WorkspaceCreationMultiForm
from app.models import Workspace, Profile, Document, Section
from app.verification import send_verification, verify_user_token
import google.oauth2.credentials
import google_auth_oauthlib.flow
import requests
from poma.search.openai import anwser
from app import tasks

PAGING = 15


class DemoMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if username := settings.DEMO_USERNAME:
            self.request.session["demo"] = True
            login(self.request, user=User.objects.get(username=username))
        else:
            self.request.session.pop("demo", None)
        return super().dispatch(request, *args, **kwargs)


class EmailSentView(TemplateView):
    template_name = "app/email_sent.html"

    def get(self, *args, **kwargs):
        self.request.session["onboarding"] = "email_sent"
        return super().get(*args, **kwargs)


class RegisterView(FormView):
    template_name = "app/register.html"
    form_class = WorkspaceCreationMultiForm
    redirect_authenticated_user = True
    success_url = reverse_lazy("email-sent",)

    def form_invalid(self, form):
        email = form.data.get("email")
        user = User.objects.filter(email=email, is_active=False).first()
        if user is not None:
            send_verification(user)
            form.add_error("email", "We sent another confirmation email just in case!")
        return super().form_invalid(form)

    def form_valid(self, form):
        user = form["user"].save()
        workspace = form["workspace"].save(commit=False)
        workspace.owner = user
        workspace.save()
        profile = Profile.objects.create(user=user, current_workspace=workspace)
        profile.available_workspaces.add(workspace)
        profile.save()
        login(self.request, user)

        ret = super(RegisterView, self).form_valid(form)
        user.is_active = False
        send_verification(user)
        return ret


class VerifyView(views.View):
    def get(self, request, *args, **kwargs):
        token = kwargs.get("token")
        success, user = verify_user_token(token)
        return render(
            request, settings.EMAIL_PAGE_TEMPLATE, {"user": user, "success": success}
        )


class UpdateWorkspaceView(LoginRequiredMixin, UpdateView):
    model = Workspace
    success_url = reverse_lazy("workspace-update")
    form_class = WorkspaceForm

    def get_object(self):
        return self.request.user.profile.current_workspace

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        workspace = self.request.user.profile.current_workspace
        context["has_google"] = (
            workspace.google_token is not None and workspace.google_active is not None
        )
        return context

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.profile.is_admin():
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)


class SearchMixin(DemoMixin):
    default_template = "app/home.html"

    def post(self, request, *args, **kwargs):
        query = self.request.POST.get("search", "")
        gpt = self.request.POST.get("gpt")
        if not query:
            return render(request, self.default_template)
        params = {"q": query}
        if gpt == "on":
            params["gpt"] = "true"
        params = urllib.parse.urlencode(params)
        url = reverse("search") + f"?{params}"
        return redirect(url)


class Home(SearchMixin, LoginRequiredMixin, views.View):
    def get(self, request, *args, **kwargs):
        return render(request, "app/home.html")


class Search(SearchMixin, LoginRequiredMixin, views.View):
    def get(self, request, *args, **kwargs):
        query = request.GET.get("q")
        gpt = request.GET.get("gpt")
        response, error, success = request.user.profile.current_workspace.search(query)
        if not success:
            logging.error("Search failed, %s", error)
            params = {"reason": error}
            params = urllib.parse.urlencode(params)
            url = reverse("search-failure") + f"?{params}"
            return redirect(url)

        data = response.json()
        results = {}
        response_sets = data.get("responseSet", [])
        document_ids = []
        section_ids = []
        for response_set in response_sets:
            documents = response_set.get("document", [])
            for response in response_set.get("response"):
                link = title = ""
                try:
                    document_id = documents[response.get("documentIndex")].get("id")
                    document = Document.objects.filter(identifier=document_id).first()
                    document_ids.append(document.id)
                    if document:
                        link = document.link
                        title = document.title
                except IndexError as e:
                    logging.error("Getting the document failed", exc_info=e)
                    pass
                text = response.get("text", "")
                results[text + "-" + link] = {
                    "text": text,
                    "score": response.get("score", ""),
                    "link": link,
                    "title": title,
                }
                for metadata in response.get("metadata", []):
                    if metadata.get("name") == "section":
                        section_ids.append(int(metadata.get("value")))
        if gpt == "true":
            context = (
                "".join(
                    Section.objects.filter(
                        document_id=document_ids[0], section_id__in=section_ids
                    ).values_list("text", flat=True)
                )[:1000]
                + "..."
            )
            gpt = anwser(query, context)
        else:
            gpt = ""
        return render(
            request,
            "app/search-result.html",
            context={
                "results": sorted(results.values(), key=lambda r: -r["score"]),
                "q": query,
                "gpt_response": gpt,
            },
        )


class SearchFailure(SearchMixin, LoginRequiredMixin, TemplateView):
    template_name = "app/search-failed.html"
    default_template = template_name

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["reason"] = self.request.GET.get("reason", "Unknown")
        return context


class GoogleOauth(views.View):
    def get(self, request, *args, **kwargs):
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            "client_secret.json",
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        flow.redirect_uri = request.build_absolute_uri(reverse("google-oauth-callback"))
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=secrets.token_urlsafe(),
            login_hint=self.request.user.email,
        )
        request.session["google-state"] = state
        return redirect(authorization_url)


class GoogleOauthCallback(views.View):
    def get(self, request, *args, **kwargs):
        state = request.session.pop("google-state")
        code = request.GET.get("code")
        error = request.GET.get("error")
        if error is not None:
            pass
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            "client_secret.json",
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
            state=state,
        )
        flow.redirect_uri = request.build_absolute_uri(reverse("google-oauth-callback"))
        flow.fetch_token(code=code)
        credentials = flow.credentials
        profile = request.user.profile
        if not profile.is_admin():
            return redirect("home")
        workspace = profile.current_workspace

        workspace.add_google_credentials(credentials)
        workspace.activate_google()
        workspace.save()
        tasks.index_workspace.delay(workspace.id)
        return redirect("workspace-update")


class RevokeGoogleCredentials(views.View):
    def get(self, request, *args, **kwargs):
        profile = request.user.profile
        if not profile.is_admin():
            return redirect("home")
        workspace = profile.current_workspace
        workspace_credentials = {
            "token": workspace.google_token,
            "refresh_token": workspace.google_refresh_token,
            "client_id": workspace.google_client_id,
            "client_secret": workspace.google_client_secret,
            "scopes": workspace.google_scopes,
        }
        credentials = google.oauth2.credentials.Credentials(**workspace_credentials)
        response = requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": credentials.token},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        if response.status_code == 200:
            workspace.google_token = None
            workspace.google_refresh_token = None
            workspace.google_active = None
            workspace.save()
        return redirect("workspace-update")
