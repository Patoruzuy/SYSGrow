/**
 * Help Center JavaScript Module
 * Handles help page functionality including categories, articles, and search
 */

// API endpoints
const HELP_ENDPOINTS = {
    categories: '/api/help/categories',
    articles: '/api/help/articles',
    article: (category, id) => `/api/help/article/${category}/${id}`,
    search: '/api/help/search'
};

// State
let state = {
    categories: [],
    articles: [],
    selectedCategory: null,
    searchQuery: ''
};

/**
 * Fetch data from API with error handling
 */
async function fetchAPI(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            console.error('API HTTP error:', response.status, response.statusText);
            return null;
        }
        const data = await response.json();
        if (data.ok) {
            return data.data;
        }
        console.error('API error:', data.error);
        return null;
    } catch (error) {
        console.error('Fetch error:', error);
        return null;
    }
}

/**
 * Render categories in sidebar
 */
function renderCategories(categories, selectedId = null) {
    const container = document.getElementById('categories-list');
    if (!container) return;

    if (!categories || categories.length === 0) {
        container.innerHTML = '<li class="help-nav-item"><span>No categories found</span></li>';
        return;
    }

    // Add "All Topics" option
    const allActive = !selectedId ? 'active' : '';
    let html = `
        <li class="help-nav-item">
            <a href="/help" class="${allActive}" data-category="">
                <i class="fas fa-th-large"></i>
                <span>All Topics</span>
                <span class="article-count-badge">${categories.reduce((sum, c) => sum + c.article_count, 0)}</span>
            </a>
        </li>
    `;

    categories.forEach(cat => {
        const isActive = selectedId === cat.id ? 'active' : '';
        html += `
            <li class="help-nav-item">
                <a href="/help/${cat.id}" class="${isActive}" data-category="${cat.id}">
                    <i class="fas ${cat.icon}"></i>
                    <span>${cat.title}</span>
                    <span class="article-count-badge">${cat.article_count}</span>
                </a>
            </li>
        `;
    });

    container.innerHTML = html;

    // Add click handlers for SPA-like navigation
    container.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const category = link.dataset.category;
            navigateToCategory(category);
        });
    });
}

/**
 * Navigate to a category (SPA-like behavior)
 */
async function navigateToCategory(categoryId) {
    state.selectedCategory = categoryId || null;

    // Update URL without reload
    const url = categoryId ? `/help/${categoryId}` : '/help';
    history.pushState({ category: categoryId }, '', url);

    // Update active state in sidebar
    document.querySelectorAll('.help-nav-item a').forEach(link => {
        link.classList.toggle('active', link.dataset.category === (categoryId || ''));
    });

    // Load articles for category
    await loadArticles(categoryId);
}

/**
 * Load articles for a category
 */
async function loadArticles(categoryId = null) {
    const container = document.getElementById('articles-grid');
    const titleEl = document.getElementById('category-title');
    const countEl = document.getElementById('article-count');

    if (!container) return;

    // Show loading state
    container.innerHTML = `
        <div class="loading-state">
            <i class="fas fa-spinner fa-spin"></i>
            <p>Loading articles...</p>
        </div>
    `;

    // Build URL with optional category filter
    let url = HELP_ENDPOINTS.articles;
    if (categoryId) {
        url += `?category=${encodeURIComponent(categoryId)}`;
    }

    const data = await fetchAPI(url);

    if (!data || !data.articles) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-book-open"></i>
                <h3>No articles found</h3>
                <p>Try selecting a different category</p>
            </div>
        `;
        return;
    }

    state.articles = data.articles;

    // Update title and count
    if (categoryId && data.articles.length > 0) {
        titleEl.textContent = data.articles[0].category_title;
    } else {
        titleEl.textContent = 'All Topics';
    }
    countEl.textContent = `${data.total} article${data.total !== 1 ? 's' : ''}`;

    renderArticles(data.articles);
}

/**
 * Render articles grid
 */
function renderArticles(articles) {
    const container = document.getElementById('articles-grid');
    if (!container) return;

    if (!articles || articles.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-book-open"></i>
                <h3>No articles found</h3>
                <p>Try selecting a different category</p>
            </div>
        `;
        return;
    }

    const html = articles.map(article => `
        <a href="/help/${article.category}/${article.id}" class="article-card" data-article="${article.id}">
            <div class="article-card-header">
                <div class="article-card-icon">
                    <i class="fas ${article.category_icon}"></i>
                </div>
                <div class="article-card-meta">
                    <span class="article-card-category">${article.category_title}</span>
                    <h3>${escapeHtml(article.title)}</h3>
                </div>
            </div>
            <p>${escapeHtml(article.summary)}</p>
            <div class="article-card-footer">
                <span class="article-card-link">
                    Read article <i class="fas fa-arrow-right"></i>
                </span>
            </div>
        </a>
    `).join('');

    container.innerHTML = html;
}

/**
 * Handle search functionality
 */
async function handleSearch(query) {
    const categoryView = document.getElementById('category-view');
    const searchView = document.getElementById('search-view');
    const searchCount = document.getElementById('search-count');
    const searchList = document.getElementById('search-articles-list');
    const dropdown = document.getElementById('search-results-dropdown');
    const resultsList = document.getElementById('search-results-list');

    if (!query || query.trim().length < 2) {
        // Show category view, hide search
        if (categoryView) categoryView.classList.remove('hidden');
        if (searchView) searchView.classList.add('hidden');
        if (dropdown) dropdown.classList.add('hidden');
        return;
    }

    state.searchQuery = query.trim();

    // Show loading in dropdown
    if (dropdown && resultsList) {
        dropdown.classList.remove('hidden');
        resultsList.innerHTML = '<div class="search-result-item"><p>Searching...</p></div>';
    }

    const data = await fetchAPI(`${HELP_ENDPOINTS.search}?q=${encodeURIComponent(query)}&limit=10`);

    if (!data || !data.results) {
        if (resultsList) {
            resultsList.innerHTML = '<div class="search-no-results">No results found</div>';
        }
        return;
    }

    // Render dropdown results
    if (resultsList) {
        if (data.results.length === 0) {
            resultsList.innerHTML = '<div class="search-no-results">No results found</div>';
        } else {
            resultsList.innerHTML = data.results.map(result => `
                <a href="/help/${result.category}/${result.id}" class="search-result-item">
                    <span class="search-result-category">${result.category_title}</span>
                    <h4>${escapeHtml(result.title)}</h4>
                    <p>${escapeHtml(result.summary)}</p>
                </a>
            `).join('');
        }
    }
}

/**
 * Setup search with debounce
 */
function setupSearch() {
    const searchInput = document.getElementById('help-search');
    const clearBtn = document.getElementById('search-clear');
    const dropdown = document.getElementById('search-results-dropdown');

    if (!searchInput) return;

    let debounceTimer;

    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        const query = e.target.value;

        // Toggle clear button
        if (clearBtn) {
            clearBtn.classList.toggle('hidden', !query);
        }

        debounceTimer = setTimeout(() => {
            handleSearch(query);
        }, 300);
    });

    // Clear search
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            searchInput.value = '';
            clearBtn.classList.add('hidden');
            if (dropdown) dropdown.classList.add('hidden');

            // Reset to current category
            loadArticles(state.selectedCategory);
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (dropdown && !searchInput.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.add('hidden');
        }
    });

    // Focus shows dropdown if there's content
    searchInput.addEventListener('focus', () => {
        if (searchInput.value.length >= 2 && dropdown) {
            dropdown.classList.remove('hidden');
        }
    });
}

/**
 * Initialize Help Page
 */
export async function initHelpPage() {
    // Load categories
    const categories = await fetchAPI(HELP_ENDPOINTS.categories);
    if (categories) {
        state.categories = categories;

        // Get initial category from URL or global variable
        const initialCategory = window.HELP_INITIAL_CATEGORY || null;
        state.selectedCategory = initialCategory;

        renderCategories(categories, initialCategory);
    }

    // Load articles
    await loadArticles(state.selectedCategory);

    // Setup search
    setupSearch();

    // Handle browser back/forward
    window.addEventListener('popstate', (e) => {
        const category = e.state?.category || null;
        state.selectedCategory = category;

        // Update sidebar
        document.querySelectorAll('.help-nav-item a').forEach(link => {
            link.classList.toggle('active', link.dataset.category === (category || ''));
        });

        loadArticles(category);
    });
}

/**
 * Initialize Help Article Page
 */
export async function initHelpArticle() {
    const category = window.HELP_ARTICLE_CATEGORY;
    const articleId = window.HELP_ARTICLE_ID;

    if (!category || !articleId) {
        console.error('Missing article info');
        return;
    }

    // Load article
    const article = await fetchAPI(HELP_ENDPOINTS.article(category, articleId));

    if (!article) {
        document.getElementById('article-content').innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Article not found</h3>
                <p>The requested article could not be loaded</p>
            </div>
        `;
        return;
    }

    // Update page title
    document.title = `${article.title} - Help - SYSGrow`;

    // Update breadcrumb
    const breadcrumbCategory = document.getElementById('breadcrumb-category');
    const breadcrumbArticle = document.getElementById('breadcrumb-article');
    if (breadcrumbCategory) {
        breadcrumbCategory.textContent = article.category_title;
        breadcrumbCategory.href = `/help/${article.category}`;
    }
    if (breadcrumbArticle) {
        breadcrumbArticle.textContent = article.title;
    }

    // Update header
    document.getElementById('category-name').textContent = article.category_title;
    document.getElementById('article-title').textContent = article.title;
    document.getElementById('article-summary').textContent = article.summary;

    // Render markdown content
    const contentEl = document.getElementById('article-content');
    if (contentEl && article.content) {
        // Configure marked for safe rendering
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,
                gfm: true
            });
            contentEl.innerHTML = marked.parse(article.content);
        } else {
            // Fallback to plain text if marked.js not loaded
            contentEl.innerHTML = `<pre>${escapeHtml(article.content)}</pre>`;
        }
    }

    // Load related articles
    await loadRelatedArticles(category, articleId);
}

/**
 * Load related articles for sidebar
 */
async function loadRelatedArticles(category, currentId) {
    const container = document.getElementById('related-articles');
    if (!container) return;

    const data = await fetchAPI(`${HELP_ENDPOINTS.articles}?category=${encodeURIComponent(category)}&limit=5`);

    if (!data || !data.articles) {
        container.innerHTML = '<li>No related articles</li>';
        return;
    }

    // Filter out current article
    const related = data.articles.filter(a => a.id !== currentId).slice(0, 4);

    if (related.length === 0) {
        container.innerHTML = '<li>No related articles</li>';
        return;
    }

    container.innerHTML = related.map(article => `
        <li>
            <a href="/help/${article.category}/${article.id}">
                ${escapeHtml(article.title)}
            </a>
        </li>
    `).join('');
}

/**
 * Escape HTML to prevent XSS — delegate to shared utility
 */
function escapeHtml(text) {
    if (window.escapeHtml) return window.escapeHtml(text);
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
