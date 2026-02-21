/**
 * My Plant Detail — client-side logic
 * ====================================
 * Tabbed interface: Overview · Journal · Analytics · Stage
 *
 * Data loaded from:
 *   GET /api/plants/<id>/detail          (unified payload)
 *   GET /api/plants/<id>/journal/entries  (paginated)
 *   GET /api/plants/<id>/journal/summary
 *   GET /api/plants/<id>/journal/watering-history
 *   GET /api/plants/<id>/journal/stage-timeline
 *   POST /api/plants/<id>/journal/*       (add entries)
 *   POST /api/plants/<id>/stage/extend
 */
(function () {
  "use strict";

  /* ====== constants ====== */
  const plantId = document.getElementById("my-plant-detail")?.dataset.plantId;
  if (!plantId) return;

  const API = `/api/plants/${plantId}`;
  const PER_PAGE = 20;

  let currentPage = 1;
  let currentFilter = "";
  let plantData = null; // cached detail payload
  let wateringChart = null;
  let healthChart = null;

  /* ====== helpers ====== */
  async function api(path, opts = {}) {
    const url = path.startsWith("http") ? path : `${API}${path}`;
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...opts.headers },
      ...opts,
    });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.error?.message || errBody.message || `HTTP ${res.status}`);
    }
    const json = await res.json();
    // Backend returns {ok, data, error} envelope — normalise to {success, data, message}
    if (json && typeof json.ok === 'boolean') {
      return { success: json.ok, data: json.data, message: json.error?.message || json.error || null };
    }
    return json;
  }

  function el(id) {
    return document.getElementById(id);
  }

  function formatDate(d) {
    if (!d) return "—";
    const dt = new Date(d);
    return dt.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function badge(text, variant = "default") {
    return `<span class="badge badge--${variant}">${window.escapeHtml(text)}</span>`;
  }

  function entryIcon(type) {
    const icons = {
      observation: "fa-eye",
      watering: "fa-tint",
      nutrient: "fa-flask",
      treatment: "fa-medkit",
      pruning: "fa-cut",
      stage_change: "fa-layer-group",
      harvest: "fa-apple-alt",
      transplant: "fa-exchange-alt",
      environmental_adjustment: "fa-sliders-h",
      note: "fa-sticky-note",
    };
    return icons[type] || "fa-circle";
  }

  function healthVariant(status) {
    if (!status) return "default";
    const s = status.toLowerCase();
    if (s === "healthy") return "success";
    if (s === "stressed") return "warning";
    if (s === "diseased" || s === "critical") return "danger";
    return "info";
  }

  /* ====== Tab switching ====== */
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      document.querySelectorAll(".tab-panel").forEach((p) => {
        p.classList.remove("active");
        p.hidden = true;
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      const panel = el(`tab-${btn.dataset.tab}`);
      if (panel) {
        panel.classList.add("active");
        panel.hidden = false;
      }

      // Lazy-load analytics/stage data on first view
      if (btn.dataset.tab === "analytics" && !wateringChart) loadAnalytics();
      if (btn.dataset.tab === "stage") loadStageTimeline();
    });
  });

  /* ====== 1. Load Plant Detail (Overview) ====== */
  async function loadDetail() {
    try {
      const res = await api("/detail");
      if (!res.success) throw new Error(res.message);
      plantData = res.data;
      renderHeader();
      renderKPIs();
      renderPlantInfo();
      renderLinkedDevices();
      renderRecentEntries();
    } catch (err) {
      console.error("Failed to load plant detail:", err);
      el("plant-name-header").textContent = "Plant not found";
    }
  }

  function renderHeader() {
    const p = plantData.plant || {};
    el("plant-name-header").textContent = p.plant_name || `Plant #${plantId}`;
    el("plant-subtitle-header").textContent = [
      p.plant_type,
      p.current_stage ? `Stage: ${p.current_stage}` : null,
    ]
      .filter(Boolean)
      .join(" · ");
  }

  function renderKPIs() {
    const p = plantData.plant || {};
    const summary = plantData.journal_summary || {};

    const healthStatus = p.current_health_status || "unknown";
    el("kpi-health-value").textContent = healthStatus;
    // Update variant
    const healthCard = el("kpi-card-health");
    if (healthCard) {
      healthCard.className = `kpi-card kpi-card--${healthVariant(healthStatus)}`;
    }

    el("kpi-stage-value").textContent = p.current_stage || "—";
    el("kpi-days-value").textContent = plantData.stage_info?.days_in_stage ?? p.days_in_stage ?? "—";
    el("kpi-entries-value").textContent = summary.total_entries ?? "—";
  }

  function renderPlantInfo() {
    const p = plantData.plant || {};
    const rows = [
      ["Name", p.plant_name],
      ["Type", p.plant_type],
      ["Strain", p.strain],
      ["Stage", p.current_stage],
      ["Health", p.current_health_status],
      ["Medium", p.growing_medium],
      ["Added", formatDate(p.created_at || p.date_added)],
    ].filter(([, v]) => v);

    el("plant-info-body").innerHTML = rows
      .map(([k, v]) => `<div class="info-row"><span class="info-label">${window.escapeHtml(k)}</span><span class="info-value">${window.escapeHtml(v)}</span></div>`)
      .join("");
  }

  function renderLinkedDevices() {
    const sensors = plantData.linked_sensors || [];
    const actuators = plantData.linked_actuators || [];
    const body = el("linked-devices-body");

    if (!sensors.length && !actuators.length) {
      body.innerHTML = '<p class="text-muted">No devices linked to this plant.</p>';
      return;
    }

    let html = "";
    if (sensors.length) {
      html += '<h5 class="mb-2"><i class="fas fa-broadcast-tower"></i> Sensors</h5><ul class="device-list">';
      sensors.forEach((s) => {
        const name = s.sensor_name || s.name || `Sensor #${s.sensor_id || s.id}`;
        html += `<li><i class="fas fa-thermometer-half"></i> ${window.escapeHtml(name)}</li>`;
      });
      html += "</ul>";
    }
    if (actuators.length) {
      html += '<h5 class="mb-2 mt-3"><i class="fas fa-bolt"></i> Actuators</h5><ul class="device-list">';
      actuators.forEach((a) => {
        const name = a.actuator_name || a.name || `Actuator #${a.actuator_id || a.id}`;
        html += `<li><i class="fas fa-plug"></i> ${window.escapeHtml(name)}</li>`;
      });
      html += "</ul>";
    }
    body.innerHTML = html;
  }

  function renderRecentEntries() {
    const entries = plantData.recent_entries || [];
    const body = el("recent-entries-body");
    if (!entries.length) {
      body.innerHTML = '<p class="text-muted">No recent activity.</p>';
      return;
    }
    body.innerHTML = `<div class="timeline-compact">${entries.map(renderEntryRow).join("")}</div>`;
  }

  function renderEntryRow(entry) {
    const icon = entryIcon(entry.entry_type);
    const dateStr = formatDate(entry.created_at);
    const typeBadge = badge(entry.entry_type.replace(/_/g, " "), "info");
    const notes = entry.notes ? `<span class="entry-notes">${window.escapeHtml(truncate(entry.notes, 120))}</span>` : "";
    return `
      <div class="timeline-item">
        <div class="timeline-icon"><i class="fas ${icon}"></i></div>
        <div class="timeline-content">
          <div class="d-flex gap-2 align-items-center">${typeBadge} <small class="text-muted">${dateStr}</small></div>
          ${notes}
        </div>
      </div>`;
  }

  function truncate(str, len) {
    return str.length > len ? str.slice(0, len) + "…" : str;
  }

  /* ====== 2. Journal (paginated) ====== */
  async function loadJournalPage(page = 1, type = "") {
    currentPage = page;
    currentFilter = type;
    const body = el("journal-entries-body");
    body.innerHTML = '<p class="text-muted">Loading…</p>';

    try {
      let url = `/journal/entries?page=${page}&per_page=${PER_PAGE}`;
      if (type) url += `&type=${type}`;
      const res = await api(url);
      if (!res.success) throw new Error(res.message);
      renderJournalEntries(res.data);
      renderPagination(res.data);
    } catch (err) {
      body.innerHTML = `<p class="text-danger">Failed to load journal: ${window.escapeHtml(err.message)}</p>`;
    }
  }

  function renderJournalEntries(data) {
    const body = el("journal-entries-body");
    const items = data.items || [];
    if (!items.length) {
      body.innerHTML = '<p class="text-muted">No entries found.</p>';
      return;
    }
    body.innerHTML = `<div class="journal-list">${items.map(renderJournalCard).join("")}</div>`;
  }

  function renderJournalCard(entry) {
    const icon = entryIcon(entry.entry_type);
    const dateStr = formatDate(entry.created_at);
    const healthBadge = entry.health_status
      ? badge(entry.health_status, healthVariant(entry.health_status))
      : "";

    let extraHtml = "";
    if (entry.extra_data && typeof entry.extra_data === "object") {
      const pairs = Object.entries(entry.extra_data)
        .filter(([, v]) => v !== null && v !== "")
        .map(([k, v]) => `<span class="extra-tag">${window.escapeHtml(k.replace(/_/g, " "))}: ${window.escapeHtml(String(v))}</span>`)
        .join(" ");
      if (pairs) extraHtml = `<div class="entry-extra mt-1">${pairs}</div>`;
    }

    return `
      <div class="journal-card" data-entry-id="${entry.id}">
        <div class="journal-card__icon"><i class="fas ${icon}"></i></div>
        <div class="journal-card__body">
          <div class="d-flex gap-2 align-items-center flex-wrap">
            ${badge(entry.entry_type.replace(/_/g, " "), "info")}
            ${healthBadge}
            <small class="text-muted">${dateStr}</small>
          </div>
          ${entry.notes ? `<p class="entry-notes mt-1 mb-0">${window.escapeHtml(entry.notes)}</p>` : ""}
          ${extraHtml}
        </div>
        <div class="journal-card__actions">
          <button class="btn btn-outline-danger btn-xs" data-action="delete-entry" data-entry-id="${entry.id}" title="Delete">
            <i class="fas fa-trash"></i>
          </button>
        </div>
      </div>`;
  }

  function renderPagination(data) {
    const nav = el("journal-pagination");
    const total = data.total_pages || 1;
    const page = data.page || 1;

    if (total <= 1) {
      nav.innerHTML = "";
      return;
    }

    let html = "";
    // Prev
    html += `<button class="btn btn-sm btn-outline-secondary" ${page <= 1 ? "disabled" : ""} data-page="${page - 1}"><i class="fas fa-chevron-left"></i></button>`;

    // Page numbers
    const range = buildPageRange(page, total);
    range.forEach((p) => {
      if (p === "…") {
        html += `<span class="page-ellipsis">…</span>`;
      } else {
        html += `<button class="btn btn-sm ${p === page ? "btn-primary" : "btn-outline-secondary"}" data-page="${p}">${p}</button>`;
      }
    });

    // Next
    html += `<button class="btn btn-sm btn-outline-secondary" ${page >= total ? "disabled" : ""} data-page="${page + 1}"><i class="fas fa-chevron-right"></i></button>`;

    nav.innerHTML = html;
  }

  function buildPageRange(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    const pages = [1];
    if (current > 3) pages.push("…");
    for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) pages.push(i);
    if (current < total - 2) pages.push("…");
    pages.push(total);
    return pages;
  }

  // Delegation for pagination + delete
  document.addEventListener("click", (e) => {
    const pageBtn = e.target.closest("[data-page]");
    if (pageBtn && !pageBtn.disabled) {
      loadJournalPage(parseInt(pageBtn.dataset.page, 10), currentFilter);
      return;
    }

    const delBtn = e.target.closest('[data-action="delete-entry"]');
    if (delBtn) {
      deleteEntry(parseInt(delBtn.dataset.entryId, 10));
    }
  });

  // Type filter
  el("journal-type-filter")?.addEventListener("change", (e) => {
    loadJournalPage(1, e.target.value);
  });

  /* ====== 3. Analytics ====== */
  async function loadAnalytics() {
    try {
      const [wateringRes, summaryRes] = await Promise.all([
        api("/journal/watering-history?days=90"),
        api("/journal/summary"),
      ]);

      if (wateringRes.success) renderWateringChart(wateringRes.data);
      if (summaryRes.success) {
        renderHealthTrendChart(summaryRes.data);
        renderJournalSummary(summaryRes.data);
      }
    } catch (err) {
      console.error("Analytics load error:", err);
    }
  }

  function renderWateringChart(data) {
    const entries = data.entries || [];
    if (!entries.length) {
      el("watering-chart-card")
        ?.querySelector(".card-body")
        ?.insertAdjacentHTML("afterbegin", '<p class="text-muted">No watering data.</p>');
      return;
    }

    const labels = entries.map((e) => formatDate(e.created_at));
    const amounts = entries.map((e) => {
      if (e.extra_data && e.extra_data.amount_ml) return e.extra_data.amount_ml;
      return 0;
    });

    const ctx = el("watering-chart")?.getContext("2d");
    if (!ctx) return;

    if (wateringChart) { wateringChart.destroy(); wateringChart = null; }
    wateringChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Water (ml)",
            data: amounts,
            backgroundColor: "rgba(54, 162, 235, 0.6)",
            borderColor: "rgba(54, 162, 235, 1)",
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, title: { display: true, text: "ml" } } },
      },
    });
  }

  function renderHealthTrendChart(summary) {
    const trend = summary.health_trend;
    if (!trend || !["improving", "declining", "stable"].includes(trend)) {
      return;
    }

    // Build simplified health scores from type counts over last 30d
    const typeCounts = summary.last_30d_counts || {};
    const labels = Object.keys(typeCounts);
    const values = Object.values(typeCounts);

    if (!labels.length) return;

    const ctx = el("health-trend-chart")?.getContext("2d");
    if (!ctx) return;

    if (healthChart) { healthChart.destroy(); healthChart = null; }
    healthChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels.map((l) => l.replace(/_/g, " ")),
        datasets: [
          {
            data: values,
            backgroundColor: [
              "#4caf50", "#2196f3", "#ff9800", "#f44336", "#9c27b0",
              "#00bcd4", "#795548", "#607d8b", "#e91e63", "#3f51b5",
            ],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom" },
          title: { display: true, text: `Health Trend: ${trend}` },
        },
      },
    });
  }

  function renderJournalSummary(summary) {
    const body = el("journal-summary-body");
    const counts = summary.entry_type_counts || {};
    const lastDates = summary.last_entry_dates || {};

    let html = '<div class="summary-grid">';
    for (const [type, count] of Object.entries(counts)) {
      const last = lastDates[type] ? formatDate(lastDates[type]) : "Never";
      html += `
        <div class="summary-item">
          <i class="fas ${entryIcon(type)} summary-icon"></i>
          <div>
            <strong>${window.escapeHtml(type.replace(/_/g, " "))}</strong>
            <div class="text-muted small">${count} entries · Last: ${last}</div>
          </div>
        </div>`;
    }
    html += "</div>";

    if (summary.watering_frequency) {
      html += `<div class="mt-3"><strong>Avg watering interval:</strong> ${summary.watering_frequency.avg_interval_days?.toFixed(1) ?? "—"} days</div>`;
    }

    body.innerHTML = html;
  }

  /* ====== 4. Stage Management ====== */
  async function loadStageTimeline() {
    try {
      const res = await api("/journal/stage-timeline");
      if (!res.success) throw new Error(res.message);
      renderStageInfo();
      renderStageTimeline(res.data.timeline || []);
    } catch (err) {
      el("stage-timeline-body").innerHTML = `<p class="text-danger">Failed: ${window.escapeHtml(err.message)}</p>`;
    }
  }

  function renderStageInfo() {
    if (!plantData) return;
    const info = plantData.stage_info || {};
    const body = el("stage-info-body");
    body.innerHTML = `
      <div class="info-row"><span class="info-label">Current Stage</span><span class="info-value">${window.escapeHtml(info.current_stage || "—")}</span></div>
      <div class="info-row"><span class="info-label">Days in Stage</span><span class="info-value">${info.days_in_stage ?? "—"}</span></div>
      <div class="info-row"><span class="info-label">Active Plant</span><span class="info-value">${info.is_active_plant ? "Yes" : "No"}</span></div>
    `;
  }

  function renderStageTimeline(timeline) {
    const body = el("stage-timeline-body");
    if (!timeline.length) {
      body.innerHTML = '<p class="text-muted">No stage changes recorded.</p>';
      return;
    }
    body.innerHTML = `<div class="timeline-compact">${timeline
      .map(
        (t) => `
      <div class="timeline-item">
        <div class="timeline-icon"><i class="fas fa-layer-group"></i></div>
        <div class="timeline-content">
          <strong>${window.escapeHtml(t.notes || "Stage change")}</strong>
          <small class="text-muted d-block">${formatDate(t.created_at)}</small>
        </div>
      </div>`
      )
      .join("")}</div>`;
  }

  // Stage extension form
  el("stage-extend-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const days = parseInt(el("extend-days").value, 10);
    const reason = el("extend-reason").value;

    if (days < 1 || days > 5) {
      window.showNotification("Please enter between 1 and 5 days.", "warning");
      return;
    }

    try {
      const res = await api("/stage/extend", {
        method: "POST",
        body: JSON.stringify({ extend_days: days, reason }),
      });

      const resultEl = el("extend-result");
      resultEl.hidden = false;

      if (res.success) {
        resultEl.innerHTML = `<div class="alert alert-success">${window.escapeHtml(res.data.message)}</div>`;
        // Refresh stage info
        loadDetail();
        loadStageTimeline();
      } else {
        resultEl.innerHTML = `<div class="alert alert-danger">${window.escapeHtml(res.message || "Extension failed")}</div>`;
      }
    } catch (err) {
      el("extend-result").hidden = false;
      el("extend-result").innerHTML = `<div class="alert alert-danger">${window.escapeHtml(err.message)}</div>`;
    }
  });

  /* ====== 5. Add Journal Entry ====== */
  el("btn-add-journal-entry")?.addEventListener("click", () => {
    el("add-entry-modal").hidden = false;
    updateEntryFormFields();
  });

  // Close modal
  document.querySelectorAll("[data-dismiss='modal']").forEach((btn) => {
    btn.addEventListener("click", () => {
      el("add-entry-modal").hidden = true;
    });
  });

  el("new-entry-type")?.addEventListener("change", updateEntryFormFields);

  function updateEntryFormFields() {
    const type = el("new-entry-type").value;
    const container = el("entry-form-fields");
    let html = "";

    switch (type) {
      case "watering":
        html = `
          <div class="mb-3">
            <label class="form-label">Amount (ml)</label>
            <input type="number" id="field-amount-ml" class="form-control" min="0" step="1" placeholder="250">
          </div>
          <div class="mb-3">
            <label class="form-label">Method</label>
            <select id="field-method" class="form-select">
              <option value="manual">Manual</option>
              <option value="drip">Drip</option>
              <option value="spray">Spray</option>
              <option value="bottom_feed">Bottom Feed</option>
              <option value="automated">Automated</option>
            </select>
          </div>`;
        break;
      case "observation":
        html = `
          <div class="mb-3">
            <label class="form-label">Observation Type</label>
            <select id="field-obs-type" class="form-select">
              <option value="general">General</option>
              <option value="health">Health</option>
              <option value="growth">Growth</option>
              <option value="pest">Pest</option>
              <option value="disease">Disease</option>
            </select>
          </div>
          <div class="mb-3">
            <label class="form-label">Health Status</label>
            <select id="field-health-status" class="form-select">
              <option value="">— No change —</option>
              <option value="healthy">Healthy</option>
              <option value="stressed">Stressed</option>
              <option value="diseased">Diseased</option>
            </select>
          </div>`;
        break;
      case "pruning":
        html = `
          <div class="mb-3">
            <label class="form-label">Pruning Type</label>
            <select id="field-pruning-type" class="form-select">
              <option value="topping">Topping</option>
              <option value="lollipopping">Lollipopping</option>
              <option value="defoliation">Defoliation</option>
              <option value="lst">LST</option>
              <option value="scrog">ScrOG</option>
              <option value="other">Other</option>
            </select>
          </div>`;
        break;
      case "transplant":
        html = `
          <div class="mb-3">
            <label class="form-label">From Container</label>
            <input type="text" id="field-from-container" class="form-control" placeholder="e.g. 1gal pot">
          </div>
          <div class="mb-3">
            <label class="form-label">To Container</label>
            <input type="text" id="field-to-container" class="form-control" placeholder="e.g. 5gal pot">
          </div>
          <div class="mb-3">
            <label class="form-label">New Soil Mix</label>
            <input type="text" id="field-new-soil" class="form-control" placeholder="e.g. coco/perlite 70/30">
          </div>`;
        break;
      case "environmental_adjustment":
        html = `
          <div class="mb-3">
            <label class="form-label">Parameter</label>
            <input type="text" id="field-parameter" class="form-control" placeholder="e.g. fan_speed, light_intensity">
          </div>
          <div class="mb-3">
            <label class="form-label">Old Value</label>
            <input type="text" id="field-old-value" class="form-control">
          </div>
          <div class="mb-3">
            <label class="form-label">New Value</label>
            <input type="text" id="field-new-value" class="form-control">
          </div>`;
        break;
      default:
        html = "";
    }
    container.innerHTML = html;
  }

  el("btn-save-entry")?.addEventListener("click", async () => {
    const type = el("new-entry-type").value;
    const notes = el("new-entry-notes").value;
    let endpoint = "";
    let body = {};

    switch (type) {
      case "watering":
        endpoint = "/journal/watering";
        body = {
          amount_ml: parseFloat(el("field-amount-ml")?.value) || null,
          method: el("field-method")?.value || "manual",
          notes,
        };
        break;
      case "observation":
        // Use existing observation endpoint
        endpoint = "/health/observations";
        body = {
          observation_type: el("field-obs-type")?.value || "general",
          health_status: el("field-health-status")?.value || null,
          notes,
        };
        break;
      case "pruning":
        endpoint = "/journal/pruning";
        body = { pruning_type: el("field-pruning-type")?.value || "other", notes };
        break;
      case "transplant":
        endpoint = "/journal/transplant";
        body = {
          from_container: el("field-from-container")?.value || "",
          to_container: el("field-to-container")?.value || "",
          new_soil_mix: el("field-new-soil")?.value || null,
          notes,
        };
        break;
      case "environmental_adjustment":
        endpoint = "/journal/environmental-adjustment";
        body = {
          parameter: el("field-parameter")?.value || "",
          old_value: el("field-old-value")?.value || "",
          new_value: el("field-new-value")?.value || "",
          notes,
        };
        break;
      case "note":
      case "nutrient":
        // Use existing journal endpoints
        endpoint = type === "note" ? "/journal/note" : "/journal/nutrient";
        body = { notes };
        break;
      default:
        window.showNotification("Unsupported entry type", "warning");
        return;
    }

    try {
      const res = await api(endpoint, {
        method: "POST",
        body: JSON.stringify(body),
      });

      if (res.success) {
        el("add-entry-modal").hidden = true;
        el("new-entry-notes").value = "";
        loadJournalPage(currentPage, currentFilter);
        loadDetail(); // refresh KPIs
      } else {
        window.showNotification(res.message || "Failed to save entry", "error");
      }
    } catch (err) {
      window.showNotification("Error: " + err.message, "error");
    }
  });

  /* ====== 6. Delete Entry ====== */
  async function deleteEntry(entryId) {
    if (!confirm("Delete this journal entry?")) return;
    try {
      const res = await api(`/journal/${entryId}`, { method: "DELETE" });
      if (res.success) {
        loadJournalPage(currentPage, currentFilter);
        loadDetail();
      } else {
        window.showNotification(res.message || "Delete failed", "error");
      }
    } catch (err) {
      window.showNotification("Error: " + err.message, "error");
    }
  }

  /* ====== INIT ====== */
  loadDetail();
  loadJournalPage(1);
})();
