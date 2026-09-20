import asyncio
from app.ai_gateway import classify_mode
from app.models.schemas import AskRequest
from app.rag.rag_service import RagService
from app.retrieval.hybrid_retriever import Chunk,HybridRetriever

def test_eight_mode_classifier():
    cases={"What repository URL do we use?":"ANSWER","Explain refresh tokens":"TEACH","How should I structure this?":"GUIDE","This stack trace failed":"DEBUG","Review my pull request":"REVIEW","Clarify this ambiguous requirement":"CLARIFY","Can I replace the confirmed decision?":"DECISION","Escalate this to a mentor":"ESCALATE"}
    assert {classify_mode(q) for q in cases}==set(cases.values())
    assert all(classify_mode(q)==mode for q,mode in cases.items())

def test_project_isolation_and_grounded_answer():
    chunks=[Chunk("p1","d1","Cart decision","Use cart_v2 in CartContext.tsx",metadata={"source_type":"decision"}),Chunk("p2","d2","Secret","Unrelated tenant data",metadata={"source_type":"decision"})]
    service=RagService(HybridRetriever(chunks))
    result=asyncio.run(service.ask(AskRequest(project_id="p1",user_id="u1",question="What cart decision applies?")))
    assert result.decision=="ANSWER"
    assert all(e.document_id!="d2" for e in result.evidence)
    assert "CartContext.tsx" in result.answer

def test_no_evidence_escalates():
    service=RagService(HybridRetriever([]))
    result=asyncio.run(service.ask(AskRequest(project_id="missing",user_id="u1",question="How do I proceed?")))
    assert result.needs_escalation is True
    assert result.can_continue is False

