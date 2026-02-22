# SYSGrow — Frontend Design Language

> Living reference for all UI/UX decisions. Update this file when adding new
> design tokens, component patterns, or layout conventions.

---

## 1  Typography

| Role | Family | Weights | CSS Token |
|------|--------|---------|-----------|
| **Headings** | [Outfit](https://fonts.google.com/specimen/Outfit) | 500 / 600 / 700 | `var(--font-heading)` |
| **Body** | [Source Sans 3](https://fonts.google.com/specimen/Source+Sans+3) | 400 / 600 / 700 (+ 400 italic) | `var(--font-sans)` |
| **Code / Data** | System mono stack | — | `var(--font-mono)` |

Fonts are loaded from Google Fonts via `<link>` in `base.html`.
Fallback chain: `system-ui, -apple-system, "Segoe UI", sans-serif`.

### Type Scale

| Element | Size | Weight | Token / Selector |
|---------|------|--------|-----------------|
| Page title `<h1>` | 1.875 rem | 700 | — |
| Section heading `<h2>` | 1.5 rem | 700 | — |
| Card heading `<h3>` | 1.25 rem | 700 | — |
| Subheading `<h4>` | 1.125 rem | 700 | — |
| Body text | 14 px / 1.6 | 400 | `body` |
| Eyebrow label | 0.78 rem | 600 | `.eyebrow` |
| Small text | 0.85 rem | 400 | `.small` |
| Large value | 1.8 rem | 700 | `.value-lg` |

### Rules

- **Never** hard-code a font stack — always use `var(--font-sans)`,
  `var(--font-heading)`, or `var(--font-mono)`.
- Heading elements (`h1`–`h6`) automatically use Outfit via `base.css`.
- Display numerics on KPI cards, gauges, and grade badges should use
  `var(--font-heading)` for visual weight.

---

## 2  Colour System

### Brand Greens

| Token | Hex | Usage |
|-------|-----|-------|
| `--brand-950` | `#0a2a1f` | Deep forest |
| `--brand-800` | `#14532d` | Evergreen |
| `--brand-700` | `#166534` | Primary hover |
| `--brand-600` | `#4E7400` | **Primary brand colour** |
| `--brand-500` | `#22c55e` | Lime accent |
| `--brand-300` | `#e3ffaa` | Light tint |

### Supporting Accents

| Token | Hex | Meaning |
|-------|-----|---------|
| `--sky-500` | `#06b6d4` | Irrigation / telemetry |
| `--earth-600` | `#92400e` | Warm earth highlight |
| `--earth-400` | `#d97706` | — |
| `--earth-300` | `#fbbf24` | — |
| `--accent-growth` | `#10b981` | Growth indicator |
| `--accent-soil` | `#92400e` | Soil metric |
| `--accent-water` | `#0ea5e9` | Water metric |
| `--accent-sun` | `#f59e0b` | Light / UV metric |
| `--accent-harvest` | `#dc2626` | Harvest / alert |

### Semantic Colours

Each semantic set has four shades: `-600` (dark), `-500` (base),
`-300` (translucent), `-100` (background).

| Set | Base token |
|-----|-----------|
| Success | `--success-*` |
| Warning | `--warning-*` |
| Danger / Error | `--danger-*` / `--error-*` |
| Info | `--info-*` |

### Dark Mode

- Toggled via `[data-theme="dark"]` attribute on `<html>`, or auto-detected
  via `prefers-color-scheme: dark`.
- All surfaces and text colours are aliased through `--color-*` / `--bg-*`
  tokens in `theme.css`. **Never** use raw colours (`#fff`, `#1e293b`)
  directly in component CSS — always reference a token.

---

## 3  Breakpoints

Five canonical breakpoints. **Use these values** in `@media` rules — do not
invent new ones.

| Name | Width | Typical target |
|------|-------|----------------|
| **xs** | `480px` | Small phones |
| **sm** | `640px` | Large phones / small tablets |
| **md** | `768px` | Tablets (portrait) |
| **lg** | `1024px` | Laptops / tablets (landscape) |
| **xl** | `1280px` | Desktops |

> CSS custom properties cannot be used inside `@media` conditions.
> The values above are documented for human reference and may be consumed by
> JavaScript via `getComputedStyle`.

### Media Query Convention

```css
/* Mobile-first: use min-width */
@media (max-width: 768px)  { /* tablet and below */ }
@media (max-width: 480px)  { /* phone only */ }
@media (min-width: 1024px) { /* laptop and above */ }
```

---

## 4  Spacing Scale

Defined in `theme.css` as `--space-{n}`:

| Token | Value |
|-------|-------|
| `--space-1` | 0.25 rem |
| `--space-2` | 0.5 rem |
| `--space-3` | 0.75 rem |
| `--space-4` | 1 rem |
| `--space-5` | 1.25 rem |
| `--space-6` | 1.5 rem |
| `--space-7` | 2 rem |
| `--space-8` | 2.5 rem |

Gap utility classes: `.gap-1` through `.gap-6`.

---

## 5  Layout Tokens

| Token | Default | Purpose |
|-------|---------|---------|
| `--sidebar-w` | `230px` | Sidebar width |
| `--header-h` | `70px` | Header height |
| `--footer-h` | `70px` | Footer height |
| `--content-max` | `1400px` | Max content width |
| `--content-compact` | `1200px` | Narrower content max |
| `--page-gutter` | `18px` | Page horizontal padding |
| `--section-gap` | `15px` | Vertical gap between sections |

---

## 6  Radii & Shadows

| Token | Value |
|-------|-------|
| `--radius-sm` | 6 px |
| `--radius-md` | 8 px |
| `--radius-lg` | 12 px |
| `--shadow-sm` | subtle |
| `--shadow-md` | medium elevation |
| `--shadow-lg` | high elevation |

Shadows are suppressed in dark mode (`none`).

---

## 7  Motion

| Token | Duration | Usage |
|-------|----------|-------|
| `--transition-fast` | 150 ms | Hover, focus |
| `--transition-normal` | 250 ms | Panel open/close |
| `--transition-slow` | 350 ms | Page transitions |

All motion is disabled when `prefers-reduced-motion: reduce` is set.

---

## 8  Component Conventions

### Cards

```html
<div class="card">
  <h3>Title</h3>
  <p>Body text</p>
</div>
```

- Background: `var(--card-bg)` / `var(--card-bg-muted)`
- Border: `var(--card-border)`
- Radius: `var(--radius-lg)` (12 px)
- Entrance animation: `fadeInUp 0.5s` (staggered).

### Buttons

| Class | Appearance |
|-------|-----------|
| `.btn-primary` | Brand gradient |
| `.btn-secondary` | Translucent surface |
| `.btn-outline` | Transparent + border |
| `.btn-danger` | Red surface |
| `.btn-success` | Green surface |
| `.btn-info` | Blue surface |
| `.btn-sm` / `.btn-lg` | Size variants |
| `.btn-icon` | 40 × 40 px square |

### KPI / Stat Cards

Use `.kpi-card` or `.stat-card` inside `.dashboard-kpi-grid`. Cards auto-fit
from `200px` minimum width.

### Eyebrow Labels

```html
<span class="eyebrow">Metric Name</span>
<span class="value-lg">72.4</span>
```

---

## 9  Icons

[Font Awesome 6.4 Free](https://fontawesome.com/) loaded from CDN.
Prefer `<i class="fas fa-*">` for solid, `<i class="far fa-*">` for regular.

---

## 10  Accessibility Checklist

- [x] Skip-to-content link (`.skip-link`)
- [x] `prefers-reduced-motion` respected
- [x] `prefers-contrast: high` increases border widths
- [x] Focus-visible ring: `var(--focus-ring)` / `var(--focus-ring-color)`
- [x] `aria-label` / `aria-expanded` on interactive elements
- [ ] Colour contrast ≥ 4.5:1 for text (verify after palette changes)

---

## 11  File Organisation

```
static/css/
├── tokens.css            ← Layout tokens (sidebar width, content max, etc.)
├── theme.css             ← Colour + font + spacing + motion tokens
├── base.css              ← Reset, typography, utility classes, buttons
├── layout.css            ← Main-content / sidebar / footer grid
├── components.css        ← Shared UI components (cards, grids, modals)
├── navigation.css        ← Header + sidebar + mobile toggle
├── forms.css             ← Form controls
├── tables.css            ← Table styles
├── analytics.css         ← Analytics page scoping
├── dashboard.css         ← Dashboard page styles
├── settings.css          ← Settings page
├── fullscreen.css        ← Fullscreen kiosk mode
├── system-efficiency-score.css
├── ...page-specific CSS
└── components/
    └── notifications.css ← Header notification dropdown
```

### JS Architecture (per page)

```
static/js/<page>/
├── data-service.js       ← API calls + CacheService
├── ui-manager.js         ← DOM rendering + Chart.js bindings
└── main.js               ← Wiring, Socket.IO listeners, init
```

---

## 12  Changelog

| Date | Change |
|------|--------|
| 2025-07 | Initial design language document |
| 2025-07 | Font migration: Inter → Outfit + Source Sans 3 |
| 2025-07 | Font tokens (`--font-sans`, `--font-heading`, `--font-mono`) added to `theme.css` |
| 2025-07 | Breakpoints standardised to 5 canonical values |
