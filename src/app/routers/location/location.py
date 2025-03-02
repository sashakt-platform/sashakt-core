from fastapi import APIRouter

from app.routers.location import block, country, district, state

router = APIRouter(prefix="/location", tags=["Location"])

# Include all routers
router.include_router(country.router, prefix="/country", tags=["Country"])
router.include_router(state.router, prefix="/state", tags=["State"])
router.include_router(district.router, prefix="/district", tags=["District"])
router.include_router(block.router, prefix="/block", tags=["Block"])
