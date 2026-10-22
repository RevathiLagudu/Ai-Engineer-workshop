from pydantic import Field
from app.schemas.ingestion import IngestionResult

class AssistantResult(IngestionResult):
    #week2 response: intent analysis plus generated answer.
    response_markdown: str = Field(
        min_length=1,
        description="LLM-Generated answer formatted as a markdown",
    )
     