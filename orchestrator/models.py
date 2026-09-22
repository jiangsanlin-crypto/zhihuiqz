from typing import Any, Literal
from pydantic import BaseModel, Field
AgentName=Literal["workbuddy","sandbox","codex"]
class AgentRunRequest(BaseModel):
    task_id:str
    agent:AgentName
    repository:str
    source_kind:Literal["issue","pull_request"]
    source_number:int
    event_name:str
    action:str|None=None
    prompt_path:str
    payload:dict[str,Any]=Field(default_factory=dict)
class AgentRunResult(BaseModel):
    status:Literal["success","blocked","failed"]
    summary:str
    artifacts:list[str]=Field(default_factory=list)
    next_labels:list[str]=Field(default_factory=list)
    pr_number:int|None=None
