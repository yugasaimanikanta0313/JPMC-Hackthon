import httpx

MODES=("ANSWER","TEACH","GUIDE","DEBUG","REVIEW","CLARIFY","DECISION","ESCALATE")

def classify_mode(question,requested=None):
    if requested and requested.upper() in MODES:return requested.upper()
    text=question.lower();rules=(("ESCALATE",("escalate","mentor","human help")),("DECISION",("decision","allowed to change","can i replace","client changed")),("DEBUG",("error","exception","stack trace","failed","bug","not working")),("REVIEW",("review","pull request","code quality")),("CLARIFY",("unclear","ambiguous","clarify","what does requirement")),("TEACH",("explain","what is","why does","teach")),("GUIDE",("how should","how do i","help me implement","approach")))
    return next((mode for mode,words in rules if any(word in text for word in words)),"ANSWER")

class AIGateway:
    """Provider-neutral AI gateway with local Ollama primary and Gemini fallback."""
    def __init__(self,settings):self.settings=settings
    async def _ollama(self,prompt):
        async with httpx.AsyncClient(timeout=180) as client:
            r=await client.post(self.settings.ollama_base_url.rstrip("/")+"/api/generate",json={"model":self.settings.ollama_model,"prompt":prompt,"stream":False,"options":{"temperature":.1}});r.raise_for_status();return r.json()["response"]
    async def _gemini(self,prompt):
        if not self.settings.gemini_api_key:raise RuntimeError("Gemini is not configured")
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent?key={self.settings.gemini_api_key}"
        async with httpx.AsyncClient(timeout=90) as client:
            r=await client.post(url,json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":.1}});r.raise_for_status();return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    async def generate_text(self,prompt):
        providers=(self._ollama,self._gemini) if self.settings.ai_provider.lower()=="ollama" else (self._gemini,self._ollama);errors=[]
        for provider in providers:
            try:return await provider(prompt),provider.__name__.removeprefix("_")
            except Exception as exc:errors.append(f"{provider.__name__}: {exc}")
        raise RuntimeError("; ".join(errors))
