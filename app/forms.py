from django import forms
from django.contrib.auth.forms import UserCreationForm
from betterforms.multiform import MultiModelForm
from django.utils.html import format_html

from django.contrib.auth.models import User

from app.models import Workspace, is_ascii


class PictureWidget(forms.widgets.FileInput):
    def render(self, *args, **kwargs):
        return format_html(
            """
            <img width="80px" height="80px" class="rounded-2xl aspect-1 aspect object-cover" id="img_logo" src="/media/{}"/></td></tr>
            <tr><td class="flex justify-center">
            <input  class="p-2 block w-text-sm text-gray-900 border border-black border-1  rounded-lg cursor-pointer bg-gray-50 focus:outline-none" type="file" id="id_logo" name="logo" accept="image/*">
            </td></tr>""",
            kwargs.get("value"),
        )


class RegisterForm(UserCreationForm):
    email = forms.EmailField(max_length=254, required=True)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password1",
            "password2",
        )


class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ("logo", "name")
        labels = {
            "logo" "Workspace logo",
            "name" "Workspace name",
        }
        widgets = {
            "logo": PictureWidget(),
        }


class WorkspaceCreationMultiForm(MultiModelForm):
    form_classes = {
        "user": RegisterForm,
        "workspace": WorkspaceForm,
    }
