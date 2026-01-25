SYSGrow — UI/CSS Bindings (Updated)

Scan Summary
- Classes used in templates (unique): ~613
- Classes defined in CSS (unique): ~470
- Missing in CSS (used in templates, no definition): sample below
- Unused in templates (defined in CSS, never used): sample below
- Ignored prefixes: fa, fas, fab (FontAwesome)

Missing CSS Classes (samples)
~ action-buttons (added in components.css)
~ actuator-icon (added in components.css)
~ actuator-status (added in components.css)
- actuators-state
- actuatorstate
~ align-items-center (added in components.css)
- analytics-access
- analytics-btn
- analytics-link-card
- analytics-quick-access-settings
- analytics-quick-links
- aside-panels
- auth-footer
- auth-submit
- auth-title
- available-list
- badge-
- bg-info
- bg-light
- bg-primary
- bg-success
- block
- body_class
- brand
~ btn-action (consider mapping to .btn)
~ btn-large, btn-lg, btn-off, btn-on, btn-remove (added in components.css)

Unused CSS Classes (samples)
- activity-critical
- activity-danger
- activity-details
- activity-entry
- activity-header
- activity-message
- activity-success
- activity-timeline
- activity-warning
- actuators
- alert
- alert-content
- alert-critical
- alert-device
- alert-error
- alert-footer
- alert-header
- alert-icon
- alert-info
- alert-item
- alert-success
- alert-title
- alert-warning
- badge-danger
- badge-diseased
- badge-healthy
- badge-info
- badge-recovering
- badge-secondary
- badge-stressed

Hotspots
- Templates: plant_health.html, units.html, settings.html, dashboard.html make heavy use of utility-like classes (grid/cards/buttons) that should live in static/css/components.css or utilities.css
- CSS: Similar card/grid/button styles exist in dashboard.css, units.css, settings.css; consolidate to reduce drift

Remediations Implemented
- Added shared utilities/components to `static/css/components.css` covering many previously missing classes
- Preserved dynamic class flexibility while providing safe defaults
- Dashboard Device State tile: added in-header CSV export, auto-refresh toggle, and unit filter using shared button/input styles

Recommendations
- Add missing definitions to `static/css/components.css` where appropriate, or rename template usage to nearest existing utility
- Normalize button sizes to `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-sm|.btn-lg`
- Avoid dynamic Jinja tokens in class attributes leaking into class names (e.g., `badge-{{ ... }}`); provide guard defaults or map to known classes
- Run a template pass to replace bespoke names with existing utilities (`.content`, `.card`, `.card-header`, `.card-actions`, `.data-table`, etc.)

Checklist
- [x] Add or rename classes to eliminate “missing” set (first pass complete)
- [ ] Remove/merge unused CSS classes in dashboard.css/units.css/settings.css
- [x] Centralize shared components in components.css/utilities.css (in progress)
