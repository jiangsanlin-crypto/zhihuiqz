import httpx
class GitHubClient:
    def __init__(self,token:str): self.token=token
    def headers(self): return {"Authorization":f"Bearer {self.token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
    async def comment(self,repo,num,body):
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.post(f"https://api.github.com/repos/{repo}/issues/{num}/comments",headers=self.headers(),json={"body":body}); r.raise_for_status()
    async def set_labels(self,repo,num,labels):
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.put(f"https://api.github.com/repos/{repo}/issues/{num}/labels",headers=self.headers(),json={"labels":labels}); r.raise_for_status()
