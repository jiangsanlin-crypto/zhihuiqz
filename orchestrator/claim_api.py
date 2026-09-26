"""Authenticated shared leases. A lease is not a CI/review/production approval."""

import json
from .state_writer import write_labels
import hashlib
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .security import verify_bearer
from .handoff_gate import HandoffGateError
from .evidence_gate import successful_current_ci, validate_qa_evidence
from .state_projection import verified_next_workflow
from .state_store import now
from .queue_discovery import discover
from .head_transition import publication_audit, refresh_declared_head
from .task_router import TASK_MARKER
from .models import FileChange


class AcquireClaim(BaseModel):
    model_config = {"extra": "forbid"}
    repository: str = Field(min_length=3, max_length=200)
    pr_number: int = Field(gt=0)
    source_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    head_ref: str = Field(min_length=1, max_length=250)
    task_id: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,150}$")
    phase: Literal["phase:implementation", "phase:code-review", "phase:escalation-repair", "phase:prototype", "phase:qa"]
    worker_id: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,150}$")
    request_id: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,150}$")


class OwnedClaim(BaseModel):
    model_config = {"extra": "forbid"}
    delivery_id: str
    lease_id: str
    worker_id: str


class PrepareHead(OwnedClaim):
    target_sha: str = Field(pattern=r"^[0-9a-f]{40}$")


class ReportFile(BaseModel):
    model_config = {"extra": "forbid"}
    path: str = Field(min_length=1, max_length=220)
    content: str = Field(max_length=250_000)


class PublishReports(OwnedClaim):
    files: list[ReportFile] = Field(min_length=1, max_length=8)


REPORT_PATHS = {
    "phase:prototype": {
        "reports/prototype_review.md",
        "reports/data_analysis.md",
        "reports/classification_validation.md",
        "reports/uiux_prototype.md",
        "reports/prototype_gate.json",
    },
    "phase:qa": {
        "reports/test_report.md",
        "reports/uiux_acceptance.md",
        "reports/classification_validation.md",
        "reports/qa_summary.json",
    },
}


def create_claim_router(store, github, settings):
    async def authenticated(authorization: str | None = Header(None)):
        if not verify_bearer(settings.orchestrator_token, authorization):
            raise HTTPException(401, "invalid claim authentication")

    router = APIRouter(prefix="/claims", dependencies=[Depends(authenticated)])

    @router.get("/recovery")
    async def recovery():
        with store.conn() as db:
            rows=db.execute("SELECT payload_json,action FROM timeout_observations WHERE active=1 AND action!='none'").fetchall()
        return {'observations': [{**json.loads(row['payload_json']), 'action': row['action']}
            for row in rows if json.loads(row['payload_json'])['repository']==settings.github_repository]}

    @router.get("/ready")
    async def ready():
        if not settings.github_repository:
            raise HTTPException(503, "REPOSITORY_NOT_CONFIGURED")
        return {"candidates": [binding for _, binding in
                await discover(github, settings.github_repository)]}

    def owned(value: OwnedClaim):
        row = store.get(value.delivery_id)
        if (not row or row["event_name"] != "external_claim"
            or row["lease_id"] != value.lease_id
            or json.loads(row["payload_json"]).get("worker_id") != value.worker_id):
            raise HTTPException(409, "WORKER_LEASE_LOST")
        binding = json.loads(row["payload_json"])
        try:
            store.assert_operation(binding["operation_key"], value.delivery_id, value.lease_id)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return row, binding

    async def current(binding, *, resumed=False, projected_route=None):
        if not settings.github_repository or binding["repository"] != settings.github_repository:
            raise HTTPException(409, "REPOSITORY_MISMATCH")
        pr = await github.get_pr_snapshot(binding["repository"], binding["pr_number"])
        head, base = pr.get("head") or {}, pr.get("base") or {}
        if (pr.get("state") != "open" or pr.get("merged_at")
            or (head.get("repo") or {}).get("full_name") != binding["repository"]
            or head.get("ref") != binding["head_ref"]
            or (binding.get("base_ref") and base.get("ref") != binding["base_ref"])
            or head.get("ref") in {"main", base.get("ref"), (head.get("repo") or {}).get("default_branch")}):
            raise HTTPException(409, "PR_BRANCH_IDENTITY_CHANGED")
        if head.get("sha") != binding["source_sha"]:
            raise HTTPException(409, "HEAD_CHANGED")
        if set(TASK_MARKER.findall(str(pr.get("body") or ""))) != {binding["task_id"]}:
            raise HTTPException(409, "TASK_CHANGED")
        labels = {item["name"] if isinstance(item, dict) else item for item in pr.get("labels", [])}
        route = {x for x in labels if x.startswith(("agent:", "phase:", "status:", "approval:"))}
        expected = {binding["agent"], binding["phase"], "status:todo"}
        running = {binding["agent"], binding["phase"], "status:running"}
        if (route != expected and not (resumed and route == running)
            and route != projected_route) or any(
            x.startswith(("blocker:", "recovery:", "watchdog:")) for x in labels
        ):
            raise HTTPException(409, "STATE_CHANGED")
        return pr

    def response(row):
        return {**{key: row[key] for key in ("delivery_id", "lease_id", "lease_expires_at")},
                "source_sha": json.loads(row["payload_json"])["source_sha"]}

    @router.post("/prepare-head")
    async def prepare_head(value: PrepareHead):
        row, binding = owned(value)
        if binding["phase"] not in {"phase:implementation", "phase:escalation-repair"}:
            raise HTTPException(409, "PHASE_CANNOT_PUBLISH_CODE")
        pr = await current(binding, resumed=True)
        if "status:running" not in labels(pr):
            raise HTTPException(409, "WORKER_NOT_STARTED")
        checkpoint = json.loads(row.get("checkpoint_json") or "{}")
        started = checkpoint.get("start_projection") or {}
        if started.get("status") != "applied" or started.get("lease_id") != value.lease_id:
            raise HTTPException(409, "WORKER_NOT_STARTED")
        if checkpoint.get("projection"):
            raise HTTPException(409, "PHASE_ALREADY_ADVANCING")
        previous = checkpoint.get("head_publication") or {}
        if previous and previous["status"] == "prepared":
            if previous["to_sha"] != value.target_sha:
                raise HTTPException(409, "PUBLICATION_ALREADY_PREPARED")
            return {"status": "prepared", **response(row)}
        commit = await github.get_publication_commit(binding["repository"], value.target_sha)
        if (commit.get("sha") != value.target_sha
            or [x.get("sha") for x in commit.get("parents", [])] != [binding["source_sha"]]
            or not commit.get("files")):
            raise HTTPException(409, "PUBLICATION_NOT_DIRECT_CHILD")
        paths = [x.get(key, "") for x in commit["files"] for key in ("filename", "previous_filename")]
        if any(path.startswith(".github/workflows/") for path in paths):
            raise HTTPException(409, "WORKFLOW_PUBLICATION_FORBIDDEN")
        live = await current(binding, resumed=True)
        if labels(live) != labels(pr) or live["base"]["ref"] != pr["base"]["ref"]:
            raise HTTPException(409, "STATE_CHANGED")
        owned(value)
        intent = dict(from_sha=binding["source_sha"], to_sha=value.target_sha,
                      base_ref=pr["base"]["ref"], status="prepared")
        checkpoint["head_publication"] = intent
        store.checkpoint(value.delivery_id, checkpoint, value.lease_id)
        store.record_recovery_audit(value.delivery_id, publication_audit(binding, value.lease_id, intent, "prepared"))
        return {"status": "prepared", **response(row)}

    @router.post("/confirm-head")
    async def confirm_head(value: OwnedClaim):
        row, binding = owned(value)
        try:
            row, binding = await refresh_declared_head(store, github, row, binding)
        except (HandoffGateError, RuntimeError) as exc:
            raise HTTPException(409, str(exc)) from exc
        publication = json.loads(row.get("checkpoint_json") or "{}").get("head_publication") or {}
        if publication.get("status") != "applied":
            raise HTTPException(409, "HEAD_NOT_PUBLISHED")
        await current(binding, resumed=True)
        return {"status": "applied", **response(row)}

    @router.post("/acquire")
    async def acquire(value: AcquireClaim):
        binding = value.model_dump(exclude={"worker_id", "request_id"})
        binding["agent"] = ("agent:chatgpt" if value.phase == "phase:implementation"
                            else "agent:workreview" if value.phase in {"phase:code-review", "phase:escalation-repair"}
                            else "agent:workbuddy")
        binding["operation_key"] = json.dumps(
            [value.repository, value.pr_number, value.source_sha, value.phase], separators=(",", ":"))
        previous = store.get(store.external_delivery_id(value.worker_id, value.request_id))
        if previous:
            owned(OwnedClaim(delivery_id=previous["delivery_id"],
                             lease_id=previous["lease_id"] or "", worker_id=value.worker_id))
        snapshot = await current(binding, resumed=previous is not None)
        binding["base_ref"] = snapshot["base"]["ref"]
        try:
            row = store.claim_external(binding, value.worker_id, value.request_id)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        try:
            # A push or human-wait transition during acquisition revokes it.
            await current(binding, resumed=previous is not None)
        except HTTPException:
            store.finish(row["delivery_id"], "superseded", lease_id=row["lease_id"])
            raise
        return response(row)

    @router.post("/heartbeat")
    async def heartbeat(value: OwnedClaim):
        row, binding = owned(value)
        try:
            row, binding = await refresh_declared_head(store, github, row, binding)
        except (HandoffGateError, RuntimeError) as exc:
            raise HTTPException(409, str(exc)) from exc
        projection = json.loads(row.get("checkpoint_json") or "{}").get("projection") or {}
        target = (set(projection["workflow_after"])
                  if projection.get("lease_id") == value.lease_id else None)
        try:
            await current(binding, resumed=True, projected_route=target)
        except HTTPException:
            store.finish(row["delivery_id"], "superseded", lease_id=row["lease_id"])
            raise
        if not store.heartbeat(value.delivery_id, value.lease_id):
            raise HTTPException(409, "WORKER_LEASE_LOST")
        return response(store.get(value.delivery_id))

    @router.post("/publish-reports")
    async def publish_reports(value: PublishReports):
        row, binding = owned(value)
        if binding["phase"] not in REPORT_PATHS:
            raise HTTPException(409, "PHASE_CANNOT_PUBLISH_REPORTS")
        supplied = {item.path for item in value.files}
        if len(supplied) != len(value.files) or not supplied <= REPORT_PATHS[binding["phase"]]:
            raise HTTPException(409, "REPORT_PATH_NOT_ALLOWED")

        checkpoint = json.loads(row.get("checkpoint_json") or "{}")
        started = checkpoint.get("start_projection") or {}
        if started.get("status") != "applied" or started.get("lease_id") != value.lease_id:
            raise HTTPException(409, "WORKER_NOT_STARTED")
        if checkpoint.get("projection"):
            raise HTTPException(409, "PHASE_ALREADY_ADVANCING")

        digest = hashlib.sha256(json.dumps(
            [{"path": item.path, "content": item.content} for item in value.files],
            sort_keys=True, ensure_ascii=False
        ).encode()).hexdigest()
        previous = checkpoint.get("report_publication") or {}
        if previous.get("status") == "applied":
            if previous.get("content_sha256") != digest:
                raise HTTPException(409, "REPORT_PUBLICATION_ALREADY_APPLIED")
            return {
                "status": "already_applied",
                "head_changed": previous["from_sha"] != previous["to_sha"],
                **response(row),
            }

        pr = await current(binding, resumed=True)
        if "status:running" not in labels(pr):
            raise HTTPException(409, "WORKER_NOT_STARTED")
        request = {
            "status": "prepared",
            "phase": binding["phase"],
            "from_sha": binding["source_sha"],
            "content_sha256": digest,
            "files": [{"path": item.path, "content": item.content} for item in value.files],
        }
        prior_request = checkpoint.get("report_request")
        if prior_request and prior_request != request:
            raise HTTPException(409, "REPORT_PUBLICATION_REQUEST_CHANGED")
        checkpoint["report_request"] = request
        store.checkpoint(value.delivery_id, checkpoint, value.lease_id)

        changes = [FileChange(path=item.path, content=item.content) for item in value.files]
        try:
            new_sha = await github.update_pr_files(
                binding["repository"],
                binding["pr_number"],
                changes,
                message_prefix=f"reports: {binding['phase'].removeprefix('phase:')}",
                expected_head_sha=binding["source_sha"],
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc

        # Recheck ownership after the GitHub write. A retry with the same lease
        # can recover a lost response because update_pr_files recognizes the
        # exact direct-child report commit.
        owned(value)
        publication = {
            "status": "applied",
            "phase": binding["phase"],
            "from_sha": binding["source_sha"],
            "to_sha": new_sha,
            "content_sha256": digest,
        }
        checkpoint["report_publication"] = publication
        checkpoint["report_request"]["status"] = "applied"
        if new_sha != binding["source_sha"]:
            checkpoint.pop("projection", None)
            checkpoint.pop("recovery_projection", None)
            row = store.move_external_head(
                value.delivery_id,
                value.lease_id,
                binding["source_sha"],
                new_sha,
                checkpoint,
            )
            binding = json.loads(row["payload_json"])
            store.record_recovery_audit(value.delivery_id, {
                "rule_id": "REPORT_HEAD_PUBLICATION",
                "lease_id": value.lease_id,
                "repository": binding["repository"],
                "pr_number": binding["pr_number"],
                "worker_id": value.worker_id,
                "phase": binding["phase"],
                "source_sha": publication["from_sha"],
                "target_sha": publication["to_sha"],
                "action_type": "invalidate_old_sha",
                "status": "applied",
                "reason": "report commit changed HEAD; all prior advancement evidence is stale",
                "created_at": now(),
                "evidence_generation": digest,
            })
        else:
            store.checkpoint(value.delivery_id, checkpoint, value.lease_id)

        await current(binding, resumed=True)
        return {
            "status": "applied",
            "head_changed": publication["from_sha"] != publication["to_sha"],
            **response(store.get(value.delivery_id)),
        }


    @router.post("/release")
    async def release(value: OwnedClaim):
        owned(value)
        if not store.finish(value.delivery_id, "done", lease_id=value.lease_id):
            raise HTTPException(409, "WORKER_LEASE_LOST")
        return {"released": True}

    @router.post("/start")
    async def start(value: OwnedClaim):
        row, binding = owned(value)
        projection_key = json.dumps([binding["repository"], binding["pr_number"], "state-projection"])
        if not store.claim_operation(projection_key, value.delivery_id, value.lease_id):
            raise HTTPException(409, "ANOTHER_WORKER_OWNS_PROJECTION")
        checkpoint = json.loads(row.get("checkpoint_json") or "{}")
        previous = checkpoint.get("start_projection") or {}
        target = {binding["agent"], binding["phase"], "status:running"}
        # Only accept RUNNING as a retry when this lease recorded its intent.
        replay = previous.get("lease_id") == value.lease_id
        pr = await current(binding, projected_route=target if replay else None)
        if binding["phase"] == "phase:qa":
            comments = await github.list_comments(binding["repository"], binding["pr_number"])
            runs = await github.list_workflow_runs(binding["repository"], binding["source_sha"])
            try:
                validate_qa_evidence(comments, runs, task_id=binding["task_id"],
                    head_sha=binding["source_sha"], head_ref=binding["head_ref"],
                    trusted_login=binding["repository"].split("/", 1)[0],
                    pr_number=binding["pr_number"])
            except HandoffGateError as exc:
                raise HTTPException(409, str(exc)) from exc
        before = labels(pr)
        after = (before - {"status:todo"}) | target
        audit = previous if replay else {
            "rule_id": "LEASED_WORKER_START", "lease_id": value.lease_id,
            "repository": binding["repository"], "pr_number": binding["pr_number"],
            "task_id": binding["task_id"], "phase": binding["phase"],
            "worker_id": value.worker_id, "source_sha": binding["source_sha"],
            "operation_key": binding["operation_key"], "action_type": "start",
            "reason": "live lease verified before READY to RUNNING",
            "status": "planned", "created_at": now(),
            "labels_before": sorted(before), "labels_after": sorted(after),
            "evidence_generation": hashlib.sha256(
                f"start:{binding['operation_key']}:{value.lease_id}".encode()).hexdigest(),
        }
        # Do not overwrite a newer label edit while recovering a lost response.
        if replay and (sorted(before) not in [audit["labels_before"], audit["labels_after"]]):
            raise HTTPException(409, "STATE_CHANGED")
        if replay and audit["status"] == "applied" and sorted(before) != audit["labels_after"]:
            raise HTTPException(409, "STATE_CHANGED")
        checkpoint["start_projection"] = audit
        store.checkpoint(value.delivery_id, checkpoint, value.lease_id)
        store.record_recovery_audit(value.delivery_id, audit)
        live = await current(binding, projected_route=target if replay else None)
        if labels(live) != before:
            raise HTTPException(409, "STATE_CHANGED")
        owned(value)
        store.assert_operation(projection_key, value.delivery_id, value.lease_id)
        if before != after:
            await write_labels(store, github, binding, value.delivery_id, value.lease_id, before, after)
        verified = await current(binding, projected_route=target)
        if labels(verified) != after:
            raise HTTPException(409, "PROJECTION_UNVERIFIED")
        owned(value)  # An expired worker must not receive permission to execute.
        already_applied = audit["status"] == "applied"
        audit["status"] = "applied"
        audit["applied_at"] = now()
        store.record_recovery_audit(value.delivery_id, audit)
        store.checkpoint(value.delivery_id, checkpoint, value.lease_id)
        return {"status": "already_applied" if already_applied else "applied",
                "audit": audit, **response(store.get(value.delivery_id))}

    @router.post("/advance")
    async def advance(value: OwnedClaim):
        row = store.get(value.delivery_id)
        checkpoint = json.loads(row.get("checkpoint_json") or "{}") if row else {}
        projection = checkpoint.get("projection") or {}
        if (row and row["event_name"] == "external_claim" and row["status"] == "done"
            and projection.get("lease_id") == value.lease_id
            and projection.get("status") == "applied"
            and json.loads(row["payload_json"]).get("worker_id") == value.worker_id):
            binding = json.loads(row["payload_json"])
            live = await current(binding, projected_route=set(projection["workflow_after"]))
            if sorted(labels(live)) != projection["labels_after"]:
                raise HTTPException(409, "STATE_CHANGED")
            return {"status": "already_applied", "audit": projection}

        row, binding = owned(value)
        projection_key = json.dumps([binding["repository"], binding["pr_number"], "state-projection"])
        if not store.claim_operation(projection_key, value.delivery_id, value.lease_id):
            raise HTTPException(409, "ANOTHER_WORKER_OWNS_PROJECTION")
        previous_target = (set(projection["workflow_after"])
                           if projection.get("lease_id") == value.lease_id else None)
        pr = await current(binding, resumed=True, projected_route=previous_target)
        comments = await github.list_comments(binding["repository"], binding["pr_number"])
        runs = await github.list_workflow_runs(binding["repository"], binding["source_sha"])
        report_publication = checkpoint.get("report_publication") or {}
        qa_head_changed = (
            binding["phase"] == "phase:qa"
            and report_publication.get("status") == "applied"
            and report_publication.get("from_sha") != report_publication.get("to_sha")
            and report_publication.get("to_sha") == binding["source_sha"]
        )
        try:
            if qa_head_changed:
                if successful_current_ci(
                    runs, head_sha=binding["source_sha"], head_ref=binding["head_ref"]
                ) is None:
                    raise HandoffGateError("current-SHA ordinary CI has not passed")
                target = {"agent:workreview", "phase:code-review", "status:todo"}
                marker = "<!-- qa-postwrite-review:v1 -->"
                required = {
                    f"task_id={binding['task_id']}",
                    f"source_sha={binding['source_sha']}",
                    "next=NEW_INDEPENDENT_WORK_CODE_REVIEW",
                }
                marker_exists = any(
                    (item.get("user") or {}).get("login")
                    in {binding["repository"].split("/", 1)[0], "github-actions[bot]"}
                    and marker in str(item.get("body") or "")
                    and required <= set(str(item.get("body") or "").splitlines())
                    for item in comments
                )
                if not marker_exists:
                    owned(value)
                    await github.comment(
                        binding["repository"],
                        binding["pr_number"],
                        marker + "\n"
                        + f"task_id={binding['task_id']}\n"
                        + f"source_sha={binding['source_sha']}\n"
                        + f"previous_sha={report_publication['from_sha']}\n"
                        + "next=NEW_INDEPENDENT_WORK_CODE_REVIEW",
                    )
                    comments = await github.list_comments(
                        binding["repository"], binding["pr_number"]
                    )
            else:
                target = verified_next_workflow(binding, comments, runs)
        except HandoffGateError as exc:
            raise HTTPException(409, str(exc)) from exc
        before = labels(pr)
        after = (before - {x for x in before if x.startswith(("agent:", "phase:", "status:", "approval:"))}) | target
        audit = {
            "rule_id": "VERIFIED_PHASE_ADVANCE", "lease_id": value.lease_id,
            "repository": binding["repository"], "pr_number": binding["pr_number"],
            "task_id": binding["task_id"], "phase": binding["phase"],
            "action_type": "advance", "reason": "verified current-SHA phase evidence",
            "worker_id": value.worker_id, "source_sha": binding["source_sha"],
            "operation_key": binding["operation_key"], "status": "planned",
            "workflow_after": sorted(target), "labels_before": sorted(before),
            "labels_after": sorted(after), "created_at": now(),
            "evidence_generation": hashlib.sha256(json.dumps(
                [binding["source_sha"], comments, runs], sort_keys=True).encode()).hexdigest(),
        }
        checkpoint["projection"] = audit
        store.checkpoint(value.delivery_id, checkpoint, value.lease_id)
        store.record_recovery_audit(value.delivery_id, audit)
        live = await current(binding, resumed=True, projected_route=previous_target)
        if labels(live) != before:
            raise HTTPException(409, "STATE_CHANGED")
        owned(value)  # Fence an expired lease immediately before the write.
        store.assert_operation(projection_key, value.delivery_id, value.lease_id)
        if before != after:
            await write_labels(store, github, binding, value.delivery_id, value.lease_id, before, after)
        verified = await current(binding, resumed=True, projected_route=target)
        if labels(verified) != after:
            raise HTTPException(409, "PROJECTION_UNVERIFIED")
        audit["status"] = "applied"
        audit["applied_at"] = now()
        store.record_recovery_audit(value.delivery_id, audit)
        checkpoint["projection"] = audit
        store.checkpoint(value.delivery_id, checkpoint, value.lease_id)
        if not store.finish(value.delivery_id, "done", lease_id=value.lease_id):
            raise HTTPException(409, "WORKER_LEASE_LOST")
        return {"status": "applied", "audit": audit}

    def labels(pr):
        return {x["name"] if isinstance(x, dict) else x for x in pr.get("labels", [])}

    return router
