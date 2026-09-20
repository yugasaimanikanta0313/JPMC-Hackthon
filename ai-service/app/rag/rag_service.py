from app.models.schemas import AskResponse,Evidence
from app.ai_gateway import AIGateway,classify_mode

class RagService:
    def __init__(self,retriever,settings=None):self.retriever=retriever;self.settings=settings;self.gateway=AIGateway(settings) if settings else None
    async def ask(self,request):
        mode=classify_mode(request.question,request.mode)
        matches=self.retriever.search(request.project_id,request.question)
        evidence=[Evidence(document_id=c.document_id,title=c.title,content=c.content[:5000],score=score,metadata=c.metadata) for c,score in matches]
        confidence=evidence[0].score if evidence else 0.0
        if not evidence:return AskResponse(decision="ESCALATE",mode="ESCALATE",confidence=0,evidence=[],escalation_reason="No verified project evidence is indexed yet",needs_escalation=True,can_continue=False,next_action="submit_escalation")
        context="\n\n".join(f"[{e.title} | {e.metadata.get('source_type','knowledge')}]\n{e.content}" for e in evidence)
        conflicts=[{"type":"decision_conflict","decision_id":e.document_id,"description":f"Proposed change may conflict with confirmed decision: {e.title}"} for e in evidence if e.metadata.get("source_type")=="decision" and any(w in request.question.lower() for w in ("change","replace","remove","instead"))]
        if self.gateway:
            prompt=(f"You are Barabari's support engineer operating in {mode} mode. Use only verified evidence. Confirmed decisions outrank requirements, which outrank documents and prior resolutions. For GUIDE, TEACH, DEBUG, and REVIEW, be Socratic: evaluate attempts and provide progressive hints rather than a copy-paste solution. State uncertainty and cite evidence titles.\n\nQUESTION:\n{request.question}\n\nATTEMPTED:\n{request.attempted_solutions}\n\nEVIDENCE:\n{context}")
            try:
                answer,_=await self.gateway.generate_text(prompt);needs=bool(conflicts) or mode=="ESCALATE"
                return AskResponse(decision="ESCALATE" if needs else "ANSWER",mode="ESCALATE" if needs else mode,confidence=max(confidence,.55),evidence=evidence,answer=answer,evidence_status="confirmed",conflicts=conflicts,next_action="submit_escalation" if needs else "submit_attempt" if mode in {"GUIDE","DEBUG","REVIEW","TEACH"} else "review_answer",can_continue=not needs,needs_escalation=needs,escalation_reason="Confirmed project evidence requires core-team review" if needs else None)
            except Exception:pass
        threshold=self.settings.rag_min_confidence if self.settings else .32
        if confidence<threshold:return AskResponse(decision="ESCALATE",mode="ESCALATE",confidence=confidence,evidence=evidence,escalation_reason="Indexed evidence is not relevant enough",needs_escalation=True,can_continue=False,next_action="submit_escalation")
        return AskResponse(decision="ANSWER",mode=mode,confidence=confidence,evidence=evidence,answer="Based on verified project evidence:\n"+context[:12000],evidence_status="confirmed",conflicts=conflicts,needs_escalation=bool(conflicts),can_continue=not conflicts,next_action="submit_escalation" if conflicts else "review_answer")
