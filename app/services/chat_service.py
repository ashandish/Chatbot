from typing import List

from openai import AsyncOpenAI

from app.config import Settings, get_settings
from app.services.embedding_service import EmbeddingService


class ChatService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.embedding_service = EmbeddingService(self.settings)
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def get_response(self, question: str) -> dict:
        if not self.embedding_service.has_embeddings():
            return {
                "status": "error",
                "message": "The retrieval database is not built. Please ingest documents first.",
            }

        relevant_chunks = await self.embedding_service.similarity_search(
            question, self.settings.top_k_results
        )

        if not relevant_chunks:
            return {
                "status": "error",
                "message": "No relevant context was found for your question.",
            }

        context_blocks: List[str] = []
        for chunk in relevant_chunks:
            metadata = chunk["metadata"]
            document_label = metadata.get("filename", "unknown")
            context_blocks.append(
                f"From {document_label} (chunk {metadata.get('chunk_index')}):\n{chunk['document']}"
            )

        prompt = (
            "You are a retrieval augmented assistant. Use the provided context to answer "
            "the user's question. If the context is insufficient, say so explicitly.\n\n"
            "Context:\n" + "\n\n".join(context_blocks) + "\n\nQuestion: " + question
        )

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        answer = response.choices[0].message.content
        return {
            "status": "ok",
            "answer": answer,
            "sources": relevant_chunks,
        }
