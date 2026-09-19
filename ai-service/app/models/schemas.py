from pydantic import BaseModel, Field

class Evidence(BaseModel):
    document_id: str
    title: str
    content: str
    score: float = Field(ge=0, le=1)
    verified: bool = True
    metadata: dict = {}

class AskRequest(BaseModel):
    project_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    question: str = Field(min_length=3, max_length=4000)
    attempted_solutions: list[str] = []

class AskResponse(BaseModel):
    decision: str
    answer: str | None = None
    evidence: list[Evidence] = []
    confidence: float
    escalation_reason: str | None = None

class IngestRequest(BaseModel):
    project_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    title: str
    content: str = Field(min_length=3)
    verified: bool = True
