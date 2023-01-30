from typing import Tuple, Union
import jwt
from datetime import timedelta
from urllib.parse import urljoin

from django.template.loader import get_template
from django.template import Context
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.core.exceptions import BadRequest


def send_verification(user: User):
    payload = {
        "email": user.email,
        "expiration": (
            timezone.now() + timedelta(seconds=settings.EMAIL_TOKEN_LIFE)
        ).isoformat(),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    link = urljoin(settings.EMAIL_PAGE_DOMAIN, f"/verify/{token}/")

    plaintext = get_template(settings.EMAIL_PLAIN)
    htmly = get_template(settings.EMAIL_HTML)
    context = {"username": user.username, "link": link}

    subject, from_email, to = (
        settings.EMAIL_SUBJECT,
        settings.EMAIL_FROM_ADDRESS,
        user.email,
    )
    text_content = plaintext.render(context)
    html_content = htmly.render(context)
    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html_content, "text/html")
    msg.send()


def verify_user_token(token: str) -> Tuple[bool, Union[User, None]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.exceptions.InvalidTokenError:
        return False, None
    expiration = payload.get("expiration")
    if expiration and timezone.datetime.fromisoformat(expiration) < timezone.now():
        return False, None
    user = User.objects.get(email=payload.get("email"))
    user.is_active = True
    user.save()
    return True, user
