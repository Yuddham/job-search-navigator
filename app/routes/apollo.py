from fastapi import APIRouter

from app import apollo_client
from app.models import ApolloCompaniesResponse, ApolloCompany, ApolloJobPosting, ApolloJobPostingsResponse

router = APIRouter(prefix="/api/apollo", tags=["apollo"])


@router.get("/similar-companies", response_model=ApolloCompaniesResponse)
def similar_companies(keyword: str = "", location: str = "") -> ApolloCompaniesResponse:
    if not keyword:
        return ApolloCompaniesResponse(companies=[], warning="Provide a company name, industry, or keyword to search.")
    try:
        companies = apollo_client.search_companies(keyword=keyword, location=location, per_page=8)
        return ApolloCompaniesResponse(companies=[ApolloCompany(**c) for c in companies])
    except apollo_client.ApolloConfigError as exc:
        return ApolloCompaniesResponse(companies=[], warning=str(exc))
    except apollo_client.ApolloAPIError as exc:
        return ApolloCompaniesResponse(companies=[], warning=f"Apollo search failed: {exc}")


@router.get("/job-postings", response_model=ApolloJobPostingsResponse)
def job_postings(organization_id: str) -> ApolloJobPostingsResponse:
    try:
        postings = apollo_client.get_job_postings(organization_id)
        return ApolloJobPostingsResponse(postings=[ApolloJobPosting(**p) for p in postings])
    except apollo_client.ApolloConfigError as exc:
        return ApolloJobPostingsResponse(postings=[], warning=str(exc))
    except apollo_client.ApolloAPIError as exc:
        return ApolloJobPostingsResponse(postings=[], warning=f"Apollo job postings failed: {exc}")
