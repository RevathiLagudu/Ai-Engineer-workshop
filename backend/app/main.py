import json
from contextlib import asynccontextmanager
from uuid import UUID, uuid4
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from app.config import ALLOWED_ORIGINS, ARCHIVE_RETENTION_DAYS, GROQ_API_KEY, GROQ_MODEL
from app.schemas.ingestion import IngestionRequest, RenameRequest
from app.schemas.assistant import AssistantResult, TokenUsage
from app.services.database_service import (initialize_database, check_database, database_kind, ensure_conversation, add_chat_message, get_chat_history, list_conversations, get_conversation_messages, rename_conversation, delete_conversation, archive_conversation, restore_conversation, list_archived_conversations, purge_expired_archives, get_archive_status)
from app.services.llm_service import analyze_message
from app.services.response_service import generate_response, stream_response
from app.utils.token_counter import estimate_tokens

# Shown to end users when the AI fails. The real cause is printed to the server log, never sent to the browser.
USER_ERROR = "The assistant couldn't answer right now. Please try again in a moment."

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()  # runs once when the server starts
    purge_expired_archives()
    yield

app = FastAPI(title="Indigo.ai API", description="AI-powered message analysis and contextual assistance.", version="4.0.0", lifespan=lifespan)
# Only the frontends listed in ALLOWED_ORIGINS (backend/.env or Render settings) may call the API.
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type"])

@app.get("/")
def root():
    """Public landing response: confirms the service is up without listing the API."""
    return {"service": app.title, "status": "running"}

@app.get("/health")
def health_check(response: Response):
    """Cheap check for Render and the frontend: never calls the LLM or returns secrets."""
    database_ok = check_database()
    if not database_ok:
        response.status_code = 503
    return {
        "status": "ok" if database_ok else "error",
        "message": "Indigo.ai API is running",
        "database": database_kind(),
        "database_ok": database_ok,
        "groq_api_key_configured": bool(GROQ_API_KEY),
        "model": GROQ_MODEL,
    }

@app.get("/api/conversations")
def conversations():
    purge_expired_archives()  # the 30-day clean-up runs whenever chats are listed
    return {"items": list_conversations()}

@app.get("/api/conversations/archived")
def archived_conversations():
    purge_expired_archives()
    return {"retention_days": ARCHIVE_RETENTION_DAYS, "items": list_archived_conversations()}

def _check_conversation_id(session_id: str) -> None:
    try: UUID(session_id)
    except ValueError: raise HTTPException(status_code=400, detail="Invalid conversation ID.")

@app.get("/api/conversations/{session_id}/messages")
def conversation_messages(session_id: str):
    _check_conversation_id(session_id)
    return {
        "session_id": session_id,
        "archive": get_archive_status(session_id),  # null unless the chat is archived
        "items": get_conversation_messages(session_id),
    }

@app.post("/api/conversations/{session_id}/archive")
def archive(session_id: str):
    _check_conversation_id(session_id)
    if not archive_conversation(session_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"session_id": session_id, **get_archive_status(session_id)}

@app.post("/api/conversations/{session_id}/restore")
def restore(session_id: str):
    _check_conversation_id(session_id)
    if not restore_conversation(session_id):
        raise HTTPException(status_code=404, detail="This chat isn't in the archive.")
    return {"session_id": session_id, "restored": True}

@app.patch("/api/conversations/{session_id}")
def rename(session_id: str, body: RenameRequest):
    _check_conversation_id(session_id)
    if not rename_conversation(session_id, body.title):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"session_id": session_id, "title": body.title}

@app.delete("/api/conversations/{session_id}", status_code=204)
def delete(session_id: str):
    _check_conversation_id(session_id)
    if not delete_conversation(session_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return Response(status_code=204)

def _classify_and_load_history(request: IngestionRequest, message: str, session_id: str, usage: dict):
    """Week 1 classification + the history to send to the LLM.

    Normal mode reads history from SQLite. Incognito mode never touches the
    database and uses the history the browser sent instead.
    `usage` is filled with the classification call's token counts.
    """
    if not request.incognito:
        ensure_conversation(session_id, message[:70])
    result = analyze_message(message, usage=usage)
    result.token_metadata.estimated_input_tokens = estimate_tokens(message)
    if request.incognito:
        history = [turn.model_dump() for turn in request.history]
    else:
        history = get_chat_history(session_id)
    return result, history

def _save_exchange(request: IngestionRequest, session_id: str, message: str, answer: str) -> None:
    if request.incognito:
        return  # incognito: nothing is stored
    add_chat_message(session_id, "user", message)
    add_chat_message(session_id, "assistant", answer)

@app.post("/api/analyze", response_model=AssistantResult)
def analyze(request: IngestionRequest):
    message = request.message.strip()
    if not message: raise HTTPException(status_code=422, detail="Message cannot be empty.")
    session_id = request.session_id or str(uuid4())
    try: UUID(session_id)
    except ValueError: raise HTTPException(status_code=422, detail="session_id must be a valid UUID.")
    classify_usage, reply_usage = {}, {}
    try:
        result, history = _classify_and_load_history(request, message, session_id, classify_usage)
        response_markdown = generate_response(result, history=history, current_message=message, usage=reply_usage)
        _save_exchange(request, session_id, message, response_markdown)
        return AssistantResult(
            **result.model_dump(),
            session_id=session_id,
            response_markdown=response_markdown,
            token_usage=TokenUsage.combine(classify_usage, reply_usage),
        )
    except ValidationError as exc:
        print(f"Validation failed for session {session_id}: {exc}")
        raise HTTPException(status_code=502, detail=USER_ERROR) from exc
    except Exception as exc:
        print(f"Request failed for session {session_id}: {exc}")
        raise HTTPException(status_code=502, detail=USER_ERROR) from exc


def _event(payload: dict) -> str:
    """One streaming event = one line of JSON (NDJSON)."""
    return json.dumps(payload, ensure_ascii=False) + "\n"

@app.post("/api/analyze/stream")
def analyze_stream(request: IngestionRequest):
    """Same as /api/analyze, but the answer arrives piece by piece (like ChatGPT).

    Events, one JSON object per line:
      {"type": "analysis", ...intent fields..., "session_id": "..."}   first, once
      {"type": "token", "text": "..."}                                    many times
      {"type": "done", "session_id": "...", "token_usage": {...}}         last, once
      {"type": "error", "detail": "..."}                                  instead of "done" if writing fails
    """
    classify_usage, reply_usage = {}, {}
    message = request.message.strip()
    if not message: raise HTTPException(status_code=422, detail="Message cannot be empty.")
    session_id = request.session_id or str(uuid4())
    try: UUID(session_id)
    except ValueError: raise HTTPException(status_code=422, detail="session_id must be a valid UUID.")

    # Week 1 runs before streaming starts, so classification errors still return a normal HTTP error.
    try:
        result, history = _classify_and_load_history(request, message, session_id, classify_usage)
    except Exception as exc:
        print(f"Classification failed for session {session_id}: {exc}")
        raise HTTPException(status_code=502, detail=USER_ERROR) from exc

    def events():
        yield _event({"type": "analysis", **result.model_dump(), "session_id": session_id})
        parts = []
        try:
            for text in stream_response(result, history=history, current_message=message, usage=reply_usage):
                parts.append(text)
                yield _event({"type": "token", "text": text})
            answer = "".join(parts).strip()
            if not answer:
                raise ValueError("The LLM returned an empty response.")
            # Saved only after the full answer arrives; a stopped reply is not saved.
            _save_exchange(request, session_id, message, answer)
            token_usage = TokenUsage.combine(classify_usage, reply_usage)
            yield _event({"type": "done", "session_id": session_id, "token_usage": token_usage.model_dump()})
        except Exception as exc:
            print(f"Streaming failed for session {session_id}: {exc}")
            yield _event({"type": "error", "detail": USER_ERROR})

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )