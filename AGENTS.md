# Agent workflow

Labels:
- agent:workbuddy
- agent:sandbox
- agent:codex
- needs:qa
- ready-for-codex
- status:todo
- status:running
- status:blocked
- status:review
- status:done

Runner contract: POST /run

Each runner returns:
```json
{"status":"success","summary":"...","artifacts":[],"next_labels":[],"pr_number":null}
```

Hard safety boundary: no automatic merge to main, no production deploy, no production payment, no write access to real candidate data.
