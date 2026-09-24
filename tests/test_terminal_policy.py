from orchestrator.terminal_policy import owner_wait_labels, resolve_terminal_policy


def test_release_enabled_allows_release():
    decision = resolve_terminal_policy("terminal_policy: release_enabled")
    assert decision.release_enabled is True
    assert decision.policy == "release_enabled"


def test_stop_after_qa_waits_for_owner():
    decision = resolve_terminal_policy("terminal_policy: stop_after_qa")
    assert decision.release_enabled is False


def test_owner_approval_required_waits_for_owner():
    decision = resolve_terminal_policy("terminal_policy: owner_approval_required")
    assert decision.release_enabled is False


def test_missing_policy_fails_closed():
    decision = resolve_terminal_policy("no terminal policy here")
    assert decision.release_enabled is False
    assert decision.policy is None
    assert "missing" in decision.reason


def test_invalid_policy_fails_closed():
    decision = resolve_terminal_policy("terminal_policy: automatic")
    assert decision.release_enabled is False
    assert "invalid" in decision.reason


def test_conflicting_values_fail_closed():
    decision = resolve_terminal_policy(
        "terminal_policy: release_enabled\nterminal_policy: stop_after_qa"
    )
    assert decision.release_enabled is False
    assert "conflicting" in decision.reason


def test_restrictive_text_overrides_permissive_structured_policy():
    decision = resolve_terminal_policy(
        "terminal_policy: release_enabled\nDo not deploy without explicit owner approval."
    )
    assert decision.release_enabled is False
    assert "conflicts" in decision.reason


def test_owner_wait_labels_remove_active_routes_and_are_idempotent():
    labels = owner_wait_labels(
        ["agent:codex", "phase:release", "status:todo", "keep:me"]
    )
    assert labels == ["approval:production-required", "keep:me", "status:review"]
    assert owner_wait_labels(labels) == labels
