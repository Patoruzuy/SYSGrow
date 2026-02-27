# Audit Remediation Backlog (Open Items Only)

Filtered on 2026-02-25 after a targeted verification pass.
This file intentionally contains only issues that still need work.
Resolved items were removed from this list.

## How to Use This File

- Implement items from top to bottom by priority.
- Re-run focused checks after each item.
- Run full verification (radon, bandit, integration tests) after the remediation wave.

## P1 - Architecture / Layering

### 1) Large/Fat Modules Still Need Decomposition

Status: Open
Severity: Medium

Problem:
- Several high-complexity files from the audit remain large and difficult to maintain.

Priority targets (current snapshot):
- `app/services/ai/ml_trainer.py` (~2389 LOC)
- `app/services/application/growth_service.py` (~1887 LOC)
- `app/services/application/plant_service.py` (~1862 LOC)
- `app/services/ai/feature_engineering.py` (~1795 LOC)
- `app/services/hardware/actuator_management_service.py` (~1476 LOC)

Required work:
- Split by sub-domain responsibility (service extraction, helper modules, smaller route handlers).
- Prefer behavior-preserving refactors with tests before logic changes.

Acceptance criteria:
- Targeted files are reduced meaningfully in size/complexity.
- Radon complexity tail (D/F functions) trends downward after refactors.
- Existing behavior covered by tests.

## P2 - Hardening / Hygiene (Still Worth Doing)

### 2) Broad Exception Usage Still High

Status: Open
Severity: Medium

Problem:
- Broad `except Exception` usage remains pervasive (quick grep snapshot still shows high volume).

Required work:
- Start with top-risk request and background-task paths.
- Replace broad catches with specific exceptions where feasible.
- For unavoidable broad catches, ensure robust logging + safe client responses.

Acceptance criteria:
- Top hot-path modules audited and narrowed.
- Error handling remains user-safe and observable.

## Deferred / Later (After Current Priority Items)

These were identified in the original audit and are still likely open, but should be scheduled after the items above unless they block current work:

- Decompose remaining god services/blueprints beyond the priority targets.
- Narrow more broad exception handlers across services and workers.
- Expand schema validation coverage for API inputs.
- Add/expand tests for large AI and application services.
- Revisit API versioning/documentation strategy (OpenAPI/Swagger).
- Batch DB operations to reduce N+1 query patterns.
- Additional performance tuning (caching/pagination/thread lock granularity) after functional/security fixes.

## Full Verification Gate (Run After Remediation Wave)

Run these after implementing a batch of fixes:

- `python3 -m pyflakes app`
- `python3 -m bandit -r app -c pyproject.toml -f json -o bandit_report.json`
- `python3 -m radon cc app -s -a`
- `python3 -m radon mi app -s`
- Integration tests (project-specific command to be run once we pick the first implementation batch)

## Notes

This is a filtered worklist, not the full historical audit narrative. The original comprehensive report content was removed from this file to keep implementation work focused on unresolved items.
