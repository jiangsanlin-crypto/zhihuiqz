import httpx
from .models import AgentRunRequest,AgentRunResult
class HttpAgentAdapter:
    def __init__(self,name,url,token): self.name=name; self.url=url.rstrip("/"); self.token=token
    async def run(self,req:AgentRunRequest)->AgentRunResult:
        if not self.url:
            return AgentRunResult(status="blocked",summary=f"{self.name} runner is not configured")
        h={"Content-Type":"application/json"}
        if self.token: h["Authorization"]=f"Bearer {self.token}"
        try:
            async with httpx.AsyncClient(timeout=120) as c:
                r=await c.post(f"{self.url}/run",headers=h,json=req.model_dump()); r.raise_for_status()
                return AgentRunResult.model_validate(r.json())
        except Exception as e:
            return AgentRunResult(status="failed",summary=f"{self.name} runner request failed: {type(e).__name__}: {e}")
