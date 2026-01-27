/**
 * Blog JavaScript Module
 * Handles blog page functionality including posts, categories, and search
 */

// API endpoints
const API = {
    posts: '/api/blog/posts',
    post: (slug) => `/api/blog/post/${slug}`,
    categories: '/api/blog/categories',
    featured: '/api/blog/featured',
    tags: '/api/blog/tags',
    search: '/api/blog/search'
};

// State
let state = {
    posts: [],
    categories: [],
    selectedCategory: 'all',
    searchQuery: '',
    offset: 0,
    limit: 9,
    hasMore: false
};

/**
 * Fetch data from API with error handling
 */
async function fetchAPI(url) {
    try {
        const response = await fetch(url);
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
 * Format date for display
 */
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Render featured post
 */
function renderFeaturedPost(post) {
    const container = document.getElementById('featured-post');
    if (!container || !post) return;

    // Determine image content
    let imageContent;
    if (post.featured_image) {
        imageContent = `<img src="${post.featured_image}" alt="${escapeHtml(post.title)}" class="featured-post-img">`;
    } else {
        imageContent = `<span class="featured-post-emoji">${post.emoji || '📝'}</span>`;
    }

    container.innerHTML = `
        <div class="featured-post-image ${post.featured_image ? 'has-image' : ''}">
            ${imageContent}
        </div>
        <div class="featured-post-content">
            <span class="featured-badge">
                <i class="fas fa-star"></i> Featured
            </span>
            <h2><a href="/blog/${post.slug}">${escapeHtml(post.title)}</a></h2>
            <p class="featured-post-summary">${escapeHtml(post.summary)}</p>
            <div class="featured-post-meta">
                <span><i class="fas fa-folder"></i> ${escapeHtml(post.category)}</span>
                <span><i class="fas fa-calendar"></i> ${formatDate(post.published_at)}</span>
                <span><i class="fas fa-clock"></i> ${post.reading_time || 5} min read</span>
            </div>
        </div>
    `;
}

/**
 * Render category filters
 */
function renderCategories(categories) {
    const container = document.getElementById('category-filters');
    if (!container) return;

    // Keep the "All" button
    let html = `
        <button class="category-btn ${state.selectedCategory === 'all' ? 'active' : ''}" data-category="all">
            <i class="fas fa-th-large"></i> All
        </button>
    `;

    categories.forEach(cat => {
        const isActive = state.selectedCategory === cat.id ? 'active' : '';
        html += `
            <button class="category-btn ${isActive}" data-category="${cat.id}">
                <i class="fas ${cat.icon}"></i> ${escapeHtml(cat.name)}
                <span class="count">${cat.post_count}</span>
            </button>
        `;
    });

    container.innerHTML = html;

    // Add click handlers
    container.querySelectorAll('.category-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const category = btn.dataset.category;
            selectCategory(category);
        });
    });
}

function renderIrrigationGuideCard() {
    return `
        <article class="post-card">
            <div class="post-card-header">
                <span class="post-card-emoji">💧</span>
                <span class="post-card-category">Guide</span>
            </div>
            <div class="post-card-body">
                <h3><a href="/blog/irrigation-guide">How the Irrigation System Works</a></h3>
                <p class="post-card-summary">A simple walkthrough of detection, approval, safe execution, and how your feedback improves future watering.</p>
                <div class="post-card-meta">
                    <span><i class="fas fa-route"></i> 4 steps</span>
                    <span><i class="fas fa-tint"></i> Manual + Auto</span>
                </div>
            </div>
        </article>
    `;
}

/**
 * Select a category and reload posts
 */
async function selectCategory(categoryId) {
    state.selectedCategory = categoryId;
    state.offset = 0;

    // Update active state
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.category === categoryId);
    });

    // Update title
    const titleEl = document.getElementById('posts-title');
    if (titleEl) {
        if (categoryId === 'all') {
            titleEl.textContent = 'Latest Posts';
        } else {
            const cat = state.categories.find(c => c.id === categoryId);
            titleEl.textContent = cat ? cat.name : 'Posts';
        }
    }

    await loadPosts(false);
}

/**
 * Load posts with optional append mode
 */
async function loadPosts(append = false) {
    const container = document.getElementById('posts-grid');
    const countEl = document.getElementById('posts-count');
    const loadMoreBtn = document.getElementById('load-more-container');
    const emptyState = document.getElementById('empty-state');

    if (!container) return;

    if (!append) {
        container.innerHTML = `
            <div class="loading-state">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Loading posts...</p>
            </div>
        `;
    }

    // Build URL
    let url = `${API.posts}?limit=${state.limit}&offset=${state.offset}`;
    if (state.selectedCategory && state.selectedCategory !== 'all') {
        url += `&category=${encodeURIComponent(state.selectedCategory)}`;
    }
    if (state.searchQuery) {
        url += `&search=${encodeURIComponent(state.searchQuery)}`;
    }

    const data = await fetchAPI(url);

    if (!data) {
        if (!append) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-newspaper"></i>
                    <h3>Failed to load posts</h3>
                    <p>Please try again later</p>
                </div>
            `;
        }
        return;
    }

    state.hasMore = data.has_more;
    const posts = data.posts || [];

    // Update count
    if (countEl) {
        countEl.textContent = `${data.total} post${data.total !== 1 ? 's' : ''}`;
    }

    // Handle empty state
    if (posts.length === 0 && !append) {
        container.innerHTML = '';
        if (emptyState) emptyState.classList.remove('hidden');
        if (loadMoreBtn) loadMoreBtn.classList.add('hidden');
        return;
    }

    if (emptyState) emptyState.classList.add('hidden');

    // Render posts
    const html = posts.map(post => {
        // Determine header content (image or emoji)
        let headerContent;
        if (post.featured_image) {
            headerContent = `
                <img src="${post.featured_image}" alt="${escapeHtml(post.title)}" class="post-card-image">
                <span class="post-card-category overlay">${escapeHtml(post.category)}</span>
            `;
        } else {
            headerContent = `
                <span class="post-card-emoji">${post.emoji || '📝'}</span>
                <span class="post-card-category">${escapeHtml(post.category)}</span>
            `;
        }

        return `
            <article class="post-card ${post.featured_image ? 'has-image' : ''}">
                <div class="post-card-header">
                    ${headerContent}
                </div>
                <div class="post-card-body">
                    <h3><a href="/blog/${post.slug}">${escapeHtml(post.title)}</a></h3>
                    <p class="post-card-summary">${escapeHtml(post.summary)}</p>
                    <div class="post-card-meta">
                        <span><i class="fas fa-calendar"></i> ${formatDate(post.published_at)}</span>
                        <span><i class="fas fa-clock"></i> ${post.reading_time || 5} min</span>
                    </div>
                </div>
            </article>
        `;
    }).join('');

    const showGuide = !append && state.selectedCategory === 'all' && !state.searchQuery;
    const guideCard = showGuide ? renderIrrigationGuideCard() : '';

    if (append) {
        container.insertAdjacentHTML('beforeend', html);
    } else {
        container.innerHTML = guideCard + html;
    }

    // Show/hide load more button
    if (loadMoreBtn) {
        loadMoreBtn.classList.toggle('hidden', !state.hasMore);
    }
}

/**
 * Setup search functionality
 */
function setupSearch() {
    const searchInput = document.getElementById('blog-search');
    if (!searchInput) return;

    let debounceTimer;

    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            state.searchQuery = e.target.value.trim();
            state.offset = 0;
            loadPosts(false);
        }, 300);
    });
}

/**
 * Setup load more button
 */
function setupLoadMore() {
    const btn = document.getElementById('load-more-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        state.offset += state.limit;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';

        await loadPosts(true);

        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-plus"></i> Load More Posts';
    });
}

/**
 * Setup clear filters button
 */
function setupClearFilters() {
    const btn = document.getElementById('clear-filters-btn');
    if (!btn) return;

    btn.addEventListener('click', () => {
        state.selectedCategory = 'all';
        state.searchQuery = '';
        state.offset = 0;

        // Clear search input
        const searchInput = document.getElementById('blog-search');
        if (searchInput) searchInput.value = '';

        // Reset category buttons
        document.querySelectorAll('.category-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.category === 'all');
        });

        // Reset title
        const titleEl = document.getElementById('posts-title');
        if (titleEl) titleEl.textContent = 'Latest Posts';

        loadPosts(false);
    });
}

/**
 * Initialize Blog Page
 */
export async function initBlogPage() {
    // Load featured posts
    const featured = await fetchAPI(`${API.featured}?limit=1`);
    if (featured && featured.length > 0) {
        renderFeaturedPost(featured[0]);
    } else {
        // Hide featured section if no featured posts
        const featuredSection = document.getElementById('featured-section');
        if (featuredSection) featuredSection.classList.add('hidden');
    }

    // Load categories
    const categories = await fetchAPI(API.categories);
    if (categories) {
        state.categories = categories;
        renderCategories(categories);
    }

    // Load initial posts
    await loadPosts(false);

    // Setup interactions
    setupSearch();
    setupLoadMore();
    setupClearFilters();
    setupSearchAutocomplete();
}

/**
 * Initialize Blog Post Page
 */
export async function initBlogPost() {
    const slug = window.BLOG_POST_SLUG;

    if (!slug) {
        console.error('Missing post slug');
        return;
    }

    // Load post
    const post = await fetchAPI(API.post(slug));

    if (!post) {
        document.getElementById('post-content').innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Post not found</h3>
                <p>The requested post could not be loaded</p>
            </div>
        `;
        return;
    }

    // Update page title
    document.title = `${post.title} - Blog - SYSGrow`;

    // Update breadcrumb
    const breadcrumbCategory = document.getElementById('breadcrumb-category');
    const breadcrumbTitle = document.getElementById('breadcrumb-title');
    if (breadcrumbCategory) {
        breadcrumbCategory.textContent = post.category;
        breadcrumbCategory.href = `/blog#category-${post.category}`;
    }
    if (breadcrumbTitle) {
        breadcrumbTitle.textContent = post.title;
    }

    // Show hero image if available
    const heroContainer = document.getElementById('post-hero');
    const heroImage = document.getElementById('post-hero-image');
    if (heroContainer && heroImage && post.featured_image) {
        heroImage.src = post.featured_image;
        heroImage.alt = post.title;
        heroContainer.classList.remove('hidden');
    }

    // Update header
    document.getElementById('post-emoji').textContent = post.emoji || '📝';
    document.getElementById('post-category').querySelector('span').textContent = post.category;
    document.getElementById('post-date').querySelector('span').textContent = formatDate(post.published_at);
    document.getElementById('post-reading-time').querySelector('span').textContent = `${post.reading_time || 5} min read`;
    document.getElementById('post-title').textContent = post.title;
    document.getElementById('post-summary').textContent = post.summary;
    document.getElementById('post-author').querySelector('span').textContent = post.author || 'SYSGrow Team';

    // Render markdown content
    const contentEl = document.getElementById('post-content');
    if (contentEl && post.content) {
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,
                gfm: true
            });
            contentEl.innerHTML = marked.parse(post.content);
        } else {
            contentEl.innerHTML = `<pre>${escapeHtml(post.content)}</pre>`;
        }
    }

    // Render tags
    const tagsEl = document.getElementById('post-tags');
    if (tagsEl && post.tags && post.tags.length > 0) {
        tagsEl.innerHTML = post.tags.map(tag => `
            <a href="/blog?search=${encodeURIComponent(tag)}" class="post-tag">
                <i class="fas fa-tag"></i> ${escapeHtml(tag)}
            </a>
        `).join('');
    }

    // Load related posts
    await loadRelatedPosts(post.category, slug);

    // Load sidebar categories
    await loadSidebarCategories();

    // Load tags cloud
    await loadTagsCloud();

    // Initialize enhancements (TOC, copy buttons, progress, back-to-top)
    initPostEnhancements();
}

/**
 * Load related posts for sidebar
 */
async function loadRelatedPosts(category, currentSlug) {
    const container = document.getElementById('related-posts');
    if (!container) return;

    const data = await fetchAPI(`${API.posts}?category=${encodeURIComponent(category)}&limit=5`);

    if (!data || !data.posts) {
        container.innerHTML = '<li>No related posts</li>';
        return;
    }

    const related = data.posts.filter(p => p.slug !== currentSlug).slice(0, 3);

    if (related.length === 0) {
        container.innerHTML = '<li>No related posts</li>';
        return;
    }

    container.innerHTML = related.map(post => `
        <li>
            <a href="/blog/${post.slug}">
                <span class="related-title">${escapeHtml(post.title)}</span>
                <span class="related-meta">${formatDate(post.published_at)}</span>
            </a>
        </li>
    `).join('');
}

/**
 * Load categories for sidebar
 */
async function loadSidebarCategories() {
    const container = document.getElementById('sidebar-categories');
    if (!container) return;

    const categories = await fetchAPI(API.categories);

    if (!categories || categories.length === 0) {
        container.innerHTML = '<li>No categories</li>';
        return;
    }

    container.innerHTML = categories.map(cat => `
        <li>
            <a href="/blog#category-${cat.id}">
                <span>${escapeHtml(cat.name)}</span>
                <span class="count">${cat.post_count}</span>
            </a>
        </li>
    `).join('');
}

/**
 * Load tags cloud for sidebar
 */
async function loadTagsCloud() {
    const container = document.getElementById('tags-cloud');
    if (!container) return;

    const tags = await fetchAPI(API.tags);

    if (!tags || tags.length === 0) {
        container.innerHTML = '<span>No tags</span>';
        return;
    }

    // Show top 15 tags
    const topTags = tags.slice(0, 15);

    container.innerHTML = topTags.map(tag => `
        <a href="/blog?search=${encodeURIComponent(tag.name)}" class="tag-link">
            ${escapeHtml(tag.name)} (${tag.count})
        </a>
    `).join('');
}

// =============================================
// ENHANCED FEATURES
// =============================================

/**
 * Generate Table of Contents from headings
 */
function generateTableOfContents() {
    const content = document.getElementById('post-content');
    const tocContainer = document.getElementById('table-of-contents');
    if (!content || !tocContainer) return;

    const headings = content.querySelectorAll('h2, h3');
    if (headings.length < 3) {
        // Hide TOC for short articles
        tocContainer.closest('.sidebar-section')?.classList.add('hidden');
        return;
    }

    const tocItems = [];
    headings.forEach((heading, index) => {
        // Add ID to heading for linking
        const id = `heading-${index}`;
        heading.id = id;

        const level = heading.tagName === 'H2' ? 'toc-h2' : 'toc-h3';
        tocItems.push(`
            <li class="${level}">
                <a href="#${id}">${escapeHtml(heading.textContent)}</a>
            </li>
        `);
    });

    tocContainer.innerHTML = tocItems.join('');

    // Highlight current section on scroll
    setupTocHighlight(headings);
}

/**
 * Highlight current TOC item on scroll
 */
function setupTocHighlight(headings) {
    const tocLinks = document.querySelectorAll('#table-of-contents a');
    if (!tocLinks.length) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                tocLinks.forEach(link => link.classList.remove('active'));
                const activeLink = document.querySelector(`#table-of-contents a[href="#${entry.target.id}"]`);
                if (activeLink) activeLink.classList.add('active');
            }
        });
    }, { rootMargin: '-20% 0px -70% 0px' });

    headings.forEach(heading => observer.observe(heading));
}

/**
 * Add copy buttons to code blocks
 */
function addCopyCodeButtons() {
    const codeBlocks = document.querySelectorAll('.markdown-content pre');

    codeBlocks.forEach(pre => {
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';

        const button = document.createElement('button');
        button.className = 'copy-code-btn';
        button.innerHTML = '<i class="fas fa-copy"></i>';
        button.title = 'Copy to clipboard';

        button.addEventListener('click', async () => {
            const code = pre.querySelector('code')?.textContent || pre.textContent;
            try {
                await navigator.clipboard.writeText(code);
                button.innerHTML = '<i class="fas fa-check"></i>';
                button.classList.add('copied');
                setTimeout(() => {
                    button.innerHTML = '<i class="fas fa-copy"></i>';
                    button.classList.remove('copied');
                }, 2000);
            } catch (err) {
                console.error('Failed to copy:', err);
                button.innerHTML = '<i class="fas fa-times"></i>';
                setTimeout(() => {
                    button.innerHTML = '<i class="fas fa-copy"></i>';
                }, 2000);
            }
        });

        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);
        wrapper.appendChild(button);
    });
}

/**
 * Setup reading progress indicator
 */
function setupReadingProgress() {
    const progressBar = document.getElementById('reading-progress');
    const article = document.querySelector('.blog-post');
    if (!progressBar || !article) return;

    const updateProgress = () => {
        const articleRect = article.getBoundingClientRect();
        const articleTop = articleRect.top + window.scrollY;
        const articleHeight = article.offsetHeight;
        const windowHeight = window.innerHeight;
        const scrollY = window.scrollY;

        // Calculate progress
        const start = articleTop - windowHeight;
        const end = articleTop + articleHeight - windowHeight;
        const current = scrollY - start;
        const total = end - start;

        let progress = (current / total) * 100;
        progress = Math.max(0, Math.min(100, progress));

        progressBar.style.width = `${progress}%`;
    };

    window.addEventListener('scroll', updateProgress, { passive: true });
    updateProgress();
}

/**
 * Setup back to top button
 */
function setupBackToTop() {
    const button = document.getElementById('back-to-top');
    if (!button) return;

    const toggleButton = () => {
        if (window.scrollY > 400) {
            button.classList.add('visible');
        } else {
            button.classList.remove('visible');
        }
    };

    window.addEventListener('scroll', toggleButton, { passive: true });

    button.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });

    toggleButton();
}

/**
 * Setup search autocomplete
 */
function setupSearchAutocomplete() {
    const searchInput = document.getElementById('blog-search');
    if (!searchInput) return;

    let suggestions = [];
    let suggestionBox = null;

    // Create suggestion box
    suggestionBox = document.createElement('div');
    suggestionBox.className = 'search-suggestions hidden';
    searchInput.parentNode.appendChild(suggestionBox);

    // Load all posts for suggestions
    fetchAPI(`${API.posts}?limit=100`).then(data => {
        if (data && data.posts) {
            suggestions = data.posts.map(p => ({
                title: p.title,
                slug: p.slug,
                category: p.category
            }));
        }
    });

    const showSuggestions = (query) => {
        if (!query || query.length < 2) {
            suggestionBox.classList.add('hidden');
            return;
        }

        const matches = suggestions.filter(s =>
            s.title.toLowerCase().includes(query.toLowerCase())
        ).slice(0, 5);

        if (matches.length === 0) {
            suggestionBox.classList.add('hidden');
            return;
        }

        suggestionBox.innerHTML = matches.map(s => `
            <a href="/blog/${s.slug}" class="suggestion-item">
                <span class="suggestion-title">${escapeHtml(s.title)}</span>
                <span class="suggestion-category">${escapeHtml(s.category)}</span>
            </a>
        `).join('');
        suggestionBox.classList.remove('hidden');
    };

    searchInput.addEventListener('input', (e) => {
        showSuggestions(e.target.value);
    });

    searchInput.addEventListener('blur', () => {
        // Delay to allow clicking suggestions
        setTimeout(() => suggestionBox.classList.add('hidden'), 200);
    });

    searchInput.addEventListener('focus', (e) => {
        if (e.target.value.length >= 2) {
            showSuggestions(e.target.value);
        }
    });
}

/**
 * Initialize all post enhancements
 */
function initPostEnhancements() {
    generateTableOfContents();
    addCopyCodeButtons();
    setupReadingProgress();
    setupBackToTop();
}
