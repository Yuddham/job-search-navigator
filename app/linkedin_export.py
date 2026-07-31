import csv
import io
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from typing import Any, Optional

FILE_ALIASES = {
    "profile": ["Profile.csv"],
    "positions": ["Positions.csv", "Position.csv"],
    "education": ["Education.csv"],
    "skills": ["Skills.csv"],
    "certifications": ["Certifications.csv", "Certification.csv"],
}

COLUMN_ALIASES = {
    "profile": {
        "first_name": ["First Name"],
        "last_name": ["Last Name"],
        "headline": ["Headline"],
        "industry": ["Industry"],
        "location": ["Geo Location", "Location"],
    },
    "positions": {
        "title": ["Title"],
        "company": ["Company Name", "Company"],
        "location": ["Location"],
        "description": ["Description"],
        "started_on": ["Started On", "Start Date"],
        "ended_on": ["Finished On", "End Date"],
    },
    "education": {
        "school_name": ["School Name", "School"],
        "degree_name": ["Degree Name", "Degree"],
        "field_of_study": ["Field Of Study", "Field of Study"],
        "start_date": ["Start Date"],
        "end_date": ["End Date"],
        "notes": ["Notes"],
    },
    "skills": {
        "skill_name": ["Name"],
    },
    "certifications": {
        "name": ["Name"],
        "authority": ["Authority"],
        "started_on": ["Started On", "Start Date"],
        "finished_on": ["Finished On", "End Date"],
        "license_number": ["License Number"],
        "url": ["Url", "URL"],
    },
}


def _find_file(name_map: dict[str, str], candidates: list[str]) -> Optional[str]:
    for c in candidates:
        hit = name_map.get(c.lower())
        if hit:
            return hit
    return None


def _read_rows(zf: zipfile.ZipFile, entry_name: str, warnings: list[str]) -> list[dict[str, Any]]:
    try:
        with zf.open(entry_name) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8-sig")
            reader = csv.DictReader(text)
            return [row for row in reader if row]
    except Exception as exc:  # noqa: BLE001 - defensive, must never crash the upload
        warnings.append(f"Could not read {entry_name}: {exc}")
        return []


def _map_row(row: dict[str, Any], alias_map: dict[str, list[str]]) -> dict[str, Any]:
    row_lower = {(k or "").strip().lower(): v for k, v in row.items() if k}
    out: dict[str, Any] = {}
    for field, aliases in alias_map.items():
        value = None
        for alias in aliases:
            if alias.lower() in row_lower:
                value = row_lower[alias.lower()]
                break
        out[field] = value.strip() if isinstance(value, str) and value.strip() else None
    out["raw_json"] = json.dumps(row, ensure_ascii=False)
    return out


def parse_export(zip_bytes: bytes) -> dict[str, Any]:
    """Defensively parse a LinkedIn "Download your data" ZIP export.

    Never raises for malformed/partial input -- missing files or unreadable
    rows are recorded as warnings instead, so an upload always returns
    whatever could be salvaged.
    """
    warnings: list[str] = []
    result: dict[str, Any] = {
        "basics": None,
        "positions": [],
        "education": [],
        "skills": [],
        "certifications": [],
        "warnings": warnings,
    }

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        warnings.append("The uploaded file is not a valid ZIP archive.")
        return result

    name_map = {n.rsplit("/", 1)[-1].lower(): n for n in zf.namelist() if not n.endswith("/")}

    profile_file = _find_file(name_map, FILE_ALIASES["profile"])
    if profile_file:
        rows = _read_rows(zf, profile_file, warnings)
        if rows:
            result["basics"] = _map_row(rows[0], COLUMN_ALIASES["profile"])
        else:
            warnings.append("Profile.csv was found but had no rows.")
    else:
        warnings.append("Profile.csv not found — name/headline/industry not imported.")

    positions_file = _find_file(name_map, FILE_ALIASES["positions"])
    if positions_file:
        for row in _read_rows(zf, positions_file, warnings):
            mapped = _map_row(row, COLUMN_ALIASES["positions"])
            if mapped.get("title") or mapped.get("company"):
                result["positions"].append(mapped)
    else:
        warnings.append("Positions.csv not found — experience not imported.")

    education_file = _find_file(name_map, FILE_ALIASES["education"])
    if education_file:
        for row in _read_rows(zf, education_file, warnings):
            mapped = _map_row(row, COLUMN_ALIASES["education"])
            if mapped.get("school_name"):
                result["education"].append(mapped)
    else:
        warnings.append("Education.csv not found — education not imported.")

    skills_file = _find_file(name_map, FILE_ALIASES["skills"])
    if skills_file:
        for row in _read_rows(zf, skills_file, warnings):
            mapped = _map_row(row, COLUMN_ALIASES["skills"])
            if mapped.get("skill_name"):
                result["skills"].append(mapped["skill_name"])
    else:
        warnings.append("Skills.csv not found — skills not imported.")

    certifications_file = _find_file(name_map, FILE_ALIASES["certifications"])
    if certifications_file:
        for row in _read_rows(zf, certifications_file, warnings):
            mapped = _map_row(row, COLUMN_ALIASES["certifications"])
            if mapped.get("name"):
                result["certifications"].append(mapped)
    else:
        warnings.append("Certifications.csv not found — certifications not imported.")

    return result


def save_profile(conn: sqlite3.Connection, parsed: dict[str, Any]) -> dict[str, Any]:
    """Full delete-and-replace write: a re-upload represents the user's
    current LinkedIn data, not an incremental merge."""
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.cursor()

    cur.execute("DELETE FROM profile_basics")
    cur.execute("DELETE FROM profile_positions")
    cur.execute("DELETE FROM profile_education")
    cur.execute("DELETE FROM profile_skills")
    cur.execute("DELETE FROM profile_certifications")

    basics = parsed.get("basics") or {}
    cur.execute(
        "INSERT INTO profile_basics (id, first_name, last_name, headline, industry, location, raw_json, uploaded_at) "
        "VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
        (
            basics.get("first_name"), basics.get("last_name"), basics.get("headline"),
            basics.get("industry"), basics.get("location"), basics.get("raw_json"), now,
        ),
    )

    for p in parsed.get("positions", []):
        cur.execute(
            "INSERT INTO profile_positions (title, company, location, description, started_on, ended_on, raw_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (p.get("title"), p.get("company"), p.get("location"), p.get("description"),
             p.get("started_on"), p.get("ended_on"), p.get("raw_json")),
        )

    for e in parsed.get("education", []):
        cur.execute(
            "INSERT INTO profile_education (school_name, degree_name, field_of_study, start_date, end_date, notes, raw_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (e.get("school_name"), e.get("degree_name"), e.get("field_of_study"),
             e.get("start_date"), e.get("end_date"), e.get("notes"), e.get("raw_json")),
        )

    for skill_name in parsed.get("skills", []):
        cur.execute("INSERT INTO profile_skills (skill_name) VALUES (?)", (skill_name,))

    for c in parsed.get("certifications", []):
        cur.execute(
            "INSERT INTO profile_certifications (name, authority, started_on, finished_on, license_number, url, raw_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (c.get("name"), c.get("authority"), c.get("started_on"), c.get("finished_on"),
             c.get("license_number"), c.get("url"), c.get("raw_json")),
        )

    conn.commit()

    return {
        "counts": {
            "positions": len(parsed.get("positions", [])),
            "education": len(parsed.get("education", [])),
            "skills": len(parsed.get("skills", [])),
            "certifications": len(parsed.get("certifications", [])),
        },
        "warnings": parsed.get("warnings", []),
    }


def load_profile_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    basics_row = conn.execute("SELECT * FROM profile_basics WHERE id = 1").fetchone()
    positions = conn.execute("SELECT * FROM profile_positions ORDER BY id").fetchall()
    education = conn.execute("SELECT * FROM profile_education ORDER BY id").fetchall()
    skills = conn.execute("SELECT skill_name FROM profile_skills ORDER BY id").fetchall()
    certifications = conn.execute("SELECT * FROM profile_certifications ORDER BY id").fetchall()

    return {
        "basics": dict(basics_row) if basics_row else None,
        "positions": [dict(r) for r in positions],
        "education": [dict(r) for r in education],
        "skills": [r["skill_name"] for r in skills],
        "certifications": [dict(r) for r in certifications],
    }


def clear_profile(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM profile_basics")
    cur.execute("DELETE FROM profile_positions")
    cur.execute("DELETE FROM profile_education")
    cur.execute("DELETE FROM profile_skills")
    cur.execute("DELETE FROM profile_certifications")
