
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
