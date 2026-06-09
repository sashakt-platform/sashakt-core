from fastapi import APIRouter, Depends

from app.api.deps import permission_dependency
from app.models.utils import SUPPORTED_LOCALES

router = APIRouter(prefix="/languages", tags=["Languages"])


@router.get(
    "/",
    response_model=dict[str, str],
    dependencies=[Depends(permission_dependency("create_test"))],
)
def get_localization() -> dict[str, str]:
    """Return the map of supported locale codes to their display names."""
    return SUPPORTED_LOCALES
