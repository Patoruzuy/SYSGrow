/* global API */
(() => {
  'use strict';

  const DEFAULT_IMAGE = '/static/img/plant-placeholder.svg';

  function formatRating(avg, count) {
    if (!count) return 'No ratings';
    return `${avg.toFixed(1)} (${count})`;
  }

  function buildStars(avg) {
    const stars = [];
    const full = Math.floor(avg);
    const hasHalf = avg - full >= 0.4 && avg - full < 0.9;
    const total = hasHalf ? full + 1 : full;
    for (let i = 0; i < full; i += 1) {
      stars.push('<i class="fas fa-star"></i>');
    }
    if (hasHalf) {
      stars.push('<i class="fas fa-star-half-alt"></i>');
    }
    for (let i = total; i < 5; i += 1) {
      stars.push('<i class="far fa-star"></i>');
    }
    return stars.join('');
  }

  class ProfileSelector {
    constructor(container, options = {}) {
      this.container = container;
      this.options = options;
      this.selectedId = null;
      this.sections = [];
    }

    async load(params = {}) {
      if (!this.container) return;
      this.container.innerHTML = '<div class="text-muted small">Loading profiles...</div>';
      try {
        const payload = await API.PersonalizedLearning.getConditionProfileSelector(params);
        const selector = payload?.selector || payload?.data?.selector || null;
        this.sections = selector?.sections || [];
        this.linkedProfile = selector?.linked_profile || null;
        this.hasProfiles = this.sections.some((section) => (section.profiles || []).length > 0);
        if (this.options.onLoad) {
          this.options.onLoad({
            hasProfiles: this.hasProfiles,
            sections: this.sections,
            linkedProfile: this.linkedProfile,
          });
        }
        this.render();
      } catch (error) {
        console.error('[ProfileSelector] load failed:', error);
        this.container.innerHTML = '<div class="text-danger small">Failed to load profiles.</div>';
        if (this.options.onLoad) {
          this.options.onLoad({
            hasProfiles: false,
            sections: [],
            linkedProfile: null,
          });
        }
      }
    }

    render() {
      if (!this.container) return;
      if (!this.sections || this.sections.length === 0) {
        this.container.innerHTML = '<div class="text-muted small">No profiles available.</div>';
        return;
      }
      this.container.innerHTML = '';
      this.sections.forEach((section) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'profile-section';

        const header = document.createElement('div');
        header.className = 'profile-section-header';
        const esc = window.escapeHtml || ((t) => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; });
        header.innerHTML = `
          <span>${esc(section.label)}</span>
          <span>${section.profiles.length} profiles</span>
        `;
        wrapper.appendChild(header);

        const grid = document.createElement('div');
        grid.className = 'profile-card-grid';

        if (section.profiles.length === 0) {
          const empty = document.createElement('div');
          empty.className = 'text-muted small';
          empty.textContent = 'No profiles in this section yet.';
          grid.appendChild(empty);
        } else {
          section.profiles.forEach((profile) => {
            const card = this._buildCard(profile, section.section_type);
            grid.appendChild(card);
          });
        }

        wrapper.appendChild(grid);
        this.container.appendChild(wrapper);
      });
    }

    async _handleSelect(profile, sectionType) {
      let resolved = profile;
      if (this.options.onSelect) {
        const result = await this.options.onSelect(profile, sectionType);
        if (result) {
          resolved = result;
        }
      }
      if (resolved) {
        this.setSelected(resolved.profile_id);
      }
    }

    _buildCard(profile, sectionType) {
      const card = document.createElement('div');
      card.className = 'profile-card';
      card.dataset.profileId = profile.profile_id;
      card.dataset.profileMode = profile.mode || '';
      card.dataset.sectionType = sectionType || '';

      const ratingAvg = parseFloat(profile.rating_avg || 0);
      const ratingCount = parseInt(profile.rating_count || 0, 10);

      const esc = window.escapeHtml || ((t) => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; });
      const escAttr = window.escapeHtmlAttr || ((t) => String(t ?? '').replace(/[&"'<>]/g, c => ({'&':'&amp;','"':'&quot;',"'":'&#39;','<':'&lt;','>':'&gt;'}[c])));
      const safeImgSrc = profile.image_url ? escAttr(profile.image_url) : DEFAULT_IMAGE;
      const safeName = esc(profile.name || `${profile.plant_type} (${profile.growth_stage})`);
      const safeMode = esc(profile.mode || 'Template');

      card.innerHTML = `
        <div class="profile-card-media">
          <img class="profile-card-image" src="${safeImgSrc}" alt="${escAttr(profile.name || profile.plant_type)}">
          <span class="profile-card-badge ${sectionType === 'public' ? 'shared' : (profile.mode === 'active' ? 'active' : '')}">
            ${sectionType === 'public' ? 'Shared' : safeMode}
          </span>
        </div>
        <div class="profile-card-body">
          <h4 class="profile-card-title">${safeName}</h4>
          <p class="profile-card-summary">${esc(profile.plant_type)} • ${esc(profile.growth_stage)}</p>
          <div class="profile-card-rating">
            <span class="profile-card-stars">${buildStars(ratingAvg)}</span>
            <span>${formatRating(ratingAvg, ratingCount)}</span>
          </div>
          <div class="profile-card-meta">
            ${profile.pot_size_liters ? `<span>Pot: ${esc(String(profile.pot_size_liters))} L</span>` : ''}
            ${profile.plant_variety ? `<span>${esc(profile.plant_variety)}</span>` : ''}
          </div>
          <div class="profile-card-tags">
            ${(profile.tags || []).slice(0, 3).map(tag => `<span class="profile-tag">${esc(tag)}</span>`).join('')}
          </div>
        </div>
      `;

      card.addEventListener('click', () => this._handleSelect(profile, sectionType));
      return card;
    }

    setSelected(profileId) {
      this.selectedId = profileId;
      if (!this.container) return;
      this.container.querySelectorAll('.profile-card').forEach((card) => {
        card.classList.toggle('selected', card.dataset.profileId === profileId);
      });
    }
  }

  window.ProfileSelector = ProfileSelector;
})();
