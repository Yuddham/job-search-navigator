from typing import Any, Literal, Optional

from pydantic import BaseModel

STATUS_VALUES = ("not_contacted", "messaged", "responded", "interviewing", "closed")


# ---- Profile ----

class ProfilePosition(BaseModel):
    id: int
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    started_on: Optional[str] = None
    ended_on: Optional[str] = None


class ProfileEducation(BaseModel):
    id: int
    school_name: Optional[str] = None
    degree_name: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None


class ProfileCertification(BaseModel):
    id: int
    name: Optional[str] = None
    authority: Optional[str] = None
    started_on: Optional[str] = None
    finished_on: Optional[str] = None
    license_number: Optional[str] = None
    url: Optional[str] = None


class ProfileSummary(BaseModel):
    basics: Optional[dict[str, Any]] = None
    positions: list[ProfilePosition] = []
    education: list[ProfileEducation] = []
    skills: list[str] = []
    certifications: list[ProfileCertification] = []
    warnings: list[str] = []


class ProfileUploadResponse(BaseModel):
    summary: ProfileSummary
    counts: dict[str, int]
    warnings: list[str]


# ---- Search criteria ----

class SearchCriteriaIn(BaseModel):
    label: str
    keywords: str = ""
    target_roles: str = ""
    industries: str = ""
    locations: str = ""


class SearchCriteriaOut(SearchCriteriaIn):
    id: int
    created_at: str
    updated_at: str


# ---- Manual listings ----

class ManualListingIn(BaseModel):
    title: str
    company: str = ""
    location: str = ""
    url: str = ""
    description: str = ""
    notes: str = ""


class ManualListingOut(ManualListingIn):
    id: int
    created_at: str
    updated_at: str


# ---- Job search results ----

class RankedListing(BaseModel):
    source: str
    external_id: Optional[str] = None
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    posted_at: Optional[str] = None
    score: float
    matched_skills: list[str] = []
    matched_keywords: list[str] = []
    matched_title_role: bool = False
    matched_location: bool = False


class JobSearchResponse(BaseModel):
    results: list[RankedListing]
    warnings: list[str] = []


# ---- Contacts & leads ----

class ContactIn(BaseModel):
    name: str
    linkedin_url: str = ""
    company: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""
    status: str = "not_contacted"


class ContactOut(ContactIn):
    id: int
    created_at: str
    updated_at: str


class JobLeadIn(BaseModel):
    job_url: str = ""
    company: str = ""
    recruiter_name: str = ""
    recruiter_contact_id: Optional[int] = None
    notes: str = ""
    status: str = "not_contacted"


class JobLeadOut(JobLeadIn):
    id: int
    created_at: str
    updated_at: str


# ---- CV / ATS ----

class AtsChecklistItem(BaseModel):
    rule_id: str
    label: str
    status: Literal["pass", "warning", "fail"]
    detail: str


class AtsReport(BaseModel):
    id: int
    cv_document_id: int
    checked_at: str
    overall_score: int
    checklist: list[AtsChecklistItem]
    summary: str


class CvDocumentOut(BaseModel):
    id: int
    original_filename: str
    file_type: str
    uploaded_at: str
    is_active: bool
    sections: dict[str, Any]
    warnings: list[str]


class CvUploadResponse(BaseModel):
    cv_document: CvDocumentOut
    ats_report: AtsReport


# ---- Target jobs / tailoring ----

class UrlPreviewIn(BaseModel):
    url: str


class UrlPreviewOut(BaseModel):
    status: str
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    jd_text: Optional[str] = None
    warning: Optional[str] = None


class TargetJobFetchIn(BaseModel):
    url: str


class TargetJobManualIn(BaseModel):
    company: str = ""
    title: str = ""
    location: str = ""
    jd_text: str
    source_url: str = ""


class TargetJobOut(BaseModel):
    id: int
    source_url: Optional[str] = None
    source_type: str
    fetch_status: str
    fetch_warning: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    jd_text: Optional[str] = None
    fetched_at: str


class KeywordMatch(BaseModel):
    keyword: str
    jd_freq: int
    cv_freq: int
    cv_sections: list[str] = []


class KeywordGap(BaseModel):
    keyword: str
    jd_freq: int


class TailoringAnalyzeIn(BaseModel):
    cv_document_id: int
    target_job_id: int


class TailoringReportOut(BaseModel):
    id: int
    cv_document_id: int
    target_job_id: int
    created_at: str
    matched_keywords: list[KeywordMatch]
    missing_keywords: list[KeywordGap]
    match_score: float
    key_skills_line: Optional[str] = None
    generated_files: dict[str, str] = {}


class GenerateTailoredIn(BaseModel):
    format: Literal["markdown", "docx"]


# ---- Salary ----

class SalaryEstimateOut(BaseModel):
    id: int
    role_query: str
    location_query: str
    created_at: str
    ctc_low: Optional[float] = None
    ctc_median: Optional[float] = None
    ctc_high: Optional[float] = None
    inhand_low: Optional[float] = None
    inhand_high: Optional[float] = None
    disclaimer: str
    warning: Optional[str] = None
