# Job Search Navigator — User Manual

This is a local, single-user tool for a job search in India. Everything runs on your own
machine; nothing about your profile, CV, or contacts is sent anywhere except the specific
outbound calls described below (Adzuna's API, Apollo's company/job-postings API if
configured, and a single fetch of a URL you paste in yourself). This manual walks through
every tab.

## 1. First-time setup

1. Follow the "Run from source" steps in `README.md` to install dependencies and copy
   `.env.example` to `.env`.
2. Register for a free Adzuna API account at https://developer.adzuna.com/ and create an app.
   You'll get an **App ID** and an **App Key**. Put both into `.env`:
   ```
   ADZUNA_APP_ID=your-app-id
   ADZUNA_APP_KEY=your-app-key
   ```
   Without these, the **Job Search** and **Salary Insights** tabs still work but only show
   manually-added data, with a clear warning explaining why.
3. Optionally, add an Apollo.io API key (Apollo dashboard → Settings → API) to enable the
   **Similar Companies & Positions** feature and Apollo's company-postings results in Job
   Search:
   ```
   APOLLO_API_KEY=your-apollo-api-key
   ```
   Without it, those features just show a clear "not configured" message. See the note in
   section 4 about exactly what this app does and doesn't use Apollo for.
4. Start the app (`uvicorn app.main:app --reload --port 8000`) and open
   http://localhost:8000.

## 2. Profile tab

This is where you import your LinkedIn profile so the app can match jobs against your real
skills, experience, education, and certifications, and infer your experience level for
Salary Insights.

1. On LinkedIn, go to **Settings & Privacy → Data privacy → Get a copy of your data**
   (the Profile tab has this same walkthrough under "How to export your LinkedIn data").
2. Choose **"Want something in particular?"** and check at least: **Profile**, **Positions**,
   **Education**, **Skills**, and **Certifications** (checking more is fine, only these are
   read).
3. Click **Request archive**. LinkedIn emails you a download link once it's ready (usually
   minutes to a few hours).
4. Download the `.zip` from that email link — don't unzip it.
5. In the Profile tab, choose that file and click **Upload**.
6. The app shows how many positions/education/skills/certifications it imported, plus a
   warning for anything it couldn't find (e.g. if you didn't select Certifications on export).
   Re-uploading always replaces the current profile with the new export — it doesn't merge.

## 3. Search Criteria tab

Describe the kind of job you're looking for. You can save multiple named criteria sets (e.g.
one for "Backend India", another for "Product Manager Fintech") and switch between them in
Job Search. Keywords, target roles, industries, and locations all accept comma-separated
lists — leave any of them blank if not relevant. Each saved criteria card has an **Edit**
button so you can update it later without deleting and re-creating it.

## 4. Job Search tab

Pick a saved criteria set (or leave it on "ad hoc" to search with no filter) and click
**Search**. Results are pulled from up to three places and merged into one ranked list:

- **Adzuna's live India job index** (if configured) — broad keyword/location search.
- **Apollo's company + job-postings data** (if configured) — for criteria with an
  "Industries" value set, searches companies matching that industry and lists their open
  roles via Apollo. This runs alongside Adzuna even when results overlap.
- **Manual Listings** you've added yourself (see below).

Each result shows a score and the specific skills/keywords/role/location that matched — this
is exactly how the ranking is computed, not a black-box number. If a source isn't configured
or is temporarily unreachable, you'll see a warning banner, but the other sources (including
your manual listings) still show up and rank normally.

**What this app does and doesn't use Apollo/Hunter for:** only two Apollo endpoints are ever
called anywhere in this codebase — company search and organization job postings. Nothing in
this app calls Apollo's (or any other service's) people-search, contact, or email-finder
endpoints, and Hunter.io isn't integrated at all (it has no job-listing data — it's purely an
email-finding tool, which is out of scope for this project). If you're extending this code,
keep it that way.

## 5. Manual Listings tab

Paste in any listing you find yourself — from Naukri, Indeed, LinkedIn, a company careers
page, wherever. You can either fill in the fields by hand, or paste the listing's URL at the
top of the form and click **Fetch & auto-fill** — the app makes a single request to that page
and tries to fill in title/company/location/description for you (review before saving; it
won't always find everything, especially on sites like LinkedIn that block unauthenticated
requests). Either way it's automatically included in Job Search ranking. Each saved listing
has an **Edit** button to update it later.

## 6. CV & ATS tab

Upload your CV (`.pdf` or `.docx`). The app immediately runs a fully deterministic,
rule-based compliance check — no AI/LLM is involved in this check, so results are
repeatable and explainable. It looks at things like:

- Whether text could be extracted at all (catches scanned/image-only PDFs)
- Multi-column layouts, tables, and text boxes (many ATS parsers mishandle these)
- Embedded images/photos
- Whether standard section headings (Experience, Education, Skills, Summary) are present
- Whether an email and phone number are detectable
- Content stuck in headers/footers (some ATS parsers ignore these entirely)
- CV length, font variety, filename, and unusual glyphs/icons

Each check shows **pass**, **warning**, or **fail** with a plain-English explanation, rolled
into an overall 0–100 score. You can upload multiple CVs, mark one **active**, and re-run the
check at any time without re-uploading.

## 7. Tailor CV tab

This helps you adapt your CV to a specific job **without ever inventing content**.

1. **Add a target job**: paste a job URL (LinkedIn/Indeed/Naukri/anywhere) at the top and
   click **Fetch**. The app makes exactly one request to that page and tries to pull out the
   title/company/location/description. LinkedIn in particular often blocks this since it
   requires login — if fetching fails, just paste the job description text into the manual
   form below instead. Either way, the job gets added to your Target Jobs list.
2. **Analyze**: pick your CV and a target job, then click **Analyze**. The app compares the
   job description's keywords against your CV's actual text and shows:
   - **Matched keywords** — already in your CV, and which section they came from.
   - **Missing keywords** — present in the job description but not found in your CV, sorted
     by how often the job description uses them. This is a to-do list for you to consider
     adding, in your own words — the app does not add them for you.
3. **Generate a tailored copy** (Markdown or `.docx`): this does **not** use any AI writing.
   It only reorders your CV's existing bullet points within each section so the most
   keyword-relevant ones surface first, and adds one "Key Skills Match" line built strictly
   from words already present in your CV. **Every word in the generated output already exists
   somewhere in your original CV — nothing is fabricated, invented, or paraphrased by an AI.**
4. **Similar Companies & Positions**: with a target job selected in the Analyze section,
   click **Find similar companies**. This uses that job's company/location as a search term
   against Apollo's company data (requires `APOLLO_API_KEY`) to suggest similar companies,
   and lets you expand each one to see its open roles via Apollo's job-postings data. Any
   posting you like can be added straight to Manual Listings with one click. Company and
   job-posting data only — no contact/people information is fetched or shown here.

## 8. Salary Insights tab

Enter a role and location (or leave them blank to reuse a linked target job) and click
**Estimate**. This pulls aggregate salary data from Adzuna's India index for similar listings
— **not** individual salary posts scraped from Glassdoor/AmbitionBox/Reddit or anywhere else
— and computes:

- A **CTC range** (25th–75th percentile of the aggregate data, not raw min/max, since the
  extreme ends of Adzuna's data tend to be thin/noisy).
- An **estimated in-hand range**, derived by applying a configurable deduction percentage
  (tunable in `.env` via `INHAND_DEDUCTION_PCT_LOW`/`HIGH`) to approximate PF/tax/etc.

By default (toggle available above the Estimate button), the query is also refined using
**your experience level**, inferred from your uploaded LinkedIn profile's career span
(earliest position start to latest/"Present" end) and mapped to a rough band — entry level,
mid level, senior, or lead — which gets prepended to the role you typed (e.g. "backend
engineer" → "senior backend engineer"). This is a simple heuristic on dates you already gave
the app, not anything fetched from elsewhere; when it changes the query, the result shows
exactly what was searched for so it's never a silent adjustment.

A disclaimer is always shown alongside the numbers: **this is a rough market estimate, not a
guaranteed figure** — actual in-hand pay depends on the specific offer's structure. If there
isn't enough aggregate data for your query, you'll get a clear message instead of a made-up
number. Past estimates are saved so you can compare over time.

## 9. Contacts & Leads tab

A place to manually track your own outreach — nothing here is automated.

- **Contacts**: log a recruiter or employee you found (e.g. by browsing LinkedIn yourself),
  with their name, LinkedIn URL, company, and any email/phone you found yourself. Track a
  status (not contacted / messaged / responded / interviewing / closed), and use **Edit** to
  update any field later. There's deliberately no "auto-fill from URL" here the way Manual
  Listings and Job Leads have it — that field is a person's LinkedIn *profile* URL, and
  auto-filling from it would mean scraping an identified individual's personal page, which is
  out of scope for this project (see the note in section 4 for the same reasoning applied to
  Apollo/Hunter).
- **Job Leads**: log a specific job posting you found manually (most often on LinkedIn) —
  paste the posting URL at the top and click **Fetch & auto-fill** to pull in the company
  name automatically (recruiter name usually isn't in the posting's data, so add that
  yourself if you know it), or fill in everything by hand. Optionally link it to a saved
  contact. Has its own status and an **Edit** button.

## 10. Help tab

Renders this file in-app, so you don't need to leave the browser to check how something
works.
