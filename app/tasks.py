from celery import shared_task

from app.models import Workspace, Document, Section
from poma.search.semantic import upload
from poma.sources.gdrive import iter_files

EXTENSION_FROM_MIMETYPE = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
}


@shared_task
def index_workspace(workspace_id: int):
    workspace = Workspace.objects.get(pk=workspace_id)
    if workspace.corpus_id is None:
        workspace.create_corpus()
    for file_body, file_data in iter_files(workspace):
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
