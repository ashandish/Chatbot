import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.auth.dependencies import get_websocket_principal
from app.services.chat_service import ChatService

router = APIRouter(tags=["chat"])


@router.websocket("/ws/chat")
async def chat_endpoint(
    websocket: WebSocket,
    _: str | None = Depends(get_websocket_principal),
):
    await websocket.accept()
    chat_service = ChatService()

    try:
        while True:
            payload = await websocket.receive_text()
            try:
                message = json.loads(payload)
                question = message.get("question") or payload
            except json.JSONDecodeError:
                question = payload

            if not isinstance(question, str) or not question.strip():
                await websocket.send_json(
                    {"status": "error", "message": "Question payload is invalid."}
                )
                continue

            response = await chat_service.get_response(question)
            await websocket.send_json(response)

    except WebSocketDisconnect:
        return
