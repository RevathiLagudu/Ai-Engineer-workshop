from uuid import UUID, uuid4
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from app.schemas.ingestion import IngestionRequest
from app.schemas.assistant import AssistantResult
from app.services.database_service import (initialize_database, ensure_conversation, add_chat_message, get_chat_history, list_conversations, get_conversation_messages)
from app.services.llm_service import analyze_message
from app.services.response_service import generate_response
from app.utils.token_counter import estimate_tokens

app = FastAPI(title="Enterprise Ingestion Firewall", description="AI-powered message analysis and contextual assistance.", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    initialize_database()

@app.get("/health")
def health_check():
    try:
        initialize_database()
        return {
            "status": "ok",
            "message": "Ingestion Firewall API is running",
            "database": "supabase",
        }
    except Exception as exc:
        print(f"Supabase health check failed: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Supabase database connection failed.",
        ) from exc
        
@app.get("/api/conversations")
def conversations():
    return {"items": list_conversations()}

@app.get("/api/conversations/{session_id}/messages")
def conversation_messages(session_id: str):
    try: UUID(session_id)
    except ValueError: raise HTTPException(status_code=400, detail="Invalid conversation ID.")
    return {"session_id": session_id, "items": get_conversation_messages(session_id)}

@app.post("/api/analyze", response_model=AssistantResult)
def analyze(request: IngestionRequest):
    message = request.message.strip()
    if not message: raise HTTPException(status_code=422, detail="Message cannot be empty.")
    session_id = request.session_id or str(uuid4())
    try: UUID(session_id)
    except ValueError: raise HTTPException(status_code=422, detail="session_id must be a valid UUID.")
    try:
        ensure_conversation(session_id, message[:70])
        result = analyze_message(message)
        result.token_metadata.estimated_input_tokens = estimate_tokens(message)
        history = get_chat_history(session_id)
        response_markdown = generate_response(result, history=history, current_message=message)
        add_chat_message(session_id, "user", message)
        add_chat_message(session_id, "assistant", response_markdown)
        return AssistantResult(**result.model_dump(), session_id=session_id, response_markdown=response_markdown)
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail={"error":"The model response did not pass schema validation.", "validation_errors":exc.errors()}) from exc
    except Exception as exc:
        print(f"Request failed for session {session_id}: {exc}")
        raise HTTPException(status_code=502, detail="The AI request failed. Check backend/.env, your network, database connection, model name, and provider limits.") from exc