# Pure, explainable additive scoring -- no I/O, easy to unit-test and tweak.
# Weights are plain constants: edit these directly to change ranking behavior.
WEIGHT_SKILL = 10
WEIGHT_KEYWORD = 6
WEIGHT_TITLE_ROLE = 15
WEIGHT_LOCATION = 5
WEIGHT_CERT = 4


def _profile_signal_bag(profile: dict) -> dict:
    skills = [s for s in profile.get("skills", []) if s]
    certifications = [c.get("name") for c in profile.get("certifications", []) if c.get("name")]
    education_fields = []
    for e in profile.get("education", []):
        if e.get("field_of_study"):
            education_fields.append(e["field_of_study"])
        if e.get("degree_name"):
            education_fields.append(e["degree_name"])
    return {
        "skills": skills,
        "certifications": certifications,
        "education_fields": education_fields,
    }


def _split_terms(value: str) -> list[str]:
    return [t.strip() for t in (value or "").replace(";", ",").split(",") if t.strip()]


def _criteria_signal_bag(criteria: dict) -> dict:
    return {
        "keywords": _split_terms(criteria.get("keywords", "")),
        "target_roles": _split_terms(criteria.get("target_roles", "")),
        "locations": _split_terms(criteria.get("locations", "")),
    }


def _contains_phrase(haystack: str, phrase: str) -> bool:
    if not phrase or not haystack:
        return False
    return phrase.lower() in haystack.lower()


def score_listing(listing: dict, profile: dict, criteria: dict) -> dict:
    listing_text = " ".join(
        filter(None, [listing.get("title"), listing.get("company"), listing.get("description")])
    )
    profile_signals = _profile_signal_bag(profile)
    criteria_signals = _criteria_signal_bag(criteria)

    matched_skills = sorted({s for s in profile_signals["skills"] if _contains_phrase(listing_text, s)})
    matched_certs = sorted({c for c in profile_signals["certifications"] if _contains_phrase(listing_text, c)})
    matched_keywords = sorted({
        k for k in (criteria_signals["keywords"] + criteria_signals["target_roles"])
        if _contains_phrase(listing_text, k)
    })
    matched_title_role = any(
        _contains_phrase(listing.get("title") or "", r) for r in criteria_signals["target_roles"]
    )
    matched_location = any(
        _contains_phrase(listing.get("location") or "", loc) for loc in criteria_signals["locations"]
    )

    score = (
        len(matched_skills) * WEIGHT_SKILL
        + len(matched_keywords) * WEIGHT_KEYWORD
        + len(matched_certs) * WEIGHT_CERT
        + (WEIGHT_TITLE_ROLE if matched_title_role else 0)
        + (WEIGHT_LOCATION if matched_location else 0)
    )

    return {
        **listing,
        "score": float(score),
        "matched_skills": matched_skills,
        "matched_keywords": matched_keywords,
        "matched_title_role": matched_title_role,
        "matched_location": matched_location,
    }


def rank_listings(profile: dict, criteria: dict, listings: list[dict]) -> list[dict]:
    scored = [score_listing(listing, profile, criteria) for listing in listings]
    # Stable sort: freshness first (secondary key), then score (primary key) --
    # ties on score keep their freshness order because Python's sort is stable.
    scored.sort(key=lambda item: item.get("posted_at") or "", reverse=True)
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored
