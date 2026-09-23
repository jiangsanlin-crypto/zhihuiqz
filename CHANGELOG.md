# Changelog

## 2026-09-23

- Added safe degraded bootstrap mode when WorkBuddy OAuth is unavailable.
- Kept GLM-5.3-Flash and the explicit model-lock confirmation mandatory.
- Made /readyz report workbuddy_mode and workbuddy_configured while remaining
  ready in degraded mode.
- Made real WorkBuddy dispatch return HTTP 503 without creating a cloud task,
  handoff marker, or automatic phase promotion.
- Added activation/preflight coverage and documented the OAuth upgrade path.
