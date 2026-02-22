# TODO

## Irrigation ML Enhancements
- [x] Add timezone-aware timing features (unit-local hour bucketing for detected_at and delayed_until)
- [x] Expose ML gating status + metrics in irrigation prediction API responses (ml_ready, model_version, gating_metrics)
- [x] Emit telemetry when ML gating blocks inference (log/metrics hook)
- [x] Add class-balance monitoring and warnings for timing model training data
- [x] Add tests for no-fallback behavior when ML gating fails

## Docs Hygiene (Optional)
- [ ] Revisit `.gitignore` to allow tracking `docs/` and `*.md` without `-f`


### Modularity and Abstraction Analysis
- [x] Evaluate the current level of modularization
- [x] Assess the granularity of modules and classes
- [x] Check for appropriate use of interfaces and abstract classes
- [x] Identify opportunities for improved encapsulation


### Code Maintainability Indicators
- [x] Check code readability and consistency
- [x] Evaluate naming conventions and code documentation
- [x] Assess test coverage and testability of components
- [x] Identify areas with high maintenance complexity

### Frontend Consistency (Sprint 10)
- [x] Template / CSS / Jinja2 comprehensive audit
- [x] Delete orphaned templates and static/legacy files
- [x] CSS naming standardization (snake_case → kebab-case)
- [x] Jinja2 block name standardization (extra_css/extra_js → styles/scripts)
- [x] Extract inline `<style>` blocks to dedicated CSS files (521 lines)
- [x] Accessibility improvements (aria-labels, alt text)
- [x] Add macro imports to templates missing them
- [x] Blueprint return-type annotations (425 routes → `-> Response`)
- [x] CHANGELOG.md creation (Sprints 0–10)
