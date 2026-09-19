import httpx
from app.models.schemas import AskResponse,Evidence

class RagService:
    def __init__(self,retriever,settings=None):self.retriever=retriever;self.settings=settings
    async def ask(self,request):
        matches=self.retriever.search(request.project_id,request.question)
        evidence=[Evidence(document_id=c.document_id,title=c.title,content=c.content[:5000],score=score,metadata=c.metadata) for c,score in matches]
        confidence=evidence[0].score if evidence else 0.0
        if not evidence:return AskResponse(decision="ESCALATE",confidence=0,evidence=[],escalation_reason="No verified project evidence is indexed yet")
        context="\n\n".join(f"[{e.title} | {e.metadata.get('source_type','knowledge')}]\n{e.content}" for e in evidence)
        if self.settings and self.settings.gemini_api_key:
            prompt=("You are a project support engineer. Answer only from supplied verified project evidence. "
                    "Give concrete diagnostic steps and relevant files, and state uncertainty. Never invent project facts.\n\n"
                    f"QUESTION:\n{request.question}\n\nATTEMPTED:\n{request.attempted_solutions}\n\nEVIDENCE:\n{context}")
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent?key={self.settings.gemini_api_key}"
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    response=await client.post(url,json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.15}})
                    response.raise_for_status();answer=response.json()["candidates"][0]["content"]["parts"][0]["text"]
                return AskResponse(decision="ANSWER",confidence=max(confidence,.55),evidence=evidence,answer=answer)
            except Exception:pass
        if confidence<.25:return AskResponse(decision="ESCALATE",confidence=confidence,evidence=evidence,escalation_reason="Indexed evidence is not relevant enough")
        return AskResponse(decision="ANSWER",confidence=confidence,evidence=evidence,answer="Based on verified project evidence:\n"+context[:12000])
