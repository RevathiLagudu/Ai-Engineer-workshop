from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

from app.schemas.ingestion import IngestionRequest, IngestionResult
from app.schemas.assistant import AssistantResult
from app.services.llm_service import analyze_message
from app.services.response_service import generate_response
from app.utils.token_counter import estimate_tokens

app = FastAPI(
    title="Enterprise Structured Ingestion Firewall",
    description="Classifies user messages and validates structured AI output.",
    version="1.0.0",
)

# Simple local-development CORS configuration. Restrict this in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Ingestion Firewall API is running"}


@app.post("/api/analyze", response_model=AssistantResult)
def analyze(request: IngestionRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    try:
        history = [
    item.model_dump()
    for item in request.history
]
        #week1 : Detect user intent
        result = analyze_message(message, history)
        # Add a local estimate for context budgeting. Provider-reported token
        # counts may differ; this is not billed-usage accounting.
        result.token_metadata.estimated_input_tokens = estimate_tokens(message)
        
        # Week 2: Generate an answer using the detected intent
        response_markdown = generate_response(result)

        # Return intent details + generated answer
        return AssistantResult(
            **result.model_dump(),
            response_markdown=response_markdown,
        )
    
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "The model response did not pass schema validation.",
                "validation_errors": exc.errors(),
            },
        ) from exc
         
    except Exception as exc:
        # Keep the response simple; avoid exposing secrets or internal details.
        raise HTTPException(
            status_code=502,
            detail="LLM request failed. Check the API key, model name, network, and provider limits.",
        ) from exc