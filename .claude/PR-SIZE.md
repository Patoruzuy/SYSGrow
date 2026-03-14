You are reviewing SYSGrow (Raspberry Pi-first). Output MUST be a Markdown checklist of PR-sized tasks.

Goal:
Produce a PR-ready implementation plan to improve structure, reduce mixed concerns, and add/clean endpoints.

Constraints:
- Pi-first: low memory/CPU, SQLite WAL, no Redis/Celery/Postgres/React unless explicitly asked.
- Keep caching lightweight (LRU+TTL), small maxsize, no route-module global caches.
- Avoid heavy imports at module level (lazy load ML modules).
- Maintain existing API response envelope: {ok: bool, data: any, error?: {message: str}}.
- Use current DI: current_app.config["CONTAINER"] (ServiceContainer).
- Prefer incremental refactors with compatibility shims (avoid breaking frontend/tests).

Output format (strict):
1) A single “PR Checklist” section.
2) Each task must be ≤ 30 minutes of work.
3) Each task must include:
   - [ ] Title
   - Files touched (explicit paths)
   - Change summary (1–3 bullets)
   - Risk: low/medium/high
   - Tests to run (specific pytest file(s))
   - Acceptance criteria (observable behavior)
4) Group tasks under 3 phases:
   - Phase 1: No behavior change cleanups
   - Phase 2: Boundary fixes (move logic out of routes, unify utilities/caching)
   - Phase 3: Optional improvements (reduce import cost, split god-services, better health snapshots)

Inputs provided:
- ServiceContainer.build() implementation
- dashboard blueprint
- SystemHealthService
- CLAUDE.md architecture constraints and patterns
(Then use these to tailor the tasks to the actual code.)
