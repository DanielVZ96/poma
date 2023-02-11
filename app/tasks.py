import logging

import os
from celery import shared_task
from django.utils import timezone

from app.models import Document, Section, SlackChannel, Workspace
from poma.search.semantic import store, upload
from poma.sources import slack
from poma.sources.gdrive import download_file, iter_files

EXTENSION_FROM_MIMETYPE = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
}


def get_username(app, user_id: str, slack_token):
    user = app.client.users_info(user=user_id, token=slack_token)
    user.validate()
    print("USER:", user)
    return user["user"]["name"]


def ts_to_timestamp(ts: str):
    return timezone.datetime.fromtimestamp(float(ts))


@shared_task
def index_google(workspace_id: int):
    workspace = Workspace.objects.get(pk=workspace_id)
    service = workspace.get_google_drive_service()
    if workspace.corpus_id is None:
        workspace.create_corpus()
    for file_data in iter_files(service, workspace):
        keys = ["mimeType", "webViewLink", "name", "id"]
        file_data = {k: v for k, v in file_data.items() if k in keys}
        index_file_data.delay(workspace_id, file_data)


@shared_task
def index_file_data(workspace_id: int, file_data: dict):
    workspace = Workspace.objects.get(pk=workspace_id)
    service = workspace.get_google_drive_service()
    file_body = download_file(service, **file_data)
    extension = EXTENSION_FROM_MIMETYPE.get(file_data["mimeType"], "")
    response, success = upload(
        file_body,
        file_data["name"],
        extension,
        file_data["mimeType"],
        corpus_id=workspace.corpus_id,
    )
    if success:
        doc = response.json()
        size = int(doc["response"]["quotaConsumed"]["numChars"]) + int(
            doc["response"]["quotaConsumed"]["numMetadataChars"]
        )
        document = Document.objects.create(
            workspace=workspace,
            link=file_data["webViewLink"],
            title=file_data["name"],
            identifier=doc["document"]["documentId"],
            size=size,
        )
        for section in doc["document"]["section"]:
            Section.objects.create(
                document=document,
                word_count=len(section.get("text", "").split()),
                section_id=section["id"],
                text=section.get("text", ""),
            )


@shared_task
def index_slack(workspace_id: int):
    workspace = Workspace.objects.get(pk=workspace_id)
    if workspace.corpus_id is None:
        workspace.create_corpus()

    credentials = workspace.slack_credentials
    if not credentials:
        logging.error("workspace [%s] slack credentials not found", workspace_id)
    slack_token = credentials["credentials"]["access_token"]
    app = slack.user_app(slack_token)
    cursor = None
    info = app.client.auth_test(token=slack_token)
    workspace_name = info["team"]
    slack_workspace_id = info["team_id"]
    i = 0
    while True:
        i += 1
        print(i)
        response = app.client.conversations_list(
            limit=200, cursor=cursor, token=slack_token
        )
        response.validate()

        for channel in response["channels"]:
            channel_id = channel["id"]
            channel_name = channel["name"]
            SlackChannel.objects.get_or_create(
                channel_id=channel_id,
                channel_name=channel_name,
                workspace=workspace,
                slack_workspace_name=workspace_name,
                slack_workspace_id=slack_workspace_id,
            )

        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break


@shared_task
def index_channel(channel_id):
    logging.info("INDEXING %s [ID: %s]", channel_name, channel_id)

    channel = SlackChannel.objects.filter(channel_id=channel_id).first()
    channel_name = channel.name
    workspace = channel.workspace
    credentials = workspace.slack_credentials
    if not credentials:
        logging.error("workspace [%s] slack credentials not found", workspace.id)
    slack_token = credentials["credentials"]["access_token"]

    app = slack.user_app(slack_token)

    cursor = None
    while True:
        response = app.client.conversations_history(
            channel=channel_id, limit=200, cursor=cursor, token=slack_token,
        )
        response.validate()

        for message in response["messages"]:
            identifier = f"{channel_id}-{message['ts']}"
            username = get_username(app, message["user"], slack_token)
            title = f"@{username} in #{channel_name}"
            section = message["text"]
            document = store(
                identifier, title, sections=[section], corpus_id=workspace.corpus_id,
            )
            if document is None:
                continue

            permalink = app.client.chat_getPermalink(
                channel=channel_id, message_ts=message["ts"], token=slack_token,
            )
            document = Document.objects.create(
                workspace=workspace,
                link=permalink,
                title=title,
                identifier=identifier,
                size=0,
            )
            Section.objects.create(
                document=document,
                word_count=len(section.split()),
                section_id=0,
                text=section,
            )

        cursor = response.get("response_metadata", {}).get("next_cursor")
        if cursor is None:
            break


@shared_task
def index_message(channel_id, user, text, ts, team):
    channel = SlackChannel.objects.filter(channel_id=channel_id).first()
    if channel is None:
        index_slack(Workspace.objects.filter(slack_workspace_id=team).first().id)
        channel = SlackChannel.objects.filter(channel_id=channel_id).first()

    logging.info(
        "Indexing message [%s] for channel: %s [%s]",
        text,
        channel.channel_name,
        channel.channel_id,
    )
    workspace = channel.workspace
    credentials = workspace.slack_credentials
    if not credentials:
        logging.error("workspace [%s] slack credentials not found", workspace.id)
    slack_token = credentials["credentials"]["access_token"]
    channel_name = channel.channel_name
    app = slack.user_app(slack_token)
    identifier = f"{channel}-{ts}"
    username = get_username(app, user, slack_token)
    title = f"@{username} in #{channel_name}"
    section = text
    document = store(
        identifier, title, False, sections=[section], corpus_id=workspace.corpus_id,
    )

    permalink = app.client.chat_getPermalink(
        channel=channel.channel_id, message_ts=ts, token=slack_token,
    )["permalink"]
    document = Document.objects.create(
        workspace=workspace, link=permalink, title=title, identifier=identifier, size=0,
    )
    Section.objects.create(
        document=document, word_count=len(section.split()), section_id=0, text=section,
    )
