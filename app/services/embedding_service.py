import base64
import mimetypes
from pathlib import Path
from typing import Iterable, List, Sequence, cast

import chromadb
from chromadb.api.types import Documents, Embeddings, IDs, Metadatas
from fastapi import UploadFile
from openai import AsyncOpenAI
from pypdf import PdfReader

from app.config import Settings, get_settings


def _read_text_from_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if path.suffix.lower() in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp"}:
        with path.open("rb") as file:
            data = base64.b64encode(file.read()).decode("utf-8")
        return data
    raise ValueError(f"Unsupported file format: {path.suffix}")


def chunk_text(text: str, max_chunk_size: int) -> List[str]:
    if not text:
        return []

    overlap = max(int(max_chunk_size * 0.2), 1)
    chunks: List[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + max_chunk_size, text_length)
        chunks.append(text[start:end])
        if end == text_length:
            break
        start = max(0, end - overlap)

    return chunks


class EmbeddingService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self._chroma_client = chromadb.PersistentClient(
            path=str(self.settings.persist_directory)
        )
        self._collection = self._chroma_client.get_or_create_collection(name="documents")

    @property
    def collection(self):
        return self._collection

    def clear_embeddings(self) -> None:
        """Remove all stored embeddings from the persistent collection."""

        # Deleting the collection ensures we remove persisted state from disk before
        # recreating a fresh, empty collection for subsequent ingestion operations.
        if any(collection.name == "documents" for collection in self._chroma_client.list_collections()):
            self._chroma_client.delete_collection(name="documents")
        self._collection = self._chroma_client.get_or_create_collection(name="documents")

    async def _embed_chunks(self, chunks: Sequence[str]) -> Embeddings:
        response = await self.client.embeddings.create(
            input=list(chunks),
            model=self.settings.embedding_model,
        )
        return [record.embedding for record in response.data]

    async def add_documents(self, files: Iterable[UploadFile]) -> dict:
        indexed_total = 0

        skipped_files: list[str] = []

        for file in files:
            sanitized_name = Path(file.filename or "uploaded").name
            suffix = Path(sanitized_name).suffix
            suffix = suffix or mimetypes.guess_extension(file.content_type or "") or ""
            temp_path = self.settings.persist_directory / f"tmp_{sanitized_name}"
            with temp_path.open("wb") as buffer:
                buffer.write(await file.read())

            try:
                text = _read_text_from_file(temp_path)
            except ValueError:
                skipped_files.append(sanitized_name)
                continue
            finally:
                temp_path.unlink(missing_ok=True)

            chunks = chunk_text(text, self.settings.max_chunk_size)
            if not chunks:
                skipped_files.append(sanitized_name)
                continue

            embeddings = await self._embed_chunks(chunks)

            ids: List[str] = []
            documents: List[str] = []
            metadatas: Metadatas = []

            base_id = sanitized_name.replace(" ", "_")
            for index, chunk in enumerate(chunks):
                ids.append(f"{base_id}_{index}")
                documents.append(chunk)
                metadatas.append(
                    {
                        "filename": sanitized_name,
                        "chunk_index": index,
                        "content_type": file.content_type,
                        "is_image": suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp"},
                    }
                )

            self.collection.upsert(
                ids=cast(IDs, ids),
                documents=cast(Documents, documents),
                metadatas=metadatas,
                embeddings=cast(Embeddings, embeddings),
            )

            indexed_total += len(ids)

        return {"chunks_indexed": indexed_total, "skipped_files": list(set(skipped_files))}

    async def similarity_search(self, query: str, top_k: int) -> list[dict]:
        query_embedding = await self._embed_chunks([query])
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
        )
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        return [
            {
                "document": doc,
                "metadata": meta,
                "score": score,
            }
            for doc, meta, score in zip(documents, metadatas, distances)
        ]

    def has_embeddings(self) -> bool:
        return self.collection.count() > 0
