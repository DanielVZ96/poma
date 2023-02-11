from functools import lru_cache
import os
import logging
from slack_bolt import App
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import FileInstallationStore
from poma.sources.slack_datastores import DjangoInstallationStore, DjangoOAuthStateStore
from slack_sdk.oauth.state_store import FileOAuthStateStore
from slack_bolt.adapter.socket_mode import SocketModeHandler


SLACK_SCOPES = os.getenv("SLACK_SCOPES", "").split(",")
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")

logger = logging.Logger(__name__)


def app():
    oauth_settings = OAuthSettings(
        client_id=os.getenv("SLACK_CLIENT_ID", ""),
        client_secret=os.getenv("SLACK_CLIENT_SECRET", ""),
        scopes=SLACK_SCOPES,
        installation_store=DjangoInstallationStore(
            os.getenv("SLACK_CLIENT_ID", ""), logger
        ),
        state_store=DjangoOAuthStateStore(expiration_seconds=600, logger=logger),
    )
    return App(
        signing_secret=os.getenv("SLACK_SIGNING_SECRET"), oauth_settings=oauth_settings
    )


def bot_app():
    return App(token=os.environ.get("SLACK_BOT_TOKEN"))


@lru_cache
def user_app(token):
    oauth_settings = OAuthSettings(
        client_id=os.getenv("SLACK_CLIENT_ID", ""),
        client_secret=os.getenv("SLACK_CLIENT_SECRET", ""),
        scopes=SLACK_SCOPES,
        installation_store=FileInstallationStore(base_dir="./data/installations"),
        state_store=FileOAuthStateStore(
            expiration_seconds=600, base_dir="./data/states"
        ),
    )
    return App(
        signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
        oauth_settings=oauth_settings,
        token=token,
    )


def socket_app(join_callback, message_callback):
    _app = bot_app()
    bot_info = _app.client.auth_test(token=os.getenv("SLACK_APP_TOKEN"))
    bot_user_id = bot_info["user_id"]

    @_app.event("member_joined_channel")
    def index_history(ack, event, say):
        if event["user"] != bot_user_id:
            logger.info("Ingoring user [%s] that joined channel", event["user"])
            return
        logger.info("BOT that joined channel: %s", event)
        join_callback(event["channel"])
        ack()
        return True

    @_app.message("")
    def index_message(message, say, **kwargs):
        print("INDEXING", message)
        if message["type"] == "message" and message["channel_type"] == "channel":
            message_callback(
                message["channel"],
                message["user"],
                message["text"],
                message["ts"],
                message["team"],
            )

    SocketModeHandler(_app).start()


def is_valid(token):
    _app = app()
    bot_info = _app.client.auth_test(token=os.getenv("SLACK_APP_TOKEN"))
    return bot_info
