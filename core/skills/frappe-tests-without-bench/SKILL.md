---
name: frappe-tests-without-bench
description: a corporate/pay/etc. tenant app change needs unit tests in this container.
version: 1.0.0
---

# Run Frappe tenant tests without a bench
**When:** a corporate/pay/etc. tenant app change needs unit tests in this container.

1. Run `scripts/run.sh <repo>/polaris/frappe/src test_module ...`.
2. It copies `tenant/` into a fake `app` package, rewrites `{app_name}`, and runs unittest with `stub/frappe` on PYTHONPATH.
3. Extend the stub when a test needs more frappe API, e.g. `frappe.cache`.
4. Some suites error from the stub's limits. Compare against a run on the base branch, so you only report new failures.
