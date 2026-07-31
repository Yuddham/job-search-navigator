(() => {
  const STATUS_VALUES = ["not_contacted", "messaged", "responded", "interviewing", "closed"];
  let currentTailoringReportId = null;

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
  }

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
        `${result.counts.skills} skill(s), ${result.counts.certifications} certification(s).` +
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
  }

  // ---- Search Criteria ----

  document.getElementById("criteriaForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      label: val("criteriaLabel"),
      keywords: val("criteriaKeywords"),
      target_roles: val("criteriaRoles"),
      industries: val("criteriaIndustries"),
      locations: val("criteriaLocations"),
    };
    await api("/api/criteria", { method: "POST", body: payload });
    e.target.reset();
    loadCriteria();
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
        loadCriteria();
      });
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

  document.getElementById("manualListingForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      title: val("listingTitle"),
      company: val("listingCompany"),
      location: val("listingLocation"),
      url: val("listingUrl"),
      description: val("listingDescription"),
      notes: val("listingNotes"),
    };
    await api("/api/jobs/manual", { method: "POST", body: payload });
    e.target.reset();
    loadManualListings();
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
        loadManualListings();
      });
      container.appendChild(node);
    });
  }

  // ---- Contacts & Leads ----

  populateStatusSelect(document.getElementById("contactStatus"));
  populateStatusSelect(document.getElementById("leadStatus"));

  document.getElementById("contactForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: val("contactName"),
      linkedin_url: val("contactLinkedin"),
      company: val("contactCompany"),
      email: val("contactEmail"),
      phone: val("contactPhone"),
      notes: val("contactNotes"),
      status: document.getElementById("contactStatus").value,
    };
    await api("/api/contacts", { method: "POST", body: payload });
    e.target.reset();
    populateStatusSelect(document.getElementById("contactStatus"));
    loadContacts();
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
        loadContacts();
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

  document.getElementById("leadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const contactId = document.getElementById("leadContactSelect").value;
    const payload = {
      job_url: val("leadJobUrl"),
      company: val("leadCompany"),
      recruiter_name: val("leadRecruiterName"),
      recruiter_contact_id: contactId ? parseInt(contactId, 10) : null,
      notes: val("leadNotes"),
      status: document.getElementById("leadStatus").value,
    };
    await api("/api/leads", { method: "POST", body: payload });
    e.target.reset();
    populateStatusSelect(document.getElementById("leadStatus"));
    loadLeads();
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
        loadLeads();
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
    if (!url) return;
    try {
      await api("/api/target-jobs/fetch-url", { method: "POST", body: { url } });
      document.getElementById("targetJobUrl").value = "";
      loadTargetJobs();
      loadJobOptions();
    } catch (err) {
      window.alert("Fetch failed: " + err.message);
    }
  });

  document.getElementById("targetJobManualForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      company: val("manualJobCompany"),
      title: val("manualJobTitle"),
      location: val("manualJobLocation"),
      source_url: val("manualJobSourceUrl"),
      jd_text: document.getElementById("manualJobText").value.trim(),
    };
    await api("/api/target-jobs/manual", { method: "POST", body: payload });
    e.target.reset();
    loadTargetJobs();
    loadJobOptions();
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

  // ---- Salary Insights ----

  document.getElementById("runSalaryEstimateBtn").addEventListener("click", async () => {
    const what = val("salaryWhat");
    const where = val("salaryWhere");
    const resultEl = document.getElementById("salaryResult");
    resultEl.textContent = "Estimating…";
    try {
      const est = await api(`/api/salary/estimate?what=${encodeURIComponent(what)}&where=${encodeURIComponent(where)}`);
      let html = "";
      if (est.warning) {
        html += `<p class="status error">${escapeHtml(est.warning)}</p>`;
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
        `<td>${new Date(e.created_at).toLocaleDateString()}</td>`;
      body.appendChild(tr);
    });
  }

  // ---- Help ----

  async function loadHelp() {
    const text = await api("/api/help/manual");
    document.getElementById("helpManualText").textContent = text;
  }

  // ---- Init ----

  onTabShown("profile");
})();
