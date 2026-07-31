# Job Search Navigator — User Manual

This is a local, single-user tool for a job search in India. Everything runs on your own
machine; nothing about your profile, CV, or contacts is sent anywhere except the specific
outbound calls described below (Adzuna's API, and a single fetch of a job URL you paste in
yourself). This manual walks through every tab.

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
3. Start the app (`uvicorn app.main:app --reload --port 8000`) and open
   http://localhost:8000.

## 2. Profile tab

This is where you import your LinkedIn profile so the app can match jobs against your real
skills, experience, education, and certifications.

1. On LinkedIn, go to **Settings & Privacy → Data privacy → Get a copy of your data**.
2. Choose **"Want something in particular?"** and check at least: **Profile**, **Positions**,
   **Education**, **Skills**, and **Certifications** (checking more is fine, only these are
   read).
3. Request the archive. LinkedIn emails you a link once it's ready (usually within minutes to
   a few hours) — download the `.zip`.
4. In the Profile tab, choose that `.zip` and click **Upload**.
5. The app shows how many positions/education/skills/certifications it imported, plus a
   warning for anything it couldn't find (e.g. if you didn't select Certifications on export).
   Re-uploading always replaces the current profile with the new export — it doesn't merge.

## 3. Search Criteria tab

Describe the kind of job you're looking for. You can save multiple named criteria sets (e.g.
one for "Backend India", another for "Product Manager Fintech") and switch between them in
Job Search. Keywords, target roles, industries, and locations all accept comma-separated
lists — leave any of them blank if not relevant.

## 4. Job Search tab

Pick a saved criteria set (or leave it on "ad hoc" to search with no filter) and click
**Search**. Results are pulled from two places and merged into one ranked list:

- **Adzuna's live India job index** (if you've configured API keys).
- **Manual Listings** you've added yourself (see below).

Each result shows a score and the specific skills/keywords/role/location that matched — this
is exactly how the ranking is computed, not a black-box number. If Adzuna isn't configured or
is temporarily unreachable, you'll see a warning banner, but your manual listings still show
up and rank normally.

## 5. Manual Listings tab

Paste in any listing you find yourself — from Naukri, Indeed, LinkedIn, a company careers
page, wherever. Give it a title, company, location, URL, and description. It's automatically
included in Job Search ranking. This is the main way to include LinkedIn job postings, since
the app never automates browsing LinkedIn itself.

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

1. **Add a target job**: paste a job URL (LinkedIn/Indeed/Naukri/anywhere) and click
   **Fetch**. The app makes exactly one request to that page and tries to pull out the
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

## 8. Salary Insights tab

Enter a role and location (or leave them blank to reuse a linked target job) and click
**Estimate**. This pulls aggregate salary data from Adzuna's India index for similar listings
— **not** individual salary posts scraped from Glassdoor/AmbitionBox/Reddit or anywhere else
— and computes:

- A **CTC range** (25th–75th percentile of the aggregate data, not raw min/max, since the
  extreme ends of Adzuna's data tend to be thin/noisy).
- An **estimated in-hand range**, derived by applying a configurable deduction percentage
  (tunable in `.env` via `INHAND_DEDUCTION_PCT_LOW`/`HIGH`) to approximate PF/tax/etc.

A disclaimer is always shown alongside the numbers: **this is a rough market estimate, not a
guaranteed figure** — actual in-hand pay depends on the specific offer's structure. If there
isn't enough aggregate data for your query, you'll get a clear message instead of a made-up
number. Past estimates are saved so you can compare over time.

## 9. Contacts & Leads tab

A place to manually track your own outreach — nothing here is automated.

- **Contacts**: log a recruiter or employee you found (e.g. by browsing LinkedIn yourself),
  with their name, LinkedIn URL, company, and any email/phone you found yourself. Track a
  status (not contacted / messaged / responded / interviewing / closed).
- **Job Leads**: log a specific job posting you found manually (most often on LinkedIn) —
  the posting URL, company, recruiter name if mentioned, and optionally link it to a saved
  contact. Also has its own status you update as you progress.

## 10. Help tab

Renders this file in-app, so you don't need to leave the browser to check how something
works.
