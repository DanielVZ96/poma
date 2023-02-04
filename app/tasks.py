from celery import shared_task

from app.models import Workspace, Document, Section
from poma.search.semantic import upload
from poma.sources.gdrive import iter_files, download_file

EXTENSION_FROM_MIMETYPE = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
}


@shared_task
def index_workspace(workspace_id: int):
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
