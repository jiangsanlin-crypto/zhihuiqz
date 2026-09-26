# Worker adoption and live acceptance gates for #80

## Read-only configuration observation (2026-09-26 UTC)

The enabled account workers `Account Chat Sol GitHub Worker` and
`Work Review Consumer v2` still claim through GitHub labels/comments and directly
write phase labels. Their current task configurations do not contain a usable
shared-claim service URL/authentication hookup. `GitHub Workflow Supervisor` is
read-only. No schedules or prompts were changed by this repair.

Installing the client in a PR branch does not connect these workers. Changing
prompts to require an unverified service would stop execution without completing
migration. Existing Actions label writers also remain outside the shared lock.

## Concrete prerequisites before migration

1. Independent review of PR #83, and separate authorization to roll out the
   reviewed SHA. Issue #80 explicitly forbids merge/deployment during this task.
2. One reachable HTTPS claim service, a persistent shared database and an
   approved account-worker authentication mechanism. Verify reachability from
   both actual worker runtimes; never put credentials in prompts, PRs or logs.
3. Connect the planning host to `/intake/issues`, acquire and heartbeat. Implement
   revision-fenced plan publication and link reconciliation before enabling new
   Issue-to-PR work. The intake queue does not itself run the planner.
4. Connect implementation and independent Review hosts to the existing account
   client. Start work only after acquire/start; heartbeat during execution, stop
   on lost ownership, publish trusted exact-SHA results, then request advance.
   Implementation/repair publication uses prepare-head/confirm-head. Review
   remains independent; it cannot approve its own repair.
5. Migrate every state writer, including Actions and legacy recovery routes, to
   the same authority. This requires a separately authorized workflow migration;
   this PR does not edit `.github/workflows`. Read-before-write is not global CAS.
6. Define policies for remaining machine blocker codes and legacy unleased
   RUNNING tasks, acquisition exhaustion, and R01/R04 time-based escalation.
   Unknown/human/content blockers must not be guessed away.

## Live acceptance evidence required after authorized rollout

Use a designated real task and record issue/PR numbers, exact SHA, service build,
lease IDs, worker identity and links to CI/handoff/audit evidence. Verify:

- An unlabelled eligible issue is discovered once, one planner owns it, and one
  linked PR reaches READY. Duplicate deliveries do not duplicate planning.
- Both actual account hosts acquire through the service; a concurrent contender
  fails. A transient acquisition failure retries; expiry fences the old worker.
- Kill a worker before a result and after durable result publication. Recovery
  respectively requeues or resumes evidence projection without duplicate work.
- Test a recoverable blocker, lost label-write response, and a same-SHA requeue.
- Publish a new HEAD: old CI/Review/QA cannot advance it. New exact-SHA ordinary
  CI and independent Review must precede QA.
- After any QA report commit, final-SHA CI, independent Review and QA evidence
  converge to resolved owner-wait policy with no active route or lease.
- Verify no retired API programmer, manual workflow dispatch/rerun, merge or
  deployment occurred; Human Approval is never automatically exited.

PR #78 is a protected owner-wait case, not permission to bypass its missing
final-SHA evidence. Re-fetch its state before any separately authorized action.
Keep #80 open and #83 draft until the complete acceptance evidence is available.

## Read-only connection preflight

Before replacing either enabled worker's prompt, run the checked-in
`scripts/check_worker_service.py` from **each actual worker runtime** with the
approved HTTPS URL and a dedicated claim-service credential file:

```sh
python scripts/check_worker_service.py --url https://CLAIM_SERVICE --token-file /secure/claim-service-token --expected-sha REVIEWED_SHA --repository jiangsanlin-crypto/zhihuiqz
```

The URL/path are placeholders, not a discovered server. The program only GETs
`/readyz`, `/claims/ready` and `/intake/issues`; it does not acquire, change labels, execute a
planner, dispatch Actions or use an OpenAI credential. It rejects redirects,
unauthorized/missing endpoints and malformed responses. Output omits credentials
and task contents. A PASS proves interface/auth reachability only; lease/content
writes and E2E still need the authorized acceptance above. Do not replace the
current workers until this passes and their execution host can heartbeat/use the
shared client. A text prompt alone is not a deployed worker integration.

The isolated service factory and backup/rollback preparation are documented in
[control-service-predeployment.md](control-service-predeployment.md). No service
was deployed and no live worker configuration changed during preparation.
