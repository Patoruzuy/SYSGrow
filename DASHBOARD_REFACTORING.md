# System Health Dashboard - Refactored Architecture

## Overview

The System Health Dashboard has been refactored from a monolithic 622-line class to a **professional component-based architecture** while maintaining vanilla JavaScript for Raspberry Pi compatibility.

**Before:** 622 lines (monolithic, hard to test, repetitive code)  
**After:** 350 lines (modular, testable, reusable components)

## Architecture

### 1. **HealthStore** (State Management)
- **Responsibility:** Centralized state container
- **Why:** Single source of truth, decoupled from UI
- **Key Methods:**
  - `setState(tab, data)` - Update state for specific tab
  - `subscribe(callback)` - Reactive updates when state changes
  - `getState()` - Read current state

```javascript
const store = new HealthStore();
store.setState('overview', overviewData);
store.subscribe(state => console.log(state));
```

### 2. **DataLoader** Classes (Data Fetching)
Handles API calls with error handling - single responsibility per loader.

```javascript
// Individual loaders for each tab
const overviewLoader = new DataLoader(
    () => window.HealthAPI.getSystemHealth(),
    'Failed to load overview'
);

// Orchestrator for all tabs
const tabDataLoader = new TabDataLoader(store);
await tabDataLoader.loadTab('health');
```

**Benefits:**
- Easy to mock for testing
- Centralized error handling
- API changes affect only one place
- Reusable across different parts of app

### 3. **Renderer Classes** (Presentational Logic)
Each renderer is responsible for ONE tab/component.

```javascript
// Base class for shared logic
class RendererBase {
    updateText(elementId, text)
    updateStatus(elementId, status)
    render(data)
}

// Specific implementations
class OverviewRenderer extends RendererBase {
    renderContent(data) { /* update overview-panel */ }
}

class HealthDetailsRenderer extends RendererBase {
    renderContent(data) { /* update health-panel */ }
}
```

**Benefits:**
- Pure functions (same input = same output)
- No side effects
- Easy to test
- Clear responsibility boundaries

### 4. **TabManager** (Orchestrator)
Coordinates between tabs, state, and renderers.

```javascript
const tabManager = new TabManager(store, dataLoader);

// Switch tab - handles loading + rendering
await tabManager.switchTab('health');

// Auto-refresh logic
tabManager.startAutoRefresh();
```

## Data Flow

```
User Click Tab Button
    ↓
TabManager.switchTab(tabName)
    ├─ Update UI (highlight button, show panel)
    ├─ Check if data cached in store
    ├─ If not cached: dataLoader.loadTab(tabName)
    │   ├─ Call API (via HealthAPI)
    │   ├─ Handle errors
    │   └─ store.setState(tabName, data)
    └─ Render data via Renderer
        └─ Updates DOM with formatted data
```

## Key Improvements

| Aspect | Before | After |
|--------|--------|-------|
| **Lines of Code** | 622 | 350 |
| **Testability** | Hard (mixed concerns) | Easy (pure functions) |
| **Reusability** | Low (duplicated logic) | High (composable classes) |
| **Maintainability** | Hard (everything connected) | Easy (separated concerns) |
| **Adding New Tab** | Modify entire class | Add new Renderer class only |
| **Changing API** | Update multiple methods | Update one DataLoader |
| **Performance** | Reload all tabs | Only reload changed tab |

## Adding a New Tab (Example)

Before refactoring: Update the monolithic class (50+ lines)

After refactoring: Just 30 lines!

```javascript
// 1. Create a renderer
class NewTabRenderer extends RendererBase {
    renderContent(data) {
        // Render your new tab here
        this.updateText('your-element-id', data.value);
    }
}

// 2. Add data loader
new DataLoader(
    () => window.HealthAPI.getNewTabData(),
    'Failed to load new tab'
);

// 3. Register in TabManager.setupRenderers()
this.renderers.newtab = new NewTabRenderer('newtab-panel');

// Done! Tab switching and auto-refresh work automatically
```

## Testing Strategy

Each class can be tested independently:

```javascript
// Test data loader in isolation
const loader = new DataLoader(() => Promise.resolve({test: 'data'}));
const data = await loader.load();
assert(data.test === 'data');

// Test renderer in isolation
const renderer = new OverviewRenderer('test-element');
renderer.render({stats: {total_units: 5}});
assert(document.getElementById('stat-units').textContent === '5');

// Test store in isolation
const store = new HealthStore();
let called = false;
store.subscribe(() => called = true);
store.setState('overview', {});
assert(called === true);
```

## Performance Optimizations

1. **Lazy Loading:** Each tab loads data only when clicked
2. **Caching:** Once loaded, tab data stays in memory until refresh
3. **Smart Re-render:** Only updates changed elements (not full replace)
4. **Auto-refresh:** Configurable interval (default 30s)
5. **Minimal Dependencies:** Pure vanilla JS, no external libraries

## Files

- `system_health_refactored.js` - Main dashboard (refactored)
- `system_health.html` - Template (updated to use refactored version)
- `system_health.css` - Styling (unchanged)

## Backward Compatibility

The old `system_health.js` is still available. To switch back, change the template script tag.

## Future Improvements

### Phase 1 (Already Done)
✅ Component-based architecture
✅ Separated concerns
✅ Testable design
✅ Vanilla JS only

### Phase 2 (Recommended)
- [ ] Add TypeScript for type safety
- [ ] Setup Vitest for unit testing
- [ ] Add component library (reusable UI components)
- [ ] Performance monitoring

### Phase 3 (Optional - When Ready)
- [ ] Migrate to lightweight framework (Preact, Vue)
- [ ] Add state persistence (localStorage)
- [ ] Add WebSocket support for real-time updates
- [ ] Build component storybook

## Migration Notes

If you have custom modifications in the old `system_health.js`, they can be:
1. Migrated to appropriate Renderer class
2. Added as new DataLoader for custom API
3. Integrated into TabManager for special handling

The architecture makes these changes straightforward!
