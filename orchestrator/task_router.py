from __future__ import annotations

import re

from .models import AgentRunRequest
from .terminal_policy import owner_wait_labels, resolve_terminal_policy

WORKFLOW_LABELS = {
    "agent:codex", "agent:chatgpt", "agent:workbuddy", "agent:workreview",
    "phase:product-plan", "phase:prototype", "phase:implementation",
    "phase:code-review", "phase:qa", "phase:release", "phase:deploy",
    "approval:production-required", "approval:production-approved",
    "status:todo", "status:running", "status:blocked", "status:review",
    "status:done", "status:deployed",
}

TASK_MARKER = re.compile(r"<!--\s*agent-task-id:([A-Za-z0-9._:-]+)\s*-->")


def label_names(items):
    return [item if isinstance(item, str) else item.get("name") for item in (items or []) if isinstance(item, str) or item.get("name")]


def phase_from_labels(labels: list[str]) -> str | None:
    for label in labels:
        if label.startswith("phase:"):
            return label
    return None


def correlated_task_id(kind: str, obj: dict, number: int) -> str:
    if kind == "pull_request":
        match = TASK_MARKER.search(str(obj.get("body") or ""))
        if match:
            return match.group(1)
    return f"GH-{kind.upper()}-{number}"


def build(event, payload, repo):
    obj = payload.get("pull_request") if event == "pull_request" else None
    if not obj or not isinstance(payload.get("number"), int) or payload.get("action") != "labeled":
        return None
    labels = label_names(obj.get("labels"))
    if ({x for x in labels if x.startswith("agent:")} != {"agent:workbuddy"}
        or {x for x in labels if x.startswith("status:")} != {"status:todo"}
        or any(x.startswith("approval:") for x in labels)):
        return None
    phases = {x for x in labels if x.startswith("phase:")}
    if len(phases) != 1:
        return None
    phase = next(iter(phases))
    if phase not in {"phase:prototype", "phase:qa", "phase:deploy"}:
        return None
    # Any routing label may be the final write that completes READY.
    added = (payload.get("label") or {}).get("name")
    if added not in {"agent:workbuddy", phase, "status:todo"}:
        return None
    if obj.get("state", "open") != "open" or obj.get("merged_at"):
        return None
    if (payload.get("repository") or {}).get("full_name", repo) != repo:
        return None
    number = payload["number"]
    head = obj.get("head") or {}
    if not head.get("ref") or not head.get("sha"):
        return None
    req = AgentRunRequest(
        task_id=correlated_task_id("pull_request", obj, number), agent="workbuddy",
        repository=repo, source_kind="pull_request", source_number=number,
        event_name=event, action="labeled", prompt_path="agents/workbuddy_prompt.md",
        phase=phase, source_ref=head.get("ref"), source_sha=head.get("sha"), payload=payload,
    )
    return req, labels


def next_labels(agent: str, kind: str, current: list[str], status: str,
                explicit: list[str], phase: str | None = None,
                terminal_policy_text: str | None = None):
    keep = [label for label in current if label not in WORKFLOW_LABELS]
    if status != "success":
        retry = ["agent:workbuddy", "status:blocked"]
        if phase:
            retry.append(phase)
        return sorted(set(keep + retry))
    # QA terminal policy is authoritative. Agent-supplied next labels must not
    # bypass stop-after-QA, owner approval, or fail-closed policy resolution.
    if agent == "workbuddy" and phase == "phase:qa":
        decision = resolve_terminal_policy(terminal_policy_text or "")
        if decision.release_enabled:
            return sorted(set(keep + ["agent:codex", "phase:release", "status:todo"]))
        return owner_wait_labels(keep)
    if explicit:
        return sorted(set(keep + explicit))
    if agent == "workbuddy" and phase == "phase:prototype":
        return sorted(set(keep + ["agent:chatgpt", "phase:implementation", "status:todo"]))
    if agent == "workbuddy" and phase == "phase:deploy":
        return sorted(set(keep + ["agent:workbuddy", "phase:deploy", "status:running"]))
    return sorted(set(keep + ["status:review"]))
