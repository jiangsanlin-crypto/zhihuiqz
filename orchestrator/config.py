from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    port:int=int(os.getenv("APP_PORT","8080"))
    state_db:str=os.getenv("STATE_DB","./data/orchestrator.db")
    github_token:str=os.getenv("GITHUB_TOKEN","")
    github_repository:str=os.getenv("GITHUB_REPOSITORY","")
    github_webhook_secret:str=os.getenv("GITHUB_WEBHOOK_SECRET","")
    orchestrator_token:str=os.getenv("ORCHESTRATOR_TOKEN","")
    workbuddy_url:str=os.getenv("WORKBUDDY_URL","")
    workbuddy_token:str=os.getenv("WORKBUDDY_TOKEN","")
    sandbox_url:str=os.getenv("SANDBOX_URL","")
    sandbox_token:str=os.getenv("SANDBOX_TOKEN","")
    codex_url:str=os.getenv("CODEX_URL","")
    codex_token:str=os.getenv("CODEX_TOKEN","")
    max_retries:int=int(os.getenv("MAX_RETRIES","3"))
settings=Settings()
