# Plants Hub - Feature Implementation Plan

Date: 2026-01-02

Goal: Implement UI and behavior improvements to the Plants Hub per the request:
- Add action icons to plant cards (remove, edit/update, link sensor).
- Use the Plant Health Status container to show either overall health or per-plant status.
- Add the same small action buttons in the dashboard KPI/plant cards.
- Show observations in a modal listing for a plant; `Add Observation` opens the form modal (do not open the form directly).
- Provide a view toggle (compact / expanded) for plant and disease unit containers.
- Fix Disease Risk Assessment 'Analyzing...' persistent state.
- Fix inconsistencies in the `status-info` container.

---

## Scope & Files
Primary files to modify:
- templates/plants.html
- templates/dashboard.html
- static/js/plants.js
- static/js/components/plant-details-modal.js
- static/js/api.js
- static/css/plants.css
- app/blueprints/api/plants/health.py

Supporting: other API blueprint files under `app/blueprints/api/plants/`

---

## Detailed Tasks (ordered)

1) Add action buttons to plant cards (plants list + dashboard)
   - Update `renderPlantsHealth()` in `static/js/plants.js` to include compact action icons inside each `.plant-item`:
     - Edit (`.action-edit`)
     - Link Sensor (`.action-link-sensor`)
     - Delete (`.action-delete`)
   - Remove inline `onclick` handlers and use delegated event listeners on `#plants-list` to support click handling without re-wiring.
   - Implement delegated handler in `attachEventListeners()` to:
     - Stop propagation when clicking an action so the card click won't open details.
     - On `.action-edit` → open `plant-details-modal` for that plant.
     - On `.action-delete` → confirm and call `API.Plant.deletePlant(plantId)` then reload data.
     - On `.action-link-sensor` → open a small linking flow (placeholder initially).
   - CSS: add `.plant-actions` styling in `static/css/plants.css` for compact icon buttons.

2) Update Plant Health Status container behavior
   - Default: show overall health (existing behaviour).
   - When a plant is focused (selected), update the same container to reflect that plant's status and context.
   - Wire UI: when `showPlantDetails(plantId)` is called, also update `.status-title` and `.status-message` to plant-specific content.

3) Plant Details modal: actions + observations listing
   - Update `static/js/components/plant-details-modal.js` `render()` to include the three action buttons at the top of the modal (edit/delete/link sensor).
   - Add `Observations` section inside the modal that fetches `/plants/<id>/health/history` and lists observations (uses existing endpoint in `health.py`).
   - Add `Add Observation` button that opens `#add-observation-modal` (the form) prefilled for the plant.

4) Observation flow change
   - Remove any flows that directly open the add-observation form; instead, open the observations list modal first.
   - Ensure `#add-observation-modal` receives `plant_id` when invoked from the observations list.

5) View toggle (compact / expanded)
   - Add toggle in header (eg. small icon group).
   - Persist setting to `localStorage`.
   - Update renderers `renderPlantsHealth()` and `renderDiseaseRisk()` to respect `.compact-view` class and render simplified cards.

6) Fix Disease Risk Assessment stuck state
   - Improve client `loadDiseaseRisk()` error handling: if null/empty returned, sanitize to `{ units: [], summary: { ... } }` and call `renderDiseaseRisk()`.
   - Update `renderDiseaseRisk()` to show a clear empty state when no data available (``"Disease risk unavailable"``), instead of showing an analyzing spinner or stale text.
   - If server returns 503 or error, show a friendly message.

7) Fix `status-info` container issues
   - Ensure `renderHeroStatus()` checks inputs and sets fallback values.
   - Add better messages and ARIA attributes for accessibility.

8) Dashboard parity
   - Add small action buttons to dashboard plant mini-cards and KPI card.
   - Reuse same handlers where possible (expose `window.plantsHub` helper methods).

9) API client additions (if missing)
   - Add helpers in `static/js/api.js` for `getHealthHistory(plantId, days)`, `deletePlant(plantId)`, `linkPlantSensor(plantId, sensorId)` as needed.

10) Tests and QA
   - Manual verification steps.
   - Edge cases: no plants, ML backend unavailable, plant without sensors.

---

## Implementation Strategy
- Work in small commits: one feature per commit.
- Start with frontend-only changes (render + event wiring + CSS) to avoid backend dependencies and to get visible results quickly.
- Next, implement observation modal flow and API hooks.
- Then address disease-risk robustness and dashboard parity.

---

## First Implementation Step (now)
Implement Task 1: Add action buttons to plant cards and wire delegated click handling; add minimal CSS. This is frontend-only and safe to deploy incrementally.

---

## Notes
- This plan favors conservative changes: minimal server edits only when required.
- I will update this file as I make progress and mark tasks in the project's TODO list.
