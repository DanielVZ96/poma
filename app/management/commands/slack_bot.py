import os
from django.core.management.base import BaseCommand
from poma.sources.slack import socket_app
from app.tasks import index_channel, index_message


class Command(BaseCommand):
    help = "Starts the slack bot"

    def handle(self, *args, **options):
        for env in [
            "USER_TOKEN",
            "SLACK_CLIENT_ID",
            "SLACK_CLIENT_SECRET",
            "SLACK_API_TOKEN_APP_LEGACY",
            "SLACK_SIGNING_SECRET",
        ]:
            os.environ.pop(env, "")
        socket_app(index_channel.delay, index_message.delay)
