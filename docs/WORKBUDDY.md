# WorkBuddy integration

The WorkBuddy runner uses WorkBuddy Cloud Tasks for product/specification work and final product review.

## Public GitHub read mode

The repository is public, so WorkBuddy is instructed to read:

- https://github.com/jiangsanlin-crypto/zhihuiqz
- public PR pages
- public files and commit history

directly. WorkBuddy does not receive a GitHub token, connector authorization, or GitHub OAuth grant.

GitHub write operations remain outside WorkBuddy.

## WorkBuddy authentication

The orchestrator still needs to start WorkBuddy Cloud Tasks. Configure WorkBuddy's own API/OAuth credentials on the persistent server:

- WORKBUDDY_CLIENT_ID
- WORKBUDDY_CLIENT_SECRET
- WORKBUDDY_REFRESH_TOKEN

A temporary WORKBUDDY_ACCESS_TOKEN can be used during setup, but refresh-token operation is preferred for unattended use.

## Specification handoff

For a source Issue, WorkBuddy returns JSON only. The runner accepts changes only for:

- docs/PRD.md
- docs/MATCHING_SPEC.md
- docs/I18N.md
- docs/MONETIZATION.md
- TASKS.md

The WorkBuddy runner does not push those files itself. It returns the validated file payload to the Orchestrator.

The Orchestrator then:
1. creates or reuses agent/workbuddy/issue-<number>;
2. writes only the validated allowlisted files;
3. creates the specification PR;
4. records the stable task ID in the PR body;
5. publishes the structured handoff comment;
6. hands the PR to Sandbox QA.

## Final review

For final review, WorkBuddy receives the public repository and PR URLs and is instructed to read the PR diff, specification files, implementation, and previous handoff comments directly.

Its result is only success or blocked. It cannot merge the PR.

## Security boundary

WorkBuddy receives no:
- GITHUB_TOKEN
- production payment credential
- production database credential
- real candidate production data

Only the Orchestrator holds the GitHub credential used for the WorkBuddy specification write-back.
