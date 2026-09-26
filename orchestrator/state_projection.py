"""Derive the next route from evidence, never from caller-supplied labels."""

from .evidence_gate import owner_wait_evidence, successful_current_ci, validate_qa_evidence
from .handoff_gate import HandoffGateError, validate_handoff


def verified_next_workflow(binding: dict, comments: list, runs: dict) -> set[str]:
    sha, phase = binding["source_sha"], binding["phase"]
    owner = binding["repository"].split("/", 1)[0]
    if successful_current_ci(runs, head_sha=sha, head_ref=binding["head_ref"]) is None:
        raise HandoffGateError("current-SHA ordinary CI has not passed")
    if phase in {"phase:code-review", "phase:qa"}:
        validate_qa_evidence(comments, runs, task_id=binding["task_id"],
            head_sha=sha, head_ref=binding["head_ref"], trusted_login=owner,
            pr_number=binding["pr_number"])
        if phase == "phase:code-review":
            return {"agent:workbuddy", "phase:qa", "status:todo"}
        if not owner_wait_evidence(comments, task_id=binding["task_id"], head_sha=sha):
            raise HandoffGateError("resolved owner-wait policy and current-SHA QA required")
        return {"status:review", "approval:production-required"}
    if phase == "phase:escalation-repair":
        required = {f"task_id={binding['task_id']}", f"source_sha={sha}",
                    "agent=workreview", "phase=escalation-repair"}
        repairs = [item for item in comments if (item.get("user") or {}).get("login") == owner
            and "<!-- agent-repair:v1 -->" in str(item.get("body") or "")
            and required <= set(str(item.get("body") or "").splitlines())]
        latest = max(repairs, key=lambda item: (str(item.get("created_at") or ""),
                                               int(item.get("id") or 0))) if repairs else {}
        if not ({"status=waiting_ci", "status=waiting_exact_sha_ci"}
                & set(str(latest.get("body") or "").splitlines())):
            raise HandoffGateError("trusted current-SHA repair record required")
        return {"agent:workreview", "phase:code-review", "status:todo"}
    if phase == "phase:implementation":
        source, destination, handoff_phase = "chatgpt", "workreview", "implementation"
        trusted = {owner}
        target = {"agent:workreview", "phase:code-review", "status:todo"}
    elif phase == "phase:prototype":
        source, destination, handoff_phase = "workbuddy", "chatgpt", "prototype_validation"
        trusted = {owner, "github-actions[bot]"}
        target = {"agent:chatgpt", "phase:implementation", "status:todo"}
    else:
        raise HandoffGateError("unsupported automatic transition")
    handoff = validate_handoff(comments, task_id=binding["task_id"], from_agent=source,
        to_agent=destination, phase=handoff_phase, source_sha=sha, trusted_logins=trusted)
    if handoff.get("pr_number") not in (None, binding["pr_number"]):
        raise HandoffGateError("handoff belongs to another PR")
    return target
