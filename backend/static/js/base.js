// SYSGrow global namespace — all shared JS utilities live here.
// Guard ensures safe re-inclusion on pages that bundle multiple scripts.
window.SYSGrow = window.SYSGrow || {};

// Shared page lifecycle + transient network error helpers.
// Used to suppress noisy "Failed to fetch" logs during rapid navigation teardown.
if (!window.__SYSGROW_PAGE_LIFECYCLE_HOOKS__) {
  window.__SYSGROW_PAGE_LIFECYCLE_HOOKS__ = true;
  window.__SYSGROW_PAGE_UNLOADING = false;
  const markUnloading = () => { window.__SYSGROW_PAGE_UNLOADING = true; };
  const clearUnloading = () => { window.__SYSGROW_PAGE_UNLOADING = false; };
  window.addEventListener('beforeunload', markUnloading);
  window.addEventListener('pagehide', markUnloading);
  window.addEventListener('pageshow', clearUnloading);
}

window.SYSGrow.isPageUnloading = function isPageUnloading() {
  return window.__SYSGROW_PAGE_UNLOADING === true || document.visibilityState === 'hidden';
};

window.SYSGrow.isTransientFetchError = function isTransientFetchError(value) {
  if (!value) return false;

  const message = typeof value === 'string'
    ? value
    : (typeof value.message === 'string' ? value.message : '');
  const name = typeof value.name === 'string' ? value.name : '';

  if (name === 'AbortError') return true;
  return /failed to fetch|networkerror when attempting to fetch resource|the user aborted a request/i.test(message);
};

window.SYSGrow.shouldSuppressNetworkErrorLog = function shouldSuppressNetworkErrorLog(args) {
  if (!window.SYSGrow.isPageUnloading()) return false;
  return Array.isArray(args) && args.some((arg) => window.SYSGrow.isTransientFetchError(arg));
};

if (!window.__SYSGROW_CONSOLE_FILTER_INSTALLED__) {
  window.__SYSGROW_CONSOLE_FILTER_INSTALLED__ = true;

  const originalError = console.error.bind(console);
  const originalWarn = console.warn.bind(console);

  console.error = (...args) => {
    if (window.SYSGrow.shouldSuppressNetworkErrorLog(args)) return;
    originalError(...args);
  };

  console.warn = (...args) => {
    if (window.SYSGrow.shouldSuppressNetworkErrorLog(args)) return;
    originalWarn(...args);
  };
}

/**
 * Read a CSS custom property from :root at call time.
 * Use this to pass live design-token values into non-CSS contexts
 * such as Chart.js datasets, Canvas rendering, or SVG attributes.
 * Reading at call time (not module load) respects dynamic theme switches.
 *
 * @param {string} name  CSS variable name, e.g. '--chart-temperature'
 * @returns {string}     Trimmed string value of the property
 */
window.SYSGrow.cssVar = function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
};

/**
 * Display a page-level initialization failure banner and log to console.
 * Call from the top-level catch block of any page module's init() function.
 * Injects a single .alert.alert-danger into .page-shell — idempotent,
 * so multiple failed modules on one page show only one banner.
 *
 * @param {string} module  Short display name shown in the banner, e.g. 'Dashboard'
 * @param {Error}  error   The caught error object
 */
window.SYSGrow.initError = function initError(module, error) {
  console.error('[' + module + '] Initialization failed:', error);
  if (document.getElementById('sysgrow-init-error')) return; // already shown
  const shell = document.querySelector('.page-shell') || document.body;
  const el = document.createElement('div');
  el.id = 'sysgrow-init-error';
  el.className = 'alert alert-danger m-4';
  el.setAttribute('role', 'alert');

  const icon = document.createElement('i');
  icon.className = 'fas fa-exclamation-triangle me-2';
  icon.setAttribute('aria-hidden', 'true');
  el.appendChild(icon);

  const title = document.createElement('strong');
  title.textContent = String(module || 'Module');
  el.appendChild(title);

  el.appendChild(document.createTextNode(' failed to load - please refresh the page.'));

  const errorMessage = error && typeof error.message === 'string' ? error.message.trim() : '';
  if (errorMessage) {
    el.appendChild(document.createTextNode(' '));
    const detail = document.createElement('small');
    detail.className = 'ms-2 text-muted';
    detail.textContent = errorMessage;
    el.appendChild(detail);
  }
  shell.prepend(el);
};

// Theme toggle + mobile menu + user menu
document.addEventListener('DOMContentLoaded', function() {
    // Theme toggle
    const THEME_KEY = 'sysgrow-theme';
    const root = document.documentElement;
    const themeToggle = document.getElementById('theme-toggle');

    function applyTheme(theme) {
        if (theme === 'dark' || theme === 'light') {
            root.setAttribute('data-theme', theme);
            if (themeToggle) {
                const icon = themeToggle.querySelector('i');
                if (icon) {
                    // Show the icon for the *next* mode as a hint
                    if (theme === 'dark') {
                        icon.classList.remove('fa-moon');
                        icon.classList.add('fa-sun');
                    } else {
                        icon.classList.remove('fa-sun');
                        icon.classList.add('fa-moon');
                    }
                }
            }
        }
    }

    // Determine initial theme: localStorage > system preference
    let theme = localStorage.getItem(THEME_KEY);
    if (theme !== 'light' && theme !== 'dark') {
        const prefersDark = window.matchMedia &&
            window.matchMedia('(prefers-color-scheme: dark)').matches;
        theme = prefersDark ? 'dark' : 'light';
    }
    applyTheme(theme);

    if (themeToggle) {
        themeToggle.addEventListener('click', function () {
            theme = (theme === 'dark') ? 'light' : 'dark';
            localStorage.setItem(THEME_KEY, theme);
            applyTheme(theme);
        });
    }

    const mobileToggle = document.getElementById('mobile-menu-toggle');
    const sidebar = document.getElementById('sidebar');
    
    if (mobileToggle && sidebar) {
        mobileToggle.addEventListener('click', function() {
            const isExpanded = this.getAttribute('aria-expanded') === 'true';
            this.setAttribute('aria-expanded', (!isExpanded).toString());
            sidebar.classList.toggle('mobile-open');
            document.body.classList.toggle('sidebar-open');
            // Reflect visibility to assistive tech
            const nowExpanded = this.getAttribute('aria-expanded') === 'true';
            sidebar.setAttribute('aria-hidden', (!nowExpanded).toString());
        });
    }
    
    // Update current time
    function updateTime() {
        const timeElement = document.getElementById('current-time');
        if (timeElement) {
            const now = new Date();
            timeElement.textContent = now.toLocaleTimeString();
        }
    }
    
    updateTime();
    setInterval(updateTime, 1000);
    
    // User menu toggle
    const userInfo = document.querySelector('.user-info');
    const userMenu = document.getElementById('user-menu');
    
    if (userInfo && userMenu) {
        const toggleUserMenu = () => {
            const isOpen = userMenu.classList.toggle('active');
            userInfo.setAttribute('aria-expanded', isOpen.toString());
        };
        userInfo.addEventListener('click', toggleUserMenu);
        userInfo.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleUserMenu();
            }
        });
        
        // Close menu when clicking outside
        document.addEventListener('click', function(e) {
            if (
                userMenu.classList.contains('active') &&
                !userInfo.contains(e.target) &&
                !userMenu.contains(e.target)
            ) {
                userMenu.classList.remove('active');
                userInfo.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // Flash message closing
    document.querySelectorAll('.flash-close').forEach(button => {
        button.addEventListener('click', function() {
            const message = this.closest('.flash-message');
            if (message) {
                message.remove();
            }
        });
    });
});
