from .models import AgentRunRequest

WF={
    "agent:workbuddy","agent:sandbox","agent:codex","needs:qa","ready-for-codex",
    "status:todo","status:running","status:blocked","status:review","status:done",
}

def names(items):
    return [x if isinstance(x,str) else x.get("name") for x in (items or [])
            if isinstance(x,str) or x.get("name")]

def choose(labels):
    s=set(labels)
    if "agent:workbuddy" in s: return "workbuddy"
    if "agent:sandbox" in s: return "sandbox"
    if "agent:codex" in s or "ready-for-codex" in s: return "codex"

def build(event,payload,repo):
    obj=(payload.get("issue") if event=="issues"
         else payload.get("pull_request") if event=="pull_request"
         else None)
    if not obj or not isinstance(payload.get("number"),int):
        return None

    action=payload.get("action")
    if action not in {"labeled","synchronize"}:
        return None

    labels=names(obj.get("labels"))
    agent=choose(labels)
    if not agent or "status:done" in labels:
        return None

    # set_labels can emit several labeled webhooks. Only the actual agent
    # label is allowed to start a labeled run; status/marker events are ignored.
    if action=="labeled":
        added=(payload.get("label") or {}).get("name")
        trigger={"workbuddy":"agent:workbuddy","sandbox":"agent:sandbox","codex":"agent:codex"}[agent]
        if added!=trigger:
            return None

    kind="issue" if event=="issues" else "pull_request"
    req=AgentRunRequest(
        task_id=f"GH-{kind.upper()}-{payload['number']}",
        agent=agent,
        repository=repo,
        source_kind=kind,
        source_number=payload["number"],
        event_name=event,
        action=action,
        prompt_path=f"agents/{agent}_prompt.md",
        payload=payload,
    )
    return req,labels

def next_labels(agent,kind,current,status,explicit):
    keep=[x for x in current if x not in WF]

    if status!="success":
        return sorted(set(keep+[f"agent:{agent}","status:blocked"]))
    if explicit:
        return sorted(set(keep+explicit))

    # WorkBuddy creates the spec PR from an issue and performs final product
    # review on the implemented PR.
    if agent=="workbuddy":
        return sorted(set(keep+["status:review"]))

    if agent=="sandbox" and kind=="pull_request":
        # First QA gate: approved spec -> Codex implementation.
        if "needs:qa" not in current:
            return sorted(set(keep+["agent:codex","status:todo"]))
        # Second QA gate: implemented PR -> WorkBuddy final review.
        return sorted(set(keep+["agent:workbuddy","status:review"]))

    if agent=="codex" and kind=="pull_request":
        # Codex implementation always returns to the sandbox with an explicit
        # second-gate marker. The agent:sandbox label is the actual webhook
        # trigger; needs:qa tells the sandbox this is the post-implementation gate.
        return sorted(set(keep+["agent:sandbox","needs:qa","status:todo"]))

    return sorted(set(keep+["status:review"]))
