## Summary

Describe the change and the task ID.

## Agent handoff

- [ ] Stable task ID is preserved.
- [ ] Latest `agent-handoff:v1` is present.
- [ ] Previous blockers are resolved.
- [ ] Expected artifacts are attached/committed.
- [ ] Correct model policy was used.

## Validation

- [ ] CI passes.
- [ ] Relevant tests pass.
- [ ] No real candidate personal data is included.
- [ ] No secret/token/private key is committed.
- [ ] Paid employer features do not directly increase match relevance.

## Production boundary

- [ ] This PR does not auto-merge `main`.
- [ ] Production deployment still requires human approval.
- [ ] If deployment logic changed, rollback behavior was reviewed.
- [ ] If model policy changed, `docs/MODEL_POLICY.md` and CI model-policy check were reviewed.

## Human review

- [ ] Repository owner approved final merge.
