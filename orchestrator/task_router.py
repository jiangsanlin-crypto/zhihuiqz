from __future__ import annotations

import re

from .models import AgentRunRequest

WORKFLOW_LABELS = {
    "agent:workbuddy",
    "agent:sandbox",
    "agent:codex",
    "needs:qa",
    "ready-for-codex",
    "status:todo",
    "status:running",
    "status:blocked",
    "status:review",
    "status:done",
}
TASK_MARKER = re.compile(r"<!--\s*agent-task-id:([A-Za-z0-9._:-]+)\s*-->")


def label_names(items):
    return [
        item if isinstance(item, str) else item.get("name")
        for item in (items or [])
        if isinstance(item, str) or item.get("name")
    ]


def choose_agent(labels):
    label_set = set(labels)
    if "agent:workbuddy" in label_set:
        return "workbuddy"
    if "agent:sandbox" in label_set:
        return "sandbox"
    if "agent:codex" in label_set or "ready-for-codex" in label_set:
        return "codex"
    return None


def correlated_task_id(kind: str, obj: dict, number: int) -> str:
    if kind == "pull_request":
        match = TASK_MARKER.search(str(obj.get("body") or ""))
        if match:
            return match.group(1)
    return f"GH-{kind.upper()}-{number}"


def build(event, payload, repo):
    obj = (
        payload.get("issue")
        if event == "issues"
        else payload.get("pull_request")
        if event == "pull_request"
        else None
    )
    if not obj or not isinstance(payload.get("number"), int):
        return None

    if payload.get("action") != "labeled":
        return None

    labels = label_names(obj.get("labels"))
    agent = choose_agent(labels)
    if not agent or "status:done" in labels:
        return None

    added = (payload.get("label") or {}).get("name")
    trigger = {
        "workbuddy": "agent:workbuddy",
        "sandbox": "agent:sandbox",
        "codex": "agent:codex",
    }[agent]
    if added != trigger:
        return None

    kind = "issue" if event == "issues" else "pull_request"
    number = payload["number"]
    head = obj.get("head") or {}
    req = AgentRunRequest(
        task_id=correlated_task_id(kind, obj, number),
        agent=agent,
        repository=repo,
        source_kind=kind,
        source_number=number,
        event_name=event,
        action="labeled",
        prompt_path=f"agents/{agent}_prompt.md",
        source_ref=head.get("ref") if kind == "pull_request" else None,
        source_sha=head.get("sha") if kind == "pull_request" else None,
        payload=payload,
    )
    return req, labels


def next_labels(agent, kind, current, status, explicit):
    keep = [label for label in current if label not in WORKFLOW_LABELS]

    if status != "success":
        retry_context = []
        if agent == "sandbox" and kind == "pull_request" and "needs:qa" in current:
            retry_context.append("needs:qa")
        return sorted(
            set(
                keep
                + retry_context
                + [f"agent:{agent}", "status:blocked"]
            )
        )

    if explicit:
        return sorted(set(keep + explicit))

    if agent == "workbuddy":
        return sorted(set(keep + ["status:review"]))

    if agent == "sandbox" and kind == "pull_request":
        if "needs:qa" not in current:
            return sorted(set(keep + ["agent:codex", "status:todo"]))
        return sorted(set(keep + ["agent:workbuddy", "status:review"]))

    return sorted(set(keep + ["status:review"]))
