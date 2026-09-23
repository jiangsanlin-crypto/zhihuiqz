## Summary

Describe the change and stable task ID.

## Agent handoff

- [ ] Stable task ID is preserved.
- [ ] Latest `agent-handoff:v1` is present.
- [ ] Previous blockers are resolved.
- [ ] Expected artifacts are committed.
- [ ] Correct model policy was used.

## Validation

- [ ] CI passes.
- [ ] Relevant tests pass.
- [ ] No secret/token/private key is committed.
- [ ] No real candidate personal data is included without explicit authorization.
- [ ] Paid employer features do not directly increase match relevance.

## Full-auto production boundary

- [ ] Release gate can be evaluated deterministically.
- [ ] Deployment rollback behavior is defined.
- [ ] Automatic merge/deployment remains blocked unless `AUTO_PRODUCTION_ENABLED=true`.
- [ ] `EMERGENCY_STOP=true` can halt production execution.
- [ ] Real payment execution and real candidate-data onboarding are not implicitly authorized.
