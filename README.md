# Navigrad

A local job-search assistant for the Indian market: ranks live Adzuna India listings (plus
listings you paste in yourself) against your actual LinkedIn profile, checks/tailors your CV
for ATS-compliance without inventing content, tracks manual outreach to recruiters/contacts,
and gives a rough CTC/in-hand salary estimate. Runs entirely on your machine.

See `USER_MANUAL.md` for a full feature walkthrough (also served in-app under the Help tab).

## Windows desktop app

A packaged Windows 11 installer is available from this repo's
[GitHub Releases](https://github.com/Yuddham/job-search-navigator/releases) page — download
`Navigrad-Setup-<version>.exe`, run it, and everything it needs (Python runtime, all
dependencies, the Microsoft Edge WebView2 Runtime if not already present) installs alongside
it. No separate setup required. Note the installer is unsigned, so Windows SmartScreen will
show an "unrecognized app" warning on first run — click **More info → Run anyway** to proceed.

## Run from source

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add your Adzuna API credentials (free signup at https://developer.adzuna.com/).

```
uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000. The interactive API docs are at http://localhost:8000/docs.

## Data

All data lives locally in `data/` (SQLite DB, uploaded CVs, generated tailored CV copies) and
is gitignored — nothing here is committed or sent anywhere except the specific outbound calls
described in `USER_MANUAL.md` (Adzuna API, and a single fetch of a job URL you paste in).
