(() => {
  const STATUS_VALUES = ["not_contacted", "messaged", "responded", "interviewing", "closed"];
  let currentTailoringReportId = null;
  let lastJobSearchResults = null;
  let lastTailoringReport = null;
  let lastSimilarCompanies = [];

  function val(id) {
    return document.getElementById(id).value.trim();
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }

  function formatINR(n) {
    if (n === null || n === undefined) return "?";
    return Math.round(n).toLocaleString("en-IN");
  }

  async function api(path, options = {}) {
    const opts = { headers: {}, ...options };
    if (opts.body && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, opts);
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const err = await res.json();
        detail = err.detail || detail;
      } catch (e) {
        /* ignore -- non-JSON error body */
      }
      throw new Error(detail);
    }
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) return res.json();
    return res.text();
  }

  // ---- Export-as-text-file ----
  // Uses the File System Access API (Chrome/Edge) so the browser's own native
  // Save As dialog lets the user pick the location and filename. Falls back
  // to a plain download (Firefox/Safari, which don't support that API yet).
  async function saveTextFile(suggestedName, content) {
    if (window.showSaveFilePicker) {
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName,
          types: [{ description: "Text file", accept: { "text/plain": [".txt"] } }],
        });
        const writable = await handle.createWritable();
        await writable.write(content);
        await writable.close();
        return "saved";
      } catch (err) {
        if (err.name === "AbortError") return "cancelled";
        throw err;
      }
    }
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = suggestedName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return "saved";
  }

  function wireExport(buttonId, statusId, suggestedName, buildText) {
    const btn = document.getElementById(buttonId);
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const statusEl = document.getElementById(statusId);
      try {
        const text = await buildText();
        if (!text || !text.trim()) {
          if (statusEl) { statusEl.textContent = "Nothing to export yet."; statusEl.className = "status"; }
          return;
        }
        const outcome = await saveTextFile(suggestedName, text);
        if (statusEl) {
          statusEl.textContent = outcome === "saved" ? "Exported." : "Export cancelled.";
          statusEl.className = "status";
        }
      } catch (err) {
        if (statusEl) { statusEl.textContent = "Export failed: " + err.message; statusEl.className = "status error"; }
      }
    });
  }

  function exportHeader(title) {
    return `${title}\nExported from Navigrad on ${new Date().toLocaleString()}\n${"=".repeat(60)}\n\n`;
  }

  function populateStatusSelect(select, current) {
    select.innerHTML = "";
    STATUS_VALUES.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s.replace("_", " ");
      if (s === current) opt.selected = true;
      select.appendChild(opt);
    });
  }

  // ---- Tab switching ----

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
  });

  function activateTab(tab) {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === tab));
    onTabShown(tab);
  }

  function onTabShown(tab) {
    if (tab === "profile") loadProfile();
    if (tab === "criteria") loadCriteria();
    if (tab === "jobsearch") loadCriteriaOptions();
    if (tab === "manuallistings") loadManualListings();
    if (tab === "contacts") {
      loadContacts();
      loadLeads();
    }
    if (tab === "cvats") loadCvs();
    if (tab === "tailor") {
      loadTargetJobs();
      loadCvOptions();
      loadJobOptions();
    }
    if (tab === "salary") loadSalaryHistory();
    if (tab === "help") loadHelp();
    if (tab === "settings") loadSettings();
  }

  // ---- Deep-link support: ?tab=<id> lets the landing page's radar blips
  // (public/landing/hud/v5-scan/hero.html) open straight into a given tab.
  // Arriving this way is a focused, single-tab view -- the other tabs are
  // hidden and a back button (top-left) returns to the radar. Opening the
  // app normally (no ?tab=) keeps the full nav, unchanged. ----
  (() => {
    const requestedTab = new URLSearchParams(location.search).get("tab");
    const targetBtn = requestedTab && document.querySelector(`.tab-btn[data-tab="${requestedTab}"]`);
    if (!targetBtn) return;

    activateTab(requestedTab);
    document.querySelector(".tabs").classList.add("focused-hidden");

    const backBtn = document.getElementById("backToScan");
    const label = document.getElementById("focusedTabLabel");
    backBtn.hidden = false;
    label.hidden = false;
    label.textContent = targetBtn.textContent;
  })();

  // ---- Profile ----

  document.getElementById("profileUploadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById("profileZipInput");
    const statusEl = document.getElementById("profileStatus");
    if (!fileInput.files.length) return;
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    statusEl.textContent = "Uploading…";
    statusEl.className = "status";
    try {
      const result = await api("/api/profile/upload", { method: "POST", body: formData });
      statusEl.textContent =
        `Imported ${result.counts.positions} position(s), ${result.counts.education} education, ` +
        `${result.counts.skills} skill(s), ${result.counts.certifications} certification(s), ` +
        `${result.counts.projects} project(s).` +
        (result.warnings.length ? " Warnings: " + result.warnings.join(" ") : "");
      renderProfile(result.summary);
    } catch (err) {
      statusEl.textContent = "Upload failed: " + err.message;
      statusEl.className = "status error";
    }
  });

  document.getElementById("clearProfileBtn").addEventListener("click", async () => {
    await api("/api/profile", { method: "DELETE" });
    document.getElementById("profileSummary").hidden = true;
    document.getElementById("profileStatus").textContent = "Profile cleared.";
  });

  async function loadProfile() {
    const summary = await api("/api/profile");
    renderProfile(summary);
  }

  function renderProfile(summary) {
    const panel = document.getElementById("profileSummary");
    const hasData = summary.basics || (summary.positions && summary.positions.length) || (summary.skills && summary.skills.length);
    panel.hidden = !hasData;
    if (!hasData) return;

    const basics = summary.basics || {};
    const name = [basics.first_name, basics.last_name].filter(Boolean).join(" ") || "(no name)";
    document.getElementById("profileBasics").innerHTML =
      `<p><strong>${escapeHtml(name)}</strong><br>${escapeHtml(basics.headline || "")}<br>` +
      `<span class="listing-meta">${escapeHtml([basics.industry, basics.location].filter(Boolean).join(" · "))}</span></p>`;

    const skillsEl = document.getElementById("profileSkills");
    skillsEl.innerHTML = "";
    (summary.skills || []).forEach((s) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = s;
      skillsEl.appendChild(chip);
    });

    const positionsEl = document.getElementById("profilePositions");
    positionsEl.innerHTML = "";
    (summary.positions || []).forEach((p) => {
      const li = document.createElement("li");
      li.textContent = `${p.title || ""} at ${p.company || ""} (${p.started_on || "?"} – ${p.ended_on || "?"})`;
      positionsEl.appendChild(li);
    });

    const eduEl = document.getElementById("profileEducation");
    eduEl.innerHTML = "";
    (summary.education || []).forEach((e) => {
      const li = document.createElement("li");
      li.textContent = `${e.degree_name || ""}${e.field_of_study ? " (" + e.field_of_study + ")" : ""} – ${e.school_name || ""}`;
      eduEl.appendChild(li);
    });

    const certEl = document.getElementById("profileCertifications");
    certEl.innerHTML = "";
    (summary.certifications || []).forEach((c) => {
      const li = document.createElement("li");
      li.textContent = `${c.name || ""}${c.authority ? " – " + c.authority : ""}`;
      certEl.appendChild(li);
    });

    const projectsEl = document.getElementById("profileProjects");
    projectsEl.innerHTML = "";
    (summary.projects || []).forEach((p) => {
      const li = document.createElement("li");
      let text = p.title || "";
      if (p.started_on || p.finished_on) text += ` (${p.started_on || "?"} – ${p.finished_on || "?"})`;
      if (p.description) text += `: ${p.description}`;
      li.textContent = text;
      if (p.url) {
        const link = document.createElement("a");
        link.href = p.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = " [link]";
        li.appendChild(link);
      }
      projectsEl.appendChild(li);
    });
  }

  // ---- Search Criteria ----

  let editingCriteriaId = null;

  function resetCriteriaForm() {
    editingCriteriaId = null;
    document.getElementById("criteriaForm").reset();
    document.getElementById("criteriaSubmitBtn").textContent = "Save criteria";
    document.getElementById("cancelCriteriaEditBtn").hidden = true;
  }

  document.getElementById("cancelCriteriaEditBtn").addEventListener("click", resetCriteriaForm);

  document.getElementById("criteriaForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("criteriaStatus");
    const payload = {
      label: val("criteriaLabel"),
      keywords: val("criteriaKeywords"),
      target_roles: val("criteriaRoles"),
      industries: val("criteriaIndustries"),
      locations: val("criteriaLocations"),
    };
    try {
      if (editingCriteriaId) {
        await api(`/api/criteria/${editingCriteriaId}`, { method: "PUT", body: payload });
        statusEl.textContent = "Criteria updated.";
      } else {
        await api("/api/criteria", { method: "POST", body: payload });
        statusEl.textContent = "Criteria saved.";
      }
      statusEl.className = "status";
      resetCriteriaForm();
      loadCriteria();
    } catch (err) {
      statusEl.textContent = "Save failed: " + err.message;
      statusEl.className = "status error";
    }
  });

  async function loadCriteria() {
    const list = await api("/api/criteria");
    const container = document.getElementById("criteriaList");
    container.innerHTML = "";
    const tpl = document.getElementById("criteriaCardTemplate");
    list.forEach((c) => {
      const node = tpl.content.cloneNode(true);
      node.querySelector(".criteria-label").textContent = c.label;
      node.querySelector(".criteria-details").textContent = [c.keywords, c.target_roles, c.industries, c.locations]
        .filter(Boolean)
        .join(" · ");
      node.querySelector(".delete-btn").addEventListener("click", async () => {
        await api(`/api/criteria/${c.id}`, { method: "DELETE" });
        if (editingCriteriaId === c.id) resetCriteriaForm();
        loadCriteria();
      });
      const editBtn = node.querySelector(".edit-btn");
      if (editBtn) {
        editBtn.addEventListener("click", () => {
          editingCriteriaId = c.id;
          document.getElementById("criteriaLabel").value = c.label || "";
          document.getElementById("criteriaKeywords").value = c.keywords || "";
          document.getElementById("criteriaRoles").value = c.target_roles || "";
          document.getElementById("criteriaIndustries").value = c.industries || "";
          document.getElementById("criteriaLocations").value = c.locations || "";
          document.getElementById("criteriaSubmitBtn").textContent = "Update criteria";
          document.getElementById("cancelCriteriaEditBtn").hidden = false;
        });
      }
      container.appendChild(node);
    });
  }

  // ---- Job Search ----

  async function loadCriteriaOptions() {
    const list = await api("/api/criteria");
    const select = document.getElementById("jobSearchCriteriaSelect");
    select.innerHTML = '<option value="">(no saved criteria – ad hoc)</option>';
    list.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.label;
      select.appendChild(opt);
    });
  }

  document.getElementById("runJobSearchBtn").addEventListener("click", async () => {
    const select = document.getElementById("jobSearchCriteriaSelect");
    const warningsEl = document.getElementById("jobSearchWarnings");
    const resultsEl = document.getElementById("jobSearchResults");
    warningsEl.textContent = "Searching…";
    warningsEl.className = "status";
    resultsEl.innerHTML = "";
    try {
      const qs = select.value ? `?criteria_id=${select.value}` : "";
      const data = await api(`/api/jobs/search${qs}`);
      lastJobSearchResults = data;
      warningsEl.textContent = data.warnings.join(" ");
      const tpl = document.getElementById("listingCardTemplate");
      data.results.forEach((r) => {
        const node = tpl.content.cloneNode(true);
        node.querySelector(".listing-title").textContent = r.title;
        node.querySelector(".listing-score").textContent = `Score ${r.score}`;
        node.querySelector(".listing-meta").textContent = [r.company, r.location, r.source].filter(Boolean).join(" · ");
        const chipsEl = node.querySelector(".matched-chips");
        [...r.matched_skills, ...r.matched_keywords].forEach((k) => {
          const chip = document.createElement("span");
          chip.className = "chip";
          chip.textContent = k;
          chipsEl.appendChild(chip);
        });
        const link = node.querySelector(".listing-link");
        if (r.url) {
          link.href = r.url;
        } else {
          link.remove();
        }
        resultsEl.appendChild(node);
      });
      if (!data.results.length) {
        resultsEl.innerHTML = '<p class="status">No results yet – add manual listings or configure Adzuna.</p>';
      }
    } catch (err) {
      warningsEl.textContent = "Search failed: " + err.message;
      warningsEl.className = "status error";
    }
  });

  // ---- Manual Listings ----

  let editingListingId = null;

  function resetListingForm() {
    editingListingId = null;
    document.getElementById("manualListingForm").reset();
    document.getElementById("listingSubmitBtn").textContent = "Add listing";
    document.getElementById("cancelListingEditBtn").hidden = true;
  }

  document.getElementById("cancelListingEditBtn").addEventListener("click", resetListingForm);

  document.getElementById("fetchListingUrlBtn").addEventListener("click", async () => {
    const url = val("listingUrl");
    const statusEl = document.getElementById("listingFetchStatus");
    if (!url) {
      statusEl.textContent = "Paste a URL first.";
      statusEl.className = "status error";
      return;
    }
    statusEl.textContent = "Fetching…";
    statusEl.className = "status";
    try {
      const preview = await api("/api/fetch-url-preview", { method: "POST", body: { url } });
      if (preview.status === "ok") {
        if (preview.title) document.getElementById("listingTitle").value = preview.title;
        if (preview.company) document.getElementById("listingCompany").value = preview.company;
        if (preview.location) document.getElementById("listingLocation").value = preview.location;
        if (preview.jd_text) document.getElementById("listingDescription").value = preview.jd_text;
        statusEl.textContent = "Auto-filled from the page. Review before saving.";
      } else {
        statusEl.textContent = preview.warning || "Couldn't fetch this page -- fill in the fields manually.";
        statusEl.className = "status error";
      }
    } catch (err) {
      statusEl.textContent = "Fetch failed: " + err.message;
      statusEl.className = "status error";
    }
  });

  document.getElementById("manualListingForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("manualListingStatus");
    const payload = {
      title: val("listingTitle"),
      company: val("listingCompany"),
      location: val("listingLocation"),
      url: val("listingUrl"),
      description: val("listingDescription"),
      notes: val("listingNotes"),
    };
    try {
      if (editingListingId) {
        await api(`/api/jobs/manual/${editingListingId}`, { method: "PUT", body: payload });
        statusEl.textContent = "Listing updated.";
      } else {
        await api("/api/jobs/manual", { method: "POST", body: payload });
        statusEl.textContent = "Listing added.";
      }
      statusEl.className = "status";
      resetListingForm();
      loadManualListings();
    } catch (err) {
      statusEl.textContent = "Save failed: " + err.message;
      statusEl.className = "status error";
    }
  });

  async function loadManualListings() {
    const list = await api("/api/jobs/manual");
    const container = document.getElementById("manualListingsList");
    container.innerHTML = "";
    const tpl = document.getElementById("manualListingCardTemplate");
    list.forEach((l) => {
      const node = tpl.content.cloneNode(true);
      node.querySelector(".listing-title").textContent = l.title;
      node.querySelector(".listing-meta").textContent = [l.company, l.location].filter(Boolean).join(" · ");
      node.querySelector(".listing-description").textContent = l.description || "";
      node.querySelector(".delete-btn").addEventListener("click", async () => {
        await api(`/api/jobs/manual/${l.id}`, { method: "DELETE" });
        if (editingListingId === l.id) resetListingForm();
        loadManualListings();
      });
      node.querySelector(".edit-btn").addEventListener("click", () => {
        editingListingId = l.id;
        document.getElementById("listingTitle").value = l.title || "";
        document.getElementById("listingCompany").value = l.company || "";
        document.getElementById("listingLocation").value = l.location || "";
        document.getElementById("listingUrl").value = l.url || "";
        document.getElementById("listingDescription").value = l.description || "";
        document.getElementById("listingNotes").value = l.notes || "";
        document.getElementById("listingSubmitBtn").textContent = "Update listing";
        document.getElementById("cancelListingEditBtn").hidden = false;
      });
      container.appendChild(node);
    });
  }

  // ---- Contacts & Leads ----

  populateStatusSelect(document.getElementById("contactStatus"));
  populateStatusSelect(document.getElementById("leadStatus"));

  let editingContactId = null;

  function resetContactForm() {
    editingContactId = null;
    document.getElementById("contactForm").reset();
    populateStatusSelect(document.getElementById("contactStatus"));
    document.getElementById("contactSubmitBtn").textContent = "Add contact";
    document.getElementById("cancelContactEditBtn").hidden = true;
  }

  document.getElementById("cancelContactEditBtn").addEventListener("click", resetContactForm);

  document.getElementById("contactForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("contactFormStatus");
    const payload = {
      name: val("contactName"),
      linkedin_url: val("contactLinkedin"),
      company: val("contactCompany"),
      email: val("contactEmail"),
      phone: val("contactPhone"),
      notes: val("contactNotes"),
      status: document.getElementById("contactStatus").value,
    };
    try {
      if (editingContactId) {
        await api(`/api/contacts/${editingContactId}`, { method: "PUT", body: payload });
        statusEl.textContent = "Contact updated.";
      } else {
        await api("/api/contacts", { method: "POST", body: payload });
        statusEl.textContent = "Contact added.";
      }
      statusEl.className = "status";
      resetContactForm();
      loadContacts();
    } catch (err) {
      statusEl.textContent = "Save failed: " + err.message;
      statusEl.className = "status error";
    }
  });

  async function loadContacts() {
    const list = await api("/api/contacts");
    const container = document.getElementById("contactsList");
    container.innerHTML = "";
    const tpl = document.getElementById("contactCardTemplate");
    list.forEach((c) => {
      const node = tpl.content.cloneNode(true);
      node.querySelector(".contact-name").textContent = c.name;
      node.querySelector(".contact-meta").textContent = [c.company, c.linkedin_url, c.email, c.phone]
        .filter(Boolean)
        .join(" · ");
      const statusSelect = node.querySelector(".contact-status-select");
      populateStatusSelect(statusSelect, c.status);
      statusSelect.addEventListener("change", async () => {
        await api(`/api/contacts/${c.id}`, { method: "PUT", body: { ...c, status: statusSelect.value } });
      });
      node.querySelector(".delete-btn").addEventListener("click", async () => {
        await api(`/api/contacts/${c.id}`, { method: "DELETE" });
        if (editingContactId === c.id) resetContactForm();
        loadContacts();
      });
      node.querySelector(".edit-btn").addEventListener("click", () => {
        editingContactId = c.id;
        document.getElementById("contactName").value = c.name || "";
        document.getElementById("contactLinkedin").value = c.linkedin_url || "";
        document.getElementById("contactCompany").value = c.company || "";
        document.getElementById("contactEmail").value = c.email || "";
        document.getElementById("contactPhone").value = c.phone || "";
        document.getElementById("contactNotes").value = c.notes || "";
        populateStatusSelect(document.getElementById("contactStatus"), c.status);
        document.getElementById("contactSubmitBtn").textContent = "Update contact";
        document.getElementById("cancelContactEditBtn").hidden = false;
      });
      container.appendChild(node);
    });
    loadLeadContactOptions(list);
  }

  async function loadLeadContactOptions(list) {
    const contacts = list || (await api("/api/contacts"));
    const select = document.getElementById("leadContactSelect");
    const previous = select.value;
    select.innerHTML = '<option value="">(no linked contact)</option>';
    contacts.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.name;
      select.appendChild(opt);
    });
    select.value = previous;
  }

  let editingLeadId = null;

  function resetLeadForm() {
    editingLeadId = null;
    document.getElementById("leadForm").reset();
    populateStatusSelect(document.getElementById("leadStatus"));
    document.getElementById("leadSubmitBtn").textContent = "Add lead";
    document.getElementById("cancelLeadEditBtn").hidden = true;
  }

  document.getElementById("cancelLeadEditBtn").addEventListener("click", resetLeadForm);

  document.getElementById("fetchLeadUrlBtn").addEventListener("click", async () => {
    const url = val("leadJobUrl");
    const statusEl = document.getElementById("leadFetchStatus");
    if (!url) {
      statusEl.textContent = "Paste a URL first.";
      statusEl.className = "status error";
      return;
    }
    statusEl.textContent = "Fetching…";
    statusEl.className = "status";
    try {
      const preview = await api("/api/fetch-url-preview", { method: "POST", body: { url } });
      if (preview.status === "ok") {
        if (preview.company) document.getElementById("leadCompany").value = preview.company;
        statusEl.textContent = preview.company
          ? "Auto-filled company. Recruiter name usually isn't in the posting -- add it manually if you know it."
          : "Fetched the page but couldn't identify a company -- fill in manually.";
      } else {
        statusEl.textContent = preview.warning || "Couldn't fetch this page -- fill in the fields manually.";
        statusEl.className = "status error";
      }
    } catch (err) {
      statusEl.textContent = "Fetch failed: " + err.message;
      statusEl.className = "status error";
    }
  });

  document.getElementById("leadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("leadFormStatus");
    const contactId = document.getElementById("leadContactSelect").value;
    const payload = {
      job_url: val("leadJobUrl"),
      company: val("leadCompany"),
      recruiter_name: val("leadRecruiterName"),
      recruiter_contact_id: contactId ? parseInt(contactId, 10) : null,
      notes: val("leadNotes"),
      status: document.getElementById("leadStatus").value,
    };
    try {
      if (editingLeadId) {
        await api(`/api/leads/${editingLeadId}`, { method: "PUT", body: payload });
        statusEl.textContent = "Lead updated.";
      } else {
        await api("/api/leads", { method: "POST", body: payload });
        statusEl.textContent = "Lead added.";
      }
      statusEl.className = "status";
      resetLeadForm();
      loadLeads();
    } catch (err) {
      statusEl.textContent = "Save failed: " + err.message;
      statusEl.className = "status error";
    }
  });

  async function loadLeads() {
    const list = await api("/api/leads");
    const container = document.getElementById("leadsList");
    container.innerHTML = "";
    const tpl = document.getElementById("leadCardTemplate");
    list.forEach((l) => {
      const node = tpl.content.cloneNode(true);
      node.querySelector(".lead-company").textContent = l.company || "(unknown company)";
      node.querySelector(".lead-meta").textContent = l.recruiter_name ? `Recruiter: ${l.recruiter_name}` : "";
      const link = node.querySelector(".lead-link");
      if (l.job_url) {
        link.href = l.job_url;
      } else {
        link.remove();
      }
      const statusSelect = node.querySelector(".lead-status-select");
      populateStatusSelect(statusSelect, l.status);
      statusSelect.addEventListener("change", async () => {
        await api(`/api/leads/${l.id}`, { method: "PUT", body: { ...l, status: statusSelect.value } });
      });
      node.querySelector(".delete-btn").addEventListener("click", async () => {
        await api(`/api/leads/${l.id}`, { method: "DELETE" });
        if (editingLeadId === l.id) resetLeadForm();
        loadLeads();
      });
      node.querySelector(".edit-btn").addEventListener("click", () => {
        editingLeadId = l.id;
        document.getElementById("leadJobUrl").value = l.job_url || "";
        document.getElementById("leadCompany").value = l.company || "";
        document.getElementById("leadRecruiterName").value = l.recruiter_name || "";
        document.getElementById("leadContactSelect").value = l.recruiter_contact_id || "";
        document.getElementById("leadNotes").value = l.notes || "";
        populateStatusSelect(document.getElementById("leadStatus"), l.status);
        document.getElementById("leadSubmitBtn").textContent = "Update lead";
        document.getElementById("cancelLeadEditBtn").hidden = false;
      });
      container.appendChild(node);
    });
  }

  // ---- CV & ATS ----

  document.getElementById("cvUploadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById("cvFileInput");
    const statusEl = document.getElementById("cvUploadStatus");
    if (!fileInput.files.length) return;
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    statusEl.textContent = "Uploading…";
    statusEl.className = "status";
    try {
      const result = await api("/api/cv/upload", { method: "POST", body: formData });
      statusEl.textContent = `Uploaded. ATS score: ${result.ats_report.overall_score}/100.`;
      showAtsReport(result.ats_report);
      loadCvs();
    } catch (err) {
      statusEl.textContent = "Upload failed: " + err.message;
      statusEl.className = "status error";
    }
  });

  async function loadCvs() {
    const list = await api("/api/cv");
    const container = document.getElementById("cvList");
    container.innerHTML = "";
    const tpl = document.getElementById("cvCardTemplate");
    list.forEach((cv) => {
      const node = tpl.content.cloneNode(true);
      node.querySelector(".cv-filename").textContent = cv.original_filename + (cv.is_active ? " (active)" : "");
      node.querySelector(".cv-meta").textContent =
        `${cv.file_type.toUpperCase()} · uploaded ${new Date(cv.uploaded_at).toLocaleString()}`;
      node.querySelector(".activate-cv-btn").addEventListener("click", async () => {
        await api(`/api/cv/${cv.id}/activate`, { method: "POST" });
        loadCvs();
      });
      node.querySelector(".view-ats-btn").addEventListener("click", async () => {
        const report = await api(`/api/cv/${cv.id}/ats-report`);
        showAtsReport(report);
      });
      node.querySelector(".delete-btn").addEventListener("click", async () => {
        await api(`/api/cv/${cv.id}`, { method: "DELETE" });
        loadCvs();
      });
      container.appendChild(node);
    });
  }

  function showAtsReport(report) {
    const panel = document.getElementById("atsReportPanel");
    panel.hidden = false;
    document.getElementById("atsSummary").textContent = report.summary;
    const fill = panel.querySelector(".score-meter-fill");
    fill.style.width = report.overall_score + "%";
    fill.style.background =
      report.overall_score >= 80 ? "var(--success)" : report.overall_score >= 50 ? "var(--warning)" : "var(--danger)";
    panel.querySelector(".score-meter-label").textContent = `${report.overall_score}/100`;

    const body = document.getElementById("atsChecklistBody");
    body.innerHTML = "";
    report.checklist.forEach((item) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${escapeHtml(item.label)}</td>` +
        `<td><span class="badge badge-${item.status}">${item.status}</span></td>` +
        `<td>${escapeHtml(item.detail)}</td>`;
      body.appendChild(tr);
    });
  }

  // ---- Tailor CV ----

  document.getElementById("fetchTargetJobBtn").addEventListener("click", async () => {
    const url = val("targetJobUrl");
    const statusEl = document.getElementById("targetJobStatus");
    if (!url) return;
    statusEl.textContent = "Fetching…";
    statusEl.className = "status";
    try {
      const job = await api("/api/target-jobs/fetch-url", { method: "POST", body: { url } });
      document.getElementById("targetJobUrl").value = "";
      statusEl.textContent = job.fetch_status === "ok" ? "Fetched successfully." : job.fetch_warning || "Could not fetch this page.";
      statusEl.className = job.fetch_status === "ok" ? "status" : "status error";
      loadTargetJobs();
      loadJobOptions();
    } catch (err) {
      statusEl.textContent = "Fetch failed: " + err.message;
      statusEl.className = "status error";
    }
  });

  document.getElementById("targetJobManualForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("targetJobStatus");
    const payload = {
      company: val("manualJobCompany"),
      title: val("manualJobTitle"),
      location: val("manualJobLocation"),
      source_url: val("manualJobSourceUrl"),
      jd_text: document.getElementById("manualJobText").value.trim(),
    };
    try {
      await api("/api/target-jobs/manual", { method: "POST", body: payload });
      statusEl.textContent = "Job description saved.";
      statusEl.className = "status";
      e.target.reset();
      loadTargetJobs();
      loadJobOptions();
    } catch (err) {
      statusEl.textContent = "Save failed: " + err.message;
      statusEl.className = "status error";
    }
  });

  async function loadTargetJobs() {
    const list = await api("/api/target-jobs");
    const container = document.getElementById("targetJobsList");
    container.innerHTML = "";
    const tpl = document.getElementById("targetJobCardTemplate");
    list.forEach((j) => {
      const node = tpl.content.cloneNode(true);
      node.querySelector(".target-job-title").textContent = j.title || "(untitled)";
      node.querySelector(".target-job-meta").textContent = [j.company, j.location, j.source_type, j.fetch_status]
        .filter(Boolean)
        .join(" · ");
      node.querySelector(".target-job-warning").textContent = j.fetch_warning || "";
      node.querySelector(".delete-btn").addEventListener("click", async () => {
        await api(`/api/target-jobs/${j.id}`, { method: "DELETE" });
        loadTargetJobs();
        loadJobOptions();
      });
      container.appendChild(node);
    });
  }

  async function loadCvOptions() {
    const list = await api("/api/cv");
    const select = document.getElementById("tailorCvSelect");
    select.innerHTML = "";
    list.forEach((cv) => {
      const opt = document.createElement("option");
      opt.value = cv.id;
      opt.textContent = cv.original_filename;
      if (cv.is_active) opt.selected = true;
      select.appendChild(opt);
    });
  }

  async function loadJobOptions() {
    const list = await api("/api/target-jobs");
    const select = document.getElementById("tailorJobSelect");
    select.innerHTML = "";
    list.forEach((j) => {
      const opt = document.createElement("option");
      opt.value = j.id;
      opt.textContent = j.title ? `${j.title}${j.company ? " – " + j.company : ""}` : `Job #${j.id}`;
      select.appendChild(opt);
    });
  }

  document.getElementById("runTailoringBtn").addEventListener("click", async () => {
    const cvId = document.getElementById("tailorCvSelect").value;
    const jobId = document.getElementById("tailorJobSelect").value;
    if (!cvId || !jobId) {
      window.alert("Upload a CV and add a target job first.");
      return;
    }
    const report = await api("/api/tailoring/analyze", {
      method: "POST",
      body: { cv_document_id: parseInt(cvId, 10), target_job_id: parseInt(jobId, 10) },
    });
    currentTailoringReportId = report.id;
    showTailoringReport(report);
  });

  function showTailoringReport(report) {
    lastTailoringReport = report;
    const panel = document.getElementById("tailoringResult");
    panel.hidden = false;
    document.getElementById("tailoringScore").textContent = `Match score: ${report.match_score}%`;
    document.getElementById("tailoringKeySkills").textContent = report.key_skills_line || "";

    const matchedEl = document.getElementById("matchedKeywordChips");
    matchedEl.innerHTML = "";
    report.matched_keywords.forEach((m) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = `${m.keyword} (${m.cv_sections.join(", ")})`;
      matchedEl.appendChild(chip);
    });

    const missingEl = document.getElementById("missingKeywordChips");
    missingEl.innerHTML = "";
    report.missing_keywords.forEach((m) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = m.keyword;
      missingEl.appendChild(chip);
    });

    renderDownloadLinks(report);
  }

  function renderDownloadLinks(report) {
    const container = document.getElementById("tailoringDownloads");
    container.innerHTML = "";
    Object.keys(report.generated_files || {}).forEach((format) => {
      const a = document.createElement("a");
      a.href = `/api/tailoring/${report.id}/download?format=${format}`;
      a.textContent = `Download ${format}`;
      a.className = "listing-link";
      a.style.marginRight = "1rem";
      container.appendChild(a);
    });
  }

  document.getElementById("generateMarkdownBtn").addEventListener("click", () => generateTailored("markdown"));
  document.getElementById("generateDocxBtn").addEventListener("click", () => generateTailored("docx"));

  async function generateTailored(format) {
    if (!currentTailoringReportId) return;
    const report = await api(`/api/tailoring/${currentTailoringReportId}/generate`, {
      method: "POST",
      body: { format },
    });
    showTailoringReport(report);
  }

  // ---- Similar Companies & Positions (Apollo: company + job-postings data only) ----

  document.getElementById("findSimilarCompaniesBtn").addEventListener("click", async () => {
    const jobId = document.getElementById("tailorJobSelect").value;
    const statusEl = document.getElementById("similarCompaniesStatus");
    const listEl = document.getElementById("similarCompaniesList");
    listEl.innerHTML = "";
    if (!jobId) {
      statusEl.textContent = "Add/select a target job first.";
      statusEl.className = "status error";
      return;
    }
    statusEl.textContent = "Searching…";
    statusEl.className = "status";
    try {
      const job = await api(`/api/target-jobs/${jobId}`);
      const keyword = job.company || job.title || "";
      const location = job.location || "";
      const resp = await api(
        `/api/apollo/similar-companies?keyword=${encodeURIComponent(keyword)}&location=${encodeURIComponent(location)}`
      );
      if (resp.warning) {
        statusEl.textContent = resp.warning;
        statusEl.className = "status error";
      } else {
        statusEl.textContent = `Found ${resp.companies.length} compan${resp.companies.length === 1 ? "y" : "ies"}.`;
      }
      lastSimilarCompanies = resp.companies.map((c) => ({ ...c, postings: null }));
      const tpl = document.getElementById("apolloCompanyCardTemplate");
      resp.companies.forEach((c) => {
        const node = tpl.content.cloneNode(true);
        node.querySelector(".apollo-company-name").textContent = c.name || "(unnamed company)";
        node.querySelector(".apollo-company-meta").textContent = [
          c.industry,
          c.location,
          c.employee_count ? `${c.employee_count} employees` : null,
        ]
          .filter(Boolean)
          .join(" · ");
        const postingsList = node.querySelector(".apollo-postings-list");
        node.querySelector(".view-postings-btn").addEventListener("click", async (evt) => {
          evt.target.textContent = "Loading…";
          try {
            const postingsResp = await api(`/api/apollo/job-postings?organization_id=${encodeURIComponent(c.id)}`);
            const tracked = lastSimilarCompanies.find((sc) => sc.id === c.id);
            if (tracked) tracked.postings = postingsResp.warning ? null : postingsResp.postings;
            postingsList.innerHTML = "";
            if (postingsResp.warning) {
              postingsList.innerHTML = `<p class="status error">${escapeHtml(postingsResp.warning)}</p>`;
            } else if (!postingsResp.postings.length) {
              postingsList.innerHTML = '<p class="status">No open postings found via Apollo for this company.</p>';
            } else {
              const itemTpl = document.getElementById("apolloPostingItemTemplate");
              postingsResp.postings.forEach((p) => {
                const item = itemTpl.content.cloneNode(true);
                item.querySelector(".apollo-posting-title").textContent = p.title || "(untitled role)";
                const link = item.querySelector(".apollo-posting-link");
                if (p.url) {
                  link.href = p.url;
                } else {
                  link.remove();
                }
                item.querySelector(".add-as-listing-btn").addEventListener("click", async () => {
                  await api("/api/jobs/manual", {
                    method: "POST",
                    body: {
                      title: p.title || "",
                      company: c.name || "",
                      location: p.location || "",
                      url: p.url || "",
                      description: "",
                      notes: "Added from Apollo similar-companies search",
                    },
                  });
                  window.alert("Added to Manual Listings.");
                });
                postingsList.appendChild(item);
              });
            }
          } finally {
            evt.target.textContent = "View job postings";
          }
        });
        listEl.appendChild(node);
      });
    } catch (err) {
      statusEl.textContent = "Search failed: " + err.message;
      statusEl.className = "status error";
    }
  });

  // ---- Salary Insights ----

  document.getElementById("runSalaryEstimateBtn").addEventListener("click", async () => {
    const what = val("salaryWhat");
    const where = val("salaryWhere");
    const useExperience = document.getElementById("salaryUseExperience").checked;
    const resultEl = document.getElementById("salaryResult");
    resultEl.textContent = "Estimating…";
    try {
      const est = await api(
        `/api/salary/estimate?what=${encodeURIComponent(what)}&where=${encodeURIComponent(where)}&use_profile_experience=${useExperience}`
      );
      let html = "";
      if (est.warning) {
        html += `<p class="status error">${escapeHtml(est.warning)}</p>`;
      }
      if (est.role_query && est.role_query !== what) {
        html += `<p class="listing-meta">Queried as: "${escapeHtml(est.role_query)}" (adjusted using your profile's inferred experience level)</p>`;
      }
      if (est.ctc_low !== null && est.ctc_low !== undefined) {
        html += `<p><strong>CTC range:</strong> ₹${formatINR(est.ctc_low)} – ₹${formatINR(est.ctc_high)} (median ~₹${formatINR(est.ctc_median)})</p>`;
        html += `<p><strong>Estimated in-hand range:</strong> ₹${formatINR(est.inhand_low)} – ₹${formatINR(est.inhand_high)}</p>`;
      }
      html += `<p class="listing-meta">${escapeHtml(est.disclaimer)}</p>`;
      resultEl.innerHTML = html;
      loadSalaryHistory();
    } catch (err) {
      resultEl.innerHTML = `<p class="status error">${escapeHtml(err.message)}</p>`;
    }
  });

  async function loadSalaryHistory() {
    const list = await api("/api/salary/estimates");
    const body = document.getElementById("salaryHistoryBody");
    body.innerHTML = "";
    list.forEach((e) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${escapeHtml(e.role_query)}</td><td>${escapeHtml(e.location_query)}</td>` +
        `<td>${e.ctc_low !== null && e.ctc_low !== undefined ? formatINR(e.ctc_low) + " – " + formatINR(e.ctc_high) : "-"}</td>` +
        `<td>${e.inhand_low !== null && e.inhand_low !== undefined ? formatINR(e.inhand_low) + " – " + formatINR(e.inhand_high) : "-"}</td>` +
        `<td>${new Date(e.created_at).toLocaleDateString()}</td>` +
        `<td><button class="delete-btn" title="Delete">&times;</button></td>`;
      tr.querySelector(".delete-btn").addEventListener("click", async () => {
        await api(`/api/salary/estimates/${e.id}`, { method: "DELETE" });
        loadSalaryHistory();
      });
      body.appendChild(tr);
    });
  }

  // ---- Help ----

  async function loadHelp() {
    const text = await api("/api/help/manual");
    const el = document.getElementById("helpManualText");
    if (window.marked) {
      el.innerHTML = marked.parse(text);
    } else {
      // marked.js failed to load (e.g. offline) -- plain text beats nothing.
      el.textContent = text;
    }
  }

  // ---- Settings ----

  function setStatusDot(id, status) {
    const dot = document.getElementById(id);
    if (!dot) return;
    dot.classList.remove("connected", "error");
    if (!status.configured) {
      dot.title = "Not configured";
    } else if (status.connected) {
      dot.classList.add("connected");
      dot.title = status.message || "Connected";
    } else {
      dot.classList.add("error");
      dot.title = status.message || "Connection failed";
    }
  }

  async function loadSettings() {
    const keys = await api("/api/settings/keys");
    document.getElementById("settingsAdzunaAppId").value = keys.adzuna_app_id || "";
    document.getElementById("settingsAdzunaAppKey").value = keys.adzuna_app_key || "";
    document.getElementById("settingsApolloApiKey").value = keys.apollo_api_key || "";
    document.getElementById("settingsApifyApiToken").value = keys.apify_api_token || "";
    refreshSettingsStatus();
    loadAppKey();
    loadLinkedInAccountStatus();
  }

  async function loadAppKey() {
    const data = await api("/api/settings/app-key");
    document.getElementById("settingsAppKey").value = data.app_key || "";
    document.getElementById("settingsMcpUrl").value = data.mcp_url || "";
  }

  async function refreshSettingsStatus() {
    const statusEl = document.getElementById("settingsStatus");
    statusEl.textContent = "Checking connections…";
    statusEl.className = "status";
    try {
      const status = await api("/api/settings/status");
      setStatusDot("dot-adzuna-id", status.adzuna);
      setStatusDot("dot-adzuna-key", status.adzuna);
      setStatusDot("dot-apollo", status.apollo);
      setStatusDot("dot-apify", status.apify);
      statusEl.textContent = "Status updated.";
    } catch (err) {
      statusEl.textContent = err.message;
      statusEl.className = "status error";
    }
  }

  document.getElementById("refreshSettingsStatusBtn").addEventListener("click", refreshSettingsStatus);

  document.querySelectorAll(".toggle-visibility-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.target);
      const isHidden = input.type === "password";
      input.type = isHidden ? "text" : "password";
      btn.textContent = isHidden ? "Hide" : "Show";
    });
  });

  document.getElementById("settingsForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("settingsSaveStatus");
    statusEl.textContent = "Saving…";
    statusEl.className = "status";
    try {
      await api("/api/settings/keys", {
        method: "PUT",
        body: {
          adzuna_app_id: val("settingsAdzunaAppId"),
          adzuna_app_key: val("settingsAdzunaAppKey"),
          apollo_api_key: val("settingsApolloApiKey"),
          apify_api_token: val("settingsApifyApiToken"),
        },
      });
      statusEl.textContent = "Saved.";
      refreshSettingsStatus();
    } catch (err) {
      statusEl.textContent = err.message;
      statusEl.className = "status error";
    }
  });

  function copyToClipboard(text, statusEl, label) {
    navigator.clipboard.writeText(text).then(
      () => { statusEl.textContent = `${label} copied.`; statusEl.className = "status"; },
      () => { statusEl.textContent = `Couldn't copy ${label.toLowerCase()} -- copy it manually.`; statusEl.className = "status error"; },
    );
  }

  document.getElementById("copyAppKeyBtn").addEventListener("click", () => {
    copyToClipboard(val("settingsAppKey"), document.getElementById("appKeyStatus"), "App Key");
  });

  document.getElementById("copyMcpUrlBtn").addEventListener("click", () => {
    copyToClipboard(val("settingsMcpUrl"), document.getElementById("appKeyStatus"), "MCP server URL");
  });

  document.getElementById("regenerateAppKeyBtn").addEventListener("click", async () => {
    const statusEl = document.getElementById("appKeyStatus");
    if (!confirm("Regenerate the App Key? Any tool (Claude Code, etc.) already connected with the old key will stop working until you update it with the new one.")) {
      return;
    }
    statusEl.textContent = "Regenerating…";
    statusEl.className = "status";
    try {
      const data = await api("/api/settings/app-key/regenerate", { method: "POST" });
      document.getElementById("settingsAppKey").value = data.app_key || "";
      document.getElementById("settingsMcpUrl").value = data.mcp_url || "";
      statusEl.textContent = "New App Key generated.";
    } catch (err) {
      statusEl.textContent = err.message;
      statusEl.className = "status error";
    }
  });

  // ---- LinkedIn Account (optional, off by default -- see linkedin_mcp_client.py) ----

  let linkedinPollTimer = null;

  function renderLinkedInStatus(s) {
    document.getElementById("linkedinEnabledToggle").checked = !!s.enabled;
    const statusEl = document.getElementById("linkedinAccountStatus");
    const btn = document.getElementById("linkedinConnectBtn");

    if (!s.tooling_available) {
      statusEl.textContent = "Not available -- install git and uv first (links above), then reopen this tab.";
      statusEl.className = "status error";
      btn.disabled = true;
      return;
    }
    btn.disabled = false;

    if (s.error) {
      statusEl.textContent = "Connection attempt failed: " + s.error;
      statusEl.className = "status error";
    } else if (s.connecting) {
      statusEl.textContent = "Installing / waiting for LinkedIn login in the opened browser window…";
      statusEl.className = "status";
    } else if (s.connected) {
      statusEl.textContent = "Browser session set up. If searches come back empty or limited, click Connect again to (re-)log in -- this app can't verify LinkedIn login state precisely from the outside.";
      statusEl.className = "status";
    } else if (s.installed) {
      statusEl.textContent = "Installed but not set up yet -- click Connect and log in.";
      statusEl.className = "status";
    } else {
      statusEl.textContent = "Not installed yet.";
      statusEl.className = "status";
    }

    if (s.connecting) {
      if (!linkedinPollTimer) linkedinPollTimer = setInterval(loadLinkedInAccountStatus, 3000);
    } else if (linkedinPollTimer) {
      clearInterval(linkedinPollTimer);
      linkedinPollTimer = null;
    }
  }

  async function loadLinkedInAccountStatus() {
    try {
      const s = await api("/api/settings/linkedin-account");
      renderLinkedInStatus(s);
    } catch (err) {
      document.getElementById("linkedinAccountStatus").textContent = err.message;
      document.getElementById("linkedinAccountStatus").className = "status error";
    }
  }

  document.getElementById("linkedinEnabledToggle").addEventListener("change", async (e) => {
    try {
      const s = await api("/api/settings/linkedin-account/enable", { method: "POST", body: { enabled: e.target.checked } });
      renderLinkedInStatus(s);
    } catch (err) {
      document.getElementById("linkedinAccountStatus").textContent = err.message;
      document.getElementById("linkedinAccountStatus").className = "status error";
      e.target.checked = !e.target.checked;
    }
  });

  document.getElementById("linkedinConnectBtn").addEventListener("click", async () => {
    const statusEl = document.getElementById("linkedinAccountStatus");
    if (!confirm(
      "This will install eliasbiondo/linkedin-mcp-server (if not already) and open a real LinkedIn " +
      "login page in its own browser window for you to sign in. Using your LinkedIn account this way " +
      "may violate LinkedIn's Terms of Service and could get it suspended or banned. Continue?"
    )) {
      return;
    }
    statusEl.textContent = "Starting…";
    statusEl.className = "status";
    try {
      const s = await api("/api/settings/linkedin-account/connect", { method: "POST" });
      renderLinkedInStatus(s);
    } catch (err) {
      statusEl.textContent = err.message;
      statusEl.className = "status error";
    }
  });

  // ---- Exports (each opens a native Save As dialog via saveTextFile) ----

  wireExport("exportProfileBtn", "profileExportStatus", "profile.txt", async () => {
    const summary = await api("/api/profile");
    const basics = summary.basics || {};
    const name = [basics.first_name, basics.last_name].filter(Boolean).join(" ") || "(no name)";
    let text = exportHeader("LINKEDIN PROFILE");
    text += `${name}\n`;
    if (basics.headline) text += `${basics.headline}\n`;
    text += [basics.industry, basics.location].filter(Boolean).join(" · ") + "\n\n";

    text += "SKILLS\n" + (summary.skills || []).map((s) => `- ${s}`).join("\n") + "\n\n";

    text +=
      "EXPERIENCE\n" +
      (summary.positions || [])
        .map((p) => `- ${p.title || ""} at ${p.company || ""} (${p.started_on || "?"} – ${p.ended_on || "?"})`)
        .join("\n") +
      "\n\n";

    text +=
      "EDUCATION\n" +
      (summary.education || [])
        .map((e) => `- ${e.degree_name || ""}${e.field_of_study ? " (" + e.field_of_study + ")" : ""} – ${e.school_name || ""}`)
        .join("\n") +
      "\n\n";

    text +=
      "CERTIFICATIONS\n" +
      (summary.certifications || []).map((c) => `- ${c.name || ""}${c.authority ? " – " + c.authority : ""}`).join("\n") +
      "\n\n";

    text +=
      "PROJECTS\n" +
      (summary.projects || [])
        .map((p) => {
          let line = `- ${p.title || ""}`;
          if (p.started_on || p.finished_on) line += ` (${p.started_on || "?"} – ${p.finished_on || "?"})`;
          if (p.description) line += `: ${p.description}`;
          if (p.url) line += ` [${p.url}]`;
          return line;
        })
        .join("\n") +
      "\n";

    return text;
  });

  wireExport("exportCriteriaBtn", "criteriaExportStatus", "search-criteria.txt", async () => {
    const list = await api("/api/criteria");
    let text = exportHeader("SAVED SEARCH CRITERIA");
    list.forEach((c, i) => {
      text += `${i + 1}. ${c.label}\n`;
      if (c.keywords) text += `   Keywords: ${c.keywords}\n`;
      if (c.target_roles) text += `   Target roles: ${c.target_roles}\n`;
      if (c.industries) text += `   Industries: ${c.industries}\n`;
      if (c.locations) text += `   Locations: ${c.locations}\n`;
      text += "\n";
    });
    return text;
  });

  wireExport("exportJobSearchBtn", "jobSearchExportStatus", "job-search-results.txt", () => {
    if (!lastJobSearchResults) return "";
    let text = exportHeader("JOB SEARCH RESULTS");
    if (lastJobSearchResults.warnings && lastJobSearchResults.warnings.length) {
      text += `Warnings: ${lastJobSearchResults.warnings.join(" ")}\n\n`;
    }
    lastJobSearchResults.results.forEach((r, i) => {
      text += `${i + 1}. ${r.title} — Score ${r.score}\n`;
      text += `   Company: ${r.company || "-"}\n`;
      text += `   Location: ${r.location || "-"}\n`;
      text += `   Source: ${r.source || "-"}\n`;
      const matched = [...(r.matched_skills || []), ...(r.matched_keywords || [])];
      if (matched.length) text += `   Matched: ${matched.join(", ")}\n`;
      if (r.url) text += `   URL: ${r.url}\n`;
      text += "\n";
    });
    return text;
  });

  wireExport("exportManualListingsBtn", "manualListingsExportStatus", "manual-listings.txt", async () => {
    const list = await api("/api/jobs/manual");
    let text = exportHeader("MANUAL LISTINGS");
    list.forEach((l, i) => {
      text += `${i + 1}. ${l.title}\n`;
      text += `   Company: ${l.company || "-"}\n`;
      text += `   Location: ${l.location || "-"}\n`;
      if (l.url) text += `   URL: ${l.url}\n`;
      if (l.description) text += `   Description: ${l.description}\n`;
      if (l.notes) text += `   Notes: ${l.notes}\n`;
      text += "\n";
    });
    return text;
  });

  wireExport("exportContactsBtn", "contactsExportStatus", "contacts.txt", async () => {
    const list = await api("/api/contacts");
    let text = exportHeader("CONTACTS");
    list.forEach((c, i) => {
      text += `${i + 1}. ${c.name}\n`;
      if (c.company) text += `   Company: ${c.company}\n`;
      if (c.linkedin_url) text += `   LinkedIn: ${c.linkedin_url}\n`;
      if (c.email) text += `   Email: ${c.email}\n`;
      if (c.phone) text += `   Phone: ${c.phone}\n`;
      text += `   Status: ${(c.status || "").replace("_", " ")}\n`;
      if (c.notes) text += `   Notes: ${c.notes}\n`;
      text += "\n";
    });
    return text;
  });

  wireExport("exportLeadsBtn", "leadsExportStatus", "job-leads.txt", async () => {
    const list = await api("/api/leads");
    let text = exportHeader("JOB LEADS");
    list.forEach((l, i) => {
      text += `${i + 1}. ${l.company || "(unknown company)"}\n`;
      if (l.job_url) text += `   URL: ${l.job_url}\n`;
      if (l.recruiter_name) text += `   Recruiter: ${l.recruiter_name}\n`;
      text += `   Status: ${(l.status || "").replace("_", " ")}\n`;
      if (l.notes) text += `   Notes: ${l.notes}\n`;
      text += "\n";
    });
    return text;
  });

  wireExport("exportCvsBtn", "cvExportStatus", "cv-ats-summary.txt", async () => {
    const list = await api("/api/cv");
    let text = exportHeader("CV & ATS SUMMARY");
    for (const cv of list) {
      text += `${cv.original_filename}${cv.is_active ? " (active)" : ""}\n`;
      text += `   Type: ${cv.file_type.toUpperCase()}, uploaded ${new Date(cv.uploaded_at).toLocaleString()}\n`;
      try {
        const report = await api(`/api/cv/${cv.id}/ats-report`);
        text += `   ATS score: ${report.overall_score}/100\n`;
        text += `   Summary: ${report.summary}\n`;
      } catch (e) {
        text += `   ATS report unavailable.\n`;
      }
      text += "\n";
    }
    return text;
  });

  wireExport("exportTargetJobsBtn", "targetJobsExportStatus", "target-jobs.txt", async () => {
    const list = await api("/api/target-jobs");
    let text = exportHeader("TARGET JOBS");
    list.forEach((j, i) => {
      text += `${i + 1}. ${j.title || "(untitled)"}\n`;
      text += `   ${[j.company, j.location, j.source_type, j.fetch_status].filter(Boolean).join(" · ")}\n`;
      if (j.fetch_warning) text += `   Warning: ${j.fetch_warning}\n`;
      if (j.source_url) text += `   Source URL: ${j.source_url}\n`;
      if (j.jd_text) text += `   Description:\n     ${j.jd_text.replace(/\n/g, "\n     ")}\n`;
      text += "\n";
    });
    return text;
  });

  wireExport("exportTailoringBtn", "tailoringExportStatus", "cv-tailoring-analysis.txt", () => {
    if (!lastTailoringReport) return "";
    const r = lastTailoringReport;
    let text = exportHeader("CV TAILORING ANALYSIS");
    text += `Match score: ${r.match_score}%\n`;
    if (r.key_skills_line) text += `Key skills line: ${r.key_skills_line}\n`;
    text += "\nMATCHED KEYWORDS\n";
    (r.matched_keywords || []).forEach((m) => {
      text += `- ${m.keyword} (found in: ${(m.cv_sections || []).join(", ")})\n`;
    });
    text += "\nMISSING KEYWORDS (suggested gaps)\n";
    (r.missing_keywords || []).forEach((m) => {
      text += `- ${m.keyword}\n`;
    });
    return text;
  });

  wireExport("exportSimilarCompaniesBtn", "similarCompaniesExportStatus", "similar-companies.txt", () => {
    if (!lastSimilarCompanies.length) return "";
    let text = exportHeader("SIMILAR COMPANIES & POSITIONS");
    lastSimilarCompanies.forEach((c, i) => {
      text += `${i + 1}. ${c.name || "(unnamed company)"}\n`;
      text += `   ${[c.industry, c.location, c.employee_count ? c.employee_count + " employees" : null].filter(Boolean).join(" · ")}\n`;
      if (c.postings === null) {
        text += `   Open postings: not loaded yet -- click "View job postings" first\n`;
      } else if (!c.postings.length) {
        text += `   Open postings: none found via Apollo\n`;
      } else {
        text += `   Open postings:\n`;
        c.postings.forEach((p) => {
          text += `     - ${p.title || "(untitled role)"}${p.location ? " (" + p.location + ")" : ""}${p.url ? " " + p.url : ""}\n`;
        });
      }
      text += "\n";
    });
    return text;
  });

  wireExport("exportSalaryBtn", "salaryExportStatus", "salary-estimates.txt", async () => {
    const list = await api("/api/salary/estimates");
    let text = exportHeader("PAST SALARY ESTIMATES");
    list.forEach((e, i) => {
      text += `${i + 1}. ${e.role_query} — ${e.location_query || "(no location)"}\n`;
      if (e.ctc_low !== null && e.ctc_low !== undefined) {
        text += `   CTC range: ₹${formatINR(e.ctc_low)} – ₹${formatINR(e.ctc_high)} (median ~₹${formatINR(e.ctc_median)})\n`;
        text += `   In-hand range: ₹${formatINR(e.inhand_low)} – ₹${formatINR(e.inhand_high)}\n`;
      }
      text += `   Date: ${new Date(e.created_at).toLocaleDateString()}\n\n`;
    });
    return text;
  });

  // ---- Init ----

  onTabShown("profile");
})();
