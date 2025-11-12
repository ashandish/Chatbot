# Chatbot

A production-ready retrieval augmented chatbot built with FastAPI, WebSockets, and Gunicorn. It supports uploading documents for embedding into ChromaDB and real-time chatting backed by OpenAI models.

## Features

- **Document ingestion API** – Upload multiple files (PDF, text, or images) that are chunked with 20% overlap and embedded using the configured OpenAI multi-modal model. Embeddings are persisted in ChromaDB.
- **Chat WebSocket** – Multi-user capable chat endpoint that retrieves top-ranked context from the vector store and synthesises answers via OpenAI.
- **Authentication** – Optional Active Directory (LDAP) or Google ID token based authentication that can be enabled via environment variables.
- **Dockerized deployment** – Production stack powered by Gunicorn with Uvicorn workers and docker-compose orchestration.

## Getting started

1. **Copy the environment template** and populate the mandatory values:

   ```bash
   cp .env.example .env
   # update OPENAI_API_KEY and other settings as required
   ```

2. **Build and run the stack**:

   ```bash
   docker compose up --build
   ```

   The API will be available at `http://localhost:8000`.

3. **Upload documents** via `POST /api/v1/documents` using multipart form-data with the field name `files`.

   - When embeddings already exist, the endpoint responds with guidance to either clean the
     current vector store or append additional documents. Follow the provided URLs or
     resubmit with `?strategy=clean` to rebuild from scratch, or `?strategy=append` to add
     to the existing embeddings.
   - Cleaning the store without uploading new files returns an acknowledgement and a fresh
     upload URL so you can immediately re-ingest.

4. **Start a chat session** by connecting to the WebSocket at `ws://localhost:8000/ws/chat`. Send JSON payloads like:

   ```json
   { "question": "What does the uploaded document say about pricing?" }
   ```

   If no embeddings are present the chatbot responds with an informative error.

## Authentication options

- Set `AUTH_PROVIDER=active_directory` and provide `AD_SERVER_URI`, `AD_USER_DN_TEMPLATE`, and optional `AD_USE_SSL` to enable LDAP binds with Active Directory credentials (Basic auth header or base64 token for WebSockets).
- Set `AUTH_PROVIDER=google` and provide `GOOGLE_CLIENT_ID` to require Google ID tokens (Bearer auth header or `token` query parameter for WebSockets).
- Keep `AUTH_PROVIDER=none` to disable authentication (default).

## Project structure

```
app/
├── auth/
│   └── dependencies.py       # Authentication helpers
├── config.py                 # Pydantic settings
├── main.py                   # FastAPI application entry point
├── routers/
│   ├── chat.py               # WebSocket chat endpoint
│   └── documents.py          # Document ingestion endpoint
└── services/
    ├── chat_service.py       # Retrieval augmented response generation
    └── embedding_service.py  # Chunking and embedding utilities
```

## Running tests

There are no automated tests bundled with this template yet. Consider adding unit and integration coverage for your organisation's needs.
