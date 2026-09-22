# KhmerHire staging deployment

This stack is intentionally separate from the repository's multi-agent orchestrator stack.

## 1. Prepare environment

Copy the example file outside version control:

```bash
cp deploy/.env.staging.example .env.staging
```

Replace every password and token. Use URL-safe characters for `POSTGRES_PASSWORD` unless you provide an already URL-encoded database URL.

## 2. Start staging

```bash
docker compose --env-file .env.staging -f docker-compose.khmerhire-staging.yml up -d --build
```

The public test site defaults to:

```
http://localhost:8088
```

The browser calls the backend through the same-origin `/api` reverse proxy.

## 3. Bootstrap platform admin

Do not expose a public admin-registration endpoint.

```bash
docker compose --env-file .env.staging -f docker-compose.khmerhire-staging.yml exec \
  -e ADMIN_PHONE="$SMOKE_ADMIN_PHONE" \
  -e ADMIN_PASSWORD="$SMOKE_ADMIN_PASSWORD" \
  backend python scripts/create_admin.py
```

For a real staging admin, use separate credentials from the smoke-test account.

## 4. Database migrations

PostgreSQL schema changes are managed by Alembic. Backend startup runs:

```bash
alembic upgrade head
```

Check migration state:

```bash
docker compose --env-file .env.staging -f docker-compose.khmerhire-staging.yml exec backend alembic current
```

SQLite development remains auto-created for local tests only.

## 5. End-to-end smoke test

The smoke test verifies:

- API health/readiness
- candidate and employer registration/login
- candidate profile
- employer verification
- job publishing
- authenticated application
- employer/candidate messaging
- hiring pipeline transition
- interview scheduling
- candidate application history
- explainable candidate matching

Run:

```bash
docker compose --env-file .env.staging -f docker-compose.khmerhire-staging.yml exec \
  -e SMOKE_BASE_URL=http://frontend/api \
  -e SMOKE_ADMIN_PHONE="$SMOKE_ADMIN_PHONE" \
  -e SMOKE_ADMIN_PASSWORD="$SMOKE_ADMIN_PASSWORD" \
  backend python scripts/smoke_staging.py
```

Expected final line:

```
KHMERHIRE_STAGING_SMOKE_OK
```

## 6. Backup

Before schema changes or staging data refresh:

```bash
docker compose --env-file .env.staging -f docker-compose.khmerhire-staging.yml exec -T khmerhire-db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > khmerhire-staging-backup.sql
```

Keep backups outside the Git repository.

## 7. Rollback

Application rollback:

1. Keep the previous container image or Git commit.
2. Stop the current application containers without deleting the PostgreSQL volume.
3. Restore the previous application version.
4. Only run `alembic downgrade` when the migration is explicitly known to be reversible.
5. For destructive database failures, restore the PostgreSQL backup instead of guessing.

Never use `docker compose down -v` on a staging host containing data you want to keep. The CI workflow uses `-v` only because its database is disposable.
