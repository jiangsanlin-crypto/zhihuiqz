from __future__ import annotations

import re
from dataclasses import dataclass

VALID_POLICIES = {"release_enabled", "stop_after_qa", "owner_approval_required"}
RESTRICTIVE_PATTERNS = (
    r"stop\s+after\s+(?:successful\s+)?qa",
    r"human\s+approval\s+required",
    r"owner[ -]approval\s+required",
    r"do\s+not\s+(?:merge|deploy)",
    r"without\s+(?:separate\s+)?(?:explicit\s+)?owner\s+approval",
)


@dataclass(frozen=True)
class TerminalPolicyDecision:
    policy: str | None
    release_enabled: bool
    reason: str


def resolve_terminal_policy(text: str) -> TerminalPolicyDecision:
    """Resolve a task's terminal policy, failing closed to owner review."""
    values = re.findall(
        r"(?im)^\s*terminal_policy\s*:\s*([a-z0-9_-]+)\s*$", text or ""
    )
    distinct = set(values)
    restrictive = any(re.search(pattern, text or "", re.I) for pattern in RESTRICTIVE_PATTERNS)

    if len(distinct) > 1:
        return TerminalPolicyDecision(None, False, "conflicting terminal_policy values")
    if not distinct:
        return TerminalPolicyDecision(None, False, "missing terminal_policy")

    policy = next(iter(distinct))
    if policy not in VALID_POLICIES:
        return TerminalPolicyDecision(policy, False, f"invalid terminal_policy: {policy}")
    if restrictive and policy == "release_enabled":
        return TerminalPolicyDecision(
            policy, False, "restrictive task instruction conflicts with release_enabled"
        )
    if policy == "release_enabled":
        return TerminalPolicyDecision(policy, True, "release explicitly enabled")
    return TerminalPolicyDecision(policy, False, f"{policy} requires owner review")


def owner_wait_labels(current: list[str]) -> list[str]:
    """Return the canonical human-wait state with no active worker route."""
    keep = [
        label
        for label in current
        if not label.startswith("agent:")
        and not label.startswith("phase:")
        and not label.startswith("status:")
        and label not in {"approval:production-approved", "approval:production-required"}
    ]
    return sorted(set(keep + ["status:review", "approval:production-required"]))
