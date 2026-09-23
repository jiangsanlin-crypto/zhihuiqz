from __future__ import annotations

import re

from .models import AgentRunRequest

WORKFLOW_LABELS = {
    "agent:codex",
    "agent:chatgpt",
    "agent:workbuddy",
    "phase:product-plan",
    "phase:prototype",
    "phase:implementation",
    "phase:qa",
    "phase:release",
    "phase:deploy",
    "approval:production-required",
    "approval:production-approved",
    "status:todo",
    "status:running",
    "status:blocked",
    "status:review",
    "status:done",
    "status:deployed",
}

TASK_MARKER = re.compile(r"<!--\s*agent-task-id:([A-Za-z0-9._:-]+)\s*-->")


def label_names(items):
    return [
        item if isinstance(item, str) else item.get("name")
        for item in (items or [])
        if isinstance(item, str) or item.get("name")
    ]


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
    # Codex and ChatGPT are executed by dedicated GitHub Actions.
    # The persistent Orchestrator routes WorkBuddy only.
    obj = payload.get("pull_request") if event == "pull_request" else None
    if not obj or not isinstance(payload.get("number"), int):
        return None
    if payload.get("action") != "labeled":
        return None

    labels = label_names(obj.get("labels"))
    if (
        "status:done" in labels
        or "status:todo" not in labels
        or "agent:workbuddy" not in labels
    ):
        return None

    added = (payload.get("label") or {}).get("name")
    if added != "agent:workbuddy":
        return None

    phase = phase_from_labels(labels)
    if phase not in {"phase:prototype", "phase:qa", "phase:deploy"}:
        return None

    number = payload["number"]
    head = obj.get("head") or {}
    req = AgentRunRequest(
        task_id=correlated_task_id("pull_request", obj, number),
        agent="workbuddy",
        repository=repo,
        source_kind="pull_request",
        source_number=number,
        event_name=event,
        action="labeled",
        prompt_path="agents/workbuddy_prompt.md",
        phase=phase,
        source_ref=head.get("ref"),
        source_sha=head.get("sha"),
        payload=payload,
    )
    return req, labels


def next_labels(
    agent: str,
    kind: str,
    current: list[str],
    status: str,
    explicit: list[str],
    phase: str | None = None,
):
    keep = [label for label in current if label not in WORKFLOW_LABELS]

    if status != "success":
        # Includes degraded dispatches: keep the same phase blocked and never promote.
        retry = ["agent:workbuddy", "status:blocked"]
        if phase:
            retry.append(phase)
        return sorted(set(keep + retry))

    if explicit:
        return sorted(set(keep + explicit))

    if agent == "workbuddy" and phase == "phase:prototype":
        return sorted(
            set(
                keep
                + [
                    "agent:chatgpt",
                    "phase:implementation",
                    "status:todo",
                ]
            )
        )

    if agent == "workbuddy" and phase == "phase:qa":
        return sorted(
            set(
                keep
                + [
                    "agent:codex",
                    "phase:release",
                    "status:todo",
                ]
            )
        )

    if agent == "workbuddy" and phase == "phase:deploy":
        return sorted(
            set(
                keep
                + [
                    "agent:workbuddy",
                    "phase:deploy",
                    "status:running",
                ]
            )
        )

    return sorted(set(keep + ["status:review"]))
