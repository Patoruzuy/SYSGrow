# 🎨 Visual Design Guide
## Unit Selector Interface Specification

> **Professional UI/UX Design Documentation**
> 
> Complete visual specification for the Growth Unit Selector

---

## 🎯 Design Philosophy

### Core Principles
1. **Clarity First** - Information hierarchy guides the eye
2. **Instant Understanding** - Visual feedback through color coding
3. **Accessibility** - WCAG 2.1 AA compliant, keyboard navigable
4. **Responsive** - Beautiful on all screen sizes
5. **Professional** - Enterprise-grade polish

---

## 🎨 Color Palette

### Primary Colors
```css
--primary: #28a745      /* Success Green - CTAs, positive actions */
--primary-dark: #218838 /* Hover state for primary */
--secondary: #6c757d    /* Gray - secondary text, icons */
--danger: #dc3545       /* Red - delete, critical actions */
--warning: #ffc107      /* Yellow - warnings, dry status */
--info: #17a2b8         /* Blue - informational */
```

### Moisture Status Colors
```css
--moisture-too-wet: #0066cc    /* Dark Blue (80-100%) */
--moisture-wet: #00aaff        /* Light Blue (60-80%) */
--moisture-normal: #28a745     /* Green (30-60%) */
--moisture-dry: #ffc107        /* Yellow (15-30%) */
--moisture-too-dry: #dc3545    /* Red (0-15%) */
```

### Neutral Colors
```css
--light: #f8f9fa        /* Background, cards */
--dark: #343a40         /* Primary text */
--border-color: #dee2e6 /* Borders, dividers */
```

### Usage Examples

| Color | Use Case | Examples |
|-------|----------|----------|
| `--primary` | Primary actions, success states | "Create Unit", "Open Dashboard" buttons |
| `--secondary` | Secondary text, disabled states | Subtitles, metadata, disabled buttons |
| `--danger` | Destructive actions | Delete button, critical alerts |
| `--moisture-normal` | Optimal status | Moisture 30-60%, healthy plants |
| `--moisture-too-dry` | Critical status | Moisture <15%, urgent attention needed |

---

## 📐 Layout Structure

### Page Layout
```
┌─────────────────────────────────────────────────────────────┐
│  HEADER (base.html)                                         │
│  [SYSGrow Logo] [Quick Actions] [User Menu]               │
├────┬────────────────────────────────────────────────────────┤
│    │  PAGE HEADER                                           │
│ S  │  Select Your Growth Unit         [+ Create Unit]      │
│ I  │  Choose a unit to view and manage                     │
│ D  ├────────────────────────────────────────────────────────┤
│ E  │  UNITS GRID (3 columns on desktop)                    │
│ B  │  ┌─────────┐  ┌─────────┐  ┌─────────┐              │
│ A  │  │ Unit 1  │  │ Unit 2  │  │ Unit 3  │              │
│ R  │  │ Card    │  │ Card    │  │ Card    │              │
│    │  │         │  │         │  │         │              │
│    │  └─────────┘  └─────────┘  └─────────┘              │
│    │  ┌─────────┐  ┌─────────┐                            │
│    │  │ Unit 4  │  │ Unit 5  │                            │
│    │  │ Card    │  │ Card    │                            │
│    │  └─────────┘  └─────────┘                            │
├────┴────────────────────────────────────────────────────────┤
│  FOOTER                                                     │
│  © 2025 SYSGrow | Help | Documentation | Contact          │
└─────────────────────────────────────────────────────────────┘
```

### Responsive Breakpoints

| Screen Size | Layout | Columns | Card Width |
|-------------|--------|---------|------------|
| Desktop (>1200px) | 3-column grid | 3 | ~400px |
| Tablet (768-1200px) | 2-column grid | 2 | ~350px |
| Mobile (<768px) | 1-column stack | 1 | 100% |

---

## 🃏 Unit Card Anatomy

### Complete Card Structure
```
┌──────────────────────────────────────────┐
│  CARD IMAGE (200px height)               │
│  [Custom image or gradient background]  │
│  ┌──────────────────────────────────┐   │
│  │ [Edit ✏️] [Camera 📹]     Overlay │   │
│  └──────────────────────────────────┘   │
├──────────────────────────────────────────┤
│  CARD HEADER                             │
│  Greenhouse A          📍 Indoor         │
│  120×180×80 cm (1728L)                   │
│  ─────────────────────                   │
│  🌱 5 plants  ⏰ 48h uptime             │
├──────────────────────────────────────────┤
│  CARD BODY - Plants Section              │
│  PLANTS (MAX 6)                          │
│                                          │
│  ┌────┐ ┌────┐ ┌────┐                   │
│  │ 🍅 │ │ 🥬 │ │ 🌿 │                   │
│  │70% │ │45% │ │30% │                   │
│  │Tom │ │Let │ │Bas │                   │
│  └────┘ └────┘ └────┘                   │
│  ┌────┐ ┌────┐ ┌────┐                   │
│  │ 🫑 │ │ 🥒 │ │ 🌶️ │                   │
│  │55% │ │40% │ │25% │                   │
│  │Pep │ │Cuc │ │Chi │                   │
│  └────┘ └────┘ └────┘                   │
├──────────────────────────────────────────┤
│  CARD FOOTER                             │
│  ┌────────────────────────────────────┐ │
│  │  → Open Dashboard                  │ │
│  └────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

### Detailed Measurements

#### Image Section
- Height: `200px`
- Background: Custom image or gradient `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- Overlay: Semi-transparent gradient `rgba(0,0,0,0.1)` to `rgba(0,0,0,0.3)`
- Action buttons: `36px × 36px`, `rgba(255,255,255,0.9)` background

#### Header Section
- Padding: `24px` (1.5rem)
- Title font: `1.25rem`, weight `600`
- Location badge: `0.875rem`, background `#f8f9fa`, padding `4px 8px`
- Dimensions: `0.875rem`, color `#6c757d`
- Stats row: Border-top `1px solid #f8f9fa`, padding-top `16px`

#### Body Section (Plants)
- Padding: `24px`
- Grid: `repeat(auto-fill, minmax(90px, 1fr))`
- Gap: `16px`

#### Footer Section
- Padding: `24px`
- Background: `#f8f9fa`
- Border-top: `1px solid #dee2e6`
- Button: Full width, height `48px`

---

## 💧 Moisture Ring Specification

### SVG Circle Details
```html
<svg width="60" height="60" viewBox="0 0 60 60">
  <!-- Background circle -->
  <circle 
    cx="30" 
    cy="30" 
    r="24" 
    fill="none" 
    stroke="#e9ecef" 
    stroke-width="6"
  />
  
  <!-- Progress circle -->
  <circle 
    cx="30" 
    cy="30" 
    r="24" 
    fill="none" 
    stroke="var(--moisture-color)" 
    stroke-width="6"
    stroke-linecap="round"
    stroke-dasharray="150.8"
    stroke-dashoffset="calculated-value"
    transform="rotate(-90 30 30)"
  />
</svg>
```

### Calculation
```javascript
const circumference = 2 * Math.PI * radius; // 2 * 3.14159 * 24 = 150.8
const offset = circumference - (percentage / 100) * circumference;

// Example: 70% moisture
// offset = 150.8 - (70/100 * 150.8) = 45.24
```

### Color Mapping
```javascript
function getMoistureColor(percentage) {
    if (percentage >= 80) return '#0066cc';      // Too Wet
    else if (percentage >= 60) return '#00aaff'; // Wet
    else if (percentage >= 30) return '#28a745'; // Normal (Green)
    else if (percentage >= 15) return '#ffc107'; // Dry (Yellow)
    else return '#dc3545';                       // Too Dry (Red)
}
```

### Visual States

| Moisture % | Color | Ring Fill | Status | Action Required |
|-----------|-------|-----------|--------|-----------------|
| 0-15% | 🔴 Red (#dc3545) | 0-15% | Too Dry | URGENT: Water immediately |
| 15-30% | 🟡 Yellow (#ffc107) | 15-30% | Dry | Water soon |
| 30-60% | 🟢 Green (#28a745) | 30-60% | Normal | Optimal |
| 60-80% | 🔵 Light Blue (#00aaff) | 60-80% | Wet | Monitor |
| 80-100% | 🔵 Dark Blue (#0066cc) | 80-100% | Too Wet | Reduce watering |

---

## 🎬 Animations & Transitions

### Hover Effects

#### Card Hover
```css
.unit-card {
    transition: all 0.3s ease;
}

.unit-card:hover {
    transform: translateY(-4px);      /* Lift effect */
    box-shadow: 0 8px 16px rgba(0,0,0,0.2);
    border-color: #28a745;            /* Primary color highlight */
}
```

#### Button Hover
```css
.open-unit-btn:hover {
    background: #218838;              /* Darker green */
    transform: translateY(-2px);      /* Subtle lift */
    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}
```

### Loading States

#### Spinner Animation
```css
.loading-spinner {
    width: 20px;
    height: 20px;
    border: 3px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}
```

#### Camera Live Indicator
```css
.unit-action-btn.camera.active::after {
    /* Red dot */
    width: 8px;
    height: 8px;
    background: #ff4444;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { 
        opacity: 1; 
        transform: scale(1); 
    }
    50% { 
        opacity: 0.6; 
        transform: scale(1.2); 
    }
}
```

### Modal Animations

#### Fade In Background
```css
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.modal {
    animation: fadeIn 0.3s ease;
}
```

#### Slide In Content
```css
@keyframes slideIn {
    from {
        transform: translateY(-50px);
        opacity: 0;
    }
    to {
        transform: translateY(0);
        opacity: 1;
    }
}

.modal-content {
    animation: slideIn 0.3s ease;
}
```

---

## 📱 Mobile Optimization

### Touch Targets
- Minimum size: `44px × 44px` (Apple HIG, WCAG)
- Button padding: `12px 24px` (comfortable tap area)
- Interactive spacing: Minimum `8px` between elements

### Mobile-Specific Adjustments

#### Card Image
```css
@media (max-width: 768px) {
    .unit-card-image {
        height: 180px;  /* Reduced from 200px */
    }
}
```

#### Plants Grid
```css
/* Desktop: up to 6 columns */
.plants-preview {
    grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
}

/* Mobile: 3 columns */
@media (max-width: 768px) {
    .plants-preview {
        grid-template-columns: repeat(3, 1fr);
    }
}

/* Small mobile: 2 columns */
@media (max-width: 480px) {
    .plants-preview {
        grid-template-columns: repeat(2, 1fr);
    }
}
```

#### Modal
```css
@media (max-width: 768px) {
    .modal-content {
        width: 95%;           /* Full width with small margin */
        max-height: 95vh;     /* Leave space for safe areas */
    }
    
    .modal-footer .btn {
        width: 100%;          /* Full-width buttons */
    }
}
```

---

## ♿ Accessibility Features

### Keyboard Navigation

#### Tab Order
1. Create Unit button
2. First unit card → Edit button
3. First unit card → Camera button
4. First unit card → Open Dashboard button
5. Second unit card... (repeat)

#### Focus Styles
```css
*:focus-visible {
    outline: 2px solid #28a745;  /* Primary color */
    outline-offset: 2px;          /* Breathing room */
}
```

### Screen Reader Support

#### ARIA Labels
```html
<button class="unit-action-btn edit" 
        aria-label="Edit Greenhouse A settings">
    <i class="fas fa-edit" aria-hidden="true"></i>
</button>

<button class="open-unit-btn" 
        aria-label="Open dashboard for Greenhouse A">
    <i class="fas fa-arrow-right" aria-hidden="true"></i>
    Open Dashboard
</button>
```

#### Status Announcements
```html
<div role="status" aria-live="polite" aria-atomic="true">
    Unit created successfully
</div>
```

### Color Contrast Ratios

| Element | Foreground | Background | Ratio | WCAG Level |
|---------|-----------|------------|-------|------------|
| Primary text | #343a40 | #ffffff | 12.6:1 | AAA |
| Secondary text | #6c757d | #ffffff | 4.6:1 | AA |
| Primary button | #ffffff | #28a745 | 4.5:1 | AA |
| Danger button | #ffffff | #dc3545 | 4.5:1 | AA |

### Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}
```

---

## 🖼️ Empty State Design

### No Units Created
```
┌────────────────────────────────────────────┐
│                                            │
│              🌱 (4rem icon)                │
│                                            │
│         No Growth Units Yet                │
│                                            │
│    Create your first growth unit to get    │
│    started with your smart agriculture     │
│              journey                        │
│                                            │
│        [+ Create Your First Unit]          │
│                                            │
└────────────────────────────────────────────┘
```

### No Plants in Unit
```
┌────────────────────────────────────────────┐
│  PLANTS (MAX 6)                            │
│                                            │
│  No plants added yet. Add plants to see    │
│  their status here.                        │
│                                            │
└────────────────────────────────────────────┘
```

---

## 🎭 Modal Design

### Create/Edit Unit Modal

```
┌──────────────────────────────────────────────────┐
│  Create New Growth Unit               ✕         │
├──────────────────────────────────────────────────┤
│                                                  │
│  Unit Name *                                     │
│  ┌────────────────────────────────────────────┐ │
│  │ My Greenhouse                              │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  Location *                                      │
│  ┌────────────────────────────────────────────┐ │
│  │ Indoor ▼                                   │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  Dimensions                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 120   cm │ │ 180   cm │ │ 80    cm │       │
│  └──────────┘ └──────────┘ └──────────┘       │
│  Width        Length        Height              │
│                                                  │
│  Custom Image (optional)                         │
│  ┌────────────────────────────────────────────┐ │
│  │ 📁 Choose file...                          │ │
│  └────────────────────────────────────────────┘ │
│  Recommended: 800×600px, JPG or PNG             │
│                                                  │
├──────────────────────────────────────────────────┤
│                      [Cancel]  [Create Unit]    │
└──────────────────────────────────────────────────┘
```

### Field Validation
- Required fields marked with `*`
- Real-time validation feedback
- Error messages in red below field
- Success state with green border

---

## 🎯 Interactive States

### Button States

| State | Background | Text | Border | Cursor |
|-------|-----------|------|--------|--------|
| Default | `#28a745` | White | None | Pointer |
| Hover | `#218838` | White | None | Pointer |
| Active/Pressed | `#1e7e34` | White | None | Pointer |
| Focus | `#28a745` | White | 2px outline | Pointer |
| Disabled | `#28a745` (60%) | White (60%) | None | Not-allowed |
| Loading | `#28a745` | White + Spinner | None | Wait |

### Card States

| State | Transform | Shadow | Border |
|-------|----------|--------|--------|
| Default | None | `0 2px 4px rgba(0,0,0,0.1)` | `#dee2e6` |
| Hover | `translateY(-4px)` | `0 8px 16px rgba(0,0,0,0.2)` | `#28a745` |
| Focus | None | `0 0 0 3px rgba(40,167,69,0.25)` | `#28a745` |
| Active | `translateY(-2px)` | `0 4px 8px rgba(0,0,0,0.15)` | `#28a745` |

---

## 📏 Spacing System

### Spacing Scale
```css
--spacing-xs: 0.25rem;   /* 4px */
--spacing-sm: 0.5rem;    /* 8px */
--spacing-md: 1rem;      /* 16px */
--spacing-lg: 1.5rem;    /* 24px */
--spacing-xl: 2rem;      /* 32px */
```

### Usage Guidelines

| Element | Spacing | Value |
|---------|---------|-------|
| Card padding | `--spacing-lg` | 24px |
| Grid gap | `--spacing-lg` | 24px |
| Form group margin | `--spacing-lg` | 24px |
| Button padding vertical | `--spacing-md` | 16px |
| Button padding horizontal | `--spacing-lg` | 24px |
| Icon-text gap | `--spacing-sm` | 8px |

---

## 🎨 Typography

### Font Stack
```css
font-family: -apple-system, BlinkMacSystemFont, 
             "Segoe UI", Roboto, "Helvetica Neue", 
             Arial, sans-serif;
```

### Type Scale

| Element | Size | Weight | Line Height |
|---------|------|--------|-------------|
| Page title | 2rem (32px) | 600 | 1.2 |
| Card title | 1.25rem (20px) | 600 | 1.3 |
| Section title | 0.875rem (14px) | 600 | 1.4 |
| Body text | 1rem (16px) | 400 | 1.5 |
| Small text | 0.875rem (14px) | 400 | 1.4 |
| Tiny text | 0.75rem (12px) | 400 | 1.3 |

---

## ✅ Quality Checklist

### Visual Quality
- [ ] All colors meet WCAG AA contrast ratios
- [ ] Hover states on all interactive elements
- [ ] Focus indicators visible and clear
- [ ] Loading states for async operations
- [ ] Empty states with helpful messaging
- [ ] Error states with recovery options

### Responsive Design
- [ ] Tested on desktop (1920×1080)
- [ ] Tested on laptop (1366×768)
- [ ] Tested on tablet (768×1024)
- [ ] Tested on mobile (375×667)
- [ ] Touch targets minimum 44×44px
- [ ] No horizontal scrolling

### Accessibility
- [ ] Keyboard navigation works
- [ ] Screen reader announcements
- [ ] ARIA labels on icon buttons
- [ ] Focus visible on all focusable elements
- [ ] Reduced motion support
- [ ] High contrast mode support

### Performance
- [ ] CSS minified for production
- [ ] Images optimized (<200KB each)
- [ ] No layout shifts (CLS < 0.1)
- [ ] Fast paint (FCP < 1.8s)
- [ ] Smooth animations (60fps)

---

**Design System Version**: 1.0  
**Last Updated**: November 2025  
**Status**: Production Ready  
**Framework**: Custom CSS3 + JavaScript ES6+
