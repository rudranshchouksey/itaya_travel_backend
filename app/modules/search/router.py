from fastapi import APIRouter, Depends

from app.api.deps import SessionDep
from app.modules.search.schemas import SearchParams, SearchResponse
from app.modules.search.service import search_service

router = APIRouter(tags=["Search"])


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Unified search",
)
async def unified_search(
    session: SessionDep,
    params: SearchParams = Depends(),
):
    """
    Search for listings and experiences using basic criteria.
    """
    return await search_service.search(session, params)
