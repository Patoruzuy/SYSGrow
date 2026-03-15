# Frontend Audit Report & Remediation Plan

> **Date:** 2026-02-22  
> **Scope:** Templates, Macros, CSS Architecture, JavaScript Architecture  
> **Method:** Full static audit of `templates/`, `static/css/`, `static/js/`  
> **Status:** Audit complete — remediation pending

---

## Executive Summary

The frontend is a well-structured custom stack (Jinja2 + vanilla CSS design tokens + vanilla JS modules) with a solid foundation. The main issues fall into three clusters:

1. **Bootstrap class leakage** — Templates inconsistently mix the project's own utility class names (`.flex`, `.align-center`) with Bootstrap names (`d-flex`, `align-items-center`). Bootstrap is NOT loaded. Several critical classes like `d-none` are missing, causing elements to always be visible that should be hidden.

2. **CSS token system fracture** — `theme.css` overwrites `--section-gap` with a hardcoded `15px`, bypassing the design token. Duplicate CSS rules in `components.css` create dead styles. The `.btn` shimmer effect is broken because `.btn` lacks `position: relative`.

3. **Structural debt** — `components.css` at 4,437 lines is unmaintainable. The `help_banner` block is copy-pasted 7× instead of being a macro. Several Bootstrap utility classes that are legitimately missing (spacing, display, form) need to be added to `base.css`.

**Fix cost is low** — no architectural rebuilds required. All Phase 1 and Phase 2 fixes are single-file edits with no breaking changes.

---

## Component Inventory

| Component | File(s) | Status | Notes |
|-----------|---------|--------|-------|
| `.btn`, `.btn-primary`, etc. | `components.css:3–40`, `components.css:256–295` | ⚠️ Duplicate | Two definitions; shimmer broken |
| `.card`, `.surface` | `components.css:317+` | ✅ OK | Uses tokens |
| `.kpi-card` | `components.css/kpi-cards.css` | ✅ OK | Has macro |
| `.section`, `.sub-section` | `base.css:66–67` | ⚠️ Token broken | `--section-gap` wrong value |
| `.alert` | `unit-selector.css:677`, `plants.css:1570` | ❌ Not global | No variants (`alert-warning` etc.) |
| `.form-check`, `.form-switch` | Not defined | ❌ Missing | Toggle switches are unstyled |
| `.list-group-item` | Not defined | ❌ Missing | Used in `system_health.html` |
| `d-flex`, `d-none`, `align-items-*` | Not defined | ❌ Missing | Bootstrap names not aliased |
| Spacing utilities (`mt-4/5`, `mb-5/6`, `ms-2`) | Not defined | ❌ Incomplete | Only partial set in `base.css` |
| `macros.html` – `help_banner` | Duplicated inline | ❌ Missing macro | Repeated 7× across templates |
| `macros.html` – `content_card` | `macros.html:191` | ⚠️ Hardcoded h3 | No heading level parameter |
| `window.socketManager` | `socket.js:101` & `socket.js:471` | ⚠️ Double assign | Constructor exposes partial object |

---

## Detailed Issues

### Issue 1 — `d-none` is missing → hidden elements are always visible

**Severity:** 🔴 Critical  
**Files:** `templates/system_health.html`, `templates/ml_dashboard.html`, `templates/devices.html`, `templates/settings.html`

The custom CSS has `.hidden` / `.is-hidden` (`display: none !important`) but templates use Bootstrap's `d-none` in 10+ locations:

```html
<!-- system_health.html:33 — alert banner that must start hidden -->
<div id="alert-banner" class="alert alert-warning d-flex align-items-center … d-none">

<!-- ml_dashboard.html:141 — drift alert hidden until triggered -->
<div class="alert alert-warning mt-3 mb-0 d-none" id="drift-alert">

<!-- devices.html:26 — text hidden on small screens -->
<span class="d-none d-sm-inline">Device Health</span>
```

Without `d-none`, these elements render as always-visible, which breaks the UI state machine for alert banners and drift notifications.

**Class name audit — Bootstrap vs custom:**

| Bootstrap class | Custom equivalent | Defined? |
|----------------|-------------------|----------|
| `d-flex` | `.flex` | Custom only — `d-flex` missing |
| `d-none` | `.hidden`, `.is-hidden` | Custom only — `d-none` missing |
| `d-sm-inline` | _(none)_ | ❌ Missing |
| `d-md-flex` | _(none)_ | ❌ Missing |
| `align-items-center` | `.align-center` | Custom only — Bootstrap name missing |
| `align-items-start` | `.align-start` | Custom only — Bootstrap name missing |
| `align-items-end` | `.align-end` | `align-items-end` defined in `components.css:1197` — inconsistent |
| `justify-content-between` | `.justify-between` | Custom only — Bootstrap name missing |
| `justify-content-center` | `.justify-center` | Custom only — Bootstrap name missing |
| `justify-content-end` | `.justify-end` | Custom only — Bootstrap name missing |
| `justify-content-around` | _(none)_ | ❌ Missing entirely |
| `flex-column` | `.flex-col` | Custom only — Bootstrap name missing |
| `flex-wrap` | `.flex-wrap` | ✅ Defined (same name) |
| `align-items-end` | `.align-end` | Partially (Bootstrap name in `components.css:1197`) |

**Fix:** Add Bootstrap compatibility aliases to `base.css`. This is ~25 lines.

---

### Issue 2 — `--section-gap` design token broken

**Severity:** 🔴 Critical  
**Files:** `static/css/tokens.css:21`, `static/css/theme.css:65`

`tokens.css` defines:
```css
--section-gap: var(--space-6);  /* 1.5rem — scales with rem */
```

`theme.css` (loaded after) overrides it:
```css
--section-gap: 15px;  /* hardcoded px — doesn't scale */
```

`theme.css` wins. All 20+ usages of `--section-gap` across `base.css`, `components.css`, `dashboard.css`, `devices.css`, `settings.css`, `units.css`, `analytics.css` are getting `15px` instead of `var(--space-6)` = `1.5rem`. This defeats the design token system and prevents any future font-size-based responsive scaling.

**Fix:** Remove the `--section-gap: 15px` line from `theme.css:65`. One-line deletion.

---

### Issue 3 — `.btn` shimmer effect is broken

**Severity:** 🟠 High  
**File:** `static/css/components.css:3–16`, `components.css:256–270`

`.btn` base definition (lines 3–16) does not include `position: relative`. The `::before` pseudo-element shimmer added later (line 256) uses `position: absolute; inset: 0`, which requires a positioned ancestor:

```css
/* components.css:256 — requires position: relative on .btn */
.btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, transparent 0%, color-mix(in srgb, white 10%, transparent) 100%);
  opacity: 0;
  …
}
```

Without `position: relative` on `.btn`, the shimmer pseudo-element is positioned relative to the nearest positioned ancestor (often the page body), causing visual overflow or invisible positioning.

**Fix:** Add `position: relative; overflow: hidden;` to `.btn` base definition.

---

### Issue 4 — Duplicate `.btn-primary` definition

**Severity:** 🟠 High  
**File:** `static/css/components.css`

Two separate `.btn-primary` blocks exist:

```css
/* components.css:24 — flat background */
.btn-primary {
  background: var(--brand-600);
  color: var(--color-on-brand);
  border-color: var(--brand-600);
}
.btn-primary:hover {
  background: var(--brand-700);
  border-color: var(--brand-700);
  transform: translateY(-1px);  /* ← also duplicated by .btn:hover at line 271 */
  box-shadow: var(--shadow-md);
}

/* components.css:280 — gradient background (wins, but silently) */
.btn-primary {
  background: var(--gradient-primary);
  border-color: var(--brand-600);
  /* note: color: var(--color-on-brand) is NOT re-declared — inherited from above */
}
```

The first definition's `:hover` transform (`translateY(-1px)`) is then also declared globally at line 271 (`.btn:hover { transform: translateY(-1px); }`). The duplication creates confusion about which rule is authoritative and adds maintenance risk.

**Fix:** Remove the first `.btn-primary` block (lines 24–41). Keep the second (gradient) definition. Move `color: var(--color-on-brand)` into the second block. Remove the duplicate `transform: translateY(-1px)` from `.btn-primary:hover` since `.btn:hover` already handles it.

---

### Issue 5 — Missing `.alert` global definition and variants

**Severity:** 🟠 High  
**Files:** `templates/system_health.html:33`, `templates/ml_dashboard.html:141`, `templates/energy_analytics.html:88`

`.alert` is defined in two page-specific files (`unit-selector.css` and `plants.css`) but not in `components.css`. `alert-warning`, `alert-danger`, `alert-success`, `alert-info` variants are never defined anywhere.

Used in templates:
```html
<!-- system_health.html:33 -->
<div id="alert-banner" class="alert alert-warning d-flex …">

<!-- energy_analytics.html:88 -->
<div class="row g-3 align-items-end mb-4 bg-light p-3 rounded border">

<!-- ml_dashboard.html:141 -->
<div class="alert alert-warning mt-3 mb-0 d-none" id="drift-alert">
```

**Fix:** Add global `.alert` + semantic variants to `components.css`.

---

### Issue 6 — `.form-check` and `.form-switch` toggle styles missing

**Severity:** 🟠 High  
**Files:** `templates/system_health.html:19`, `templates/settings.html` (multiple)

```html
<!-- system_health.html:19 -->
<div class="form-check form-switch mb-0 ms-2 d-none d-md-flex align-items-center">
```

Neither `form-check` nor `form-switch` are defined in the custom CSS. Toggle switches in System Health and Settings pages render as plain unstyled checkboxes.

**Fix:** Add `.form-check` and `.form-switch` to `forms.css`.

---

### Issue 7 — `.list-group-item` missing

**Severity:** 🟡 Medium  
**File:** `templates/system_health.html:111–135`

Five items in the system health detail panel use `list-group-item`:
```html
<div class="list-group-item d-flex justify-content-between align-items-center px-0 border-0 py-3">
```
This class is not defined — the layout of this panel is entirely broken.

**Fix:** Add `.list-group-item` to `components.css`.

---

### Issue 8 — `#fff` hardcoded in `units.css`

**Severity:** 🟡 Medium  
**File:** `static/css/units.css:200`

```css
/* units.css:200 */
color: #fff;
```

This hardcoded value breaks in dark mode — the element uses pure white text regardless of theme. Should use `var(--color-on-brand)`.

**Fix:** One-line replacement.

---

### Issue 9 — `window.socketManager` assigned in constructor (partially-initialized)

**Severity:** 🟡 Medium  
**File:** `static/js/socket.js:101` and `socket.js:471`

```javascript
// socket.js:101 — inside constructor, before setupConnectionHandlers()
if (typeof window !== 'undefined') {
  window.socketManager = this;  // ← partially initialized at this point
}

this.setupConnectionHandlers();   // ← handlers not yet registered
this.setupDataHandlers();

// socket.js:471 — module bottom (fully initialized)
window.socketManager = socketManager;  // ← redundant, same reference
```

The constructor assignment at line 101 is redundant (same object reference as line 471) and exposes the manager before connection handlers are wired. If any IO event fires during construction, callbacks accessing `window.socketManager` methods will find them undefined.

**Fix:** Remove line 101 assignment. Keep only the module-level assignment at line 471.

---

### Issue 10 — `help_banner` pattern copy-pasted 7× across templates

**Severity:** 🟡 Medium  
**Files:** `dashboard.html`, `devices.html`, `settings.html`, `sensor_analytics.html`, `units.html`, `energy_analytics.html`, `system_health.html`

A "contextual help panel" block (info box with icon, message, and optional close button) is pasted verbatim in each page with minor text variations. This is the classic macro candidate.

**Fix:** Add `help_banner` macro to `macros.html`:

```jinja2
{# Contextual help/info banner #}
{% macro help_banner(message, id=none, variant='info', dismissible=True, icon='circle-info') %}
<div class="help-banner help-banner--{{ variant }}{% if id %} {{ id }}-banner{% endif %}"
     {% if id %}id="{{ id }}-help-banner"{% endif %}>
  <i class="fas fa-{{ icon }}"></i>
  <span>{{ message }}</span>
  {% if dismissible %}
  <button class="help-banner__close" aria-label="Dismiss"
          {% if id %}onclick="this.closest('.help-banner').style.display='none'"{% endif %}>
    <i class="fas fa-times"></i>
  </button>
  {% endif %}
</div>
{% endmacro %}
```

---

### Issue 11 — `content_card` macro hardcodes `<h3>` heading level

**Severity:** 🟡 Medium  
**File:** `templates/macros.html:191`

```jinja2
{% macro content_card(title=none, icon=none, subtitle=none, class='', id=none, header_extra=none, variant=none, actions=none) %}
…
<h3 class="surface-title">…</h3>  {# hardcoded — no heading_level param #}
```

Cards nested inside other sections incorrectly produce `<h3>` elements even when they should be `<h4>` or `<h5>` in the document hierarchy. This is an accessibility issue (broken heading outline).

**Fix:** Add `heading_level=3` parameter and use `<h{{ heading_level }}>`.

---

### Issue 12 — Incomplete spacing utility set in `base.css`

**Severity:** 🟡 Medium  
**File:** `static/css/base.css:96–103`

Current utilities:
```css
.mb-0, .mt-0, .mb-2, .mb-3, .mb-4, .mt-2, .mt-3
```

Missing (used in templates):
- `mt-4`, `mt-5` — used in `settings.html`, `devices.html`, `my_plant_detail.html`
- `mb-5`, `mb-6` — used in `my_plant_detail.html`
- `ms-2`, `ms-4` — margin-start (used in `system_health.html`, `settings.html`)
- `pt-3`, `pb-3` — padding top/bottom (used in `settings.html`, `ml_dashboard.html`)
- `px-0` — zero horizontal padding (used in `system_health.html`)
- `p-3` — padding shorthand (used in `energy_analytics.html`, `system_health.html`)

---

### Issue 13 — Redundant radius tokens

**Severity:** 🟢 Low  
**File:** `static/css/tokens.css:10`

`tokens.css` defines `--radius: 12px` (bare alias). `theme.css` defines `--radius-2: 8px`, `--radius-3: 12px`. These coexist with the canonical `--radius-sm`, `--radius-md`, `--radius-lg` system. Consumers have no clear guidance on which to use.

**Fix:** Deprecate `--radius`, `--radius-2`, `--radius-3` with comments pointing to `--radius-sm/md/lg`.

---

### Issue 14 — `components.css` is monolithic at 4,437 lines

**Severity:** 🟢 Low (structural debt)  
**File:** `static/css/components.css`

The file already has a `components/` subfolder with 11 specialized files (`actuators.css`, `alerts.css`, `energy.css`, etc.). However, the main `components.css` has never been split. This makes it difficult to locate, maintain, or incrementally load component styles.

---

## Remediation Plan

### Phase 1 — Critical fixes (< 2 hours total, zero risk)

All single-file edits. No template changes.

| # | Fix | File | Effort |
|---|-----|------|--------|
| 1.1 | Add Bootstrap compat aliases to `base.css` | `base.css` | 30 min |
| 1.2 | Remove `--section-gap: 15px` from `theme.css:65` | `theme.css` | 2 min |
| 1.3 | Add `position: relative; overflow: hidden` to `.btn` | `components.css:3` | 2 min |
| 1.4 | Remove duplicate `.btn-primary` (lines 24–41) | `components.css` | 5 min |
| 1.5 | Fix `#fff` → `var(--color-on-brand)` in `units.css:200` | `units.css` | 1 min |
| 1.6 | Remove constructor `window.socketManager` in `socket.js:101` | `socket.js` | 2 min |

---

### Phase 2 — Complete missing utilities (2–4 hours)

| # | Fix | File | Effort |
|---|-----|------|--------|
| 2.1 | Add `.alert`, `.alert-warning/danger/success/info` | `components.css` | 30 min |
| 2.2 | Add `.form-check`, `.form-switch` toggle styles | `forms.css` | 45 min |
| 2.3 | Add `.list-group-item` | `components.css` | 15 min |
| 2.4 | Complete spacing utilities (`mt-4/5`, `mb-5/6`, `ms-2/4`, `pt-3`, `px-0`, `p-3`) | `base.css` | 15 min |
| 2.5 | Add `bg-light`, `rounded`, `border`, `border-top`, `border-0` utilities | `base.css` | 15 min |

---

### Phase 3 — Macro improvements (2–3 hours)

| # | Fix | File | Effort |
|---|-----|------|--------|
| 3.1 | Add `help_banner` macro to `macros.html` | `macros.html` | 20 min |
| 3.2 | Replace 7× inline `help_banner` blocks with macro calls | 7 templates | 30 min |
| 3.3 | Add `heading_level=3` param to `content_card` | `macros.html` | 10 min |
| 3.4 | Audit and update heading levels in all `content_card` usages | All templates | 45 min |

---

### Phase 4 — CSS architecture cleanup (4–8 hours)

| # | Fix | File | Effort |
|---|-----|------|--------|
| 4.1 | Deprecate `--radius`, `--radius-2`, `--radius-3` in `tokens.css` | `tokens.css` | 10 min |
| 4.2 | Migrate all `--radius-2/3` usages to `--radius-sm/md/lg` | `theme.css`, `components.css` | 1 hour |
| 4.3 | Split `components.css` into logical sections (see below) | `components.css` | 4–6 hours |

**Proposed `components.css` split:**

```
static/css/components/
  buttons.css      (lines 1–100, ~300 lines)
  kpi-cards.css    (already exists — consolidate)
  cards.css        (~200 lines)
  badges.css       (~150 lines)
  tabs.css         (~200 lines)
  tables.css       (already exists — consolidate)
  modals.css       (~300 lines)
  forms-advanced.css (~200 lines, modal forms)
  navigation-components.css (~300 lines)
  data-grids.css   (~400 lines)
  charts.css       (~300 lines)
  alerts.css       (already exists — consolidate)
```

The existing `components/` subfolder already houses `actuators.css`, `alerts.css`, `anomaly-panel.css`, etc. — this phase finishes the split.

---

### Phase 5 — JS architecture (4–8 hours)

| # | Fix | File | Effort |
|---|-----|------|--------|
| 5.1 | Add `window.SYSGrow = window.SYSGrow || {}` namespace guard | `base.js` | 10 min |
| 5.2 | Migrate hardcoded chart hex colors to `getComputedStyle` | `dashboard/main.js` | 1 hour |
| 5.3 | Document `api.js` domain namespaces (4,851 lines, no top-level comment) | `api.js` | 2 hours |
| 5.4 | Introduce consistent error-handling pattern across page `main.js` files | All `main.js` | 2–4 hours |

---

## Bootstrap Compatibility Shim (Phase 1.1 spec)

These additions to `base.css` will resolve the majority of template layout breakage in one change:

```css
/* =====================================================================
   Bootstrap Compatibility Aliases
   These map Bootstrap utility class names to our design-token values.
   Do NOT add Bootstrap as a dependency — maintain these shims instead.
   ===================================================================== */

/* Display */
.d-none   { display: none !important; }
.d-block  { display: block; }
.d-flex   { display: flex; }
.d-grid   { display: grid; }
.d-inline { display: inline; }
.d-inline-flex   { display: inline-flex; }
.d-inline-block  { display: inline-block; }

/* Responsive display (sm = 576px, md = 768px) */
@media (min-width: 576px) {
  .d-sm-none   { display: none !important; }
  .d-sm-block  { display: block; }
  .d-sm-flex   { display: flex; }
  .d-sm-inline { display: inline; }
  .d-sm-inline-flex { display: inline-flex; }
}
@media (min-width: 768px) {
  .d-md-none   { display: none !important; }
  .d-md-block  { display: block; }
  .d-md-flex   { display: flex; }
  .d-md-inline { display: inline; }
  .d-md-inline-flex { display: inline-flex; }
}

/* Flex utilities */
.flex-column  { flex-direction: column; }
.flex-row     { flex-direction: row; }
.flex-nowrap  { flex-wrap: nowrap; }

/* Alignment */
.align-items-center  { align-items: center; }
.align-items-start   { align-items: flex-start; }
.align-items-end     { align-items: flex-end; }
.align-items-stretch { align-items: stretch; }
.justify-content-between { justify-content: space-between; }
.justify-content-center  { justify-content: center; }
.justify-content-end     { justify-content: flex-end; }
.justify-content-start   { justify-content: flex-start; }
.justify-content-around  { justify-content: space-around; }
.justify-content-evenly  { justify-content: space-evenly; }

/* Spacing — Bootstrap scale mapped to design tokens */
.mt-4  { margin-top: var(--space-4); }
.mt-5  { margin-top: var(--space-5); }
.mb-5  { margin-bottom: var(--space-5); }
.mb-6  { margin-bottom: var(--space-6); }
.ms-1  { margin-left: var(--space-1); }
.ms-2  { margin-left: var(--space-2); }
.ms-3  { margin-left: var(--space-3); }
.ms-4  { margin-left: var(--space-4); }
.me-1  { margin-right: var(--space-1); }
.me-2  { margin-right: var(--space-2); }
.me-3  { margin-right: var(--space-3); }
.pt-1  { padding-top: var(--space-1); }
.pt-2  { padding-top: var(--space-2); }
.pt-3  { padding-top: var(--space-3); }
.pt-4  { padding-top: var(--space-4); }
.pb-3  { padding-bottom: var(--space-3); }
.pb-4  { padding-bottom: var(--space-4); }
.ps-0  { padding-left: 0; }
.pe-0  { padding-right: 0; }
.px-0  { padding-left: 0; padding-right: 0; }
.py-3  { padding-top: var(--space-3); padding-bottom: var(--space-3); }
.p-3   { padding: var(--space-3); }
.p-4   { padding: var(--space-4); }

/* Border utilities */
.border       { border: 1px solid var(--border); }
.border-top   { border-top: 1px solid var(--border); }
.border-bottom { border-bottom: 1px solid var(--border); }
.border-0     { border: none !important; }
.rounded      { border-radius: var(--radius-md); }
.rounded-sm   { border-radius: var(--radius-sm); }
.rounded-lg   { border-radius: var(--radius-lg); }

/* Background utilities */
.bg-light { background-color: var(--color-surface-soft); }
.bg-white { background-color: var(--bg-1); }

/* Sizing */
.w-100 { width: 100%; }
.h-100 { height: 100%; }

/* Grid gutter (Bootstrap g-* replicated) */
.g-1 { gap: var(--space-1); }
.g-2 { gap: var(--space-2); }
.g-3 { gap: var(--space-3); }
.g-4 { gap: var(--space-4); }

/* Overflow */
.overflow-hidden { overflow: hidden; }
.overflow-auto   { overflow: auto; }
```

---

## Accessibility Issues

| Issue | Location | WCAG Impact |
|-------|----------|-------------|
| `content_card` always emits `<h3>` regardless of nesting level | `macros.html:191` | 1.3.1 Info and Relationships |
| No skip-navigation link in `base.html` | `base.html` | 2.4.1 Bypass Blocks |
| `aria-label` missing from icon-only buttons in `macros.html:ui_button` | `macros.html:150` | 4.1.2 Name, Role, Value |
| `<h3>/<h4>` used for sidebar section titles inconsistently | `base.html` | 1.3.1 |
| Footer year hardcoded to 2025 | `base.html` | (non-WCAG, UX) |

---

## Performance Notes

- `api.js` is 4,851 lines served as a single synchronous script — consider chunking by page module if load time becomes measurable
- `DashboardUIManager` is ~4,200 lines in a single file — split into sub-managers when next touched
- Chart colors are hardcoded hex strings in JS — extracting to CSS custom properties allows theme-aware charts without JS changes
- All CSS is loaded globally via `base.html` regardless of which page is active — page-specific files add ~50–80KB total; acceptable for now but worth monitoring

---

## Testing Checklist

For each Phase 1 fix, verify:

- [ ] **Issue 1 (d-none shim)**: Alert banner on System Health page starts hidden. Drift alert on ML Dashboard starts hidden. Mobile-only text labels hidden on small screens.
- [ ] **Issue 2 (section-gap)**: Section spacing increases from 15px to ~24px (1.5rem). No layout collapse.
- [ ] **Issue 3 (btn position)**: Button shimmer hover effect visible, contained within button bounds.
- [ ] **Issue 4 (btn-primary dedupe)**: Primary buttons still render with gradient. No visual regression.
- [ ] **Issue 5 (units.css #fff)**: Units page in dark mode — text readable on colored backgrounds.
- [ ] **Issue 6 (socketManager)**: Socket connects correctly. Real-time data flows to dashboard. No console errors.

---

## Appendix — File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `static/css/tokens.css` | 31 | Layout/spacing/structural tokens |
| `static/css/theme.css` | 285 | Color, typography, dark mode, legacy aliases |
| `static/css/base.css` | 360 | Reset, global layout, utility classes |
| `static/css/layout.css` | — | Page layout, sidebar, header, footer |
| `static/css/components.css` | 4,437 | Shared component styles (monolithic) |
| `static/css/forms.css` | — | Form field styles |
| `static/css/components/` | 11 files | Feature-specific component overrides |
| `templates/macros.html` | 290 | 10 Jinja2 macros |
| `templates/base.html` | 491 | Master template, all 14 pages extend this |
| `static/js/socket.js` | 485 | Socket.IO multi-namespace manager |
| `static/js/api.js` | 4,851 | Centralized API client |
| `static/js/base.js` | — | Global init, theme toggle, notification setup |
| `static/js/dashboard/main.js` | — | Dashboard page controller |


Frontend Deep-Dive Audit & Refactoring Plan
Executive Summary
The frontend is architecturally sound in its broad strokes (flat template inheritance, centralized API client, per-page JS modules, design token system). The main problems are: Bootstrap class leakage with no Bootstrap loaded, a duplicate/conflicting CSS variable system, a monolithic components.css, and repeated template patterns that aren't macros. The JS is globally-scoped but well-structured within that constraint.

1. Template Architecture
✅ What's Working
Single-level inheritance: all 14 app pages extend only base.html — clean and predictable
macros.html has 10 well-documented macros: form_field, select_field, checkbox_field, ui_button, kpi_card, content_card, sensor_tile, section_header, page_header, help_link/help_tooltip
page_header and content_card are consistently used across most templates
data-selected-unit-id on .page-shell is the authoritative unit source — good
🔴 Critical: help-banner Not a Macro — Copied 7× Verbatim
Every page pastes this identical block:
<div class="help-banner">
  <i class="fas fa-lightbulb"></i>
  <div class="help-banner-content">
    <p class="help-banner-title">...</p>
    <p class="help-banner-text">...</p>
  </div>
  {{ ui.help_link(...) }}
</div>
This violates DRY and makes maintenance a nightmare. A single `help_banner` macro with parameters for message, variant, and optional dismiss button would solve this.

Appears in: dashboard.html, devices.html, settings.html, sensor_analytics.html, units.html, energy_analytics.html, system_health.html. Add to macros.html:
{% macro help_banner(title, text, link_category=none, link_article=none, link_text='Learn more', icon='fa-lightbulb') %}
<div class="help-banner">
  <i class="fas {{ icon }}" aria-hidden="true"></i>
  <div class="help-banner-content">
    <p class="help-banner-title">{{ title }}</p>
    <p class="help-banner-text">{{ text }}</p>
  </div>
  {% if link_category and link_article %}
    {{ help_link(link_category, link_article, link_text) }}
  {% endif %}
</div>
{% endmacro %}
 Critical: Bootstrap Classes Everywhere — Bootstrap Is Not Loaded
base.html loads: socket.io, Font Awesome, and the custom CSS stack. Bootstrap is not loaded. Yet templates use Bootstrap utility classes throughout:

Bootstrap class	Appears in	Custom equivalent
d-flex	40+ locations	.flex
d-none	15+ locations	.hidden
align-items-center	30+ locations	.align-center
justify-content-between	10+	.justify-between
mb-5, mb-6, mt-5, ms-2	15+	.mb-4, .mt-3, .ml-auto
form-check, form-switch	system_health.html	not defined
alert alert-warning	system_health.html, ml_dashboard.html	not defined
list-group-item	system_health.html	not defined
border-top, border-0, px-0, py-3	devices.html, settings.html	not defined
These are silent no-ops. The layouts they intend to create are broken on those elements. Fix approach — two options:

Option A (preferred): Standardize on the custom utility names. Audit-replace all d-flex → .flex, d-none → .hidden, etc. globally.

Option B: Add Bootstrap-compatible shim utilities to base.css:
/* Bootstrap compatibility shims */
.d-flex { display: flex; }
.d-none { display: none !important; }
.d-md-flex { display: flex; } /* or media-query scoped */
.align-items-center { align-items: center; }
.justify-content-between { justify-content: space-between; }
.justify-content-end { justify-content: flex-end; }
.justify-content-around { justify-content: space-around; }
.flex-wrap { flex-wrap: wrap; }
.mb-5 { margin-bottom: var(--space-6); }
.mb-6 { margin-bottom: var(--space-7); }
.mt-4 { margin-top: var(--space-4); }
.mt-5 { margin-top: var(--space-6); }
.ms-2 { margin-left: var(--space-2); }
.pt-3 { padding-top: var(--space-3); }
.px-0 { padding-left: 0; padding-right: 0; }
.border-top { border-top: 1px solid var(--border); }
.border-0 { border: none; }
Option B is lower-risk since it doesn't require touching every template. Add the missing form-check, alert, list-group-item counterparts or migrate those templates to use the existing custom component classes.

🟠 Medium: page_header Actions Are Raw String Concatenation
In devices.html, settings.html, sensor_analytics.html:

{{ ui.page_header(
  title="...",
  actions='<a href="' ~ url_for('ui.device_health') ~ '" class="btn ...">...'
) }}
This is fragile and hard to maintain. The page_header macro already supports actions | safe. The issue is that url_for can't be called inside a string argument. Fix: Use a call block instead:
{% call(slot) ui.page_header(title="Device Management", icon="fas fa-cogs",
    subtitle="Add, remove, and monitor sensors and actuators.") %}
  {% if slot == 'actions' %}
    <a href="{{ url_for('ui.device_health') }}" class="btn btn-secondary btn-sm">
      <i class="fas fa-heartbeat"></i>
      <span class="d-none d-sm-inline">Device Health</span>
    </a>
  {% endif %}
{% endcall %}

This requires a small update to the page_header macro to use caller().

🟠 Medium: content_card Heading Level Is Always h3
The content_card macro hardcodes <h3> regardless of where it appears in the document. On the dashboard, section headings inside the page's <h1> should be <h2>, not <h3>. Add a heading_level parameter defaulting to 3.

🟡 Minor: section_header vs page_header Naming Confusion
section_header renders a <h2> with dashboard-header card-header classes — it's used inside card bodies. page_header renders an <h1>. The distinction is clear but section_header's outer div.dashboard-header.card-header double-class is semantically odd outside the dashboard context.

2. CSS Architecture
🔴 Critical: --section-gap Defined Twice With Different Values
tokens.css: --section-gap: var(--space-6); → 1.5rem
theme.css line 64: --section-gap: 15px;
theme.css loads after tokens.css so it wins — --section-gap is 15px. The tokens.css definition is silently overridden. Remove the one in theme.css and keep tokens.css as the single source (or pick one value and delete the other).

🔴 Critical: Legacy Alias Variables Not Updated in Dark Mode
theme.css defines legacy bridges like --primary-text-color, --secondary-text-color, --bg-primary, --bg-secondary, --border-color in the :root block. The dark mode block (@media (prefers-color-scheme: dark)) does not re-declare them. So settings.css (which uses --primary-text-color in 12 places) and notifications-page.css (uses --border-color in 8 places) get light-mode values even in dark mode.

Fix: Either update the dark-mode block to redefine these aliases, or — better — migrate those files to use the canonical tokens (--color-text, --color-text-muted, --border).

🔴 Critical: Dark Mode JS Toggle Has No CSS Target
base.js sets document.documentElement.setAttribute('data-theme', 'dark') but all dark-mode CSS is under @media (prefers-color-scheme: dark). The [data-theme="dark"] attribute selector is never used in any CSS file. System dark mode works; the JS toggle silently does nothing to the stylesheet.

Fix in theme.css:

@media (prefers-color-scheme: dark),
[data-theme="dark"] {
  :root {
    --bg-0: #0f172a;
    /* ... all dark tokens ... */
  }
}
Or — more precisely:
@media (prefers-color-scheme: dark) { :root { /* tokens */ } }
[data-theme="dark"] { /* same tokens */ }
Critical: btn-primary and btn::before Defined Twice in components.css
Lines ~25–40 define btn-primary with a flat background: var(--brand-600). Lines ~230–260 redefine btn-primary with background: var(--gradient-primary) and btn::before with a gradient shimmer overlay. The first definition is silently overridden — the ::before ripple only works because of the second block. Remove the first, keep the second. Also clean up the duplicate btn:hover transform: translateY(-1px) that appears in both .btn-primary:hover and a separate .btn:hover block.

🟠 Medium: components.css Is 4,437 Lines — Needs Splitting
Current components.css contains: buttons, grid layouts, alert items, KPI/stat/prediction cards, sensor cards, badge pills, tab components, progress bars, tooltip stubs, scroll indicators, help banners, chart containers, carousel controls, notification items, modal base styles, and more.

Recommended split:

New file	Contents
components/buttons.css	All .btn-* variants
components/cards.css	.card, .kpi-card, .stat-card, .ai-prediction-card, .sensor-card
components/alerts.css	Already split out — keep
components/badges.css	.nav-badge, .trend-pill, .status-badge, chip/pill variants
components/tabs.css	.settings-tabs, .tab-button
components/modals.css	Modal base styles
components/grids.css	.dashboard-kpi-grid, .dashboard-sensors-row, auto-fit grid patterns
🟠 Medium: Hardcoded #fff in units.css
units.css:200: color: #fff; — should be var(--color-on-brand) for dark mode correctness.

🟡 Minor: Radius Token Split
--radius (12px) is in tokens.css. --radius-sm (6px), --radius-md (8px), --radius-lg (12px) are in theme.css. --radius-2 (8px) and --radius-3 (12px) are also in theme.css (legacy). Consolidate: keep --radius-sm/md/lg in tokens.css, remove --radius-2, --radius-3, --radius.

🟡 Minor: Mobile-First Inconsistency
navigation.css and layout.css use max-width breakpoints (desktop-first). The rest of the CSS is mostly desktop-first as well. This is consistent internally but means most overrides go @media (max-width: 768px) — fine, but document it in a comment in tokens.css alongside the breakpoint reference already there in theme.css.

3. JavaScript Architecture
🟠 Medium: All Globals on window.* — No Isolation
Every module assigns itself to window: window.API, window.SocketManager, window.DashboardDataService, window.DashboardUIManager, window.BaseManager, etc. This is manageable with the current load-order contract but fragile — any name collision silently breaks things.

The architecture is already clean enough (IIFEs, class-per-file, BaseManager base class) that migrating to ES modules would be straightforward. Since there's no bundler, type="module" script tags in base.html would be the incremental path.

Interim improvement (no bundler needed): Add a single namespace object:
// In base.js, before anything else:
window.SYSGrow = window.SYSGrow || {};
Then each module registers as window.SYSGrow.API, window.SYSGrow.DashboardDataService, etc. Reduces global namespace pollution from ~25 names to 1.

🟠 Medium: socket.js Double-Assigns window.socketManager
// Line 101 (in constructor):
window.socketManager = this;
// Line 471 (at module bottom):
window.socketManager = socketManager;
The constructor assignment happens before all namespaces are connected, giving pages that initialize immediately a partially-set-up manager. The bottom assignment is the correct one. Remove the constructor assignment.

🟠 Medium: Chart Fallback Uses Hardcoded Hex Colors
In main.js createSimpleEnvironmentalChart(), the Chart.js datasets use #ff6b6b, #4dabf7, #8b5a2b. These don't respect dark mode and diverge from the design system. Use CSS custom property values:

const styles = getComputedStyle(document.documentElement);
const tempColor = styles.getPropertyValue('--accent-harvest').trim() || '#ef4444';
const humColor  = styles.getPropertyValue('--accent-water').trim()   || '#0ea5e9';
const soilColor = styles.getPropertyValue('--accent-soil').trim()    || '#92400e';
🟡 Minor: api.js Is 4,851 Lines
The API client is well-structured with domain namespaces (API.Dashboard, API.Plant, API.Sensor, etc.) but the single file is very large. Given the current no-bundler architecture, splitting into api/dashboard.js, api/sensors.js, etc. loaded in base.html is low-risk and improves navigability. The apiRequest base function would move to api/core.js.

🟡 Minor: DashboardUIManager Is 4,214 Lines
This is the largest single JS file after api.js. It mixes: DOM element indexing, socket event subscriptions, sensor card rendering, actuator panel management, plant card rendering, alert timeline rendering, connectivity status, VPD gauge management, and periodic refresh scheduling. Extract:

SensorCardRenderer (from _flushSensorUpdates, _renderSensorCard, etc.)
ActuatorPanel (already partially a separate component in components/actuator-panel.js)
PlantGrid (plant cards)
✅ What's Working Well in JS
DashboardDataService: TTL cache + in-flight deduplication pattern is excellent
BaseManager base class with _safeInit, _startPeriodicRefresh, destroy() lifecycle is solid
SocketManager multi-namespace architecture with local pub/sub is clean
FormValidator, DateUtils, HtmlUtils in utils/ are properly isolated
apiRequest in api.js properly normalizes data.data unwrapping, handles non-JSON bodies, and attaches CSRF token
4. Accessibility Gaps
Issue	Location	Fix
<h3> always in content_card macro	macros.html	Add heading_level param
<h3> vs <h4> nav section titles in sidebar	base.html lines 248–260	"Dashboard" section uses <h3>, all others use <h4> — standardize to <h3>
user-role always hardcoded "Administrator"	base.html line 188	Pass role from session
<section> elements without aria-label	dashboard.html chart section	Add aria-label="Environmental chart"
Missing aria-label on filter <select> elements	devices.html, sensor_analytics.html	Already present on some, missing on others
Footer copyright says "2025"	base.html line 417	Update to 2026 or use dynamic year
5. Prioritized Remediation Roadmap
Phase 1 — Quick Wins (< 1 day each)
Add Bootstrap shim utilities to base.css — fixes all the d-flex/d-none silent failures. Lowest risk, highest visual impact.
Fix dark mode [data-theme="dark"] selector in theme.css — the JS toggle currently does nothing.
Fix --section-gap conflict — remove the 15px override from theme.css.
Fix legacy aliases in dark mode — add them to the dark block in theme.css.
Remove duplicate btn-primary / btn::before from components.css.
Fix hardcoded #fff in units.css.
Phase 2 — Macro Improvements (1–2 days)
Add help_banner macro — eliminates 7 duplicate blocks.
Add heading_level param to content_card — fixes heading hierarchy.
Add call-block support to page_header — removes all the fragile string-concatenation action buttons.
Fix h3/h4 inconsistency in sidebar.
Phase 3 — CSS Modularization (2–3 days)
Split components.css into the 6 sub-files above.
Consolidate radius tokens — remove --radius, --radius-2, --radius-3.
Migrate settings.css and notifications-page.css off legacy alias variables.
Phase 4 — JS Cleanup (3–5 days)
Add window.SYSGrow namespace — one-line guard in base.js, then migrate registrations.
Fix double window.socketManager assignment in socket.js.
Fix chart hardcoded colors to read from CSS custom properties.
Split api.js by domain namespace.
Phase 5 — Architecture (1+ sprint)
Migrate to ES modules with type="module" — eliminates all window.* globals.
Extract SensorCardRenderer and PlantGrid from DashboardUIManager.
6. Component Inventory — Current State
Component	Location	State	Issues
form_field	macros.html	✅ Solid	[kwargs
select_field	macros.html	✅ Solid	Dual param aliases (id/field_id) needed but messy
checkbox_field	macros.html	✅ Good	No indeterminate state
ui_button	macros.html	✅ Good	No loading state variant
kpi_card	macros.html	✅ Good	VPD canvas special-cased inside generic macro — extract
content_card	macros.html	🟡 OK	h3 hardcoded; caller() required but not obvious
sensor_tile	macros.html	✅ Good	Values always -- at server render — intentional
section_header	macros.html	🟡 OK	Double class .dashboard-header.card-header
page_header	macros.html	🟡 OK	Actions require string concat workaround
help_link / help_tooltip	macros.html	✅ Good	—
help_banner	Templates only	🔴 Not a macro	7× duplicate
Notification dropdown	base.html	✅ Good	ARIA properly implemented
Global unit switcher	base.html	✅ Good	Properly clears stale readings on switch
Device tab panel	devices.html	✅ Good	Full ARIA role/controls/selected
Flash messages	base.html	✅ Good	aria-live="polite" present
