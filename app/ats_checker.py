import re

from app import config

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")
ALLOWED_GLYPHS = set("-•*▪–—/&,.():;'\"!?@#%")

# Each rule contributes a weight to the overall score; pass = full weight,
# warning = half, fail = none. Tweak these directly to change how heavily
# a given issue affects the score.
RULE_WEIGHTS = {
    "scanned_pdf": 15,
    "multi_column": 5,
    "tables": 5,
    "text_boxes": 8,
    "images": 4,
    "required_sections": 20,
    "contact_email": 15,
    "contact_phone": 5,
    "header_footer_content": 6,
    "length": 8,
    "fonts": 4,
    "file_naming": 3,
    "special_glyphs": 7,
}

STATUS_MULTIPLIER = {"pass": 1.0, "warning": 0.5, "fail": 0.0}


def _item(rule_id: str, label: str, status: str, detail: str) -> dict:
    return {"rule_id": rule_id, "label": label, "status": status, "detail": detail}


def run_ats_checks(
    raw_text: str,
    sections: dict,
    layout_meta: dict,
    original_filename: str,
) -> dict:
    checklist: list[dict] = []
    raw_text = raw_text or ""

    pages = max(layout_meta.get("pages") or 1, 1)
    chars_per_page = layout_meta.get("text_chars_per_page")
    if chars_per_page is None:
        chars_per_page = len(raw_text) / pages

    if chars_per_page < config.ATS_MIN_TEXT_CHARS_PER_PAGE and layout_meta.get("image_count", 0) > 0:
        checklist.append(_item(
            "scanned_pdf", "Text extractability", "fail",
            "Very little text could be extracted relative to the page count, and images are present -- "
            "this looks like a scanned/image-only file, which most ATS parsers cannot read at all.",
        ))
    elif chars_per_page < config.ATS_MIN_TEXT_CHARS_PER_PAGE:
        checklist.append(_item(
            "scanned_pdf", "Text extractability", "warning",
            "Less text than expected was extracted for the page count.",
        ))
    else:
        checklist.append(_item("scanned_pdf", "Text extractability", "pass", "Text extracted normally."))

    if layout_meta.get("multi_column_pages", 0) > 0:
        checklist.append(_item(
            "multi_column", "Layout columns", "warning",
            "This CV appears to use a multi-column layout -- some ATS parsers read across columns and "
            "scramble the text order.",
        ))
    else:
        checklist.append(_item("multi_column", "Layout columns", "pass", "Single-column layout detected."))

    table_count = layout_meta.get("table_count", 0)
    if table_count > 0:
        checklist.append(_item(
            "tables", "Tables", "warning",
            f"{table_count} table(s) detected -- content inside tables is sometimes dropped or "
            "misordered by ATS parsers.",
        ))
    else:
        checklist.append(_item("tables", "Tables", "pass", "No tables detected."))

    textbox_count = layout_meta.get("textbox_count", 0)
    if textbox_count > 0:
        checklist.append(_item(
            "text_boxes", "Text boxes", "warning",
            "Text box content detected -- many ATS parsers skip text inside text boxes entirely.",
        ))
    else:
        checklist.append(_item("text_boxes", "Text boxes", "pass", "No text boxes detected."))

    image_count = layout_meta.get("image_count", 0)
    if image_count > 0:
        checklist.append(_item(
            "images", "Images / photo", "warning",
            f"{image_count} embedded image(s) detected -- ATS systems ignore images, and some "
            "penalize photo-containing resumes.",
        ))
    else:
        checklist.append(_item("images", "Images / photo", "pass", "No embedded images detected."))

    missing_required = [s for s in ("experience", "education") if not sections.get(s)]
    missing_optional = [s for s in ("skills", "summary") if not sections.get(s)]
    if missing_required:
        checklist.append(_item(
            "required_sections", "Standard section headings", "fail",
            f"Missing required section(s): {', '.join(missing_required)}.",
        ))
    elif missing_optional:
        checklist.append(_item(
            "required_sections", "Standard section headings", "warning",
            f"Missing optional section(s): {', '.join(missing_optional)}.",
        ))
    else:
        checklist.append(_item(
            "required_sections", "Standard section headings", "pass",
            "Experience, Education, Skills, and Summary sections all detected.",
        ))

    if EMAIL_RE.search(raw_text):
        checklist.append(_item("contact_email", "Contact email", "pass", "An email address was detected."))
    else:
        checklist.append(_item(
            "contact_email", "Contact email", "fail",
            "No email address could be detected in the CV text.",
        ))

    if PHONE_RE.search(raw_text):
        checklist.append(_item("contact_phone", "Contact phone", "pass", "A phone number was detected."))
    else:
        checklist.append(_item(
            "contact_phone", "Contact phone", "warning",
            "No phone number could be detected in the CV text.",
        ))

    header_footer_text = layout_meta.get("header_footer_text", [])
    if header_footer_text:
        checklist.append(_item(
            "header_footer_content", "Header/footer content", "warning",
            "Content was found in a header or footer -- some ATS parsers ignore headers/footers "
            "entirely, so critical info there (like contact details) may be lost.",
        ))
    else:
        checklist.append(_item(
            "header_footer_content", "Header/footer content", "pass", "No content relying on headers/footers.",
        ))

    word_count = len(raw_text.split())
    if word_count < config.ATS_MIN_WORD_COUNT:
        checklist.append(_item("length", "Length", "warning", f"Only {word_count} words -- this CV may be too short."))
    elif word_count > config.ATS_MAX_WORD_COUNT:
        checklist.append(_item("length", "Length", "warning", f"{word_count} words -- this CV may be too long."))
    else:
        checklist.append(_item("length", "Length", "pass", f"{word_count} words -- reasonable length."))

    fonts = layout_meta.get("font_families", [])
    if len(fonts) > 4:
        checklist.append(_item(
            "fonts", "Font variety", "warning",
            f"{len(fonts)} distinct fonts detected -- consider standardizing to 1-2 fonts.",
        ))
    else:
        checklist.append(_item("fonts", "Font variety", "pass", "Consistent font usage."))

    generic_names = {"resume", "cv", "document1", "untitled"}
    name_stem = (original_filename or "").rsplit(".", 1)[0].strip().lower()
    if not name_stem or name_stem in generic_names or " " in name_stem:
        checklist.append(_item(
            "file_naming", "File naming", "warning",
            f"'{original_filename}' is a generic or space-containing filename -- consider "
            "something like 'FirstName-LastName-CV.pdf'.",
        ))
    else:
        checklist.append(_item("file_naming", "File naming", "pass", "Filename looks specific and clean."))

    unusual = sorted({
        ch for ch in raw_text
        if ch.isprintable() and not ch.isalnum() and not ch.isspace()
        and ch not in ALLOWED_GLYPHS and ord(ch) > 127
    })
    if unusual:
        checklist.append(_item(
            "special_glyphs", "Unusual characters", "warning",
            f"Unusual glyphs detected ({''.join(unusual[:10])}) -- icons/emoji are often mis-rendered "
            "or dropped by ATS parsers.",
        ))
    else:
        checklist.append(_item("special_glyphs", "Unusual characters", "pass", "No unusual glyphs/icons detected."))

    total_weight = sum(RULE_WEIGHTS[c["rule_id"]] for c in checklist)
    earned = sum(RULE_WEIGHTS[c["rule_id"]] * STATUS_MULTIPLIER[c["status"]] for c in checklist)
    overall_score = round((earned / total_weight) * 100) if total_weight else 0

    fails = [c["label"] for c in checklist if c["status"] == "fail"]
    warns = [c["label"] for c in checklist if c["status"] == "warning"]
    if fails:
        summary = f"{overall_score}/100 -- fix: {', '.join(fails)}."
    elif warns:
        summary = f"{overall_score}/100 -- looks solid, minor warnings: {', '.join(warns)}."
    else:
        summary = f"{overall_score}/100 -- passes all checks."

    return {"overall_score": overall_score, "checklist": checklist, "summary": summary}
