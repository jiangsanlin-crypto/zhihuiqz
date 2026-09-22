# WorkBuddy integration

This repository includes a WorkBuddy Runner based on the official WorkBuddy Open API.

## Required scopes

Create/authorize a WorkBuddy third-party application with:

- user.task.invokable
- user.task.readable

The runner uses the Cloud Task API rather than giving WorkBuddy a GitHub credential.

## Required server variables

- WORKBUDDY_CLIENT_ID
- WORKBUDDY_CLIENT_SECRET
- WORKBUDDY_REFRESH_TOKEN

You may temporarily use WORKBUDDY_ACCESS_TOKEN, but a refresh token is preferred for unattended operation.

Keep OAuth material only on the persistent server. Never put it in GitHub source files or an Issue.

## What the runner does

For an Issue:
1. reads safe repository context through the server-side GitHub token;
2. creates a WorkBuddy Cloud Task;
3. waits for completion;
4. reads the task overview artifact;
5. accepts JSON output only;
6. permits writes only to docs/PRD.md, docs/MATCHING_SPEC.md, docs/I18N.md, docs/MONETIZATION.md, and TASKS.md;
7. creates a new agent/workbuddy/* branch and PR using the server-side GitHub credential.

For final PR review:
1. reads PR metadata and bounded patch excerpts;
2. asks WorkBuddy for a success/blocked product review;
3. never writes to the PR branch.

## Security boundary

WorkBuddy never receives GITHUB_TOKEN, production credentials, candidate production data, or payment credentials. Its response cannot choose arbitrary repository paths.
