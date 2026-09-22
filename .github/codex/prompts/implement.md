# Codex implementation contract

Implement the approved product specification already present in this PR.

Before changing code:
- read AGENTS.md and docs/HANDOFF_PROTOCOL.md;
- read TASKS.md and all specification documents;
- read the prior agent-handoff comments included below;
- preserve the stable task ID and satisfy the acceptance criteria from the specification.

Rules:
- Work only in this repository and current PR branch.
- Do not create or merge another PR.
- Preserve Khmer as the default product language, followed by English and Chinese.
- Payment or employer plan level must never directly increase candidate relevance scores.
- Do not use or invent real candidate personal data; use synthetic fixtures.
- Do not add production payment credentials, production database credentials, API secrets, or private keys.
- Do not merge main and do not deploy production.
- Run relevant unit/API/i18n/permission tests before finishing.
- Keep changes scoped to the approved PR task.
- If a prior Sandbox handoff contains a blocker, fix it before adding unrelated work.
