from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_user_permissions,
    permission_dependency,
)
from app.core.roles import super_admin
from app.crud import organization_settings as crud_settings
from app.models.organization import Organization
from app.models.organization_settings import (
    OrganizationSettingsPayload,
    OrganizationSettingsPublic,
    OrganizationSettingsUpdate,
)

router = APIRouter(prefix="/organization", tags=["Organization Settings"])


def _get_active_organization(
    *, session: SessionDep, organization_id: int
) -> Organization:
    organization = session.get(Organization, organization_id)
    if not organization or organization.is_deleted:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


def _ensure_read_scope(*, current_user: CurrentUser, organization_id: int) -> None:
    """super_admin: any org. All other roles: only their own org."""
    if current_user.role.name == super_admin.name:
        return
    if current_user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access settings for another organization",
        )


def _ensure_update_permission_and_scope(
    *,
    current_user: CurrentUser,
    permissions: list[str],
    organization_id: int,
) -> None:
    """Allow super_admin (via update_organization_settings) on any org; otherwise
    require update_my_organization_settings AND target to be the caller's org."""
    if "update_organization_settings" in permissions:
        return
    if (
        "update_my_organization_settings" in permissions
        and current_user.organization_id == organization_id
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not permitted to update settings for this organization",
    )


@router.get(
    "/{organization_id}/settings",
    response_model=OrganizationSettingsPublic,
    dependencies=[Depends(permission_dependency("read_organization"))],
)
def get_organization_settings(
    organization_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrganizationSettingsPublic:
    _get_active_organization(session=session, organization_id=organization_id)
    _ensure_read_scope(current_user=current_user, organization_id=organization_id)
    row = crud_settings.get_or_create(session=session, organization_id=organization_id)
    return OrganizationSettingsPublic(
        id=row.id,
        organization_id=row.organization_id,
        settings=OrganizationSettingsPayload.model_validate(row.settings),
        created_date=row.created_date,
        modified_date=row.modified_date,
    )


@router.put(
    "/{organization_id}/settings",
    response_model=OrganizationSettingsPublic,
)
def update_organization_settings(
    organization_id: int,
    payload: OrganizationSettingsUpdate,
    session: SessionDep,
    current_user: CurrentUser,
    permissions: list[str] = Depends(get_user_permissions),
) -> OrganizationSettingsPublic:
    _get_active_organization(session=session, organization_id=organization_id)
    _ensure_update_permission_and_scope(
        current_user=current_user,
        permissions=permissions,
        organization_id=organization_id,
    )
    row = crud_settings.upsert(
        session=session,
        organization_id=organization_id,
        payload=payload.settings,
    )
    return OrganizationSettingsPublic(
        id=row.id,
        organization_id=row.organization_id,
        settings=OrganizationSettingsPayload.model_validate(row.settings),
        created_date=row.created_date,
        modified_date=row.modified_date,
    )
