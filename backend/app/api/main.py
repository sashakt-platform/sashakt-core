from fastapi import APIRouter

from app.api.routes import (
    candidate,
    entity,
    languages,
    location,
    login,
    organization,
    permissions,
    private,
    providers,
    question,
    roles,
    tag,
    test,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(roles.router)
api_router.include_router(permissions.router)
api_router.include_router(organization.router)
api_router.include_router(location.router)
api_router.include_router(test.router)
api_router.include_router(tag.router_tag)
api_router.include_router(tag.router_tagtype)
api_router.include_router(question.router)
api_router.include_router(candidate.router)
api_router.include_router(candidate.router_candidate_test)
api_router.include_router(candidate.router_candidate_test_answer)
api_router.include_router(entity.router_entitytype)
api_router.include_router(entity.router_entity)
api_router.include_router(providers.router)
api_router.include_router(languages.router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
