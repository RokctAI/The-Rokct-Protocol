---
name: tenant-control-hub-call
description: tenant code must call a `control:*` cmd.
version: 1.0.0
---

# Tenant-to-control-hub call (Frappe)
**When:** tenant code must call a `control:*` cmd.

1. There is no shared client, so repeat the house pattern:
   - read site_config `control_plane_url`, `api_secret` and `control_plane_scheme`;
   - send headers `X-Rokct-Secret` and `X-Rokct-Tenant: frappe.local.site`;
   - `POST {scheme}://{url}/api/v1/method/rokct.platform.api` with `{"cmd": "control:<name>", "payload": {...}}`.
2. Always set an explicit timeout, read from a settings doctype with a safe default and a cap.
3. Unwrap `message`, falling back to `data`.
4. Log only the status and exception type, never the URL, secret, body or personal data.
5. Rate-limit anything billable with a `frappe.cache()` fixed window. Gateway cmds bypass `frappe.rate_limiter` decorators; see pay's `wallet/frappe/src/tenant/api/transfer.py`.
6. Every outcome other than success falls back to a manual path, never a hard block for the end user.
