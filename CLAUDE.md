# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

This is `job-search-navigator` — a local job-search assistant for the Indian market (Python/FastAPI, plain HTML/CSS/JS frontend). Ranks live Adzuna India job listings and Apollo company/job-postings data (plus manually-pasted listings) against a profile parsed from a LinkedIn data export, runs a deterministic ATS-compliance check on an uploaded CV and a keyword-gap "tailoring" tool (mechanical reordering only — never LLM-generated text), estimates CTC/in-hand pay from Adzuna's aggregate salary data adjusted for inferred experience level, and provides a manual contact/lead tracker for outreach. Deliberately avoids any automated scraping of LinkedIn or other job sites — see `USER_MANUAL.md` for the full feature walkthrough and the reasoning behind that constraint (also summarized in the scope note at the bottom of this file). Windows `.exe` packaging (PyInstaller + pywebview) is a planned later phase, not yet built. A dedicated visual-design pass via Higgsfield is planned next, on top of the current functional-but-minimal UI.

This repository was split out of a shared multi-project repo (previously alongside an unrelated `rss-repository` project) via `git subtree split`, preserving full commit history.

## Version control

Commit and push to GitHub regularly as work progresses — after each meaningful, working chunk of change, not just at the end of a session — so in-progress work is never sitting only on disk. Use clean, descriptive commit messages (what changed and why, not "wip" or "updates"). Don't let uncommitted changes pile up across multiple features/fixes in one commit.

## Commands

All commands run from the repo root:

```
py -m venv .venv                          # create a virtual environment (Windows: `py`, not `python`)
.venv\Scripts\activate
pip install -r requirements.txt           # fastapi, uvicorn, pydantic, requests, pdfplumber, pypdf, python-docx, beautifulsoup4, lxml
copy .env.example .env                    # then fill in ADZUNA_APP_ID / ADZUNA_APP_KEY / (optional) APOLLO_API_KEY
uvicorn app.main:app --reload --port 8000  # dev server at http://localhost:8000, data in data/job_search.db
```

There are no lint or test scripts/tooling in this project.

All dependencies are pure-Python wheels with no external binaries or compiled extensions (`pdfplumber`+`pypdf` for PDF, `python-docx` for DOCX, `beautifulsoup4`+`lxml` for HTML parsing) — kept intentionally PyInstaller-freezable for the planned `.exe` packaging phase, even though that phase hasn't been built yet.

**Restart required for backend changes**: everything under `app/` is loaded once at process start. Everything under `public/` (`index.html`, `style.css`, `app.js`) is served via FastAPI's `StaticFiles` and reflects on a plain browser refresh — no restart needed.

**Data path**: `app/config.py` resolves `DB_PATH`/`CV_UPLOAD_DIR`/`TAILORED_OUTPUT_DIR` from `.env` (relative paths resolve against the project root, not `cwd`) — this is deliberate so a future frozen-exe entry point can resolve the same paths identically to `uvicorn` dev mode.

## Architecture

### Data layer (`app/db.py`)
Single local SQLite file (`data/job_search.db`), no ORM — plain `sqlite3` with `CREATE TABLE IF NOT EXISTS` run idempotently at startup. Tables: `profile_*` (parsed LinkedIn export, incl. `profile_projects`), `search_criteria`, `manual_listings`, `contacts` / `job_leads` (manual outreach tracking), `cv_documents` / `cv_ats_reports`, `target_jobs` / `cv_tailoring_reports`, `salary_estimates`.

### Profile ingestion (`app/linkedin_export.py`)
Defensively parses the ZIP from LinkedIn's "Download your data" export (Profile, Positions, Education, Skills, Certifications, Projects CSVs) — case-insensitive filename/column matching, per-row `raw_json` catch-all for unmapped columns, missing files degrade to a warning rather than a crash. Re-upload does a full delete-and-replace of the profile tables (current-snapshot semantics, not a merge).

### Job search (`app/adzuna_client.py`, `app/apollo_client.py`, `app/matching.py`, `app/sources/`)
`adzuna_client.py` wraps Adzuna's India job-search and salary-histogram/history endpoints behind one auth-checked, TTL-cached client. `apollo_client.py` is deliberately scoped to exactly two Apollo endpoints — organization/company search (`POST /organizations/search`) and organization job postings (`GET /organizations/{id}/job_postings`) — nothing else in this codebase touches Apollo's people/contacts/email endpoints (see the scope note below). `sources/adzuna_source.py`, `sources/apollo_source.py`, and `sources/manual_source.py` share a `fetch(conn, criteria)` contract so `routes/jobs.py` can merge all three and let each fail independently — they intentionally run "in tandem" even when results overlap. Apollo results are capped at 10 postings/company to avoid runaway result counts from large companies. `matching.py` is pure, explainable additive scoring (skill/keyword/title-role/location/cert hits against weighted constants at the top of the file) — no I/O, easy to tweak directly.

### CV / ATS (`app/cv_parser.py`, `app/ats_checker.py`)
`cv_parser.py` extracts text/sections/layout metadata from PDF (`pdfplumber` + `pypdf` fallback) and DOCX (`python-docx`, plus a raw-XML scan for text boxes since python-docx doesn't expose them). `ats_checker.py` runs a fixed, deterministic rule checklist (layout, sections, contact info, length, fonts, filename, glyphs) into a weighted 0–100 score — no ML/LLM involved in the check.

### Tailoring (`app/job_fetch.py`, `app/keyword_gap.py`)
`job_fetch.py` makes exactly one GET per user-pasted job URL (own timeout/UA, no retries, no site-specific scraping) preferring JSON-LD `JobPosting` structured data with a heuristic text-extraction fallback; blocked/short results degrade to "please paste the description manually." The same fetch function backs both `/api/target-jobs/fetch-url` (persists a `target_jobs` row, used by Tailor CV) and the preview-only `/api/fetch-url-preview` (used by Manual Listings' and Job Leads' "Fetch & auto-fill" — no side-effect row created). `keyword_gap.py` compares JD keywords against the CV's own tokens and produces a **mechanically** tailored copy (bullet reordering + a "Key Skills Match" line built only from words already in the CV) — deliberately no LLM rewriting anywhere in this path; every word in the output must already exist in the source CV.

### Similar companies (`app/routes/apollo.py`)
On top of the job-search integration, Tailor CV's "Similar Companies & Positions" action calls `apollo_client.search_companies`/`get_job_postings` directly (same two-endpoint scope) using the selected target job's company/location as the query, letting the user add any posting straight to `manual_listings`.

### Experience inference (`app/experience.py`)
Estimates years of experience from the parsed LinkedIn positions' date spans (earliest start to latest end/"Present" — a simple heuristic, no external data) and maps it to a seniority label (entry/mid/senior/lead). `routes/salary.py` prepends this to the Adzuna salary query by default (toggleable via `use_profile_experience`); the actual query used is always returned in `role_query` so the adjustment is never silent.

### Salary estimation (`app/salary_estimator.py`)
Pure calculation over Adzuna's aggregate histogram/history data (interquartile-range CTC estimate, configurable deduction-percentage in-hand heuristic, fixed disclaimer) — deliberately does not scrape individual salary-discussion posts from Glassdoor/AmbitionBox/Reddit or similar; this was asked for twice during the project's requirements-gathering and declined both times for the same reason.

### Routes (`app/routes/`)
One module per domain (`profile.py`, `criteria.py`, `jobs.py`, `contacts.py`, `cv.py`, `tailoring.py`, `salary.py`, `apollo.py`, `help.py`), all registered in `main.py`. Request/response bodies are typed via `app/models.py` Pydantic schemas, which also gives free interactive docs at `/docs`.

### Frontend (`public/`)
A single `index.html` with nine tab-switched views (no framework, no build step, plain `app.js`): Profile, Search Criteria, Job Search, Manual Listings, Contacts & Leads, CV & ATS, Tailor CV, Salary Insights, Help. Talks to the backend purely through `/api/*` JSON endpoints. Visual design is intentionally minimal for now — a dedicated styling pass happens later via Higgsfield once functionality is settled. Manual Listings and Job Leads have a "Fetch & auto-fill" URL field at the top of their forms; Contacts deliberately does not (see scope note below). Manual Listings, Contacts, and Job Leads all support full edit-in-place (not just delete) via an Edit button that repopulates the add-form in an update mode.

### A note on scope (why there's no LinkedIn/people-data scraping anywhere here)
An earlier version of this project's requirements asked for automated LinkedIn scraping (first for recruiter contact emails, then for job postings/recruiter names), then later for Hunter.io/Apollo contact-enrichment integration and Glassdoor-style individual salary-post scraping. All were declined because they either automate a logged-in LinkedIn session (violates LinkedIn's User Agreement, risks the account) or amount to harvesting an identified individual's personal/contact data. What shipped instead: every external network call in this codebase is either (a) a single explicit user-triggered fetch of a URL the user pasted themselves, (b) a documented, keyed public API restricted to business/listing data (Adzuna job+salary data, Apollo company+job-postings data only — never Apollo's people/contact endpoints), or (c) manual entry. Hunter.io isn't integrated at all — it has no job-listing capability, only email-finding, which has no legitimate fit here. Keep this constraint in mind before adding new data sources.
