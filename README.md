# Job Search Navigator

A local job-search assistant for the Indian market: ranks live Adzuna India listings (plus
listings you paste in yourself) against your actual LinkedIn profile, checks/tailors your CV
for ATS-compliance without inventing content, tracks manual outreach to recruiters/contacts,
and gives a rough CTC/in-hand salary estimate. Runs entirely on your machine.

See `USER_MANUAL.md` for a full feature walkthrough (also served in-app under the Help tab).

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
