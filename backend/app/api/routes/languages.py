from fastapi import APIRouter, Depends

from app.api.deps import permission_dependency
from app.models.utils import SUPPORTED_LOCALES

router = APIRouter(prefix="/languages", tags=["Languages"])


@router.get(
    "/",
    response_model=dict[str, str],
    dependencies=[Depends(permission_dependency("create_test"))],
)
def get_languages() -> dict[str, str]:
    return SUPPORTED_LOCALES
