from .models import AgentRunRequest
WF={"agent:workbuddy","agent:sandbox","agent:codex","needs:qa","ready-for-codex","status:todo","status:running","status:blocked","status:review","status:done"}

def names(items):
    return [x if isinstance(x,str) else x.get("name") for x in (items or []) if isinstance(x,str) or x.get("name")]

def choose(labels):
    s=set(labels)
    if "agent:workbuddy" in s:return "workbuddy"
    if "agent:sandbox" in s or "needs:qa" in s:return "sandbox"
    if "agent:codex" in s or "ready-for-codex" in s:return "codex"

def build(event,payload,repo):
    obj=(payload.get("issue") if event=="issues" else payload.get("pull_request") if event=="pull_request" else None)
    if not obj or not isinstance(payload.get("number"),int): return None
    labels=names(obj.get("labels"))
    agent=choose(labels)
    if not agent or "status:done" in labels:return None
    kind="issue" if event=="issues" else "pull_request"
    req=AgentRunRequest(task_id=f"GH-{kind.upper()}-{payload['number']}",agent=agent,repository=repo,source_kind=kind,source_number=payload["number"],event_name=event,action=payload.get("action"),prompt_path=f"agents/{agent}_prompt.md",payload=payload)
    return req,labels

def next_labels(agent,kind,current,status,explicit):
    keep=[x for x in current if x not in WF]
    if status!="success": return sorted(set(keep+[f"agent:{agent}","status:blocked"]))
    if explicit:return sorted(set(keep+explicit))
    if agent=="workbuddy": return sorted(set(keep+["agent:sandbox","status:todo"]))
    if agent=="sandbox" and kind=="issue": return sorted(set(keep+["agent:codex","status:todo"]))
    if agent=="sandbox": return sorted(set(keep+["agent:workbuddy","status:review"]))
    if agent=="codex": return sorted(set(keep+["needs:qa","status:review"]))
    return sorted(set(keep+["status:review"]))
