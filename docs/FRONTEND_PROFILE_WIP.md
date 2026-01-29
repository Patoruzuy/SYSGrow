# Frontend Condition Profiles — WIP Handoff

Date: 2026-01-28

## What was implemented today

- Added a reusable profile selector component and card UI.
  - `static/js/components/profile-selector.js`
  - `static/css/units.css`
  - `static/css/plants.css`
- Wired profile selection into unit creation.
  - `templates/units.html` (create unit modal now includes profile section)
  - `static/js/units/ui-manager.js` (loads selector, imports shared token, applies profile after unit creation)
- Wired profile selection into unit “Add Plant” modal.
  - `templates/units.html`
  - `static/js/units/ui-manager.js`
- Wired profile selection into plants “Add Plant” modal.
  - `templates/plants.html`
  - `static/js/plants/ui-manager.js`
- Exposed `data-user-id` for frontend calls.
  - `templates/base.html`

## Remaining tasks

- Verify modal flows in UI:
  - Create unit → select profile → confirm profile is applied via `/api/growth/v2/units/{id}/thresholds/apply-profile`.
  - Add plant (units modal) → select profile → confirm plant created with `condition_profile_id` and proper mode.
  - Add plant (plants page) → select profile → confirm plant created with `condition_profile_id`.
  - Import by share token works in both places.
- Run a quick smoke test in browser and confirm no console errors.

## Newly completed since last handoff

- Added clear-selection buttons in all profile selectors.
- Added small profile chips in modal headers (unit + plant).

## Notes / Gotchas

- `static/js/units/ui-manager.js` now applies the chosen profile *after* unit creation. If the API errors, the unit still exists.
- The plants modal selector filters by `plant_type` (from catalog or custom) + `growth_stage`.
- The unit modal selector filters by optional `plant_type`/`growth_stage` fields that were added to the form.
- `plants_info.json` and `scripts/debug_priority.py` are still locally modified but unrelated.

## Files touched

- `templates/base.html`
- `templates/units.html`
- `templates/plants.html`
- `static/js/components/profile-selector.js`
- `static/js/units/ui-manager.js`
- `static/js/plants/ui-manager.js`
- `static/css/units.css`
- `static/css/plants.css`
