from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_user_permissions,
    permission_dependency,
)
from app.core.files import (
    delete_platform_guide_file,
    get_absolute_platform_guide_url,
    save_platform_guide_file,
    validate_platform_guide_upload,
)
from app.core.roles import super_admin
from app.crud import organization_settings as crud_settings
from app.models.organization import Organization
from app.models.organization_settings import (
    OrganizationSettings,
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


def _to_public(row: OrganizationSettings) -> OrganizationSettingsPublic:
    """Validate the row's JSON, resolve platform_guide.file_path to an absolute URL,
    and return a response object."""
    payload = OrganizationSettingsPayload.model_validate(row.settings)
    payload.platform_guide.value.file_path = get_absolute_platform_guide_url(
        payload.platform_guide.value.file_path
    )
    return OrganizationSettingsPublic(
        id=row.id,
        organization_id=row.organization_id,
        settings=payload,
        created_date=row.created_date,
        modified_date=row.modified_date,
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
    return _to_public(row)


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

    # File lifecycle for platform_guide runs through dedicated endpoints. Preserve
    # whatever file_path the server currently has so clients can't accidentally
    # orphan or swap files by editing the generic settings payload.
    current_row = crud_settings.get_or_create(
        session=session, organization_id=organization_id
    )
    current_payload = OrganizationSettingsPayload.model_validate(current_row.settings)
    payload.settings.platform_guide.value.file_path = (
        current_payload.platform_guide.value.file_path
    )

    row = crud_settings.upsert(
        session=session,
        organization_id=organization_id,
        payload=payload.settings,
    )
    return _to_public(row)


@router.post(
    "/{organization_id}/platform_guide",
    response_model=OrganizationSettingsPublic,
)
async def upload_platform_guide(
    organization_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    permissions: list[str] = Depends(get_user_permissions),
    file: UploadFile = File(
        ..., description="Platform guide PDF (max 10 MB, application/pdf)"
    ),
) -> OrganizationSettingsPublic:
    _get_active_organization(session=session, organization_id=organization_id)
    _ensure_update_permission_and_scope(
        current_user=current_user,
        permissions=permissions,
        organization_id=organization_id,
    )

    file_content, file_ext = await validate_platform_guide_upload(file)
    new_path = save_platform_guide_file(organization_id, file_content, file_ext)

    row = crud_settings.get_or_create(session=session, organization_id=organization_id)
    current_payload = OrganizationSettingsPayload.model_validate(row.settings)
    old_path = current_payload.platform_guide.value.file_path

    current_payload.platform_guide.value.file_path = new_path
    try:
        row = crud_settings.upsert(
            session=session,
            organization_id=organization_id,
            payload=current_payload,
        )
    except Exception:
        session.rollback()
        delete_platform_guide_file(new_path)
        raise

    if old_path and old_path != new_path:
        delete_platform_guide_file(old_path)

    return _to_public(row)


@router.delete(
    "/{organization_id}/platform_guide",
    response_model=OrganizationSettingsPublic,
)
def delete_platform_guide(
    organization_id: int,
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

    row = crud_settings.get_or_create(session=session, organization_id=organization_id)
    current_payload = OrganizationSettingsPayload.model_validate(row.settings)
    old_path = current_payload.platform_guide.value.file_path

    if not old_path:
        raise HTTPException(
            status_code=404,
            detail="Organization has no platform guide to delete",
        )

    current_payload.platform_guide.value.file_path = None
    row = crud_settings.upsert(
        session=session,
        organization_id=organization_id,
        payload=current_payload,
    )

    delete_platform_guide_file(old_path)
    return _to_public(row)
