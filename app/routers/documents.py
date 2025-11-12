from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status

from app.auth.dependencies import get_current_principal
from app.services.embedding_service import EmbeddingService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("", summary="Upload documents and index them into the retrieval store")
async def upload_documents(
    request: Request,
    files: List[UploadFile] | None = File(None),
    strategy: str | None = Query(
        default=None,
        description=(
            "How to handle existing embeddings when uploading new documents. "
            "Use 'clean' to wipe prior embeddings before uploading, or 'append' to "
            "add to the current store."
        ),
    ),
    _: str | None = Depends(get_current_principal),
    embedding_service: EmbeddingService = Depends(EmbeddingService),
):
    valid_strategies = {None, "clean", "append"}
    if strategy not in valid_strategies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid strategy. Choose from 'clean' or 'append'.",
        )

    has_embeddings = embedding_service.has_embeddings()
    base_upload_url = str(request.url.replace(query=""))
    clean_url = str(request.url.include_query_params(strategy="clean"))
    append_url = str(request.url.include_query_params(strategy="append"))

    if has_embeddings and strategy is None:
        return {
            "status": "embeddings_exist",
            "detail": (
                "Embeddings have already been generated. Choose whether to clean the "
                "existing embeddings and start over, or add new documents to the "
                "current store."
            ),
            "actions": {
                "clean": {
                    "description": "Remove all existing embeddings and rebuild from new uploads.",
                    "url": clean_url,
                },
                "append": {
                    "description": "Keep existing embeddings and append new documents.",
                    "url": append_url,
                },
            },
        }

    upload_files = files or []

    if strategy == "clean":
        embedding_service.clear_embeddings()
        if not upload_files:
            return {
                "status": "cleared",
                "detail": (
                    "Existing embeddings have been removed. Upload documents to rebuild "
                    "the retrieval database."
                ),
                "upload_url": base_upload_url,
            }

    if not upload_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one document must be uploaded to generate embeddings.",
        )

    result = await embedding_service.add_documents(upload_files)

    detail = "Documents were added to an empty retrieval store."
    if strategy == "clean":
        detail = (
            "Existing embeddings were cleaned and the uploaded documents were indexed into "
            "the fresh retrieval store."
        )
    elif strategy == "append" and has_embeddings:
        detail = (
            "Uploaded documents were appended to the existing embeddings without clearing the store."
        )

    return {"status": "success", "detail": detail, **result, "append_url": append_url, "clean_url": clean_url}
