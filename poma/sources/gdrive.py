import logging
from googleapiclient.http import MediaIoBaseDownload
import io
from googleapiclient.errors import HttpError

from app.models import Workspace


logger = logging.Logger(__name__)

MIMETYPES_TO_EXPORT = {
    "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def list_files(
    service,
    query="mimeType='application/vnd.google-apps.document' or mimeType='application/vnd.google-apps.presentation'",
):
    """Search file in drive location"""
    try:
        files = []
        page_token = None
        while True:
            # pylint: disable=maybe-no-member
            response = (
                service.files()
                .list(
                    q=query,
                    spaces="drive",
                    corpora="allDrives",
                    fields="nextPageToken, "
                    "files(id, name, mimeType, webViewLink, size)",
                    pageToken=page_token,
                    includeItemsFromAllDrives="true",
                    supportsAllDrives="true",
                    includePermissionsForView="published",
                )
                .execute()
            )
            for file in response.get("files", []):
                # Process change
                logger.info(f'Found file: {file.get("name")}, {file.get("id")}')
            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken", None)
            if page_token is None:
                break

    except HttpError as error:
        print(f"An error occurred: {error}")
        files = None

    return files


def download_file(service, **file):
    mimetype = MIMETYPES_TO_EXPORT.get(file["mimeType"], "text/plain")
    request = service.files().export_media(fileId=file["id"], mimeType=mimetype)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        logger.debug("Download %d%%" % int(status.progress() * 100))

    fh.seek(0)
    return fh


def iter_files(service, workspace: Workspace):
    logger.info("Listing google drive files for %s (%s)", workspace.name, workspace.id)
    files = list_files(service)
    for file in files:
        logger.info(
            "Downloading file for %s (%s) ID: %s",
            workspace.name,
            workspace.id,
            file["id"],
        )
        yield file
